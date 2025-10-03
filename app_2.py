from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import datetime, threading, time, random, math

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
    }
    for i in range(3)
]

assignments, comparison_stats, bin_alerts = [], [], []
auto_sim = {"running": False}
system_stats = {"completed": 0, "distance": 0.0, "avg_eta": 0.0}

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
# Record route assignment (simplified)
# -------------------------
@app.post("/record_route_assignment")
async def record_route_assignment(request: Request):
    data = await request.json()

    # Only keep consistent format
    rec = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "bin": data["bin_id"],
        "assigned_vehicle": data["vehicle_id"],
        "assigned_distance": round(data.get("distance", 0), 1),
        "others": []  # client can later populate or ignore
    }
    comparison_stats.append(rec)

    # Update system-level stats
    system_stats["distance"] += rec["assigned_distance"]
    if system_stats["completed"] > 0:
        system_stats["avg_eta"] = round(system_stats["distance"] / system_stats["completed"], 1)

    return {"ok": True}

# -------------------------
# Serve UI
# -------------------------
@app.get("/", response_class=HTMLResponse)
def home():
    return open("ui_final.html", encoding="utf-8").read()

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    import uvicorn, os
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting on port {port} ...")
    uvicorn.run(app, host="0.0.0.0", port=port)

