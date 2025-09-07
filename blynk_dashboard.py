# blynk_dashboard.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import requests, random, datetime

app = FastAPI()

# -------------------------
# Blynk Credentials
# -------------------------
BLYNK_TEMPLATE_ID = "TMPL3WwPBAikP"
BLYNK_AUTH_TOKEN  = "RjMBf-HzBoqR5BSr0KeYHHWFZi8B8icQ"
BASE_URL = f"https://blynk.cloud/external/api/get?token={BLYNK_AUTH_TOKEN}"

# -------------------------
# Waste Management Data (HIT Campus)
# -------------------------
CAMPUS_CENTER = (22.0509, 88.0725)

bins = [
    {"id": 1, "lat": 22.05230, "lng": 88.07240, "fill": 40, "status": "OK"},
    {"id": 2, "lat": 22.05180, "lng": 88.07195, "fill": 30, "status": "OK"},
    {"id": 3, "lat": 22.05090, "lng": 88.07260, "fill": 50, "status": "OK"},
    {"id": 4, "lat": 22.05020, "lng": 88.07130, "fill": 20, "status": "OK"},
    {"id": 5, "lat": 22.04960, "lng": 88.07090, "fill": 35, "status": "OK"},
]

vehicles = [
    {
        "id": i + 1,
        "lat": CAMPUS_CENTER[0] + random.uniform(-0.0008, 0.0008),
        "lng": CAMPUS_CENTER[1] + random.uniform(-0.0008, 0.0008),
        "status": "IDLE",
    }
    for i in range(3)
]

# -------------------------
# Complaints Storage
# -------------------------
complaints = []

# -------------------------
# Blynk Fetch Functions
# -------------------------
def get_blynk_value(pin):
    try:
        url = f"{BASE_URL}&{pin}"
        r = requests.get(url, timeout=5)
        return float(r.text)
    except:
        return None

def get_air_data():
    return {
        "NH3": get_blynk_value("v3"),
        "Smoke": get_blynk_value("v4"),
        "Alcohol": get_blynk_value("v5"),
        "Benzene": get_blynk_value("v6"),
        "CO2": get_blynk_value("v7"),
        "NOx": get_blynk_value("v8"),
    }

def get_water_data():
    return {
        "TDS": get_blynk_value("v0"),
        "EC": get_blynk_value("v1"),
    }

# -------------------------
# API Endpoints
# -------------------------
@app.get("/air")
def air(): return get_air_data()

@app.get("/water")
def water(): return get_water_data()

@app.get("/bins")
def get_bins(): return bins

@app.get("/vehicles")
def get_vehicles(): return vehicles

@app.get("/complaints")
def get_complaints(): return complaints

@app.post("/complaint")
async def submit_complaint(request: Request):
    data = await request.json()
    c = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "phone": data.get("phone",""),
        "message": data.get("message","")
    }
    complaints.append(c)
    return {"ok": True, "complaint": c}

# -------------------------
# QR Code & Complaint Form
# -------------------------
@app.get("/qrcode", response_class=HTMLResponse)
def qrcode():
    return """
    <html><body>
    <h2>Scan this QR to file a complaint</h2>
    <img src="https://api.qrserver.com/v1/create-qr-code/?data=smart-waste-management-realtime.onrender.com/complaint_form&size=200x200"/>
    </body></html>
    """

@app.get("/complaint_form", response_class=HTMLResponse)
def complaint_form():
    return """
    <html><body>
    <h2>Submit Complaint</h2>
    <form method="post" action="/complaint_form">
      Phone: <input type="text" name="phone"/><br><br>
      Message: <textarea name="message"></textarea><br><br>
      <input type="submit" value="Submit"/>
    </form>
    </body></html>
    """

@app.post("/complaint_form", response_class=HTMLResponse)
async def complaint_form_post(phone: str = Form(...), message: str = Form(...)):
    complaints.append({
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "phone": phone,
        "message": message
    })
    return "<html><body><h2>Complaint Submitted ✅</h2><a href='/'>Back to Dashboard</a></body></html>"

# -------------------------
# UI
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>HIT Real-Time Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{font-family:Arial;margin:0;background:#f5f5f5;}
h1{text-align:center;background:#004080;color:white;padding:10px;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:20px;}
.panel{background:white;padding:15px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.2);}
.gauge{width:180px;height:180px;display:inline-block;margin:10px;text-align:center;}
.gauge canvas{width:100%!important;height:100%!important;}
#alerts{max-height:200px;overflow-y:auto;background:#ffecec;padding:10px;border-radius:8px;}
</style>
</head>
<body>
<h1>🌍 HIT Real-Time Dashboard</h1>
<div class="grid">
  <div class="panel">
    <h2>🌫️ Air Quality</h2>
    <div id="airGauges" style="display:flex;flex-wrap:wrap;justify-content:center;"></div>
  </div>
  <div class="panel">
    <h2>💧 Water Quality</h2>
    <div id="waterGauges" style="display:flex;flex-wrap:wrap;justify-content:center;"></div>
  </div>
  <div class="panel">
    <h2>🚮 Waste Management</h2>
    <div id="bins"></div>
    <div id="vehicles"></div>
  </div>
  <div class="panel">
    <h2>⚠️ Alerts</h2>
    <div id="alerts"></div>
  </div>
</div>

<script>
function createGauge(id,label,maxVal){
  let ctx=document.getElementById(id).getContext("2d");
  return new Chart(ctx,{
    type:"doughnut",
    data:{datasets:[{data:[0,maxVal],backgroundColor:["#28a745","#ddd"],borderWidth:0}]},
    options:{
      circumference:180,
      rotation:270,
      cutout:"70%",
      plugins:{tooltip:{enabled:false},legend:{display:false},title:{display:true,text:label}}
    }
  });
}
let airParams=["NH3","Smoke","Alcohol","Benzene","CO2","NOx"];
let waterParams=["TDS","EC"];
let airCharts={},waterCharts={};
airParams.forEach(p=>{
  document.getElementById("airGauges").innerHTML+=`<div class="gauge"><canvas id="air_${p}"></canvas><div id="val_air_${p}">0</div></div>`;
});
waterParams.forEach(p=>{
  document.getElementById("waterGauges").innerHTML+=`<div class="gauge"><canvas id="water_${p}"></canvas><div id="val_water_${p}">0</div></div>`;
});
airParams.forEach(p=>{airCharts[p]=createGauge("air_"+p,p,100);});
waterParams.forEach(p=>{waterCharts[p]=createGauge("water_"+p,p,100);});

async function fetchData(){
  let air=await fetch('/air').then(r=>r.json());
  let water=await fetch('/water').then(r=>r.json());
  let bins=await fetch('/bins').then(r=>r.json());
  let vehicles=await fetch('/vehicles').then(r=>r.json());
  let alerts=await fetch('/complaints').then(r=>r.json());

  airParams.forEach(p=>{
    let v=air[p]||0;
    airCharts[p].data.datasets[0].data=[v,100-v];
    airCharts[p].data.datasets[0].backgroundColor=[v>70?"red":v>40?"orange":"green","#ddd"];
    airCharts[p].update();
    document.getElementById("val_air_"+p).innerText=v.toFixed(1);
  });
  waterParams.forEach(p=>{
    let v=water[p]||0;
    waterCharts[p].data.datasets[0].data=[v,100-v];
    waterCharts[p].data.datasets[0].backgroundColor=[v>70?"red":v>40?"orange":"green","#ddd"];
    waterCharts[p].update();
    document.getElementById("val_water_"+p).innerText=v.toFixed(1);
  });

  document.getElementById("bins").innerHTML=bins.map(b=>`<div>Bin ${b.id}: ${b.fill}% at (${b.lat},${b.lng})</div>`).join("");
  document.getElementById("vehicles").innerHTML=vehicles.map(v=>`<div>Vehicle ${v.id}: ${v.status} at (${v.lat.toFixed(5)},${v.lng.toFixed(5)})</div>`).join("");

  document.getElementById("alerts").innerHTML=alerts.slice().reverse().map(a=>`<div><b>${a.time}</b> 📱${a.phone}: ${a.message}</div>`).join("");
}
setInterval(fetchData,5000);
fetchData();
</script>
</body>
</html>
"""

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))   # Render supplies PORT
    print("Server starting. Use the public Render URL shown in your dashboard.")
    uvicorn.run(app, host="0.0.0.0", port=port)
