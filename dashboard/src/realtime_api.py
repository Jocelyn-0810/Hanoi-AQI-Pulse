from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


WAQI_BASE = "https://api.waqi.info"
OPEN_METEO_AQ = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_WX = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 4


def read_aqicn_token(project_root: Path) -> str | None:
    env = os.getenv("AQICN_TOKEN")
    if env:
        return env

    key_file = project_root / "aqicn_api_key.md"
    if not key_file.exists():
        return None
    text = key_file.read_text(encoding="utf-8", errors="replace")

    match = re.search(r"token=([A-Za-z0-9._-]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    candidates = re.findall(r"\b[A-Za-z0-9]{24,}\b", text)
    return candidates[0] if candidates else None


def _parse_station_time(time_payload: dict[str, Any]) -> datetime | None:
    if not time_payload:
        return None
    iso = time_payload.get("iso")
    if iso:
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return None
    s = time_payload.get("s")
    if s:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=7)))
        except ValueError:
            return None
    return None


def _is_fresh_station(station_time: datetime | None, max_age_hours: int = 48) -> bool:
    if station_time is None:
        return False
    now = datetime.now(station_time.tzinfo or timezone.utc)
    age = now - station_time
    return age <= timedelta(hours=max_age_hours)


def fetch_waqi_stations(token: str, keyword: str = "hanoi") -> list[dict[str, Any]]:
    url = f"{WAQI_BASE}/search/"
    resp = requests.get(url, params={"keyword": keyword, "token": token}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "ok":
        return []

    stations: list[dict[str, Any]] = []
    for item in payload.get("data", []):
        uid = item.get("uid")
        station = item.get("station", {})
        geo = station.get("geo")
        if not uid or not geo or len(geo) != 2:
            continue
        stations.append(
            {
                "uid": int(uid),
                "name": station.get("name", f"station-{uid}"),
                "lat": float(geo[0]),
                "lon": float(geo[1]),
                "aqi_search": item.get("aqi"),
            }
        )
    return stations


def fetch_waqi_station_detail(token: str, uid: int) -> dict[str, Any] | None:
    url = f"{WAQI_BASE}/feed/@{uid}/"
    resp = requests.get(url, params={"token": token}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "ok":
        return None
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None
    return data


def _station_snapshot_from_detail(token: str, st: dict[str, Any]) -> dict[str, Any] | None:
    detail = fetch_waqi_station_detail(token, st["uid"])
    if not detail:
        return None
    aqi = detail.get("aqi")
    if isinstance(aqi, str) and not aqi.isdigit():
        return None
    try:
        aqi_val = float(aqi)
    except (TypeError, ValueError):
        return None

    st_time = _parse_station_time(detail.get("time", {}))
    if not _is_fresh_station(st_time, max_age_hours=48):
        return None

    iaqi = detail.get("iaqi", {})
    return {
        "uid": st["uid"],
        "name": detail.get("city", {}).get("name", st["name"]),
        "lat": detail.get("city", {}).get("geo", [st["lat"], st["lon"]])[0],
        "lon": detail.get("city", {}).get("geo", [st["lat"], st["lon"]])[1],
        "aqi": aqi_val,
        "dominant": detail.get("dominentpol"),
        "time_iso": detail.get("time", {}).get("iso"),
        "pm25": (iaqi.get("pm25") or {}).get("v"),
        "pm10": (iaqi.get("pm10") or {}).get("v"),
        "o3": (iaqi.get("o3") or {}).get("v"),
        "no2": (iaqi.get("no2") or {}).get("v"),
        "so2": (iaqi.get("so2") or {}).get("v"),
        "co": (iaqi.get("co") or {}).get("v"),
        "temp": (iaqi.get("t") or {}).get("v"),
        "humidity": (iaqi.get("h") or {}).get("v"),
        "pressure": (iaqi.get("p") or {}).get("v"),
        "wind": (iaqi.get("w") or {}).get("v"),
        "source": "AQICN",
    }


def fetch_fresh_waqi_snapshot(token: str, keyword: str = "hanoi", max_details: int = 8) -> list[dict[str, Any]]:
    stations = fetch_waqi_stations(token, keyword=keyword)
    out: list[dict[str, Any]] = []

    selected = stations[:max_details]
    if not selected:
        return out

    with ThreadPoolExecutor(max_workers=min(6, len(selected))) as executor:
        futures = [executor.submit(_station_snapshot_from_detail, token, st) for st in selected]
        for future in as_completed(futures):
            try:
                item = future.result()
            except Exception:
                item = None
            if item is not None:
                out.append(item)
    return out


def fetch_open_meteo_snapshot(lat: float, lon: float) -> dict[str, Any]:
    aq_params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(
            [
                "us_aqi",
                "pm2_5",
                "pm10",
                "nitrogen_dioxide",
                "sulphur_dioxide",
                "ozone",
                "carbon_monoxide",
            ]
        ),
        "forecast_days": 2,
        "timezone": "Asia/Bangkok",
    }
    wx_params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "pressure_msl",
                "wind_speed_10m",
            ]
        ),
        "forecast_days": 2,
        "timezone": "Asia/Bangkok",
    }

    aq = requests.get(OPEN_METEO_AQ, params=aq_params, timeout=REQUEST_TIMEOUT)
    wx = requests.get(OPEN_METEO_WX, params=wx_params, timeout=REQUEST_TIMEOUT)
    aq.raise_for_status()
    wx.raise_for_status()
    aq_data = aq.json().get("current", {})
    wx_data = wx.json().get("current", {})

    return {
        "name": f"Coordinate ({lat:.4f}, {lon:.4f})",
        "lat": lat,
        "lon": lon,
        "aqi": aq_data.get("us_aqi"),
        "pm25": aq_data.get("pm2_5"),
        "pm10": aq_data.get("pm10"),
        "o3": aq_data.get("ozone"),
        "no2": aq_data.get("nitrogen_dioxide"),
        "so2": aq_data.get("sulphur_dioxide"),
        "co": aq_data.get("carbon_monoxide"),
        "temp": wx_data.get("temperature_2m"),
        "humidity": wx_data.get("relative_humidity_2m"),
        "pressure": wx_data.get("pressure_msl"),
        "wind": wx_data.get("wind_speed_10m"),
        "precipitation": wx_data.get("precipitation"),
        "time_iso": aq_data.get("time"),
        "source": "Open-Meteo",
    }


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, default=str)
