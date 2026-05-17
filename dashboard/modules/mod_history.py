"""History page — calendar heatmap, multi‑year overlay, category matrix, annual trends."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui
from shinywidgets import output_widget, render_widget

from src.utils import AQI_BANDS, aqi_category, aqi_color, sanitize_figure


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


POLLUTANT_MAP = {"AQI": "aqi", "PM2.5": "pm25", "PM10": "pm10"}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
YEAR_COLORS = {2022: "#4fc3f7", 2023: "#9aa0a6", 2024: "#ce93d8", 2025: "#7986cb", 2026: "#f5b700"}


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def history_ui():
    return ui.TagList(
        ui.div(
            ui.h3("Historical Air Quality Analysis"),
            ui.div("Hanoi, Vietnam", class_="page-intro-sub"),
            ui.p("Dive into AQI patterns with calendar views, multi-year comparisons, and seasonal insights."),
            class_="page-intro",
        ),
        # Pollutant pills + year selector
        ui.div(
            ui.input_radio_buttons("pollutant", "Indicator", choices=list(POLLUTANT_MAP.keys()), selected="AQI", inline=True),
            ui.input_select("cal_year", "Year", choices=[str(y) for y in range(2025, 2021, -1)], selected="2024", width="100px"),
            class_="control-bar",
        ),
        # Calendar heatmap
        ui.div(
            ui.h4(ui.output_text("cal_title")),
            output_widget("calendar_heatmap", height="220px"),
            ui.output_ui("cal_monthly_averages"),
            class_="panel",
        ),
        # Multi-year month overlay
        ui.div(
            ui.div(
                ui.h4(ui.output_text("monthly_title")),
                output_widget("monthly_overlay", height="380px"),
                ui.output_ui("monthly_insight"),
                class_="panel",
            ),
            ui.div(
                ui.h4("AQI Trends: Highest & Lowest"),
                ui.output_ui("trends_highlights"),
                ui.h4("Annual Comparison", style="margin-top:16px;"),
                ui.output_ui("annual_summary"),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Category matrix
        ui.div(
            ui.h4("Days by Air Quality Category"),
            ui.output_ui("category_matrix_ui"),
            ui.output_ui("category_insight"),
            class_="panel",
        ),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def history_server(
    input, output, session,
    *,
    city_hourly: pd.DataFrame,
):
    @reactive.calc
    def metric_col():
        return POLLUTANT_MAP[input.pollutant()]

    @reactive.calc
    def daily_data():
        col = metric_col()
        df = city_hourly.copy()
        if col not in df.columns:
            return pd.DataFrame()
        daily = df.set_index("local_time")[col].resample("D").mean().dropna().reset_index()
        daily.columns = ["date", "value"]
        daily["year"] = daily["date"].dt.year
        daily["month"] = daily["date"].dt.month
        daily["day"] = daily["date"].dt.day
        daily["dow"] = daily["date"].dt.dayofweek  # 0=Mon
        daily["week"] = daily["date"].dt.isocalendar().week.astype(int)
        return daily

    # ── Calendar Heatmap ────────────────────────────────────────────────────

    @output
    @render.text
    def cal_title():
        return f"{input.pollutant()} Levels in {input.cal_year()}"

    @output
    @render_widget
    def calendar_heatmap():
        df = daily_data()
        year = int(input.cal_year())
        yr = df[df["year"] == year].copy()
        if yr.empty:
            return _blank(f"No data for {year}")

        # GitHub-style: x=week_of_year, y=day_of_week (Mon=0, Sun=6)
        yr["week_in_year"] = (yr["date"] - pd.Timestamp(f"{year}-01-01")).dt.days // 7
        dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Create matrix: 7 rows (dow) × 53 columns (weeks)
        max_week = yr["week_in_year"].max() + 1
        matrix = np.full((7, max_week), np.nan)
        text_matrix = [["" for _ in range(max_week)] for _ in range(7)]
        for _, row in yr.iterrows():
            matrix[row["dow"]][row["week_in_year"]] = row["value"]
            text_matrix[row["dow"]][row["week_in_year"]] = f"{row['date'].strftime('%b %d')}: {row['value']:.0f}"

        # Month labels on x-axis
        month_ticks = []
        month_labels = []
        for m in range(1, 13):
            first_day = pd.Timestamp(f"{year}-{m:02d}-01")
            if first_day.year == year:
                week_pos = (first_day - pd.Timestamp(f"{year}-01-01")).days // 7
                month_ticks.append(week_pos)
                month_labels.append(MONTH_NAMES[m - 1])

        fig = go.Figure(data=go.Heatmap(
            z=[[None if pd.isna(v) else float(v) for v in row] for row in matrix],
            x=list(range(max_week)),
            y=dow_labels,
            text=text_matrix,
            hovertemplate="%{text}<extra></extra>",
            colorscale=[
                [0.0, "#2bb673"], [0.2, "#f5b700"], [0.4, "#f28f3b"],
                [0.6, "#d1495b"], [0.8, "#7b2cbf"], [1.0, "#5a189a"],
            ],
            zmin=0, zmax=200,
            colorbar={"title": input.pollutant(), "thickness": 10, "len": 0.8},
            xgap=2, ygap=2,
        ))
        fig.update_xaxes(tickvals=month_ticks, ticktext=month_labels, side="top")
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(yaxis_title="")
        return _dark_fig(fig, height=220)

    @output
    @render.ui
    def cal_monthly_averages():
        df = daily_data()
        year = int(input.cal_year())
        yr = df[df["year"] == year]
        if yr.empty:
            return ui.div()
        monthly = yr.groupby("month")["value"].mean()
        badges = []
        for m in range(1, 13):
            val = monthly.get(m, np.nan)
            if not pd.isna(val):
                badges.append(ui.tags.span(f"{val:.0f}", style=f"background:{aqi_color(val)};color:#fff;padding:3px 8px;border-radius:4px;font-weight:700;font-size:0.8rem;margin:2px 4px;"))
            else:
                badges.append(ui.tags.span("—", style="color:#6b7280;margin:2px 4px;"))
        return ui.div(
            *[ui.div(ui.tags.span(MONTH_NAMES[i], style="color:#6b7280;font-size:0.7rem;display:block;"), badges[i], style="display:inline-block;text-align:center;min-width:50px;") for i in range(12)],
            style="display:flex;flex-wrap:wrap;gap:2px;margin-top:8px;",
        )

    # ── Multi-year Month Overlay ────────────────────────────────────────────

    @output
    @render.text
    def monthly_title():
        now = pd.Timestamp.now()
        return f"{MONTH_NAMES[now.month - 1]} Air Quality Analysis"

    @output
    @render_widget
    def monthly_overlay():
        df = daily_data()
        if df.empty:
            return _blank()
        now = pd.Timestamp.now()
        current_month = now.month
        month_data = df[df["month"] == current_month].copy()
        if month_data.empty:
            return _blank()

        fig = go.Figure()
        years = sorted(month_data["year"].unique())
        for yr in years:
            yr_data = month_data[month_data["year"] == yr].sort_values("day")
            color = YEAR_COLORS.get(yr, "#9aa0a6")
            is_current = yr == years[-1]
            fig.add_trace(go.Scatter(
                x=list(yr_data["day"]),
                y=list(yr_data["value"]),
                mode="lines+markers" if is_current else "lines",
                name=str(yr),
                line={"color": color, "width": 3 if is_current else 1.5},
                marker={"size": 6} if is_current else None,
                fill="tozeroy" if is_current else None,
                fillcolor=f"rgba(200,164,21,0.1)" if is_current else None,
                opacity=1.0 if is_current else 0.6,
            ))
        fig.update_xaxes(title="Day of Month", dtick=2)
        fig.update_yaxes(title=input.pollutant())
        fig.update_layout(
            hovermode="x unified",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#9aa0a6"}},
        )
        return _dark_fig(fig, height=380)

    @output
    @render.ui
    def monthly_insight():
        df = daily_data()
        if df.empty:
            return ui.div()
        now = pd.Timestamp.now()
        month_data = df[df["month"] == now.month]
        if month_data.empty:
            return ui.div()

        # Same day analysis
        today_day = now.day
        same_day = month_data[month_data["day"] == today_day]
        if len(same_day) > 1:
            parts = []
            for _, r in same_day.sort_values("year").iterrows():
                parts.append(f"{int(r['year'])}: {r['value']:.0f}")
            text = f"Same Day Analysis ({today_day}{_ordinal(today_day)} {MONTH_NAMES[now.month-1]}): " + ", ".join(parts) + "."
        else:
            text = ""

        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(f"Comparing {MONTH_NAMES[now.month-1]} AQI across years reveals seasonal patterns. "
                 f"The filled area shows the most recent year. {text}"),
            class_="insight-box",
        )

    @output
    @render.ui
    def trends_highlights():
        df = daily_data()
        if df.empty:
            return ui.div("No data", style="color:#6b7280;")
        max_row = df.loc[df["value"].idxmax()]
        min_row = df.loc[df["value"].idxmin()]
        return ui.div(
            ui.div(
                ui.div(
                    ui.tags.span("Highest", class_="hl-label", style="color:#d1495b;"),
                    ui.div(f"{max_row['date'].strftime('%d %b %Y')}", class_="hl-detail"),
                    style="flex:1;",
                ),
                ui.tags.span(f"{max_row['value']:.0f}", style=f"background:#d1495b;color:#fff;padding:6px 14px;border-radius:6px;font-weight:900;font-size:1.1rem;"),
                class_="highlight-card",
            ),
            ui.div(
                ui.div(
                    ui.tags.span("Lowest", class_="hl-label", style="color:#2bb673;"),
                    ui.div(f"{min_row['date'].strftime('%d %b %Y')}", class_="hl-detail"),
                    style="flex:1;",
                ),
                ui.tags.span(f"{min_row['value']:.0f}", style=f"background:#2bb673;color:#fff;padding:6px 14px;border-radius:6px;font-weight:900;font-size:1.1rem;"),
                class_="highlight-card",
            ),
            style="display:flex;flex-direction:column;gap:10px;",
        )

    @output
    @render.ui
    def annual_summary():
        df = daily_data()
        if df.empty:
            return ui.div()
        yearly = df.groupby("year")["value"].mean().sort_index()
        rows = []
        prev = None
        for yr, avg in yearly.items():
            if prev is not None:
                pct = (avg - prev) / prev * 100
                arrow = "↑" if pct > 0 else "↓"
                change_color = "#d1495b" if pct > 0 else "#2bb673"
                change_text = f'<span style="color:{change_color};font-weight:700;">{arrow} {abs(pct):.0f}%</span>'
            else:
                change_text = ""
            color = aqi_color(avg)
            rows.append(
                f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid #363b44;">'
                f'<span style="color:#9aa0a6;min-width:40px;">{yr}</span>'
                f'<span style="background:{color};color:#fff;padding:3px 10px;border-radius:4px;font-weight:700;min-width:40px;text-align:center;">{avg:.0f}</span>'
                f'<span style="flex:1;text-align:right;">{change_text}</span></div>'
            )
            prev = avg
        return ui.HTML("".join(rows))

    # ── Category Matrix (No. of Days) ──────────────────────────────────────

    @output
    @render.ui
    def category_matrix_ui():
        df = daily_data()
        if df.empty:
            return ui.div("No data", style="color:#6b7280;")
        df = df.copy()
        df["category"] = df["value"].apply(aqi_category)
        categories = ["Good", "Moderate", "USG", "Unhealthy", "Very Unhealthy", "Hazardous"]
        cat_colors = {"Good": "#2bb673", "Moderate": "#f5b700", "USG": "#f28f3b", "Unhealthy": "#d1495b", "Very Unhealthy": "#7b2cbf", "Hazardous": "#5a189a"}

        years = sorted(df["year"].unique(), reverse=True)

        # Table header
        html = '<div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;font-size:0.82rem;">'
        html += '<tr>'
        html += '<th style="text-align:left;padding:8px;color:#6b7280;"></th>'
        for yr in years:
            yr_avg = df[df["year"] == yr]["value"].mean()
            html += f'<th style="text-align:center;padding:8px;min-width:120px;"><div style="font-weight:700;color:#e8eaed;">{yr}</div><div style="color:#9aa0a6;font-size:0.75rem;">{yr_avg:.0f} AQI</div></th>'
        html += '</tr>'

        for m in range(1, 13):
            html += f'<tr><td style="padding:6px 8px;color:#9aa0a6;font-weight:600;">{MONTH_NAMES[m-1]}</td>'
            for yr in years:
                month_data = df[(df["year"] == yr) & (df["month"] == m)]
                if month_data.empty:
                    html += '<td style="padding:4px;"></td>'
                    continue
                counts = month_data["category"].value_counts()
                total = counts.sum()
                bar = '<div style="display:flex;height:22px;border-radius:3px;overflow:hidden;gap:1px;">'
                for cat in categories:
                    cnt = counts.get(cat, 0)
                    if cnt > 0:
                        pct = cnt / total * 100
                        bar += f'<div style="width:{pct}%;background:{cat_colors[cat]};display:flex;align-items:center;justify-content:center;font-size:0.65rem;color:#fff;font-weight:700;" title="{cat}: {cnt} days">{cnt if cnt > 2 else ""}</div>'
                bar += '</div>'
                html += f'<td style="padding:4px 6px;">{bar}</td>'
            html += '</tr>'

        # Total row
        html += '<tr style="border-top:2px solid #363b44;"><td style="padding:6px 8px;color:#e8eaed;font-weight:700;">Total</td>'
        for yr in years:
            yr_data = df[df["year"] == yr]
            counts = yr_data["category"].value_counts()
            total = counts.sum()
            bar = '<div style="display:flex;height:22px;border-radius:3px;overflow:hidden;gap:1px;">'
            for cat in categories:
                cnt = counts.get(cat, 0)
                if cnt > 0:
                    pct = cnt / total * 100
                    bar += f'<div style="width:{pct}%;background:{cat_colors[cat]};display:flex;align-items:center;justify-content:center;font-size:0.65rem;color:#fff;font-weight:700;">{cnt}</div>'
            bar += '</div>'
            html += f'<td style="padding:4px 6px;">{bar}</td>'
        html += '</tr></table></div>'

        # Legend
        legend = '<div style="display:flex;gap:12px;margin-top:10px;flex-wrap:wrap;">'
        for cat in categories:
            legend += f'<span style="display:flex;align-items:center;gap:4px;font-size:0.75rem;color:#9aa0a6;"><span style="width:10px;height:10px;border-radius:2px;background:{cat_colors[cat]};display:inline-block;"></span>{cat}</span>'
        legend += '</div>'

        return ui.HTML(html + legend)

    @output
    @render.ui
    def category_insight():
        df = daily_data()
        if df.empty:
            return ui.div()
        latest_year = df["year"].max()
        yr = df[df["year"] == latest_year]
        yr_cat = yr["value"].apply(aqi_category)
        good_pct = (yr_cat == "Good").sum() / len(yr_cat) * 100 if len(yr_cat) > 0 else 0
        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(f"In {latest_year}, only {good_pct:.0f}% of days had Good air quality (AQI ≤ 50). "
                 f"Each colored segment shows the proportion of days in each AQI category per month."),
            class_="insight-box",
        )


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
