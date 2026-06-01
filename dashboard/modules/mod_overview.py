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


def _recent_aqi(city_hourly: pd.DataFrame) -> pd.DataFrame:
    if city_hourly.empty or "aqi" not in city_hourly.columns or "local_time" not in city_hourly.columns:
        return pd.DataFrame()
    recent = city_hourly[["local_time", "aqi"]].copy()
    recent["aqi"] = pd.to_numeric(recent["aqi"], errors="coerce")
    recent = recent.dropna(subset=["local_time", "aqi"]).sort_values("local_time").tail(24)
    if recent.empty:
        return recent
    recent["period"] = np.where(recent["local_time"].dt.hour.between(6, 17), "Day", "Night")
    return recent


def _time_label(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return "unknown time"
    return pd.Timestamp(ts).strftime("%I %p").lstrip("0")


def _date_label(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%d %b")


def _snapshot_aqi(snapshot_value: dict | None, city_hourly: pd.DataFrame) -> float | None:
    aqi = snapshot_value.get("aqi") if isinstance(snapshot_value, dict) else None
    if aqi is None or pd.isna(aqi):
        latest = city_hourly["aqi"].dropna() if "aqi" in city_hourly.columns else pd.Series(dtype=float)
        aqi = latest.iloc[-1] if not latest.empty else None
    if aqi is None or pd.isna(aqi):
        return None
    return float(aqi)


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
                    ui.output_ui("hero_aqi_value"),
                    ui.div("AQI (US)", class_="hero-aqi-label"),
                    ui.output_ui("hero_category"),
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
                        ui.output_ui("aqi_scale_marker"),
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
                ui.output_ui("health_advice_ui"),
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
    @render.ui
    def hero_aqi_value():
        aqi = _snapshot_aqi(snapshot.get(), city_hourly)
        if aqi is None:
            return ui.div("—", class_="hero-aqi-number")
        color = aqi_color(aqi)
        return ui.div(str(int(aqi)), class_="hero-aqi-number", style=f"color:{color};")

    @output
    @render.ui
    def hero_category():
        aqi = _snapshot_aqi(snapshot.get(), city_hourly)
        category = aqi_category(aqi)
        color = aqi_color(aqi)
        return ui.div(category, class_="hero-category", style=f"color:{color};")

    @output
    @render.ui
    def aqi_scale_marker():
        aqi = _snapshot_aqi(snapshot.get(), city_hourly)
        if aqi is None:
            return ui.div()
        pct = min(max(aqi / 500 * 100, 0), 100)
        color = aqi_color(aqi)
        return ui.tags.span(class_="aqi-scale-marker", style=f"left:{pct}%;--marker-color:{color};")

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
        recent = _recent_aqi(city_hourly)
        if len(recent) < 2:
            return _blank("Not enough hourly data")

        recent = recent.reset_index(drop=True)
        recent["plot_idx"] = np.arange(len(recent))
        fig = go.Figure()

        segments = []
        start = 0
        current_period = recent.loc[0, "period"]
        for idx in range(1, len(recent)):
            period = recent.loc[idx, "period"]
            if period != current_period:
                segments.append((start, idx - 1, current_period))
                start = idx
                current_period = period
        segments.append((start, len(recent) - 1, current_period))
        for start_idx, end_idx, period in segments:
            fill = "rgba(86,151,209,0.08)" if period == "Day" else "rgba(44,54,121,0.14)"
            fig.add_vrect(x0=start_idx - 0.5, x1=end_idx + 0.5, fillcolor=fill, line_width=0, layer="below")

        fig.add_trace(go.Scatter(
            x=list(recent["plot_idx"]),
            y=list(recent["aqi"]),
            mode="lines+markers",
            line={"color": "#f6d433", "width": 2.8, "shape": "spline", "smoothing": 0.85},
            marker={"size": 5, "color": "#f6d433", "line": {"width": 0}},
            fill="tozeroy",
            fillcolor="rgba(246,211,51,0.09)",
            name="AQI",
            customdata=np.stack([
                recent["local_time"].dt.strftime("%d %b, %H:%M"),
                recent["period"],
            ], axis=-1),
            hovertemplate="%{customdata[0]}<br>%{customdata[1]}<br>AQI %{y:.0f}<extra></extra>",
        ))

        fig.add_annotation(text="☀", x=0.31, y=0.78, xref="paper", yref="paper", showarrow=False, font={"size": 52, "color": "rgba(246,211,51,0.16)"})
        fig.add_annotation(text="☾", x=0.84, y=0.78, xref="paper", yref="paper", showarrow=False, font={"size": 52, "color": "rgba(148,163,255,0.18)"})
        fig.add_annotation(text="Day", x=0.30, y=0.96, xref="paper", yref="paper", showarrow=False, font={"size": 12, "color": "#9bdcff"})
        fig.add_annotation(text="Night", x=0.86, y=0.96, xref="paper", yref="paper", showarrow=False, font={"size": 12, "color": "#94a3ff"})
        tick_idx = list(range(0, len(recent), 3))
        fig.update_xaxes(
            title="Hour",
            tickmode="array",
            tickvals=tick_idx,
            ticktext=[recent.loc[i, "local_time"].strftime("%H:%M") for i in tick_idx],
            range=[-0.5, len(recent) - 0.5],
        )
        fig.update_yaxes(title="AQI")
        fig.update_layout(showlegend=False, hovermode="x unified")
        return _dark_fig(fig, height=260)

    @output
    @render.ui
    def daynight_summary():
        recent = _recent_aqi(city_hourly)
        if len(recent) < 2:
            return ui.div()

        day = recent[recent["period"] == "Day"]
        night = recent[recent["period"] == "Night"]
        day_max = day["aqi"].max() if not day.empty else np.nan
        day_min = day["aqi"].min() if not day.empty else np.nan
        night_max = night["aqi"].max() if not night.empty else np.nan
        night_min = night["aqi"].min() if not night.empty else np.nan
        day_avg = day["aqi"].mean() if not day.empty else np.nan
        night_avg = night["aqi"].mean() if not night.empty else np.nan
        peak = recent.loc[recent["aqi"].idxmax()]
        low = recent.loc[recent["aqi"].idxmin()]
        delta = recent["aqi"].iloc[-1] - recent["aqi"].iloc[0]
        if abs(delta) < 5:
            trend_text = "roughly stable"
        elif delta > 0:
            trend_text = f"up by {delta:.0f} points"
        else:
            trend_text = f"down by {abs(delta):.0f} points"

        def summary_card(label: str, max_val: float, min_val: float, avg_val: float, class_name: str):
            return ui.div(
                ui.div(label, class_="dn-label"),
                ui.div(f"{max_val:.0f}" if not pd.isna(max_val) else "—", class_="dn-value"),
                ui.div(
                    f"Avg {avg_val:.0f} · Low {min_val:.0f}" if not pd.isna(avg_val) and not pd.isna(min_val) else "",
                    class_="dn-detail",
                ),
                class_=class_name,
            )

        return ui.div(
            ui.div(
                summary_card("☀ Daytime Peak", day_max, day_min, day_avg, "day-summary"),
                summary_card("☾ Nighttime Peak", night_max, night_min, night_avg, "night-summary"),
                class_="day-night-container",
            ),
            ui.div(
                ui.div("WHAT THIS SHOWS", class_="insight-label"),
                ui.p(ui.HTML(
                    f"In the last <span class='insight-highlight'>24 hours</span>, Hanoi's AQI peaked at "
                    f"<span class='insight-highlight'>{peak['aqi']:.0f}</span> around "
                    f"<span class='insight-soft'>{_time_label(peak['local_time'])}</span> on {_date_label(peak['local_time'])}. "
                    f"The lowest point was <span class='insight-good'>{low['aqi']:.0f}</span> around "
                    f"<span class='insight-soft'>{_time_label(low['local_time'])}</span>. "
                    f"Compared with the first hour, the latest reading is <span class='insight-highlight'>{trend_text}</span>."
                )),
                class_="insight-box day-night-note",
            ),
            class_="day-night-block",
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
    @render.ui
    def health_advice_ui():
        recent = city_hourly.copy()
        if recent.empty or "pm25" not in recent.columns:
            return ui.div()
        recent = recent.dropna(subset=["pm25"]).tail(24)
        if recent.empty:
            return ui.div()

        pm25_avg = float(pd.to_numeric(recent["pm25"], errors="coerce").dropna().mean())
        if pd.isna(pm25_avg):
            return ui.div()
        cigs_day = max(0.0, pm25_avg / 22.0)
        cigs_week = cigs_day * 7
        cigs_month = cigs_day * 30

        return ui.div(
            ui.div(
                ui.div(
                    ui.div(f"{cigs_day:.1f}", class_="cigarette-main"),
                    ui.div("cigarettes per day", class_="cigarette-label"),
                    ui.div(class_="cigarette-visual"),
                    ui.p(
                        ui.HTML(
                            "Breathing Hanoi air in the last 24h is roughly comparable to "
                            f"<span class='insight-highlight'>{cigs_day:.1f}</span> cigarette(s) per day "
                            f"based on average PM2.5 of <span class='insight-highlight'>{pm25_avg:.1f} µg/m³</span>."
                        ),
                        class_="health-equivalent-text",
                    ),
                    class_="health-cigarette-block",
                ),
                ui.div(
                    ui.div("Weekly", class_="health-period-label"),
                    ui.div(f"{cigs_week:.1f}", class_="health-period-value"),
                    ui.div("cigarette-equivalent", class_="health-period-unit"),
                    class_="health-period-card",
                ),
                ui.div(
                    ui.div("Monthly", class_="health-period-label"),
                    ui.div(f"{cigs_month:.0f}", class_="health-period-value"),
                    ui.div("cigarette-equivalent", class_="health-period-unit"),
                    class_="health-period-card",
                ),
                class_="health-advice-top",
            ),
            ui.div(
                ui.div("Berkeley Earth rule of thumb: 1 cigarette/day ≈ 22 µg/m³ PM2.5. This is an exposure framing estimate, not a medical diagnosis.", class_="health-disclaimer"),
                ui.div("Source: Berkeley Earth", class_="health-source"),
                class_="health-note-row",
            ),
            class_="health-advice-card",
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
