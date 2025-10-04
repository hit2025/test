from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import datetime, threading, time, random, math, os

app = FastAPI()
CAMPUS_CENTER = (22.0509, 88.0725)

BLYNK_TEMPLATE_ID = "TMPL3ZHnAAMIw"
BLYNK_AUTH_TOKEN = "hpOQDbsw9BUEWc5fsZYvnqqWhqouM102"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# -------------------------
# Data stores
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
        # per-driver stats
        "completed": 0,
        "distance": 0.0,
        "history": [],  # list of {time, bin_id, distance, duration}
    }
    for i in range(3)
]

assignments, comparison_stats, bin_alerts = [], [], []
auto_sim = {"running": False}
system_stats = {"completed": 0, "distance": 0.0, "avg_eta": 0.0}

# -------------------------
# Utilities
# -------------------------
def find_vehicle(vid):
    return next((v for v in vehicles if v["id"] == vid), None)

def find_bin(bid):
    return next((b for b in bins if b["id"] == bid), None)

# -------------------------
# APIs (main)
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

@app.get("/stats")
def get_stats():
    return system_stats

# -------------------------
# Bin fill + vehicle assign
# -------------------------
@app.post("/fill_random")
def fill_random():
    b = random.choice(bins)
    b["fill"] = min(100, b["fill"] + random.randint(20, 40))
    if b["fill"] >= 100:
        b["fill"], b["status"] = 100, "FULL"
        bin_alerts.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "msg": f"⚠️ Bin {b['id']} is FULL and sent an alert"
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
        "others": [{"id": v["id"], "dist": round(d, 1)} for d, v in dists[1:]]
    }
    comparison_stats.append(comp)

    bin_alerts.append({
        "time": rec["time"],
        "msg": f"Vehicle {nearest_vehicle['id']} accepted task for Bin {b['id']} ({round(dists[0][0],1)} m)"
    })
    return {"ok": True, "assignment": rec, "comparison": comp}

# -------------------------
# Complete trip
# -------------------------
@app.post("/complete_trip/{vid}/{bid}")
def complete_trip(vid: int, bid: int):
    for v in vehicles:
        if v["id"] == vid:
            v["status"], v["target_bin"] = "IDLE", None
    for b in bins:
        if b["id"] == bid:
            b["fill"], b["status"] = 0, "OK"

    system_stats["completed"] += 1
    bin_alerts.append({
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "msg": f"✅ Vehicle {vid} completed trip for Bin {bid}"
    })

    return {"ok": True}

# -------------------------
# Reset
# -------------------------
@app.post("/reset")
def reset_all():
    for v in vehicles:
        v.update({
            "status": "IDLE",
            "target_bin": None,
            "lat": CAMPUS_CENTER[0] + random.uniform(-0.001, 0.001),
            "lng": CAMPUS_CENTER[1] + random.uniform(-0.001, 0.001),
            "completed": 0,
            "distance": 0.0,
            "history": [],
        })
    assignments.clear()
    comparison_stats.clear()
    bin_alerts.clear()
    system_stats["completed"] = 0
    system_stats["distance"] = 0.0
    system_stats["avg_eta"] = 0.0
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

# -------------------------
# Auto mode
# -------------------------
@app.post("/start_auto")
def start_auto():
    auto_sim["running"] = True
    return {"ok": True}

@app.post("/stop_auto")
def stop_auto():
    auto_sim["running"] = False
    return {"ok": True}

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
                        "msg": f"⚠️ Bin {b['id']} is FULL and sent an alert"
                    })
            assign_nearest_full()
        time.sleep(2)

threading.Thread(target=auto_loop, daemon=True).start()

# -------------------------
# Record route assignment (client sends routing summary)
# -------------------------
@app.post("/record_route_assignment")
async def record_route_assignment(request: Request):
    data = await request.json()
    # Expected keys: vehicle_id, bin_id, distance (m), time (s)
    vid = int(data.get("vehicle_id", 0))
    bid = int(data.get("bin_id", 0))
    dist = float(data.get("distance", 0.0))
    ttime = float(data.get("time", 0.0))

    v = find_vehicle(vid)
    if v is not None:
        # update vehicle level stats
        v["distance"] += round(dist, 1)
        v["completed"] += 1
        v["history"].append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "bin": bid,
            "distance": round(dist, 1),
            "duration": round(ttime, 1)
        })

    # update global stats
    system_stats["distance"] += round(dist, 1)
    system_stats["completed"] += 0  # completed will be increased on /complete_trip
    # compute avg eta if we have any completed
    if any(v["completed"] > 0 for v in vehicles):
        total_trips = sum(v["completed"] for v in vehicles)
        total_time = sum(sum(h.get("duration", 0) for h in v["history"]) for v in vehicles)
        system_stats["avg_eta"] = round(total_time / max(1, total_trips), 1)

    # store a comparison entry
    rec = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "bin": bid,
        "assigned_vehicle": vid,
        "route_distance": round(dist, 1),
        "route_time": round(ttime, 1),
        "others": data.get("others", [])
    }
    comparison_stats.append(rec)

    return {"ok": True}

# -------------------------
# Driver endpoints (per-driver JSON + serve driver HTML)
# -------------------------
@app.get("/driver/{vehicle_id}")
def driver_status(vehicle_id: int):
    v = find_vehicle(vehicle_id)
    if v is None:
        return JSONResponse({"status": "ERROR", "message": "Vehicle not found"}, status_code=404)

    if not v["target_bin"]:
        return {"status": "IDLE", "message": "No active assignment", "vehicle_id": v["id"], "location": {"lat": v["lat"], "lng": v["lng"]},
                "stats": {"completed": v["completed"], "distance": v["distance"], "history": v["history"]}}

    b = find_bin(v["target_bin"])
    if not b:
        return {"status": "ERROR", "message": "Assigned bin not found"}

    # compute haversine approx for driver notification (server-side estimate)
    dist = haversine(v["lat"], v["lng"], b["lat"], b["lng"])
    # rough ETA assuming 20 km/h
    eta = dist / (20 * 1000 / 3600)

    return {
        "status": "ASSIGNED",
        "vehicle_id": v["id"],
        "vehicle_location": {"lat": v["lat"], "lng": v["lng"]},
        "assigned_bin": {"id": b["id"], "fill": b["fill"], "lat": b["lat"], "lng": b["lng"]},
        "distance_m": round(dist, 1),
        "eta_s": round(eta, 1),
        "stats": {"completed": v["completed"], "distance": v["distance"], "history": v["history"]}
    }

@app.get("/driver_stats/{vehicle_id}")
def driver_stats(vehicle_id: int):
    v = find_vehicle(vehicle_id)
    if not v:
        return JSONResponse({"status": "ERROR", "message": "Vehicle not found"}, status_code=404)
    return {"vehicle_id": v["id"], "completed": v["completed"], "distance": v["distance"], "history": v["history"]}

@app.get("/driver_dashboard", response_class=HTMLResponse)
def serve_driver_html(id: int = 1):
    # serve the driver.html file from the same folder
    if os.path.exists("driver.html"):
        return open("driver.html", encoding="utf-8").read()
    return "<h2>Driver dashboard file not found</h2>"

# -------------------------
# Serve admin UI (existing)
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    # keep existing ui_final.html as main admin
    if os.path.exists("ui_final.html"):
        return open("ui_final.html", encoding="utf-8").read()
    return "<h2>Main UI file not found</h2>"

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting on port {port} ...")
    uvicorn.run(app, host="0.0.0.0", port=port)

