"""Download Vietnam ADM2 GeoJSON from geoBoundaries, filter to Hanoi districts,
and save a compact hanoi_districts.geojson with a name-matching table.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "data" / "hanoi_districts.geojson"

# geoBoundaries API endpoint for Vietnam ADM2
GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/VNM/ADM2/"

# HDX fallback (direct GeoJSON download)
HDX_FALLBACK = "https://data.humdata.org/dataset/5a4ddee0-2316-4cc0-8437-548134d43a65/resource/e8d8e05c-8867-43b4-9b9a-99752a48e2a7/download/vnm_adm_gov_20201027.geojson"

# Mapping from dataset district names (ASCII) to typical GeoJSON Vietnamese names
# This handles diacritics and the "Quận"/"Huyện"/"Thị xã" prefixes
NAME_MAP = {
    "Ba Dinh": ["Ba Đình", "Quận Ba Đình", "ba dinh", "ba đình"],
    "Ba Vi": ["Ba Vì", "Huyện Ba Vì", "ba vi", "ba vì"],
    "Bac Tu Liem": ["Bắc Từ Liêm", "Quận Bắc Từ Liêm", "bac tu liem", "bắc từ liêm"],
    "Cau Giay": ["Cầu Giấy", "Quận Cầu Giấy", "cau giay", "cầu giấy"],
    "Chuong My": ["Chương Mỹ", "Huyện Chương Mỹ", "chuong my", "chương mỹ"],
    "Dan Phuong": ["Đan Phượng", "Huyện Đan Phượng", "dan phuong", "đan phượng"],
    "Dong Anh": ["Đông Anh", "Huyện Đông Anh", "dong anh", "đông anh"],
    "Dong Da": ["Đống Đa", "Quận Đống Đa", "dong da", "đống đa"],
    "Gia Lam": ["Gia Lâm", "Huyện Gia Lâm", "gia lam", "gia lâm"],
    "Ha Dong": ["Hà Đông", "Quận Hà Đông", "ha dong", "hà đông"],
    "Hai Ba Trung": ["Hai Bà Trưng", "Quận Hai Bà Trưng", "hai ba trung", "hai bà trưng"],
    "Hoai Duc": ["Hoài Đức", "Huyện Hoài Đức", "hoai duc", "hoài đức"],
    "Hoan Kiem": ["Hoàn Kiếm", "Quận Hoàn Kiếm", "hoan kiem", "hoàn kiếm"],
    "Hoang Mai": ["Hoàng Mai", "Quận Hoàng Mai", "hoang mai", "hoàng mai"],
    "Long Bien": ["Long Biên", "Quận Long Biên", "long bien", "long biên"],
    "Me Linh": ["Mê Linh", "Huyện Mê Linh", "me linh", "mê linh"],
    "My Duc": ["Mỹ Đức", "Huyện Mỹ Đức", "my duc", "mỹ đức"],
    "Nam Tu Liem": ["Nam Từ Liêm", "Quận Nam Từ Liêm", "nam tu liem", "nam từ liêm"],
    "Phu Xuyen": ["Phú Xuyên", "Huyện Phú Xuyên", "phu xuyen", "phú xuyên"],
    "Phuc Tho": ["Phúc Thọ", "Huyện Phúc Thọ", "phuc tho", "phúc thọ"],
    "Quoc Oai": ["Quốc Oai", "Huyện Quốc Oai", "quoc oai", "quốc oai"],
    "Soc Son": ["Sóc Sơn", "Huyện Sóc Sơn", "soc son", "sóc sơn"],
    "Son Tay": ["Sơn Tây", "Thị xã Sơn Tây", "son tay", "sơn tây"],
    "Tay Ho": ["Tây Hồ", "Quận Tây Hồ", "tay ho", "tây hồ"],
    "Thach That": ["Thạch Thất", "Huyện Thạch Thất", "thach that", "thạch thất"],
    "Thanh Oai": ["Thanh Oai", "Huyện Thanh Oai", "thanh oai"],
    "Thanh Tri": ["Thanh Trì", "Huyện Thanh Trì", "thanh tri", "thanh trì"],
    "Thanh Xuan": ["Thanh Xuân", "Quận Thanh Xuân", "thanh xuan", "thanh xuân"],
    "Thuong Tin": ["Thường Tín", "Huyện Thường Tín", "thuong tin", "thường tín"],
    "Ung Hoa": ["Ứng Hòa", "Huyện Ứng Hòa", "ung hoa", "ứng hòa"],
}

# Build reverse lookup: lowercase Vietnamese → ASCII dataset name
_REVERSE_MAP: dict[str, str] = {}
for ascii_name, variants in NAME_MAP.items():
    for v in variants:
        _REVERSE_MAP[v.lower()] = ascii_name
    _REVERSE_MAP[ascii_name.lower()] = ascii_name


def _strip_prefix(name: str) -> str:
    """Remove Vietnamese administrative prefixes."""
    prefixes = ["Quận ", "Huyện ", "Thị xã ", "Thành phố "]
    for p in prefixes:
        if name.startswith(p):
            return name[len(p):]
    return name


def _match_district(geojson_name: str) -> str | None:
    """Try to match a GeoJSON district name to our ASCII dataset name."""
    low = geojson_name.strip().lower()
    if low in _REVERSE_MAP:
        return _REVERSE_MAP[low]
    stripped = _strip_prefix(geojson_name.strip()).lower()
    if stripped in _REVERSE_MAP:
        return _REVERSE_MAP[stripped]
    return None


def fetch_geojson() -> dict:
    """Try geoBoundaries API first, then HDX fallback."""
    # Try geoBoundaries API
    try:
        api_resp = requests.get(GEOBOUNDARIES_API, timeout=30)
        api_resp.raise_for_status()
        api_data = api_resp.json()
        gjson_url = api_data.get("gjDownloadURL") or api_data.get("simplifiedGeometryGeoJSON")
        if gjson_url:
            print(f"Downloading from geoBoundaries: {gjson_url}")
            data_resp = requests.get(gjson_url, timeout=60)
            data_resp.raise_for_status()
            return data_resp.json()
    except Exception as e:
        print(f"geoBoundaries failed: {e}, trying HDX fallback...")

    # HDX fallback
    resp = requests.get(HDX_FALLBACK, timeout=60)
    resp.raise_for_status()
    return resp.json()


def filter_hanoi(geojson: dict) -> dict:
    """Filter GeoJSON features to Hanoi districts only."""
    hanoi_features = []
    matched = set()
    unmatched = []

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        # Try common field names for district name
        name = None
        for field in ["shapeName", "NAME_2", "ADM2_EN", "ADM2_VI", "name", "NAME"]:
            if field in props and props[field]:
                name = str(props[field])
                break
        if name is None:
            continue

        # Check if parent is Hanoi
        parent = None
        for field in ["shapeGroup", "NAME_1", "ADM1_EN", "ADM1_VI"]:
            if field in props and props[field]:
                parent = str(props[field])
                break

        is_hanoi = False
        if parent:
            parent_low = parent.lower()
            if any(kw in parent_low for kw in ["ha noi", "hà nội", "hanoi"]):
                is_hanoi = True

        if not is_hanoi:
            continue

        ascii_name = _match_district(name)
        if ascii_name:
            # Add our ASCII name as a property for easy joining
            feature["properties"]["district_ascii"] = ascii_name
            hanoi_features.append(feature)
            matched.add(ascii_name)
        else:
            unmatched.append(name)

    print(f"Matched {len(matched)}/30 districts")
    if unmatched:
        print(f"Unmatched GeoJSON names: {unmatched}")
    missing = set(NAME_MAP.keys()) - matched
    if missing:
        print(f"Missing districts: {missing}")

    return {
        "type": "FeatureCollection",
        "features": hanoi_features,
    }


def main() -> None:
    print("Fetching Vietnam ADM2 GeoJSON...")
    geojson = fetch_geojson()
    print(f"Total features in source: {len(geojson.get('features', []))}")

    print("Filtering to Hanoi districts...")
    hanoi = filter_hanoi(geojson)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(hanoi, f, ensure_ascii=False)
    print(f"[ok] wrote {OUT_PATH} ({len(hanoi['features'])} features)")


if __name__ == "__main__":
    main()
