# 🚌 RoutesAI

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white" alt="Flask"/>
  <img src="https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white" alt="SQLite"/>
  <img src="https://img.shields.io/badge/Folium-77B829?style=flat" alt="Folium"/>
</p>

## ✨ Overview
**RoutesAI** is a comprehensive Data Engineering and Backend project that collects, processes, and visualizes public transportation data (EMTU) in real-time. 

It handles massive amounts of transit data (stored in SQLite) and generates interactive maps showing vehicle positions, historical traffic, and incidents.

## 🚀 Features
- **Data Collection:** Automated scripts to fetch transit data from EMTU / Noxxonsat APIs.
- **Data Engineering:** Processes and structures complex GTFS and real-time vehicle JSON streams into relational SQLite databases.
- **Interactive Visualization:** Uses Folium to generate dynamic HTML maps (e.g., `mapa_onibus_completo.html`, `mapa_incidente.html`).
- **REST API:** Flask backend to serve routes, schedules, and map data to the frontend.

## 🛠️ How to Run
```bash
git clone https://github.com/your-username/RoutesAI.git
cd RoutesAI

# GTFS Data Setup
# This project requires ARTESP GTFS data to run.
# Create a folder named `artesp_gtfs` in the root directory and extract the GTFS `.txt` files into it.
mkdir artesp_gtfs
# Extract your routes.txt, shapes.txt, stop_times.txt, etc., into this directory.

# Environment Variables Setup
# Create a `.env` file in the root directory and add your TomTom API key:
echo "TOMTOM_API_KEY=your_api_key_here" > .env

# Setup virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start the Flask API
python app.py
```
*(Note: To generate map data, you may need to run `collect_data.py` first to populate the databases).*
