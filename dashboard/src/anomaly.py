"""Data-quality and anomaly helpers for Hanoi AQI time series.

The cleaning strategy is conservative:
- keep raw columns unchanged;
- flag unusual values with physical-range and rolling robust-z checks;
- only smooth physically invalid or isolated sensor-like spikes;
- keep multi-pollutant high episodes because they may be real pollution events.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


POLLUTANT_COLS = ["aqi", "pm25", "pm10", "co", "no2", "o3", "so2"]
WEATHER_COLS = ["temperature", "relative_humidity", "pressure", "wind_speed", "precipitation", "clouds", "uv_index"]
QUALITY_COLS = POLLUTANT_COLS + WEATHER_COLS

PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    "aqi": (0, 500),
    "pm25": (0, 500),
    "pm10": (0, 1200),
    "co": (0, 20000),
    "no2": (0, 500),
    "o3": (0, 800),
    "so2": (0, 800),
    "temperature": (0, 45),
    "relative_humidity": (0, 100),
    "pressure": (950, 1050),
    "wind_speed": (0, 40),
    "precipitation": (0, 300),
    "clouds": (0, 100),
    "uv_index": (0, 15),
}

MIN_SPIKE_DELTA: dict[str, float] = {
    "aqi": 45,
    "pm25": 35,
    "pm10": 60,
    "co": 900,
    "no2": 35,
    "o3": 60,
    "so2": 60,
}


@dataclass(frozen=True)
class QualitySummary:
    rows: int
    anomaly_rows: int
    sensor_like_rows: int
    episode_rows: int
    mode_note: str


def _rolling_mad(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    med = series.rolling(window, min_periods=min_periods).median()
    abs_dev = (series - med).abs()
    mad = abs_dev.rolling(window, min_periods=min_periods).median()
    return mad.replace(0, np.nan)


def _safe_clip(series: pd.Series, center: pd.Series, scale: pd.Series, threshold: float) -> pd.Series:
    q_low = float(series.quantile(0.01)) if series.notna().any() else 0.0
    q_high = float(series.quantile(0.99)) if series.notna().any() else 0.0
    lower = (center - threshold * scale).fillna(q_low)
    upper = (center + threshold * scale).fillna(q_high)
    clipped = series.clip(lower=lower, upper=upper)
    return clipped.interpolate(limit_direction="both").ffill().bfill()


def apply_city_quality_flags(
    df: pd.DataFrame,
    cols: Iterable[str] | None = None,
    *,
    window: int = 72,
    min_periods: int = 24,
    robust_threshold: float = 6.0,
    clean_threshold: float = 4.0,
) -> pd.DataFrame:
    """Return a copy with raw, cleaned, anomaly, and episode columns.

    Added per-metric columns:
    - ``{col}_raw``
    - ``{col}_clean``
    - ``{col}_robust_z``
    - ``{col}_is_anomaly``
    - ``{col}_is_sensor_like``

    Added row-level columns:
    - ``is_anomaly_any``
    - ``is_sensor_like_any``
    - ``is_extreme_episode``
    - ``anomaly_count``
    - ``sensor_like_count``
    """
    out = df.copy()
    active_cols = [c for c in (cols or QUALITY_COLS) if c in out.columns]
    if not active_cols:
        return out

    if "local_time" in out.columns:
        out = out.sort_values("local_time").reset_index(drop=True)

    candidate_flags: dict[str, pd.Series] = {}
    invalid_flags: dict[str, pd.Series] = {}
    medians: dict[str, pd.Series] = {}
    scales: dict[str, pd.Series] = {}

    for col in active_cols:
        raw = pd.to_numeric(out[col], errors="coerce")
        out[f"{col}_raw"] = raw

        lo, hi = PHYSICAL_RANGES.get(col, (-np.inf, np.inf))
        invalid = raw.notna() & ((raw < lo) | (raw > hi))
        median = raw.rolling(window, min_periods=min_periods).median()
        mad = _rolling_mad(raw, window, min_periods)
        scale = (1.4826 * mad).replace(0, np.nan)
        robust_z = ((raw - median).abs() / scale).replace([np.inf, -np.inf], np.nan)
        min_delta = MIN_SPIKE_DELTA.get(col, 0)
        candidate = invalid | ((robust_z > robust_threshold) & ((raw - median).abs() > min_delta))

        out[f"{col}_robust_z"] = robust_z.fillna(0.0)
        candidate_flags[col] = candidate.fillna(False)
        invalid_flags[col] = invalid.fillna(False)
        medians[col] = median
        scales[col] = scale

    pollutant_candidates = [candidate_flags[c] for c in POLLUTANT_COLS if c in candidate_flags]
    if pollutant_candidates:
        support_count = pd.concat(pollutant_candidates, axis=1).sum(axis=1)
    else:
        support_count = pd.Series(0, index=out.index)

    anomaly_frame = pd.concat(candidate_flags.values(), axis=1)
    invalid_frame = pd.concat(invalid_flags.values(), axis=1)
    out["anomaly_count"] = anomaly_frame.sum(axis=1).astype(int)
    out["physical_invalid_count"] = invalid_frame.sum(axis=1).astype(int)
    out["is_anomaly_any"] = out["anomaly_count"] > 0
    out["is_extreme_episode"] = support_count >= 2

    sensor_like_cols: list[pd.Series] = []
    for col in active_cols:
        candidate = candidate_flags[col]
        invalid = invalid_flags[col]
        sensor_like = candidate & (invalid | ~out["is_extreme_episode"])
        sensor_like_cols.append(sensor_like)
        out[f"{col}_is_anomaly"] = candidate.astype(bool)
        out[f"{col}_is_sensor_like"] = sensor_like.astype(bool)

        clean_source = pd.to_numeric(out[col], errors="coerce").copy()
        capped = _safe_clip(clean_source.mask(invalid), medians[col], scales[col], clean_threshold)
        out[f"{col}_clean"] = clean_source.mask(sensor_like, capped)
        out[f"{col}_clean"] = out[f"{col}_clean"].interpolate(limit_direction="both").ffill().bfill()

    sensor_frame = pd.concat(sensor_like_cols, axis=1)
    out["sensor_like_count"] = sensor_frame.sum(axis=1).astype(int)
    out["is_sensor_like_any"] = out["sensor_like_count"] > 0
    out["quality_label"] = np.select(
        [out["is_extreme_episode"], out["is_sensor_like_any"], out["is_anomaly_any"]],
        ["Extreme pollution episode", "Sensor-like anomaly", "Unusual value"],
        default="Normal",
    )
    return out


def metric_col_for_mode(df: pd.DataFrame, metric_col: str, data_mode: str = "raw") -> str:
    """Return the column to use for a metric under a data-quality mode."""
    clean_col = f"{metric_col}_clean"
    if data_mode == "cleaned" and clean_col in df.columns:
        return clean_col
    return metric_col


def quality_summary(df: pd.DataFrame) -> QualitySummary:
    rows = len(df)
    anomaly_rows = int(df.get("is_anomaly_any", pd.Series(False, index=df.index)).sum())
    sensor_rows = int(df.get("is_sensor_like_any", pd.Series(False, index=df.index)).sum())
    episode_rows = int(df.get("is_extreme_episode", pd.Series(False, index=df.index)).sum())
    return QualitySummary(
        rows=rows,
        anomaly_rows=anomaly_rows,
        sensor_like_rows=sensor_rows,
        episode_rows=episode_rows,
        mode_note=(
            "Raw keeps all original measurements. Cleaned only smooths physically invalid "
            "or isolated sensor-like spikes while retaining multi-pollutant pollution episodes."
        ),
    )
