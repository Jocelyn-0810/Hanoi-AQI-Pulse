"""Data loading — Parquet-first with CSV fallback.

DataBundle holds three DataFrames:
  city_hourly      — phungdinhdat city-level hourly (30k rows)
  district_daily   — hau100416 district-level daily, Hanoi only
  district_hourly  — hau100416 district-level hourly, Hanoi only (optional)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.utils import aqi_category


@dataclass
class DataBundle:
    city_hourly: pd.DataFrame
    district_daily: pd.DataFrame
    district_hourly: pd.DataFrame | None = None


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


# ── City hourly ─────────────────────────────────────────────────────────────

def load_city_hourly(data_root: Path, processed_root: Path | None = None) -> pd.DataFrame:
    # Try Parquet first
    if processed_root:
        parquet = processed_root / "hanoi_city_hourly.parquet"
        if parquet.exists():
            city = pd.read_parquet(parquet)
            city["local_time"] = pd.to_datetime(city["local_time"], errors="coerce")
            if "aqi_category" not in city.columns:
                city["aqi_category"] = city["aqi"].apply(aqi_category)
            return city

    # Fallback to CSV
    phung_dir = data_root / "phungdinhdat__aqi-in-hanoi-2022-2025"
    frames: list[pd.DataFrame] = []
    for year_csv in sorted(phung_dir.glob("*.csv")):
        df = pd.read_csv(year_csv)
        df = _normalize_columns(df)
        if "local_time" not in df.columns:
            continue
        df["local_time"] = pd.to_datetime(df["local_time"], errors="coerce")
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No city-level CSV files found in phungdinhdat dataset.")

    city = pd.concat(frames, ignore_index=True)
    city = city.dropna(subset=["local_time"]).sort_values("local_time")

    numeric_cols = [
        "aqi", "pm25", "pm10", "co", "no2", "o3", "so2",
        "clouds", "precipitation", "pressure", "relative_humidity",
        "temperature", "uv_index", "wind_speed",
    ]
    for col in numeric_cols:
        if col in city.columns:
            city[col] = pd.to_numeric(city[col], errors="coerce")

    city["aqi_category"] = city["aqi"].apply(aqi_category)
    city["hour"] = city["local_time"].dt.hour
    city["day_of_week"] = city["local_time"].dt.day_name()
    city["month"] = city["local_time"].dt.month
    city["date"] = city["local_time"].dt.date
    city["year_month"] = city["local_time"].dt.to_period("M").astype(str)
    return city


# ── District daily ──────────────────────────────────────────────────────────

def load_district_daily(data_root: Path, processed_root: Path | None = None) -> pd.DataFrame:
    # Try Parquet first
    if processed_root:
        parquet = processed_root / "hanoi_district_daily.parquet"
        if parquet.exists():
            daily = pd.read_parquet(parquet)
            daily["time"] = pd.to_datetime(daily["time"], errors="coerce")
            return daily

    # Fallback to CSV
    district_path = data_root / "hau100416__vietnamese-air-quality-dataset" / "aqi_northVN_daily.csv"
    daily = pd.read_csv(district_path)
    daily = _normalize_columns(daily)
    daily = daily[daily["city"].str.lower().eq("ha noi")].copy()
    daily["time"] = pd.to_datetime(daily["time"], errors="coerce")
    daily = daily.dropna(subset=["time"]).sort_values("time")

    metric_cols = [
        "aqi_daily", "aqi_pm2_5", "aqi_pm10",
        "aqi_sulphur_dioxide", "aqi_nitrogen_dioxide",
        "aqi_carbon_monoxide", "aqi_ozone",
    ]
    for col in metric_cols:
        if col in daily.columns:
            daily[col] = pd.to_numeric(daily[col], errors="coerce")

    daily["date"] = daily["time"].dt.date
    return daily


# ── District hourly (optional) ──────────────────────────────────────────────

def load_district_hourly(processed_root: Path | None = None) -> pd.DataFrame | None:
    """Load the pre-processed district hourly Parquet (created by preprocess.py)."""
    if processed_root is None:
        return None
    parquet = processed_root / "hanoi_district_hourly.parquet"
    if not parquet.exists():
        return None
    df = pd.read_parquet(parquet)
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    return df


# ── Bundle loader ───────────────────────────────────────────────────────────

def load_bundle(data_root: Path, processed_root: Path | None = None, include_district_hourly: bool = False) -> DataBundle:
    """Load all datasets. If processed_root is given, tries Parquet first."""
    # Auto-detect processed root if not given
    if processed_root is None:
        candidate = data_root.parent / "dashboard" / "processed"
        if candidate.exists() and any(candidate.glob("*.parquet")):
            processed_root = candidate

    return DataBundle(
        city_hourly=load_city_hourly(data_root, processed_root),
        district_daily=load_district_daily(data_root, processed_root),
        district_hourly=load_district_hourly(processed_root) if include_district_hourly else None,
    )
