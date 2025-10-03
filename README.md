# 🚮 Drinking Water Points and Pollution-Free Waste Management Zones – Simulation & Real-Time Dashboard

This project demonstrates a **Smart Campus Prototype** integrating **Waste Management Simulation**, **Real-Time Environmental Monitoring**, and an **Alert System**.

---

## ✨ Features
- **Waste Management Simulation**  
  - Interactive HIT Campus map with **Bins** and **Vehicles**.  
  - Vehicle assignment to nearest full bin.  
  - Comparison stats and live assignments.  
  - Auto-simulation with random bin fills.  

- **Real-Time Monitoring (via Blynk IoT Cloud)**  
  - **Air Quality Gauges** (NH3, Smoke, Alcohol, Benzene, CO2, NOx).  
  - **Water Quality Gauges** (TDS, EC).  

- **Alert System**  
  - Users scan a QR code to submit complaints with mobile number + message.  
  - Complaints appear live in the **Dashboard Alerts Panel**.  

---

## 🌐 Public Deployment
This project is deployed on **Render.com** for jury evaluation.  

- **Simulation + Dashboard**  
  👉 [https://smart-waste-management-9zmq.onrender.com/](https://smart-waste-management-9zmq.onrender.com/)

- **Real-Time Blynk Dashboard**  
  👉 [https://smart-waste-management-realtime.onrender.com/](https://smart-waste-management-realtime.onrender.com/)

- **QR Code Complaint Page**  
  👉 [https://smart-waste-management-realtime.onrender.com/qrcode](https://smart-waste-management-realtime.onrender.com/qrcode)

---

## 📦 Requirements
- Python **3.9+**
- Dependencies listed in [`requirements.txt`](requirements.txt)

Install with:
```bash
pip install -r requirements.txt

▶️ Run Locally

    Clone the repo:

git clone https://github.com/hit2025/smart-waste-management.git
cd smart-waste-management

Start the simulation app:

python app.py

→ Opens at http://127.0.0.1:8000

Start the real-time Blynk dashboard:

python blynk_dashboard.py

→ Opens at http://127.0.0.1:8001

