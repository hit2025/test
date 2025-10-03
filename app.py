from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import datetime, threading, time, random, math
from fastapi import Request

app = FastAPI()
CAMPUS_CENTER = (22.0509, 88.0725)

# -------------------------
# Blynk placeholders
# -------------------------
BLYNK_TEMPLATE_ID = "TMPL3ZHnAAMIw"
BLYNK_AUTH_TOKEN = "hpOQDbsw9BUEWc5fsZYvnqqWhqouM102"

# -------------------------
# Utility
# -------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# -------------------------
# Data
# -------------------------
bins = [
    {"id": 1, "lat": 22.0513, "lng": 88.0721, "fill": 40, "status": "OK"},
    {"id": 2, "lat": 22.0506, "lng": 88.0712, "fill": 30, "status": "OK"},
    {"id": 3, "lat": 22.0498, "lng": 88.0728, "fill": 50, "status": "OK"},
    {"id": 4, "lat": 22.0492, "lng": 88.0705, "fill": 20, "status": "OK"},
    {"id": 5, "lat": 22.0509, "lng": 88.0698, "fill": 35, "status": "OK"},
]

vehicles = [
    {
        "id": i + 1,
        "lat": CAMPUS_CENTER[0] + random.uniform(-0.001, 0.001),
        "lng": CAMPUS_CENTER[1] + random.uniform(-0.001, 0.001),
        "status": "IDLE",
        "target_bin": None,
    }
    for i in range(3)
]

assignments, comparison_stats, bin_alerts = [], [], []
auto_sim = {"running": False}

# -------------------------
# APIs
# -------------------------
@app.get("/bins")
def get_bins():
    return bins

@app.get("/vehicles")
def get_vehicles():
    return vehicles

@app.get("/assignments")
def get_assignments():
    return assignments

@app.get("/comparisons")
def get_comparisons():
    return comparison_stats

@app.get("/alerts")
def get_alerts():
    return bin_alerts

@app.post("/fill_random")
def fill_random():
    b = random.choice(bins)
    b["fill"] = min(100, b["fill"] + random.randint(20, 40))
    if b["fill"] >= 100:
        b["fill"], b["status"] = 100, "FULL"
        bin_alerts.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "msg": f"Bin {b['id']} is FULL and sent an alert"
        })
    return {"ok": True, "bin": b}

@app.post("/assign_nearest_full")
def assign_nearest_full():
    full_bins = [b for b in bins if b["status"] == "FULL" and not any(v["target_bin"] == b["id"] for v in vehicles)]
    idle = [v for v in vehicles if v["status"] == "IDLE"]
    if not full_bins or not idle:
        return {"ok": False}

    b = random.choice(full_bins)
    dists = [(haversine(v["lat"], v["lng"], b["lat"], b["lng"]), v) for v in idle]
    dists.sort(key=lambda x: x[0])
    nearest_vehicle = dists[0][1]

    nearest_vehicle["status"], nearest_vehicle["target_bin"] = "BUSY", b["id"]
    rec = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "vehicle_id": nearest_vehicle["id"],
        "bin_id": b["id"]
    }
    assignments.append(rec)

    comp = {
        "time": rec["time"],
        "bin": b["id"],
        "assigned_vehicle": nearest_vehicle["id"],
        "assigned_distance": round(dists[0][0], 1),
        "others": [{"id": v["id"], "dist": round(d, 1)} for d, v in dists]
    }
    comparison_stats.append(comp)

    bin_alerts.append({
        "time": rec["time"],
        "msg": f"Vehicle {nearest_vehicle['id']} accepted task for Bin {b['id']} ({round(dists[0][0],1)}m)"
    })
    return {"ok": True, "assignment": rec, "comparison": comp}

@app.post("/complete_trip/{vid}/{bid}")
def complete_trip(vid: int, bid: int):
    for v in vehicles:
        if v["id"] == vid:
            v["status"], v["target_bin"] = "IDLE", None
    for b in bins:
        if b["id"] == bid:
            b["fill"], b["status"] = 0, "OK"
    bin_alerts.append({
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "msg": f"Vehicle {vid} completed trip for Bin {bid}"
    })
    return {"ok": True}

@app.post("/reset")
def reset_all():
    for v in vehicles:
        v.update({
            "status": "IDLE",
            "target_bin": None,
            "lat": CAMPUS_CENTER[0] + random.uniform(-0.001, 0.001),
            "lng": CAMPUS_CENTER[1] + random.uniform(-0.001, 0.001),
        })
    assignments.clear()
    comparison_stats.clear()
    bin_alerts.clear()
    auto_sim["running"] = False
    return {"ok": True}

@app.post("/reset_vehicles")
def reset_vehicles():
    for v in vehicles:
        v.update({
            "status": "IDLE",
            "target_bin": None,
            "lat": CAMPUS_CENTER[0] + random.uniform(-0.001, 0.001),
            "lng": CAMPUS_CENTER[1] + random.uniform(-0.001, 0.001),
        })
    return {"ok": True}

@app.post("/start_auto")
def start_auto():
    auto_sim["running"] = True
    return {"ok": True}

@app.post("/stop_auto")
def stop_auto():
    auto_sim["running"] = False
    return {"ok": True}

# -------------------------
# Auto loop
# -------------------------
def auto_loop():
    while True:
        if auto_sim["running"]:
            b = random.choice(bins)
            if b["status"] != "FULL":
                b["fill"] = min(100, b["fill"] + random.randint(10, 25))
                if b["fill"] >= 100:
                    b["status"] = "FULL"
                    bin_alerts.append({
                        "time": datetime.datetime.now().strftime("%H:%M:%S"),
                        "msg": f"Bin {b['id']} is FULL and sent an alert"
                    })
            assign_nearest_full()
        time.sleep(3)

threading.Thread(target=auto_loop, daemon=True).start()

@app.post("/record_route_assignment")
async def record_route_assignment(request: Request):
    data = await request.json()
    rec = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "vehicle_id": data["vehicle_id"],
        "bin_id": data["bin_id"],
        "route_distance": round(data["distance"],1),
        "route_time": round(data["time"],1)
    }
    comparison_stats.append(rec)
    return {"ok": True}


# -------------------------
# UI
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Drinking Water Points and Pollution-Free Waste Management Zones</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet-routing-machine/dist/leaflet-routing-machine.css"/>
<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-routing-machine/dist/leaflet-routing-machine.js"></script>
<script src="https://rawcdn.githack.com/ewoken/Leaflet.MovingMarker/master/MovingMarker.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body {{ margin:0; font-family:Arial; background:#f5f5f5; }}
.header {{ display:flex; align-items:center; gap:15px; background:#004080; color:white; padding:8px 15px; }}
.header img {{ height:60px; }}
.header .info h1 {{ margin:0; font-size:22px; }}
.header .info h2 {{ margin:2px 0; font-size:16px; font-weight:normal; }}
.header .team {{ font-size:14px; margin-top:4px; }}
.tabs {{ display:flex; background:#007bff; color:white; }}
.tab {{ flex:1; text-align:center; padding:10px; cursor:pointer; }}
.tab.active {{ background:#0056b3; }}
#content > div {{ display:none; height:calc(100vh - 100px); }}
#content > div.active {{ display:block; }}
#container {{ display:flex; height:100%; }}
#map {{ flex:2; height:100%; }}
#sidebar {{ flex:1; overflow-y:auto; padding:10px; background:#fafafa; border-left:2px solid #ddd; font-size:14px; }}
button {{ margin:5px; padding:6px 10px; border:none; border-radius:5px; background:#007bff; color:white; cursor:pointer; font-size:14px; }}
button:hover {{ background:#0056b3; }}
.binbar {{ width:100%; background:#eee; border:1px solid #ccc; margin:5px 0; position:relative; height:20px; border-radius:5px; overflow:hidden; }}
.binfill {{ height:100%; color:white; font-size:12px; text-align:center; line-height:20px; }}
.vehicle {{ margin:4px; padding:6px; border-radius:5px; color:white; font-weight:bold; }}
.vehicle.idle {{ background:#28a745; }}
.vehicle.busy {{ background:#ff9800; }}
.scrollbox {{ max-height:150px; overflow-y:auto; padding:5px; border:1px solid #ddd; background:#fff; margin-bottom:10px; }}
#grid {{ display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:10px; height:100%; padding:10px; }}
.panel {{ background:white; padding:10px; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); overflow:auto; }}
.gauge-container {{ display:flex; flex-wrap:wrap; justify-content:center; gap:10px; }}
.gauge {{ width:120px; height:120px; }}
.gauge-label {{ text-align:center; margin-top:5px; font-size:14px; }}
</style>
</head>
<body>

<div class="header">
  <img src="https://hithaldia.ac.in/wp-content/uploads/2025/09/logo-2.png" alt="HIT Logo"/>
  <div class="info">
    <h1>Haldia Institute of Technology</h1>
    <h2>Registration No.: TH12180</h2>
    <div class="team">
      Title: Drinking Water Points and Pollution-Free Waste Management Zones<br/>
      Theme: Health and Sanitation Management<br/>
      TEAM NAME: TEAM VIDYUT
    </div>
  </div>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('sim')">🚮 Simulation</div>
  <div class="tab" onclick="switchTab('dash')">📊 Dashboard</div>
</div>

<div id="content">
  <!-- Simulation Tab -->
  <div id="sim" class="active">
    <div id="container">
      <div id="map"></div>
      <div id="sidebar">
        <h3>Controls</h3>
        <button onclick="fillBin()">Fill Random Bin</button>
        <button onclick="assignCar()">Assign Vehicle</button>
        <button onclick="resetAll()">Reset All</button>
        <button onclick="resetVehicles()">Reset Vehicles</button><br/>
        <button onclick="startAuto()">▶ Start Auto</button>
        <button onclick="stopAuto()">⏹ Stop Auto</button>
        <h3>Bins</h3><div id="binlist"></div>
        <h3>Vehicles</h3><div id="vehlist"></div>
        <h3>Assignments</h3><div class="scrollbox" id="assignlist"></div>
        <h3>Comparison Stats</h3><div class="scrollbox" id="comparisons"></div>
        <h3>📡 Bin Alerts</h3><div class="scrollbox" id="alertlist"></div>
        <h3>Water Tap</h3><div id="waterTapInfo">Lat: 22.0507, Lng: 88.0723</div>
      </div>
    </div>
  </div>

  <!-- Dashboard Tab -->
  <div id="dash">
    <div id="grid">
      <div class="panel">
        <h2>🌫️ Air Quality</h2>
        <div class="gauge-container" id="airGauges"></div>
      </div>
      <div class="panel">
        <h2>💧 Water Quality</h2>
        <div class="gauge-container" id="waterGauges"></div>
      </div>
      <div class="panel" style="grid-column: span 2;">
        <h2>🚮 Waste Management</h2>
        <div><h4>Bins</h4><div id="wBins"></div></div>
        <div><h4>Vehicles</h4><div id="wVeh"></div></div>
        <div><h4>Assignments</h4><div id="wAssign" class="scrollbox"></div></div>
        <div><h4>Comparison Stats</h4><div id="wComp" class="scrollbox"></div></div>
      </div>
    </div>
  </div>
</div>

<script>
function switchTab(id) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('#content > div').forEach(c => c.classList.remove('active'));
  document.querySelector(`.tab[onclick="switchTab('${{id}}')"]`).classList.add('active');
  document.getElementById(id).classList.add('active');
}}

const map = L.map('map').setView([22.0509,88.0725], 17);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);
const binMarkers = {{}}, vehMarkers = {{}}, routes = {{}}, animHandles = {{}};

const waterTap = L.marker([22.0507, 88.0723], {{
  icon: L.icon({{
    iconUrl: "https://static.thenounproject.com/png/water-tab-icon-2606029-512.png",
    iconSize: [40, 40],
    iconAnchor: [20, 40]
  }})
}}).addTo(map).bindPopup("💧 Water Tap<br>Lat: 22.0507, Lng: 88.0723");

function carIcon(c) {{
  return L.icon({{
    iconUrl: c == "orange"
      ? "https://cdn-icons-png.flaticon.com/512/3097/3097144.png"
      : "https://cdn-icons-png.flaticon.com/512/3097/3097133.png",
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  }});
}}

function animateVehicle(v, b) {{
  // prevent duplicate animations for same vehicle
  if (animHandles[v.id] && animHandles[v.id].running) return;

  // remove previous route control and marker if any
  if (routes[v.id]) try {{ map.removeControl(routes[v.id]); }} catch(e){{}}
  if (vehMarkers[v.id]) try {{ vehMarkers[v.id].remove(); }} catch(e){{}}

  const rc = L.Routing.control({{
    waypoints: [L.latLng(v.lat, v.lng), L.latLng(b.lat, b.lng)],
    lineOptions: {{ styles: [{{ color: 'purple', weight: 4, opacity: 0.7 }}] }},
    addWaypoints: false,
    draggableWaypoints: false,
    fitSelectedRoutes: false,
    createMarker: () => null
  }}).on('routesfound', e => {{
    const route = e.routes[0];
    const coords = route.coordinates.map(c => L.latLng(c.lat, c.lng));
    const totalDist = route.summary && route.summary.totalDistance ? route.summary.totalDistance : 0; // meters
    const totalTime = route.summary && route.summary.totalTime ? route.summary.totalTime : 0; // seconds

    // report the exact route distance/time back to server so backend/dashboard match frontend
    try {{
      fetch('/record_route_assignment', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ vehicle_id: v.id, bin_id: b.id, distance: totalDist, time: totalTime }})
      }});
    }} catch (err){{}}

    // create marker at start
    const marker = L.marker([v.lat, v.lng], {{ icon: carIcon("orange") }}).addTo(map);
    vehMarkers[v.id] = marker;

    // speak assignment using routing totals (keeps consistent with map)
    try {{
      const assignMsg = `Vehicle ${{v.id}} assigned to Bin ${{b.id}} — distance ${{Math.round(totalDist)}} meters, ETA ${{Math.round(totalTime)}} seconds.`;
      speechSynthesis.speak(new SpeechSynthesisUtterance(assignMsg));
    }} catch (err){{}}

    // build segments (distance & duration) using accurate distanceTo
    const speed = 20 * 1000 / 3600; // 20 km/h -> m/s (adjust if needed)
    const segments = [];
    for (let i = 1; i < coords.length; i++) {{
      const p1 = coords[i - 1];
      const p2 = coords[i];
      const dist = p1.distanceTo(p2); // meters
      const dur = Math.max(200, Math.round((dist / speed) * 1000)); // ms per segment, min 200ms
      segments.push({{ start: p1, end: p2, dist: dist, dur: dur }});
    }}
    if (segments.length === 0) segments.push({{ start: coords[0], end: coords[0], dist: 0, dur: 1000 }});

    // set anim handle and mark running
    animHandles[v.id] = {{ running: true, raf: null }};

    // animation state
    let segIndex = 0;
    let segStartTime = null;

    function step(timestamp) {{
      if (!segStartTime) segStartTime = timestamp;
      const seg = segments[segIndex];
      const elapsed = timestamp - segStartTime;
      const t = Math.min(1, elapsed / seg.dur);

      // interpolate lat/lng
      const lat = seg.start.lat + (seg.end.lat - seg.start.lat) * t;
      const lng = seg.start.lng + (seg.end.lng - seg.start.lng) * t;
      marker.setLatLng([lat, lng]);

      if (t >= 1) {{
        // move to next segment
        segIndex++;
        segStartTime = timestamp;
        if (segIndex >= segments.length) {{
          // finished all segments
          animHandles[v.id].running = false;
          // small pause to simulate unloading then complete trip
          setTimeout(() => {{
            try {{
              const doneMsg = `Vehicle ${{v.id}} completed collection from Bin ${{b.id}}.`;
              speechSynthesis.speak(new SpeechSynthesisUtterance(doneMsg));
            }} catch (err){{}}
            fetch(`/complete_trip/${{v.id}}/${{b.id}}`, {{ method: 'POST' }})
              .then(() => refresh())
              .catch(() => refresh());
          }}, 800);
          return;
        }}
      }}

      // continue animation
      animHandles[v.id].raf = requestAnimationFrame(step);
    }}

    // start
    animHandles[v.id].raf = requestAnimationFrame(step);
  }}).addTo(map);

  // store route controller
  routes[v.id] = rc;
}}



function speak(msg) {{
  let utter = new SpeechSynthesisUtterance(msg);
  speechSynthesis.speak(utter);
}}

async function refresh() {{
  const bins = await fetch('/bins').then(r => r.json());
  const vs = await fetch('/vehicles').then(r => r.json());
  const asg = await fetch('/assignments').then(r => r.json());
  const comps = await fetch('/comparisons').then(r => r.json());
  const alerts = await fetch('/alerts').then(r => r.json());

  let bh = "";
  bins.forEach(b => {{
    const col = b.status == "FULL" ? "red" : (b.fill > 50 ? "orange" : "green");
    if (!binMarkers[b.id]) binMarkers[b.id] = L.circleMarker([b.lat, b.lng], {{ radius: 10, color: col, fillColor: col, fillOpacity: 0.9 }}).addTo(map);
    binMarkers[b.id].setLatLng([b.lat, b.lng]).setStyle({{ color: col, fillColor: col }});
    bh += `<div class="binbar"><div class="binfill" style="width:${{b.fill}}%;background:${{col}}">${{b.fill}}%</div></div>`;
  }});
  document.getElementById("binlist").innerHTML = bh;

  let vh = "";
  vs.forEach(v => {{
    const col = v.status == "BUSY" ? "orange" : "green";
    if (!vehMarkers[v.id]) vehMarkers[v.id] = L.marker([v.lat, v.lng], {{ icon: carIcon(col) }}).addTo(map);
    vehMarkers[v.id].setLatLng([v.lat, v.lng]).setIcon(carIcon(col));
    vh += `<div class="vehicle ${{v.status.toLowerCase()}}">Vehicle ${{v.id}}: ${{v.status}}${{v.target_bin ? (" → Bin " + v.target_bin) : ""}}</div>`;
    if (v.status == "BUSY" && v.target_bin) {{
      const bObj = bins.find(x => x.id == v.target_bin);
      if (bObj) animateVehicle(v, bObj);
    }}
  }});
  document.getElementById("vehlist").innerHTML = vh;

  let ah = "";
  asg.slice().reverse().forEach(a => {{
    ah += `<div>${{a.time}}: Veh ${{a.vehicle_id}} → Bin ${{a.bin_id}}</div>`;
  }});
  document.getElementById("assignlist").innerHTML = ah;

  let ch = "";
  comps.slice().reverse().forEach(c => {{
    let otherTxt = c.others.map(o => `Veh ${{o.id}} (${{o.dist}}m)`).join(", ");
    ch += `<div><b>${{c.time}}</b>: Bin ${{c.bin}} → Veh ${{c.assigned_vehicle}} (${{c.assigned_distance}}m). Others: ${{otherTxt}}</div>`;
  }});
  document.getElementById("comparisons").innerHTML = ch;

  let al = "";
  alerts.slice().reverse().forEach(a => {{
    al += `<div><b>${{a.time}}</b>: ${{a.msg}}</div>`;
  }});
  document.getElementById("alertlist").innerHTML = al;
  if (alerts.length > 0) {{
    let last = alerts[alerts.length-1];
    speak(last.msg);
  }}

  document.getElementById("wBins").innerHTML = bins.map(b => {{
    const col = b.status == "FULL" ? "red" : (b.fill > 50 ? "orange" : "green");
    return `<div class="binbar"><div class="binfill" style="width:${{b.fill}}%;background:${{col}}">${{b.fill}}%</div></div>`;
  }}).join("");
  document.getElementById("wVeh").innerHTML = vs.map(v => `<div class="vehicle ${{v.status.toLowerCase()}}">Vehicle ${{v.id}}: ${{v.status}}</div>`).join("");
  document.getElementById("wAssign").innerHTML = asg.slice().reverse().map(a => `<div>${{a.time}}: V${{a.vehicle_id}}→B${{a.bin_id}}</div>`).join("");
  document.getElementById("wComp").innerHTML = comps.slice().reverse().map(c => {{
    let otherTxt = c.others.map(o => `V${{o.id}} (${{o.dist}}m)`).join(", ");
    return `<div>${{c.time}}: Bin ${{c.bin}} → V${{c.assigned_vehicle}} (${{c.assigned_distance}}m). Others: ${{otherTxt}}</div>`;
  }}).join("");
}}

async function fillBin() {{ await fetch('/fill_random', {{ method: 'POST' }}); refresh(); }}
async function assignCar() {{ await fetch('/assign_nearest_full', {{ method: 'POST' }}); refresh(); }}
async function resetAll() {{ await fetch('/reset', {{ method: 'POST' }}); Object.values(routes).forEach(r => map.removeControl(r)); refresh(); }}
async function resetVehicles() {{ await fetch('/reset_vehicles', {{ method: 'POST' }}); Object.values(routes).forEach(r => map.removeControl(r)); refresh(); }}
async function startAuto() {{ await fetch('/start_auto', {{ method: 'POST' }}); }}
async function stopAuto() {{ await fetch('/stop_auto', {{ method: 'POST' }}); }}

setInterval(refresh, 3000);
refresh();

const airParams = ["NH3","Smoke","Alcohol","Benzene","CO2","NOx"];
const waterParams = ["TDS","EC"];
function createGauge(ctx,label) {{
  return new Chart(ctx,{{
    type:'doughnut',
    data:{{labels:[label],datasets:[{{data:[0,100],backgroundColor:['#00ff00','#eee'],borderWidth:0}}]}},
    options:{{rotation:-90,circumference:180,cutout:'70%',plugins:{{legend:{{display:false}}}},animation:false}}
  }});
}}
const airGauges = {{}}, waterGauges = {{}};
function initGauges(){{
  airParams.forEach(p=>{{
    const div=document.createElement('div');
    div.innerHTML=`<canvas class="gauge"></canvas><div class="gauge-label">${{p}}: <span id="val-${{p}}">0</span></div>`;
    document.getElementById("airGauges").appendChild(div);
    airGauges[p]=createGauge(div.querySelector("canvas"),p);
  }});
  waterParams.forEach(p=>{{
    const div=document.createElement('div');
    div.innerHTML=`<canvas class="gauge"></canvas><div class="gauge-label">${{p}}: <span id="val-${{p}}">0</span></div>`;
    document.getElementById("waterGauges").appendChild(div);
    waterGauges[p]=createGauge(div.querySelector("canvas"),p);
  }});
}}
initGauges();
function updateGauges(){{
  airParams.forEach(p=>{{
    let val=Math.floor(Math.random()*100);
    let g=airGauges[p]; g.data.datasets[0].data=[val,100-val];
    g.data.datasets[0].backgroundColor=[val>70?'#ff0000':val>40?'#ffa500':'#00ff00','#eee'];
    g.update(); document.getElementById("val-"+p).innerText=val;
  }});
  waterParams.forEach(p=>{{
    let val=Math.floor(Math.random()*100);
    let g=waterGauges[p]; g.data.datasets[0].data=[val,100-val];
    g.data.datasets[0].backgroundColor=[val>70?'#ff0000':val>40?'#ffa500':'#00ff00','#eee'];
    g.update(); document.getElementById("val-"+p).innerText=val;
  }});
}}
setInterval(updateGauges,3000);
</script>
</body>
</html>"""

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    import uvicorn, os
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting on port {port} ...")
    uvicorn.run(app, host="0.0.0.0", port=port)

