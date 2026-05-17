"""Districts page — choropleth map, ranking table with monthly heatmap, deep‑dive."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import module, reactive, render, ui
from shinywidgets import output_widget, render_widget

from src.utils import aqi_category, aqi_color, sanitize_figure

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
GEOJSON_PATH = DATA_ROOT / "hanoi_districts.geojson"

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
DISTRICT_CHOICES = sorted(DISTRICT_CENTROIDS.keys())


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


def _aqi_bg_style(val: float) -> str:
    """Return inline CSS for a cell background based on AQI value."""
    color = aqi_color(val)
    return f"background:{color};color:#fff;font-weight:700;padding:4px 8px;border-radius:4px;text-align:center;display:inline-block;min-width:36px;font-size:0.8rem;"


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def district_ui():
    return ui.TagList(
        ui.div(
            ui.h3("District Explorer"),
            ui.div("Compare air quality across Hanoi's 30 districts", class_="page-intro-sub"),
            class_="page-intro",
        ),
        # Inline controls
        ui.div(
            ui.div(
                ui.div(
                    ui.div(
                        ui.div("Districts", class_="district-picker-title"),
                        ui.output_text("selected_count"),
                        class_="district-picker-head",
                    ),
                    ui.div(
                        ui.input_action_button("select_all", "Select all", class_="picker-action"),
                        ui.input_action_button("clear_all", "Clear", class_="picker-action picker-action-muted"),
                        class_="district-picker-tools",
                    ),
                    ui.input_checkbox_group(
                        "districts",
                        None,
                        choices=DISTRICT_CHOICES,
                        selected=DISTRICT_CHOICES,
                    ),
                    class_="district-picker",
                ),
                class_="district-filter-box",
            ),
            ui.input_select("year", "Year", choices=["All"] + [str(y) for y in range(2026, 2021, -1)], selected="All", width="100px"),
            class_="control-bar district-control-bar",
        ),
        # Map + ranking
        ui.div(
            ui.div(
                ui.h4("District AQI Map"),
                output_widget("choropleth", height="480px"),
                class_="panel",
            ),
            ui.div(
                ui.h4("District Ranking"),
                ui.output_ui("ranking_table_ui"),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Insight
        ui.output_ui("district_insight"),
        # Deep dive
        ui.div(
            ui.div(
                ui.h4("Selected District — Monthly Trend"),
                output_widget("district_trend", height="320px"),
                class_="panel",
            ),
            ui.div(
                ui.h4("Pollutant Breakdown"),
                output_widget("pollutant_breakdown", height="320px"),
                class_="panel",
            ),
            class_="grid-2",
        ),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def district_server(
    input, output, session,
    *,
    district_daily: pd.DataFrame,
):
    @reactive.effect
    @reactive.event(input.select_all)
    def _select_all_districts():
        ui.update_checkbox_group("districts", selected=DISTRICT_CHOICES)

    @reactive.effect
    @reactive.event(input.clear_all)
    def _clear_all_districts():
        ui.update_checkbox_group("districts", selected=[])

    @reactive.calc
    def selected_districts() -> list[str]:
        raw = input.districts()
        if raw is None:
            return []
        if isinstance(raw, str):
            raw = [raw]
        selected = [d for d in raw if d in DISTRICT_CENTROIDS]
        return selected

    @output
    @render.text
    def selected_count():
        n = len(selected_districts())
        return f"{n}/30 selected"

    @reactive.calc
    def filtered():
        df = district_daily.copy()
        if input.year() != "All":
            year = int(input.year())
            df = df[df["time"].dt.year == year]
        return df

    @reactive.calc
    def map_data():
        df = filtered()
        if df.empty:
            return pd.DataFrame(columns=["district", "aqi_daily", "lat", "lon"])
        agg = df.groupby("district", as_index=False)["aqi_daily"].mean().dropna()
        coords = pd.DataFrame([{"district": d, "lat": lat, "lon": lon} for d, (lat, lon) in DISTRICT_CENTROIDS.items()])
        return agg.merge(coords, on="district", how="inner")

    @output
    @render_widget
    def choropleth():
        mdf = map_data()
        if mdf.empty:
            return _blank("No district data")

        selected = set(selected_districts())
        selected_df = mdf[mdf["district"].isin(selected)].copy()
        dim_df = mdf[~mdf["district"].isin(selected)].copy()

        if GEOJSON_PATH.exists():
            with open(GEOJSON_PATH) as f:
                geojson = json.load(f)
            fig = go.Figure()
            if not dim_df.empty:
                fig.add_trace(go.Choroplethmapbox(
                    geojson=geojson,
                    locations=list(dim_df["district"]),
                    z=[1] * len(dim_df),
                    featureidkey="properties.shapeName",
                    colorscale=[[0, "rgba(39,44,52,0.22)"], [1, "rgba(78,86,99,0.34)"]],
                    marker={"opacity": 0.34, "line": {"color": "rgba(255,255,255,0.08)", "width": 0.8}},
                    hoverinfo="skip",
                    showscale=False,
                    name="Not selected",
                ))
            if not selected_df.empty:
                fig.add_trace(go.Choroplethmapbox(
                    geojson=geojson,
                    locations=list(selected_df["district"]),
                    z=list(selected_df["aqi_daily"]),
                    featureidkey="properties.shapeName",
                    colorscale="YlOrRd",
                    zmin=30,
                    zmax=180,
                    marker={"opacity": 0.84, "line": {"color": "rgba(255,255,255,0.50)", "width": 1.2}},
                    colorbar={"title": "AQI", "thickness": 10, "len": 0.62},
                    customdata=np.stack(
                        [selected_df["district"], selected_df["aqi_daily"]],
                        axis=-1,
                    ),
                    hovertemplate="<b>%{customdata[0]}</b><br>AQI %{customdata[1]:.1f}<extra></extra>",
                    name="Selected districts",
                ))
                label_df = selected_df if len(selected_df) <= 12 else selected_df.nlargest(12, "aqi_daily")
                fig.add_trace(go.Scattermapbox(
                    lat=list(label_df["lat"]),
                    lon=list(label_df["lon"]),
                    mode="text",
                    text=list(label_df["district"]),
                    textposition="middle center",
                    textfont={"size": 9, "color": "#f8fafc"},
                    hoverinfo="skip",
                    showlegend=False,
                ))
            fig.update_layout(
                mapbox={"style": "carto-darkmatter", "zoom": 9.2, "center": {"lat": 21.0, "lon": 105.75}},
                height=480,
            )
        else:
            mdf["picked"] = np.where(mdf["district"].isin(selected), "Selected", "Dimmed")
            fig = px.scatter_mapbox(
                mdf, lat="lat", lon="lon",
                color="aqi_daily", size="aqi_daily", size_max=22,
                hover_name="district",
                color_continuous_scale="YlOrRd",
                zoom=9.2, height=480,
            )

        fig.update_layout(
            mapbox_style="carto-darkmatter",
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            coloraxis_colorbar={"title": "AQI", "thickness": 10, "len": 0.6},
            paper_bgcolor="rgba(0,0,0,0)",
            transition={"duration": 500, "easing": "cubic-in-out"},
            uirevision="district-map",
        )
        return sanitize_figure(fig)

    @output
    @render.ui
    def ranking_table_ui():
        df = filtered()
        if df.empty:
            return ui.div("No data", style="color:#6b7280;")

        df = df.copy()
        df["month"] = df["time"].dt.month
        monthly = df.groupby(["district", "month"], as_index=False)["aqi_daily"].mean()
        yearly = df.groupby("district", as_index=False)["aqi_daily"].mean()
        yearly = yearly.sort_values("aqi_daily", ascending=False).reset_index(drop=True)
        yearly["rank"] = range(1, len(yearly) + 1)
        selected = selected_districts()
        if not selected:
            return ui.div("No district selected. Use Select all or tick districts to populate the ranking.", class_="ranking-empty")
        yearly = yearly[yearly["district"].isin(selected)]

        # Build HTML table
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        header = "<tr><th>Rank</th><th>District</th><th>Avg</th>"
        header += "".join(f"<th>{m}</th>" for m in months)
        header += "</tr>"

        rows = []
        for _, row in yearly.iterrows():
            dist = row["district"]
            avg = row["aqi_daily"]
            r = f'<tr><td>{row["rank"]}</td><td>{dist}</td>'
            r += f'<td><span style="{_aqi_bg_style(avg)}">{avg:.0f}</span></td>'
            for m in range(1, 13):
                mv = monthly[(monthly["district"] == dist) & (monthly["month"] == m)]["aqi_daily"]
                if not mv.empty:
                    val = mv.values[0]
                    r += f'<td><span style="{_aqi_bg_style(val)}">{val:.0f}</span></td>'
                else:
                    r += '<td style="color:#6b7280;">—</td>'
            r += "</tr>"
            rows.append(r)

        html = f'<div class="ranking-scroll"><table class="ranking-table">{header}{"".join(rows)}</table></div>'
        return ui.HTML(html)

    @output
    @render.ui
    def district_insight():
        selected = selected_districts()
        df = filtered()
        if df.empty:
            return ui.div()
        if not selected:
            city_avg = df["aqi_daily"].mean()
            return ui.div(
                ui.div("WHAT THIS SHOWS", class_="insight-label"),
                ui.p(f"No district is selected. The map keeps Hanoi in a muted context layer; city-wide average is {city_avg:.0f} AQI."),
                class_="insight-box",
            )
        if len(selected) == len(DISTRICT_CHOICES):
            city_avg = df["aqi_daily"].mean() if not df.empty else 0
            return ui.div(
                ui.div("WHAT THIS SHOWS", class_="insight-label"),
                ui.p(f"The map shows average AQI across Hanoi's 30 districts. City-wide average is {city_avg:.0f} AQI. "
                     "Untick districts to isolate local AQI hotspots."),
                class_="insight-box",
            )
        dist_data = df[df["district"].isin(selected)]
        dist_avg = dist_data["aqi_daily"].mean() if not dist_data.empty else 0
        city_avg = df["aqi_daily"].mean()
        pct = (dist_avg - city_avg) / city_avg * 100 if city_avg > 0 else 0
        direction = "above" if pct > 0 else "below"
        label = selected[0] if len(selected) == 1 else f"{len(selected)} selected districts"
        return ui.div(
            ui.div("DISTRICT INSIGHT", class_="insight-label"),
            ui.p(f"{label}' average AQI ({dist_avg:.0f}) is {abs(pct):.0f}% {direction} the city average ({city_avg:.0f}). "
                 f"Category: {aqi_category(dist_avg)}."),
            class_="insight-box",
        )

    @output
    @render_widget
    def district_trend():
        selected = selected_districts()
        df = filtered()
        if not selected:
            return _blank("Tick one or more districts")
        dist = df[df["district"].isin(selected)].copy()
        if dist.empty:
            return _blank("No data for selected districts")
        dist["period"] = dist["time"].dt.to_period("M")
        monthly = dist.groupby(["district", "period"], as_index=False).agg(aqi=("aqi_daily", "mean"))
        monthly["month_str"] = monthly["period"].astype(str)
        fig = go.Figure()
        city_monthly = df.copy()
        city_monthly["period"] = city_monthly["time"].dt.to_period("M")
        city_monthly = city_monthly.groupby("period", as_index=False).agg(aqi=("aqi_daily", "mean"))
        city_monthly["month_str"] = city_monthly["period"].astype(str)
        fig.add_trace(go.Scatter(
            x=list(city_monthly["month_str"]), y=list(city_monthly["aqi"]),
            mode="lines",
            line={"color": "rgba(232,234,237,0.58)", "width": 2.4, "dash": "dot"},
            name="City avg",
            hovertemplate="City avg<br>%{x}: %{y:.1f} AQI<extra></extra>",
        ))

        district_order = (
            monthly.groupby("district", as_index=False)["aqi"]
            .mean()
            .sort_values("aqi", ascending=False)["district"]
            .tolist()
        )
        palette = px.colors.qualitative.Dark24 + px.colors.qualitative.Set3
        dense = len(selected) > 10
        legend_limit = 8 if dense else len(selected)
        for idx, district in enumerate(district_order):
            one = monthly[monthly["district"] == district]
            if one.empty:
                continue
            rank = idx + 1
            is_focus = not dense or rank <= legend_limit
            fig.add_trace(go.Scatter(
                x=list(one["month_str"]), y=list(one["aqi"]),
                mode="lines" if dense else "lines+markers",
                line={
                    "color": palette[idx % len(palette)],
                    "width": 2.5 if is_focus else 1.15,
                },
                marker={"size": 4 if is_focus else 0},
                opacity=0.88 if is_focus else 0.24,
                name=district,
                showlegend=is_focus,
                hovertemplate=f"{district}<br>%{{x}}: %{{y:.1f}} AQI<extra></extra>",
            ))
        if dense:
            fig.add_annotation(
                text=f"{len(selected)} districts selected · legend highlights top {legend_limit} by average AQI",
                x=0.01, y=1.06, xref="paper", yref="paper",
                showarrow=False,
                font={"size": 11, "color": "#9aa0a6"},
                align="left",
            )
        fig.update_xaxes(title="", tickangle=45)
        fig.update_yaxes(title="AQI")
        fig.update_layout(
            showlegend=True,
            legend={
                "font": {"color": "#9aa0a6", "size": 10},
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": -0.42,
                "yanchor": "top",
                "bgcolor": "rgba(0,0,0,0)",
            },
            margin={"l": 8, "r": 8, "t": 36, "b": 92},
            transition={"duration": 350, "easing": "cubic-in-out"},
        )
        return _dark_fig(fig, height=320)

    @output
    @render_widget
    def pollutant_breakdown():
        selected = selected_districts()
        df = filtered()
        if not selected:
            return _blank("Tick one or more districts")
        if len(selected) != len(DISTRICT_CHOICES):
            df = df[df["district"].isin(selected)]
        if df.empty:
            return _blank()

        pollutants = {
            "PM2.5": "aqi_pm2_5", "PM10": "aqi_pm10",
            "NO₂": "aqi_nitrogen_dioxide", "O₃": "aqi_ozone",
            "SO₂": "aqi_sulphur_dioxide", "CO": "aqi_carbon_monoxide",
        }
        rows = []
        for label, col in pollutants.items():
            if col in df.columns:
                val = df[col].mean()
                if not pd.isna(val) and np.isfinite(val):
                    rows.append({"pollutant": label, "value": float(val)})
        if not rows:
            return _blank("No pollutant data")
        pdf = pd.DataFrame(rows).sort_values("value", ascending=True)
        fig = px.bar(pdf, x="value", y="pollutant", orientation="h",
                     color="value", color_continuous_scale="Tealgrn")
        fig.update_layout(xaxis_title="Average AQI", yaxis_title="", coloraxis_showscale=False)
        return _dark_fig(fig, height=320)
