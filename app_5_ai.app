from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import datetime, threading, time, random, math, os

app = FastAPI()
CAMPUS_CENTER = (22.0509, 88.0725)

# ------------------------------
# Blynk placeholders (optional)
# ------------------------------
BLYNK_TEMPLATE_ID = "TMPL3ZHnAAMIw"
BLYNK_AUTH_TOKEN = "hpOQDbsw9BUEWc5fsZYvnqqWhqouM102"

# ------------------------------
# Haversine Distance
# ------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ------------------------------
# Simulated Predictive Model
# ------------------------------
def predict_fill(bin_data):
    """Simulate AI model predicting bin fill percentage."""
    growth = random.uniform(0.5, 3.0)
    next_fill = min(100, bin_data["fill"] + growth)
    return round(next_fill, 2)

# ------------------------------
# Core Data Structures
# ------------------------------
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
        "completed": 0,
        "total_distance": 0.0
    }
    for i in range(3)
]

assignments, comparison_stats, bin_alerts = [], [], []
auto_sim = {"running": False}
system_stats = {"completed": 0, "distance": 0.0, "avg_eta": 0.0}

# ------------------------------
# APIs
# ------------------------------
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

# ------------------------------
# Predictive Bin Fill (AI Layer)
# ------------------------------
@app.post("/predict_fills")
def predict_fills():
    updated = []
    for b in bins:
        new_fill = predict_fill(b)
        b["fill"] = new_fill
        if new_fill >= 100:
            b["status"] = "FULL"
            bin_alerts.append({
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "msg": f"🔮 Predicted FULL Bin {b['id']} (AI Forecast)"
            })
        updated.append(b)
    return {"ok": True, "bins": updated}

# ------------------------------
# Random Fill for Simulation
# ------------------------------
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

# ------------------------------
# Assign Nearest Vehicle (Dynamic Optimization)
# ------------------------------
@app.post("/assign_nearest_full")
def assign_nearest_full():
    full_bins = [b for b in bins if b["status"] == "FULL" and not any(v["target_bin"] == b["id"] for v in vehicles)]
    idle = [v for v in vehicles if v["status"] == "IDLE"]
    if not full_bins or not idle:
        return {"ok": False}

    # Weighted optimization: pick nearest + least busy
    b = random.choice(full_bins)
    weighted_scores = []
    for v in idle:
        dist = haversine(v["lat"], v["lng"], b["lat"], b["lng"])
        score = dist + (v["completed"] * 50)
        weighted_scores.append((score, v, dist))
    weighted_scores.sort(key=lambda x: x[0])

    nearest_vehicle = weighted_scores[0][1]
    distance_to_bin = weighted_scores[0][2]

    nearest_vehicle["status"] = "BUSY"
    nearest_vehicle["target_bin"] = b["id"]

    rec = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "vehicle_id": nearest_vehicle["id"],
        "bin_id": b["id"],
        "distance": round(distance_to_bin, 1)
    }
    assignments.append(rec)

    comp = {
        "time": rec["time"],
        "bin": b["id"],
        "assigned_vehicle": nearest_vehicle["id"],
        "assigned_distance": round(distance_to_bin, 1),
        "others": [{"id": v["id"], "dist": round(haversine(v["lat"], v["lng"], b["lat"], b["lng"]), 1)} for v in idle if v["id"] != nearest_vehicle["id"]]
    }
    comparison_stats.append(comp)

    bin_alerts.append({
        "time": rec["time"],
        "msg": f"🚗 Vehicle {nearest_vehicle['id']} assigned to Bin {b['id']} dynamically (AI Route Optimization)"
    })

    return {"ok": True, "assignment": rec, "comparison": comp}

# ------------------------------
# Trip Completion
# ------------------------------
@app.post("/complete_trip/{vid}/{bid}")
def complete_trip(vid: int, bid: int):
    for v in vehicles:
        if v["id"] == vid:
            v["status"], v["target_bin"] = "IDLE", None
            v["completed"] += 1
    for b in bins:
        if b["id"] == bid:
            b["fill"], b["status"] = 0, "OK"
    system_stats["completed"] += 1

    bin_alerts.append({
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "msg": f"✅ Vehicle {vid} completed trip for Bin {bid}"
    })
    return {"ok": True}

# ------------------------------
# Reset Functions
# ------------------------------
@app.post("/reset")
def reset_all():
    for v in vehicles:
        v.update({
            "status": "IDLE",
            "target_bin": None,
            "lat": CAMPUS_CENTER[0] + random.uniform(-0.001, 0.001),
            "lng": CAMPUS_CENTER[1] + random.uniform(-0.001, 0.001),
            "completed": 0,
            "total_distance": 0.0
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

# ------------------------------
# Auto Mode (AI + Dynamic Routing)
# ------------------------------
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
            for b in bins:
                b["fill"] = predict_fill(b)
                if b["fill"] >= 100:
                    b["status"] = "FULL"
                    bin_alerts.append({
                        "time": datetime.datetime.now().strftime("%H:%M:%S"),
                        "msg": f"⚠️ Bin {b['id']} reached FULL capacity (AI detected)"
                    })
            assign_nearest_full()
        time.sleep(3)

threading.Thread(target=auto_loop, daemon=True).start()

# ------------------------------
# Route Recording
# ------------------------------
@app.post("/record_route_assignment")
async def record_route_assignment(request: Request):
    data = await request.json()
    rec = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "bin": data["bin_id"],
        "assigned_vehicle": data["vehicle_id"],
        "assigned_distance": round(data.get("distance", 0), 1),
        "others": []
    }
    comparison_stats.append(rec)
    system_stats["distance"] += rec["assigned_distance"]
    if system_stats["completed"] > 0:
        system_stats["avg_eta"] = round(system_stats["distance"] / system_stats["completed"], 1)
    return {"ok": True}

# ------------------------------
# Driver Dashboard APIs
# ------------------------------
@app.get("/driver/{vehicle_id}")
def driver_dashboard(vehicle_id: int):
    v = next((veh for veh in vehicles if veh["id"] == vehicle_id), None)
    if not v:
        return {"status": "ERROR", "message": "Vehicle not found"}

    if not v["target_bin"]:
        return {"status": "IDLE", "message": "No active assignment"}

    b = next((bin for bin in bins if bin["id"] == v["target_bin"]), None)
    if not b:
        return {"status": "ERROR", "message": "Assigned bin not found"}

    return {
        "status": "ASSIGNED",
        "vehicle_id": v["id"],
        "vehicle_location": {"lat": v["lat"], "lng": v["lng"]},
        "assigned_bin": {"id": b["id"], "fill": b["fill"], "lat": b["lat"], "lng": b["lng"]},
        "completed": v["completed"],
        "distance_travelled": v["total_distance"],
        "instructions": f"Proceed to Bin {b['id']} at coordinates ({b['lat']}, {b['lng']})"
    }

@app.get("/driver_dashboard", response_class=HTMLResponse)
def serve_driver_dashboard():
    if os.path.exists("driver.html"):
        return open("driver.html", encoding="utf-8").read()
    return "<h2>Driver dashboard file not found</h2>"

# ------------------------------
# Serve Main UI
# ------------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return open("ui_final.html", encoding="utf-8").read()

# ------------------------------
# Run Server
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    print(f"🚀 Starting Smart Waste Management Server on http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
