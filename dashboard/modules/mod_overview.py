"""Overview page — hero card, day/night trend, district quick‑cards, station map."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import module, reactive, render, ui
from shinywidgets import output_widget, render_widget

from src.utils import AQI_BANDS, aqi_advisory, aqi_category, aqi_color, sanitize_figure


def _dark_fig(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": "#e8eaed"},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(54,59,68,0.6)", zeroline=False, color="#9aa0a6")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(54,59,68,0.6)", zeroline=False, color="#9aa0a6")
    return sanitize_figure(fig)


def _blank(msg: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, showarrow=False, font={"size": 14, "color": "#6b7280"})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _dark_fig(fig)


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def overview_ui():
    return ui.TagList(
        # Hero
        ui.div(
            ui.tags.img(src="hanoi_skyline.png", class_="hero-skyline"),
            ui.div(
                # AQI block
                ui.div(
                    ui.div("● LIVE", style="font-size:0.7rem;font-weight:700;color:#d1495b;margin-bottom:6px;letter-spacing:0.08em;"),
                    ui.div(ui.output_text("hero_aqi_value"), class_="hero-aqi-number"),
                    ui.div("AQI (US)", class_="hero-aqi-label"),
                    ui.div(ui.output_text("hero_category"), class_="hero-category"),
                    class_="hero-aqi-block",
                ),
                # Info
                ui.div(
                    ui.h2("Hanoi Air Quality Index"),
                    ui.p(ui.output_text("hero_subtitle"), style="color:#9aa0a6;font-size:0.9rem;margin:0;"),
                    # AQI scale bar
                    ui.div(
                        ui.tags.span(style="background:#2bb673"),
                        ui.tags.span(style="background:#f5b700"),
                        ui.tags.span(style="background:#f28f3b"),
                        ui.tags.span(style="background:#d1495b"),
                        ui.tags.span(style="background:#7b2cbf"),
                        ui.tags.span(style="background:#5a189a"),
                        class_="aqi-scale-bar",
                    ),
                    ui.div(
                        ui.tags.span("Good"), ui.tags.span("Moderate"), ui.tags.span("USG"),
                        ui.tags.span("Unhealthy"), ui.tags.span("Severe"), ui.tags.span("Hazardous"),
                        class_="aqi-scale-labels",
                    ),
                    class_="hero-info",
                ),
                # Weather
                ui.div(
                    ui.output_ui("hero_weather_card"),
                    class_="hero-weather-dock",
                ),
                class_="hero-content",
            ),
            class_="hero-card",
        ),
        # Advisory insight
        ui.output_ui("hero_insight"),
        # Day & Night + Station Map
        ui.div(
            ui.div(
                ui.h4("Day & Night AQI — Last 24 Hours"),
                output_widget("daynight_plot", height="260px"),
                ui.output_ui("daynight_summary"),
                class_="panel",
            ),
            ui.div(
                ui.div(
                    ui.h4("Realtime Station Map"),
                    ui.output_ui("map_source_badge"),
                    class_="panel-title-row",
                ),
                ui.div(
                    ui.div(output_widget("map_plot", height="320px"), class_="station-map-frame"),
                    ui.output_ui("map_mascot_ui"),
                    class_="station-map-showcase",
                ),
                class_="panel",
            ),
            class_="grid-hero",
        ),
        # District quick cards
        ui.div(
            ui.div(
                ui.h4("District Snapshot — Top AQI"),
                ui.p("Average AQI across Hanoi's 30 districts in the latest data window.", style="color:#9aa0a6;font-size:0.85rem;margin:-6px 0 12px 0;"),
                class_="page-intro",
            ),
        ),
        ui.output_ui("district_cards_ui"),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def overview_server(
    input, output, session,
    *,
    city_hourly: pd.DataFrame,
    station_cache: reactive.Value,
    snapshot: reactive.Value,
    district_map_frame: Callable,
):
    @output
    @render.text
    def hero_aqi_value():
        snap = snapshot.get()
        aqi = snap.get("aqi") if isinstance(snap, dict) else None
        if aqi is None or pd.isna(aqi):
            # Fallback to latest city data
            latest = city_hourly["aqi"].dropna()
            return str(int(latest.iloc[-1])) if not latest.empty else "—"
        return str(int(float(aqi)))

    @output
    @render.text
    def hero_category():
        snap = snapshot.get()
        aqi = snap.get("aqi") if isinstance(snap, dict) else None
        if aqi is None or pd.isna(aqi):
            latest = city_hourly["aqi"].dropna()
            aqi = latest.iloc[-1] if not latest.empty else None
        return aqi_category(aqi)

    @output
    @render.text
    def hero_subtitle():
        snap = snapshot.get()
        ts = snap.get("time_iso", "N/A") if isinstance(snap, dict) else "N/A"
        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        return f"Real-time data from {source} · Last updated: {ts}"

    @output
    @render.ui
    def hero_weather_card():
        snap = snapshot.get()
        if not isinstance(snap, dict) or not snap:
            return ui.div()
        items = []
        for key, label, unit in [
            ("temp", "Temp", "°C"),
            ("humidity", "Humidity", "%"),
            ("wind", "Wind", "km/h"),
            ("pressure", "Pressure", "hPa"),
        ]:
            val = snap.get(key)
            if val is not None and not pd.isna(val):
                items.append(
                    ui.div(
                        ui.div(f"{float(val):.0f}{unit}", class_="weather-val"),
                        ui.div(label, class_="weather-lbl"),
                        class_="weather-item",
                    )
                )
        if not items:
            return ui.div()
        return ui.div(*items, class_="weather-card")

    @output
    @render.ui
    def hero_insight():
        snap = snapshot.get()
        aqi = snap.get("aqi") if isinstance(snap, dict) else None
        if aqi is None or pd.isna(aqi):
            latest = city_hourly["aqi"].dropna()
            aqi = latest.iloc[-1] if not latest.empty else None
        advisory = aqi_advisory(aqi)
        return ui.div(
            ui.div("WHAT THIS MEANS", class_="insight-label"),
            ui.p(advisory),
            class_="insight-box",
        )

    @output
    @render_widget
    def daynight_plot():
        df = city_hourly.copy()
        if df.empty or "aqi" not in df.columns:
            return _blank()
        recent = df.tail(24).copy()
        if len(recent) < 2:
            return _blank("Not enough hourly data")
        recent["hour"] = recent["local_time"].dt.hour
        fig = go.Figure()
        # Day/night background
        fig.add_vrect(x0=-0.5, x1=17.5, fillcolor="rgba(74,144,217,0.06)", line_width=0)
        fig.add_vrect(x0=17.5, x1=23.5, fillcolor="rgba(26,29,78,0.12)", line_width=0)
        fig.add_trace(go.Scatter(
            x=list(recent["hour"]),
            y=list(recent["aqi"]),
            mode="lines+markers",
            line={"color": "#f5b700", "width": 2.5},
            marker={"size": 5, "color": "#f5b700"},
            fill="tozeroy",
            fillcolor="rgba(245,183,0,0.08)",
            name="AQI",
        ))
        fig.add_annotation(text="☀️ Day", x=9, y=0.95, xref="x", yref="paper", showarrow=False, font={"size": 12, "color": "#87ceeb"})
        fig.add_annotation(text="🌙 Night", x=21, y=0.95, xref="x", yref="paper", showarrow=False, font={"size": 12, "color": "#6b7cc4"})
        fig.update_xaxes(title="Hour", dtick=3, range=[-0.5, 23.5])
        fig.update_yaxes(title="AQI")
        fig.update_layout(showlegend=False)
        return _dark_fig(fig, height=260)

    @output
    @render.ui
    def daynight_summary():
        df = city_hourly.copy()
        if df.empty:
            return ui.div()
        recent = df.tail(24).copy()
        if len(recent) < 2:
            return ui.div()
        day = recent[recent["local_time"].dt.hour.between(6, 17)]
        night = recent[~recent["local_time"].dt.hour.between(6, 17)]
        day_max = day["aqi"].max() if not day.empty else np.nan
        day_min = day["aqi"].min() if not day.empty else np.nan
        night_max = night["aqi"].max() if not night.empty else np.nan
        night_min = night["aqi"].min() if not night.empty else np.nan
        return ui.div(
            ui.div(
                ui.div("☀️ Daytime", class_="dn-label"),
                ui.div(f"{day_max:.0f}" if not pd.isna(day_max) else "—", class_="dn-value"),
                ui.div(f"Peak · Low {day_min:.0f}" if not pd.isna(day_min) else "", class_="dn-detail"),
                class_="day-summary",
            ),
            ui.div(
                ui.div("🌙 Nighttime", class_="dn-label"),
                ui.div(f"{night_max:.0f}" if not pd.isna(night_max) else "—", class_="dn-value"),
                ui.div(f"Peak · Low {night_min:.0f}" if not pd.isna(night_min) else "", class_="dn-detail"),
                class_="night-summary",
            ),
            class_="day-night-container",
        )

    @output
    @render.ui
    def map_source_badge():
        snap = snapshot.get()
        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        stations = station_cache.get()
        count = len(stations) if stations else 0
        if count:
            label = f"{count} live stations"
        else:
            label = source
        return ui.div(label, class_="map-source-badge")

    @output
    @render.ui
    def map_mascot_ui():
        snap = snapshot.get()
        aqi = snap.get("aqi") if isinstance(snap, dict) else None
        if aqi is None or pd.isna(aqi):
            latest = city_hourly["aqi"].dropna()
            aqi = latest.iloc[-1] if not latest.empty else None

        category = aqi_category(aqi)
        color = aqi_color(aqi)
        aqi_text = "—" if aqi is None or pd.isna(aqi) else f"{float(aqi):.0f}"
        source = snap.get("source", "Historical") if isinstance(snap, dict) else "Historical"
        mood_class = {
            "Good": "mood-good",
            "Moderate": "mood-moderate",
            "USG": "mood-usg",
            "Unhealthy": "mood-unhealthy",
            "Very Unhealthy": "mood-severe",
            "Hazardous": "mood-hazardous",
        }.get(category, "mood-unknown")
        message = {
            "Good": "Great air for a campus stroll.",
            "Moderate": "Pretty okay, but Lexce is keeping one eye on the air.",
            "USG": "Lexce suggests sensitive groups take it gently outside.",
            "Unhealthy": "Lexce is worried. Short trips and masks are smarter today.",
            "Very Unhealthy": "Lexce recommends staying indoors where possible.",
            "Hazardous": "Lexce says: indoor mode, windows closed, no outdoor exertion.",
        }.get(category, "Lexce is using the latest available Hanoi context.")

        return ui.div(
            ui.div(
                ui.div(ui.span("AQI"), ui.strong(aqi_text), class_="mascot-aqi-chip", style=f"--chip:{color};"),
                ui.div(
                    ui.div(
                        ui.div(class_="owl-ear owl-ear-left"),
                        ui.div(class_="owl-ear owl-ear-right"),
                        ui.div(class_="owl-face"),
                        ui.div(ui.div(class_="owl-eye-shine"), class_="owl-eye owl-eye-left"),
                        ui.div(ui.div(class_="owl-eye-shine"), class_="owl-eye owl-eye-right"),
                        ui.div(class_="owl-brow owl-brow-left"),
                        ui.div(class_="owl-brow owl-brow-right"),
                        ui.div(class_="owl-beak"),
                        ui.div(class_="owl-cheek owl-cheek-left"),
                        ui.div(class_="owl-cheek owl-cheek-right"),
                        ui.div(class_="owl-wing owl-wing-left"),
                        ui.div(class_="owl-wing owl-wing-right"),
                        ui.div(class_="owl-belly-mark"),
                        ui.div(class_="owl-mouth"),
                        ui.div(class_="owl-mask"),
                        ui.div(class_="owl-foot owl-foot-left"),
                        ui.div(class_="owl-foot owl-foot-right"),
                        class_=f"vinuni-owl {mood_class}",
                    ),
                    class_="mascot-stage",
                ),
                ui.div(
                    ui.div("Lexce, AQI buddy", class_="mascot-name"),
                    ui.div(f"{category} · {source}", class_="mascot-status", style=f"color:{color};"),
                    ui.p(message),
                    class_=f"mascot-bubble {mood_class}",
                ),
                class_="map-mascot-card",
            ),
            class_="map-mascot-wrap",
        )

    @output
    @render_widget
    def map_plot():
        stations = station_cache.get()
        if stations:
            map_df = pd.DataFrame(stations)
            fig = px.scatter_mapbox(
                map_df, lat="lat", lon="lon",
                color="aqi", size="aqi", size_max=18,
                hover_name="name",
                hover_data={"aqi": ":.0f", "dominant": True},
                color_continuous_scale="Turbo",
                zoom=10.4, height=340,
            )
        else:
            fig = px.scatter_mapbox(
                pd.DataFrame([{"name": "Hanoi Center", "lat": 21.0245, "lon": 105.8412}]),
                lat="lat", lon="lon", hover_name="name", zoom=10.4, height=340,
            )
        fig.update_layout(
            mapbox_style="carto-darkmatter",
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            coloraxis_colorbar={"title": "AQI", "thickness": 10, "len": 0.6, "x": 0.98},
            paper_bgcolor="rgba(0,0,0,0)",
        )
        return sanitize_figure(fig)

    @output
    @render.ui
    def district_cards_ui():
        df = district_map_frame()
        if df.empty:
            return ui.div("No district data available.", style="color:#6b7280;")
        top = df.nlargest(8, "aqi_daily")
        cards = []
        for _, row in top.iterrows():
            aqi_val = row["aqi_daily"]
            color = aqi_color(aqi_val)
            cards.append(
                ui.div(
                    ui.div(row["district"], class_="dc-name"),
                    ui.div(f"{aqi_val:.0f}", class_="dc-aqi", style=f"color:{color};"),
                    class_="district-card",
                )
            )
        return ui.div(*cards, class_="district-cards")
