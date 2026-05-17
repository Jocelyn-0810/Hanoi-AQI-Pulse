# Walkthrough — UX Overhaul v2

## Summary

Transformed the Hanoi Air Quality Pulse from a technical sidebar+tabs layout into a **story-driven, dark-themed, 4-page dashboard** inspired by IQAir, aqi.in, and Penguin Explorer.

## What Changed

### Architecture
- **Before**: `page_sidebar` with 7+ global controls + 4 generic tabs
- **After**: `page_navbar` with 4 self-contained pages, each owning its controls

### Files Modified

| File | Action | Lines |
|---|---|---|
| [app.py](file:///vol/biomedic3/gn425/HaNoiAQI/dashboard/app.py) | REWRITE | ~180 → clean orchestrator, no sidebar |
| [styles.css](file:///vol/biomedic3/gn425/HaNoiAQI/dashboard/styles.css) | REWRITE | ~390 → full dark theme |
| [mod_overview.py](file:///vol/biomedic3/gn425/HaNoiAQI/dashboard/modules/mod_overview.py) | NEW | ~230 → hero + day/night + district cards |
| [mod_district.py](file:///vol/biomedic3/gn425/HaNoiAQI/dashboard/modules/mod_district.py) | REWRITE | ~330 → ranking table + choropleth |
| [mod_history.py](file:///vol/biomedic3/gn425/HaNoiAQI/dashboard/modules/mod_history.py) | NEW | ~280 → calendar + multi-year + category matrix |
| [mod_forecast.py](file:///vol/biomedic3/gn425/HaNoiAQI/dashboard/modules/mod_forecast.py) | NEW | ~300 → prediction hero + model transparency |
| mod_live_forecast.py | DELETED | Replaced by overview + forecast |
| mod_historical.py | DELETED | Replaced by history |
| mod_model_evidence.py | DELETED | Merged into forecast |
| hanoi_skyline.png | ADDED | Hero background image |

### Design Patterns Implemented

| # | Pattern | Status |
|---|---|---|
| R1 | "WHAT THIS SHOWS" narrative callouts | ✅ Every chart |
| R2 | Guided page-by-page exploration | ✅ 4 pages |
| R3 | Hero card (AQI + weather + scale bar + skyline) | ✅ Overview |
| R4 | District mini-cards | ✅ Overview |
| R5 | Ranking table with monthly color-coded heatmap | ✅ Districts |
| R6 | Calendar heatmap (GitHub-style) | ✅ History |
| R7 | Annual trends + YoY% change | ✅ History |
| R8 | Multi-year month overlay (area + lines) | ✅ History |
| R9 | Day & Night AQI split | ✅ Overview |
| R10 | "No. of days" category matrix | ✅ History |

### Key Removals
- ❌ Sidebar with 7+ controls
- ❌ Lat/Lon coordinate inputs
- ❌ "Model MAE" and "Realtime Source" KPIs
- ❌ Raw technical labels

## Testing

### Automated Tests
```
37 passed in 7.36s ✅
```
All data/model layer tests pass unchanged.

### Visual Verification
- ✅ Dark theme applied globally
- ✅ Navbar with 4 tabs functional
- ✅ Hero card shows live AQI 63, Moderate, weather data
- ✅ Hanoi skyline silhouette visible in hero background
- ✅ Charts loading on all pages
- ✅ Insight boxes ("WHAT THIS SHOWS") rendering
- ✅ Inline controls within pages (not sidebar)

## Running

```bash
cd /vol/biomedic3/gn425/HaNoiAQI/dashboard
.venv/bin/shiny run app.py --host 0.0.0.0 --port 8005
```

Dashboard accessible at `http://localhost:8005`
