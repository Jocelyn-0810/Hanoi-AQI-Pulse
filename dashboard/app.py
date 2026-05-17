"""Hanoi Air Quality Pulse v2 — main Shiny application.

Story-driven, dark-themed, no-sidebar architecture with four pages:
  Overview | Districts | History | Forecast
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shiny import App, reactive, render, ui

from modules.mod_overview import overview_ui, overview_server
from modules.mod_district import district_ui, district_server
from modules.mod_history import history_ui, history_server
from modules.mod_forecast import forecast_ui, forecast_server
from src.data import DataBundle, load_bundle
from src.model import ModelArtifacts, load_model_artifact, predict_next, save_model_artifact, train_city_model
from src.realtime_api import fetch_fresh_waqi_snapshot, fetch_open_meteo_snapshot, read_aqicn_token
from src.utils import aqi_category

# ── Paths & constants ─────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data"
MODEL_DIR = Path(__file__).resolve().parent / "models"
APP_DIR = Path(__file__).resolve().parent

HANOI_LAT = 21.0245
HANOI_LON = 105.8412

HORIZONS = {"1h": 1, "6h": 6, "24h": 24}

DISTRICT_CENTROIDS = {
    "Ba Dinh": (21.0368, 105.8342), "Ba Vi": (21.1990, 105.4230),
    "Bac Tu Liem": (21.0730, 105.7700), "Cau Giay": (21.0360, 105.7900),
    "Chuong My": (20.9230, 105.7010), "Dan Phuong": (21.0870, 105.6700),
    "Dong Anh": (21.1360, 105.8490), "Dong Da": (21.0180, 105.8290),
    "Gia Lam": (21.0270, 105.9590), "Ha Dong": (20.9710, 105.7780),
    "Hai Ba Trung": (21.0060, 105.8580), "Hoai Duc": (21.0320, 105.6900),
    "Hoan Kiem": (21.0285, 105.8542), "Hoang Mai": (20.9750, 105.8650),
    "Long Bien": (21.0440, 105.9000), "Me Linh": (21.1840, 105.7200),
    "My Duc": (20.7040, 105.7400), "Nam Tu Liem": (21.0160, 105.7700),
    "Phu Xuyen": (20.7300, 105.9100), "Phuc Tho": (21.1030, 105.5600),
    "Quoc Oai": (20.9900, 105.6400), "Soc Son": (21.2570, 105.8500),
    "Son Tay": (21.1400, 105.5050), "Tay Ho": (21.0680, 105.8200),
    "Thach That": (21.0300, 105.5400), "Thanh Oai": (20.8600, 105.7700),
    "Thanh Tri": (20.9400, 105.8500), "Thanh Xuan": (20.9950, 105.8090),
    "Thuong Tin": (20.8700, 105.8700), "Ung Hoa": (20.7200, 105.7800),
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def nearest_station(lat: float, lon: float, stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not stations:
        return None
    return min(stations, key=lambda s: (float(s["lat"]) - lat) ** 2 + (float(s["lon"]) - lon) ** 2)


def snapshot_overrides(snapshot: dict[str, Any] | None) -> dict[str, float]:
    if not isinstance(snapshot, dict):
        return {}
    mapping = {
        "aqi": "aqi", "pm25": "pm25", "pm10": "pm10", "co": "co",
        "no2": "no2", "o3": "o3", "so2": "so2", "temp": "temperature",
        "humidity": "relative_humidity", "pressure": "pressure",
        "wind": "wind_speed", "precipitation": "precipitation",
    }
    out: dict[str, float] = {}
    for src, dst in mapping.items():
        val = snapshot.get(src)
        if val is not None and not pd.isna(val):
            out[dst] = float(val)
    return out


# ── Load data at module level ─────────────────────────────────────────────────

bundle: DataBundle = load_bundle(DATA_ROOT)
CITY = bundle.city_hourly.copy()
DISTRICT = bundle.district_daily.copy()
TOKEN = read_aqicn_token(ROOT)


def historical_snapshot() -> dict[str, Any]:
    latest = CITY.dropna(subset=["aqi"]).tail(1)
    if latest.empty:
        return {
            "name": "Hanoi historical fallback",
            "source": "Historical",
            "aqi": np.nan,
            "lat": HANOI_LAT,
            "lon": HANOI_LON,
            "time_iso": "N/A",
        }
    row = latest.iloc[0]
    return {
        "name": "Hanoi historical fallback",
        "source": "Historical",
        "aqi": row.get("aqi", np.nan),
        "pm25": row.get("pm25", np.nan),
        "pm10": row.get("pm10", np.nan),
        "temp": row.get("temperature", np.nan),
        "humidity": row.get("relative_humidity", np.nan),
        "pressure": row.get("pressure", np.nan),
        "wind": row.get("wind_speed", np.nan),
        "lat": HANOI_LAT,
        "lon": HANOI_LON,
        "time_iso": str(row.get("local_time", "N/A")),
    }


# ── UI ─────────────────────────────────────────────────────────────────────────

app_ui = ui.page_navbar(
    ui.nav_panel("Overview", overview_ui("overview")),
    ui.nav_panel("Districts", district_ui("dist")),
    ui.nav_panel("History", history_ui("hist")),
    ui.nav_panel("Forecast", forecast_ui("forecast")),
    title=ui.div(
        ui.tags.span("🏙️", style="font-size:1.2rem;margin-right:6px;"),
        ui.tags.span("Hanoi AQI", style="font-weight:800;"),
        style="display:flex;align-items:center;",
    ),
    id="main_navbar",
    header=ui.tags.head(
        ui.tags.link(rel="stylesheet", href="styles.css"),
        ui.tags.meta(name="description", content="Interactive air quality dashboard for Hanoi, Vietnam — real-time AQI, district analysis, historical trends, and ML-powered forecasts."),
        ui.tags.title("Hanoi Air Quality Pulse"),
    ),
    fillable=True,
)


# ── Server ────────────────────────────────────────────────────────────────────

def server(input, output, session):
    station_cache: reactive.Value[list] = reactive.value([])
    snapshot_val: reactive.Value[dict] = reactive.value(historical_snapshot())
    model_cache: dict[tuple[int, str], ModelArtifacts] = {}
    refresh_state = {"started": False}

    # ── Model management ──────────────────────────────────────────────────

    def get_model(horizon: int, target_col: str = "aqi") -> ModelArtifacts | None:
        cache_key = (horizon, target_col)
        if cache_key in model_cache:
            return model_cache[cache_key]
        artifact = load_model_artifact(MODEL_DIR, horizon, target_col=target_col)
        if artifact is not None:
            model_cache[cache_key] = artifact
            return artifact
        try:
            model_cache[cache_key] = train_city_model(CITY, horizon_hours=horizon, target_col=target_col)
            save_model_artifact(model_cache[cache_key], MODEL_DIR)
            return model_cache[cache_key]
        except Exception:
            return None

    # ── Realtime refresh ─────────────────────────────────────────────────

    def refresh_realtime() -> None:
        source_payload: dict[str, Any] | None = None
        stations: list[dict[str, Any]] = []
        if TOKEN:
            try:
                stations = fetch_fresh_waqi_snapshot(TOKEN, keyword="hanoi")
                station_cache.set(stations)
                nearest = nearest_station(HANOI_LAT, HANOI_LON, stations)
                if nearest:
                    source_payload = nearest
            except Exception:
                station_cache.set([])
        if source_payload is None:
            try:
                source_payload = fetch_open_meteo_snapshot(lat=HANOI_LAT, lon=HANOI_LON)
            except Exception:
                source_payload = historical_snapshot()
        snapshot_val.set(source_payload)

    @reactive.effect
    def _poll_refresh():
        if not refresh_state["started"]:
            refresh_state["started"] = True
            reactive.invalidate_later(8)
            return
        refresh_realtime()
        reactive.invalidate_later(600)

    # ── Prediction context ───────────────────────────────────────────────

    def prediction_context(horizon: int = 6, target_col: str = "aqi") -> dict[str, Any]:
        model = get_model(horizon, target_col=target_col)
        df = CITY.copy()
        if df.empty or df[target_col].dropna().empty:
            return {"model": model, "pred": np.nan, "baseline": np.nan, "delta": np.nan}
        baseline = float(df[target_col].dropna().iloc[-1])
        pred = baseline
        snap = snapshot_val.get()
        if model is not None:
            pred = predict_next(df, model, overrides=snapshot_overrides(snap))
        return {
            "model": model, "pred": pred, "baseline": baseline,
            "delta": pred - baseline, "snapshot": snap,
        }

    # ── District map data ────────────────────────────────────────────────

    @reactive.calc
    def district_map_frame() -> pd.DataFrame:
        if DISTRICT.empty:
            return pd.DataFrame(columns=["district", "aqi_daily", "lat", "lon"])
        agg = DISTRICT.groupby("district", as_index=False)["aqi_daily"].mean().dropna()
        coords = pd.DataFrame([{"district": d, "lat": lat, "lon": lon} for d, (lat, lon) in DISTRICT_CENTROIDS.items()])
        return agg.merge(coords, on="district", how="inner")

    # ── Wire module servers ──────────────────────────────────────────────

    overview_server(
        "overview",
        city_hourly=CITY,
        station_cache=station_cache,
        snapshot=snapshot_val,
        district_map_frame=district_map_frame,
    )
    district_server(
        "dist",
        district_daily=DISTRICT,
    )
    history_server(
        "hist",
        city_hourly=CITY,
    )
    forecast_server(
        "forecast",
        prediction_context=prediction_context,
        get_model=get_model,
        snapshot=snapshot_val,
    )


app = App(app_ui, server, static_assets=APP_DIR)
