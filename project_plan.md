# Hanoi Air Quality Pulse - Proposal and Final Product Plan

## 1. One-Sentence Project Idea

**Hanoi Air Quality Pulse** is an interactive Python Shiny dashboard that helps users explore Hanoi air pollution across time, districts, pollutants, weather conditions, realtime stations, and short-term AQI/PM2.5 forecasts.

Main question:

**How does air pollution vary across Hanoi districts and time, and can recent air/weather signals help predict short-term AQI risk?**

## 2. Proposal Status for 18/05

For the proposal, we are not submitting only a sketch. We already have a working dashboard prototype that can be used as a high-fidelity wireframe.

Current dashboard tabs:

1. **Overview**
   - Realtime/historical AQI hero.
   - AQI category and weather summary.
   - Day vs night AQI chart.
   - Realtime station map.
   - Lexce mascot AQI buddy whose visual mood changes with AQI risk.
   - District snapshot mini-cards.

2. **Districts**
   - Hanoi choropleth map for 30 districts.
   - Multi-select district checkbox picker with Select all / Clear.
   - Selected districts stay colored by AQI; unselected districts become dark/muted.
   - Ranking table only shows selected districts and can scroll.
   - Monthly trend supports many districts with softer lines and highlighted high-AQI districts.
   - Pollutant breakdown for selected districts.

3. **History**
   - Calendar-style AQI/PM2.5/PM10 heatmap.
   - Multi-year comparison.
   - AQI category distribution and annual/seasonal patterns.

4. **Forecast**
   - Forecast horizon controls: 1h, 6h, 24h.
   - Target controls: AQI or PM2.5.
   - Predicted risk card and gauge.
   - Model vs no-change baseline error comparison.
   - Feature importance.
   - Validation chart: predictions vs actual values.

This is enough for the proposal demo and wireframe requirement. The final version will improve deployment, UI polish, model interpretation, and report-level findings.

## 3. Active Datasets

Only these datasets are part of the current implementation.

### Dataset A - Hanoi District Air Quality

Source:
`hau100416/vietnamese-air-quality-dataset`

Local path:
`/vol/biomedic3/gn425/HaNoiAQI/data/hau100416__vietnamese-air-quality-dataset`

Files:
- `aqi_northVN_daily.csv`
- `northVN_dataAIR.csv`

Use in dashboard:
- District choropleth map.
- District ranking table.
- District monthly trend.
- Pollutant breakdown by selected districts.
- Overview district cards.

Audited facts:
- Hanoi district coverage: 30 districts.
- Hourly Hanoi subset: 920,160 rows.
- District daily processed output: `dashboard/processed/hanoi_district_daily.parquet`.
- District hourly processed output: `dashboard/processed/hanoi_district_hourly.parquet`.
- Time range in hourly data: 2022-08-04 to 2026-02-01.

### Dataset B - City-Level AQI + Weather for Modeling

Source:
`phungdinhdat/aqi-in-hanoi-2022-2025`

Local path:
`/vol/biomedic3/gn425/HaNoiAQI/data/phungdinhdat__aqi-in-hanoi-2022-2025`

Files:
- `2022.csv`
- `2023.csv`
- `2024.csv`
- `2025.csv`

Use in dashboard:
- Overview AQI/weather hero.
- Day/night chart.
- History page.
- Forecast model training.

Audited facts:
- 30,341 hourly rows.
- Time range: 2022-01-13 to 2025-06-30.
- Fields include AQI, PM2.5, PM10, CO, NO2, O3, SO2, clouds, precipitation, pressure, humidity, temperature, UV index, and wind speed.

### Spatial Boundary Data

Local path:
`/vol/biomedic3/gn425/HaNoiAQI/data/hanoi_districts.geojson`

Use:
- District choropleth boundaries.
- Name-matched to the 30 district names used in the air-quality dataset.

### Realtime APIs

1. **AQICN/WAQI**
   - Primary realtime station source.
   - Reads token from `AQICN_TOKEN` or `aqicn_api_key.md`.
   - The app filters stale/missing station data where possible.

2. **Open-Meteo**
   - Fallback for coordinate-based weather/air context when AQICN is unavailable.

## 4. Current Technical Stack

- Python Shiny for the dashboard.
- Plotly for interactive charts/maps.
- Pandas and NumPy for preprocessing and aggregation.
- Scikit-learn for forecasting models.
- Joblib for offline model caching.
- GeoJSON district boundaries for spatial visualization.
- Custom CSS for dark UI, glass panels, AQI colors, animations, and responsive layout.

Run command:

```bash
cd /vol/biomedic3/gn425/HaNoiAQI/dashboard
.venv/bin/shiny run app.py
```

## 5. Forecasting Method

Training data:
- City-level AQI + weather dataset from 2022 to 2025.

Targets:
- Primary: AQI.
- Secondary: PM2.5.

Forecast horizons:
- 1 hour.
- 6 hours.
- 24 hours.

Features:
- Current pollutants: AQI, PM2.5, PM10, CO, NO2, O3, SO2.
- Weather: temperature, humidity, pressure, precipitation, clouds, wind speed, UV index.
- Time features: hour, day of week, month, weekend flag.
- Lag features: 1h, 6h, 24h.
- Rolling features: 3h, 6h, 24h mean/max.

Models:
- Histogram Gradient Boosting variants.
- Model selection based on chronological validation MAE.
- Baseline: persistence/no-change forecast.

Current model cache:
- `dashboard/models/aqi_horizon_1h.joblib`
- `dashboard/models/aqi_horizon_6h.joblib`
- `dashboard/models/aqi_horizon_24h.joblib`
- `dashboard/models/pm25_horizon_1h.joblib`
- `dashboard/models/pm25_horizon_6h.joblib`
- `dashboard/models/pm25_horizon_24h.joblib`

Important framing for presentation:
- This is a short-term risk forecast, not a perfect sensor simulator.
- The model is explained visually using error comparison, feature importance, and validation plots.

## 6. Wireframe Sketch Plan

Because the dashboard already runs, the wireframe can be a PowerPoint/draw.io layout based on screenshots. Annotate each screenshot with arrows and short labels.

Recommended screenshots:

1. **Overview full page**
   - Annotate: realtime AQI card, weather card, AQI scale, day/night chart, station map, Lexce mascot.
   - Interaction notes: realtime source updates AQI/weather; station map shows live AQICN stations; Lexce changes mood by AQI risk.

2. **Districts tab**
   - Annotate: district checkbox picker, choropleth map, muted unselected districts, selected-district ranking table.
   - Interaction notes: Select all/Clear; ticking districts updates map, ranking, monthly trend, pollutant breakdown.

3. **History tab**
   - Annotate: pollutant/year controls, calendar heatmap, multi-year comparison, category distribution.
   - Interaction notes: changing pollutant/year changes all historical charts.

4. **Forecast tab**
   - Annotate: horizon/target controls, prediction card, gauge, model-vs-baseline error chart, feature importance, validation plot.
   - Interaction notes: horizon/target controls change model output and diagnostics.

## 7. Five-Minute Proposal Story

Suggested flow:

1. **Motivation**
   - Hanoi AQI is not only a single number. It changes by district, hour, season, pollutant, and weather.

2. **Data**
   - Explain district dataset, city weather/AQI dataset, GeoJSON, and realtime APIs.

3. **Dashboard**
   - Overview gives public-facing AQI context.
   - Districts reveals spatial inequality and local hotspots.
   - History reveals temporal rhythm.
   - Forecast turns the dashboard into visual analytics, not just reporting.

4. **Technical approach**
   - Python Shiny + Plotly + Pandas + scikit-learn.
   - Preprocessed Parquet for speed.
   - Offline model cache for reliable demo.

5. **Future work**
   - Improve final UI background and screenshots.
   - Add richer model explanation and final findings.
   - Deploy to shinyapps.io.
   - Prepare final report and live demo.

## 8. Phase 2 Plan After Proposal

### UI/UX Polish

- Replace or improve the Hanoi background image with a wide 21:9 scene.
- Improve mobile layout and visual consistency.
- Add clearer loading states and source badges.
- Refine Lexce mascot messages.

### Data and Model Work

- Validate AQICN station freshness rules.
- Improve feature names and explanation.
- Add stronger model comparison if time allows.
- Export model metrics for final report.

### Final Deliverables

- Deploy Shiny app.
- Final report up to 6 pages in LaTeX.
- Final presentation with live demo.
- Clean GitHub documentation and reproducible setup.

## 9. Suggested Team Task Allocation

Replace names with actual team members.

- **Member 1: Data + preprocessing**
  - Dataset documentation, Parquet preprocessing, GeoJSON name matching, data limitations.

- **Member 2: Dashboard UI + wireframe**
  - Slide design, screenshots, annotated wireframe, visual consistency.

- **Member 3: Visualization + storytelling**
  - Explain each tab, interaction flow, chart purpose, proposal presentation.

- **Member 4: Model/API + technical explanation**
  - AQICN/Open-Meteo logic, forecasting method, model metrics, forecast slide.

## 10. Risks and Limitations

- Realtime AQICN stations can be stale or missing, so the app needs fallback behavior.
- District-level sensor data may be uneven across time and districts.
- City-level forecasting is stronger than district-level forecasting at this stage.
- The proposal dashboard is already functional, but final insights and deployment still need refinement.
