# Proposal Write-up

## Title

**Hanoi Air Quality Pulse: Interactive Spatial, Temporal, and Predictive Visualization of Urban Pollution**

## Write-up

This project builds an interactive Python Shiny dashboard for exploring Hanoi air pollution as a spatial, temporal, and predictive problem. Our central question is: **How does air pollution vary across Hanoi districts and time, and can recent air-quality and weather signals support short-term AQI risk prediction?**

The motivation is practical and public-facing. Hanoi's air quality is often summarized as one citywide AQI value, but that hides important differences across districts, hours, seasons, pollutants, and weather conditions. A static chart can show that pollution is high, but it cannot let users ask follow-up questions such as: Which districts are worse? Does AQI behave differently at night? Which weather variables are associated with pollution spikes? What might happen in the next few hours?

Our dashboard uses two main historical datasets. First, the Kaggle Vietnamese air quality dataset provides Hanoi district-level air pollution data. Our local processed data covers 30 Hanoi districts, with the hourly subset containing 920,160 rows from 2022-08-04 to 2026-02-01, including PM2.5, PM10, NO2, SO2, O3, AQI components, and AQI. This dataset drives the district choropleth map, district ranking table, selected-district monthly trends, and pollutant breakdowns. Second, the Kaggle `aqi-in-hanoi-2022-2025` dataset provides 30,341 hourly city-level records from 2022-01-13 to 2025-06-30, combining AQI, pollutant levels, and weather variables such as temperature, humidity, pressure, precipitation, wind speed, cloud cover, and UV index. This supports historical analysis and short-term forecasting. We also use Hanoi district GeoJSON boundaries, AQICN/WAQI realtime station data, and Open-Meteo as a fallback weather/air source.

The visualization challenge is non-trivial because the data is multi-scale and multi-dimensional: hourly and daily time, 30 districts, multiple pollutants, weather drivers, AQI categories, realtime station freshness, and model predictions. Our proposed dashboard addresses this with four linked pages: an Overview page for current AQI context, a Districts page for spatial comparison, a History page for temporal patterns, and a Forecast page for predictive visual analytics. Interactions include district multi-select filtering, Select all/Clear controls, choropleth highlighting, muted unselected districts, tooltips, pollutant/year controls, forecast horizon controls, and model diagnostics. For forecasting, we train cached scikit-learn Histogram Gradient Boosting models for AQI and PM2.5 at 1h, 6h, and 24h horizons, using pollutant, weather, time, lag, and rolling-window features, then compare them against a no-change baseline.
