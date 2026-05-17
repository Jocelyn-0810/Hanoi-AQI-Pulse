# Hanoi Air Quality Pulse Dashboard v2

This folder contains the Python Shiny dashboard codebase for Project 2. It has been completely overhauled into a visually immersive, story-driven, and highly intuitive web application featuring a custom dark theme and Hanoi's cultural identity.

## What This Dashboard Includes

A custom-designed dashboard built without the traditional Shiny sidebar, focusing on rich aesthetics, storytelling, and modern web design.

### Four Main Pages:
1. **Overview**:
   - Hero card with a custom Hanoi skyline silhouette background.
   - Real-time AQI with color-coded category labels, scale bars, and weather drivers.
   - "Day & Night" 24-hour AQI split analysis.
   - Dynamic top district mini-cards and a realtime station map.
2. **Districts**:
   - Interactive choropleth map across Hanoi's 30 districts.
   - Ranked monthly heatmap table showing AQI by month for each district.
   - Selected district deep-dive with monthly trends and a horizontal pollutant breakdown.
3. **History**:
   - GitHub-style calendar heatmap showing daily average AQI/PM2.5/PM10.
   - Multi-year same-month overlay charts.
   - Annual trend tracking (Highest/Lowest days and YoY% change arrows).
   - "No. of days" category matrix (stacked color bars representing days in each AQI category per month).
4. **Forecast**:
   - Prediction playground predicting short-term (+1h, +6h, +24h) AQI and PM2.5.
   - Model transparency insights: plain-English summaries explaining the HistGB Regressor's accuracy over a no-change baseline.
   - Feature importance and historical validation plots.

### Narrative-Driven Design
Every section includes **"WHAT THIS SHOWS"** / **"WHAT THIS MEANS"** insight boxes that automatically generate textual summaries of the data, making the dashboard highly accessible to non-technical users.

## Dataset Scope

Active datasets used by this dashboard:

1. `../data/hau100416__vietnamese-air-quality-dataset/aqi_northVN_daily.csv`
2. `../data/hau100416__vietnamese-air-quality-dataset/northVN_dataAIR.csv` (kept for extension)
3. `../data/phungdinhdat__aqi-in-hanoi-2022-2025/*.csv`

## Quick Start

```bash
cd /vol/biomedic3/gn425/HaNoiAQI/dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
shiny run app.py --host 0.0.0.0 --port 8005
```

Then open `http://localhost:8005` in your browser.

## Offline Model Cache

For a faster demo, train and save the forecasting models before launching Shiny:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI/dashboard
.venv/bin/python scripts/train_models.py
.venv/bin/shiny run app.py --host 0.0.0.0 --port 8005
```

The script writes:

- `models/aqi_horizon_1h.joblib`
- `models/aqi_horizon_6h.joblib`
- `models/aqi_horizon_24h.joblib`

At runtime, the app loads these files first. If a model file is missing, Shiny trains that horizon once and saves it for future runs.

## Optional: Preprocess To Parquet

This step is optional for MVP but useful for final performance tuning:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI
python dashboard/scripts/preprocess.py
```

Outputs:

- `dashboard/processed/hanoi_city_hourly.parquet`
- `dashboard/processed/hanoi_district_daily.parquet`

## AQICN Token

The app tries token sources in this order:

1. `AQICN_TOKEN` environment variable.
2. Regex extraction from `../aqicn_api_key.md`.

If AQICN is unavailable, the app falls back to Open-Meteo for the selected coordinate.

## Files

- `app.py`: Shiny app UI + server logic orchestrator with navbar layout.
- `styles.css`: Complete dark theme and custom layout components.
- `modules/mod_overview.py`: Overview page UI and server.
- `modules/mod_district.py`: Districts page UI and server.
- `modules/mod_history.py`: History page UI and server.
- `modules/mod_forecast.py`: Forecast page UI and server.
- `src/data.py`: Data loading and normalization.
- `src/model.py`: Feature engineering + model training + inference.
- `src/realtime_api.py`: AQICN/Open-Meteo clients and station freshness logic.
- `src/utils.py`: AQI band definitions, color logic, and string formatting.
