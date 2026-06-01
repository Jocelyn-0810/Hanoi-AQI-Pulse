"""Tests for anomaly-aware quality flags."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from src.anomaly import apply_city_quality_flags, metric_col_for_mode, quality_summary
from src.data import load_bundle

PROJECT_ROOT = DASHBOARD_ROOT.parent
DATA_ROOT = PROJECT_ROOT / "data"


def test_apply_city_quality_flags_adds_clean_columns():
    df = pd.DataFrame(
        {
            "local_time": pd.date_range("2025-01-01", periods=80, freq="h"),
            "aqi": [80.0] * 79 + [500.0],
            "pm25": [35.0] * 80,
            "pm10": [45.0] * 80,
            "co": [100.0] * 80,
            "temperature": [25.0] * 80,
            "relative_humidity": [80.0] * 80,
            "pressure": [1010.0] * 80,
        }
    )
    out = apply_city_quality_flags(df, cols=["aqi", "pm25", "pm10", "co", "temperature", "relative_humidity", "pressure"])
    assert "aqi_raw" in out.columns
    assert "aqi_clean" in out.columns
    assert "aqi_is_anomaly" in out.columns
    assert out["is_anomaly_any"].dtype == bool


def test_metric_col_for_mode_prefers_cleaned_when_available():
    df = pd.DataFrame({"aqi": [1], "aqi_clean": [2]})
    assert metric_col_for_mode(df, "aqi", "raw") == "aqi"
    assert metric_col_for_mode(df, "aqi", "cleaned") == "aqi_clean"


def test_loaded_city_has_quality_summary():
    bundle = load_bundle(DATA_ROOT)
    city = bundle.city_hourly
    assert "is_anomaly_any" in city.columns
    assert "aqi_clean" in city.columns
    summary = quality_summary(city)
    assert summary.rows == len(city)
    assert summary.anomaly_rows >= 0
