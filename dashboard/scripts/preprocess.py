"""Preprocessing script — reads raw CSVs and writes compact Parquet files.

Outputs:
  processed/hanoi_city_hourly.parquet     — phungdinhdat city-level hourly
  processed/hanoi_district_daily.parquet  — hau100416 daily, Hanoi only
  processed/hanoi_district_hourly.parquet — hau100416 hourly, Hanoi only (from 1.27 GB CSV)
  processed/model_features.parquet        — pre-computed lag/rolling features for model training
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data"
OUT_ROOT = ROOT / "dashboard" / "processed"


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


# ── City hourly (phungdinhdat) ──────────────────────────────────────────────

def build_city_hourly() -> pd.DataFrame:
    phung = DATA_ROOT / "phungdinhdat__aqi-in-hanoi-2022-2025"
    frames = []
    for p in sorted(phung.glob("*.csv")):
        df = normalize_cols(pd.read_csv(p))
        df["local_time"] = pd.to_datetime(df["local_time"], errors="coerce")
        frames.append(df)
    city = pd.concat(frames, ignore_index=True).dropna(subset=["local_time"]).sort_values("local_time")

    numeric_cols = [
        "aqi", "pm25", "pm10", "co", "no2", "o3", "so2",
        "clouds", "precipitation", "pressure", "relative_humidity",
        "temperature", "uv_index", "wind_speed",
    ]
    for col in numeric_cols:
        if col in city.columns:
            city[col] = pd.to_numeric(city[col], errors="coerce")

    city["hour"] = city["local_time"].dt.hour
    city["day_of_week"] = city["local_time"].dt.day_name()
    city["month"] = city["local_time"].dt.month
    city["date"] = city["local_time"].dt.date
    city["year_month"] = city["local_time"].dt.to_period("M").astype(str)
    return city


# ── District daily (hau100416) ──────────────────────────────────────────────

def build_district_daily() -> pd.DataFrame:
    p = DATA_ROOT / "hau100416__vietnamese-air-quality-dataset" / "aqi_northVN_daily.csv"
    daily = normalize_cols(pd.read_csv(p))
    daily = daily[daily["city"].str.lower().eq("ha noi")].copy()
    daily["time"] = pd.to_datetime(daily["time"], errors="coerce")
    metric_cols = [
        "aqi_daily", "aqi_pm2_5", "aqi_pm10",
        "aqi_sulphur_dioxide", "aqi_nitrogen_dioxide",
        "aqi_carbon_monoxide", "aqi_ozone",
    ]
    for col in metric_cols:
        if col in daily.columns:
            daily[col] = pd.to_numeric(daily[col], errors="coerce")
    daily["date"] = daily["time"].dt.date
    return daily.dropna(subset=["time"]).sort_values("time")


# ── District hourly (hau100416 — large file, chunked read) ─────────────────

def build_district_hourly() -> pd.DataFrame:
    """Read the 1.27 GB northVN_dataAIR.csv in chunks, filter to Hanoi only."""
    p = DATA_ROOT / "hau100416__vietnamese-air-quality-dataset" / "northVN_dataAIR.csv"
    if not p.exists():
        print(f"[skip] {p} not found — skipping district hourly.")
        return pd.DataFrame()

    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(p, chunksize=100_000, low_memory=False):
        chunk = normalize_cols(chunk)
        if "city" in chunk.columns:
            hanoi = chunk[chunk["city"].str.lower().eq("ha noi")].copy()
            if not hanoi.empty:
                chunks.append(hanoi)

    if not chunks:
        print("[warn] No Hanoi rows found in northVN_dataAIR.csv")
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"]).sort_values("time")

    # Normalize column names that contain units like "pm10_(μg/m³)"
    rename_map = {}
    for c in df.columns:
        clean = c.split("(")[0].strip().replace(" ", "_")
        if clean != c:
            rename_map[c] = clean
    if rename_map:
        df = df.rename(columns=rename_map)

    # Coerce numeric columns
    numeric_candidates = [
        "pm10", "pm2_5", "carbon_monoxide", "carbon_dioxide",
        "nitrogen_dioxide", "sulphur_dioxide", "ozone",
        "aerosol_optical_depth", "dust", "uv_index", "uv_index_clear_sky",
        "nowcast_pm10", "aqi_pm10", "nowcast_pm2_5", "aqi_pm2_5",
        "aqi_carbon_monoxide", "aqi_nitrogen_dioxide",
        "aqi_sulphur_dioxide", "aqi_ozone", "aqi_h",
    ]
    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["hour"] = df["time"].dt.hour
    df["date"] = df["time"].dt.date
    print(f"[ok] district hourly: {len(df)} rows, {df['district'].nunique()} districts")
    return df


# ── Model features (pre-computed lags/rolling for city data) ────────────────

def build_model_features(city: pd.DataFrame) -> pd.DataFrame:
    """Pre-compute lag and rolling features to speed up model training."""
    df = city.sort_values("local_time").copy()

    feature_base = [
        "aqi", "pm25", "pm10", "co", "no2", "o3", "so2",
        "clouds", "precipitation", "pressure", "relative_humidity",
        "temperature", "uv_index", "wind_speed",
    ]
    for col in feature_base:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Time features
    df["hour"] = df["local_time"].dt.hour
    df["dow"] = df["local_time"].dt.dayofweek
    df["month"] = df["local_time"].dt.month
    df["is_weekend"] = (df["dow"] >= 5).astype(int)

    # Lag and rolling
    for c in ["aqi", "pm25"]:
        if c not in df.columns:
            continue
        for lag in [1, 6, 24]:
            df[f"{c}_lag_{lag}"] = df[c].shift(lag)
        for w in [3, 6, 24]:
            df[f"{c}_roll_mean_{w}"] = df[c].rolling(w).mean()
            df[f"{c}_roll_max_{w}"] = df[c].rolling(w).max()

    return df


# ── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    print("Building city hourly...")
    city = build_city_hourly()
    city_path = OUT_ROOT / "hanoi_city_hourly.parquet"
    city.to_parquet(city_path, index=False)
    print(f"[ok] wrote {city_path} ({len(city)} rows)")

    print("Building district daily...")
    district_daily = build_district_daily()
    district_path = OUT_ROOT / "hanoi_district_daily.parquet"
    district_daily.to_parquet(district_path, index=False)
    print(f"[ok] wrote {district_path} ({len(district_daily)} rows)")

    print("Building district hourly (this may take a few minutes)...")
    district_hourly = build_district_hourly()
    if not district_hourly.empty:
        hourly_path = OUT_ROOT / "hanoi_district_hourly.parquet"
        district_hourly.to_parquet(hourly_path, index=False)
        print(f"[ok] wrote {hourly_path} ({len(district_hourly)} rows)")

    print("Building model features...")
    features = build_model_features(city)
    feat_path = OUT_ROOT / "model_features.parquet"
    features.to_parquet(feat_path, index=False)
    print(f"[ok] wrote {feat_path} ({len(features)} rows)")

    print("\nDone! All Parquet files written to:", OUT_ROOT)


if __name__ == "__main__":
    main()
