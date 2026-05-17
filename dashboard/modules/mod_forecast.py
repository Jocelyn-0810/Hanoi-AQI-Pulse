"""Forecast page — prediction hero, model transparency, pollutant mix."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from shiny import module, reactive, render, ui
from shinywidgets import output_widget, render_widget

from src.utils import aqi_advisory, aqi_category, aqi_color, sanitize_figure


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


HORIZONS = {"1h": 1, "6h": 6, "24h": 24}


# ── UI ──────────────────────────────────────────────────────────────────────────

@module.ui
def forecast_ui():
    return ui.TagList(
        ui.div(
            ui.h3("Forecast Lab"),
            ui.div("Short-term AQI prediction powered by machine learning", class_="page-intro-sub"),
            ui.p("Our model analyzes the latest air quality data, weather conditions, and time patterns to predict future AQI levels."),
            class_="page-intro",
        ),
        # Controls
        ui.div(
            ui.input_radio_buttons("horizon", "Forecast Horizon", choices=list(HORIZONS.keys()), selected="6h", inline=True),
            ui.input_radio_buttons("target", "Target", choices=["AQI", "PM2.5"], selected="AQI", inline=True),
            class_="control-bar",
        ),
        # Prediction hero
        ui.div(
            ui.div(
                ui.output_ui("prediction_hero"),
                class_="panel",
            ),
            ui.div(
                ui.h4("Predicted AQI Gauge"),
                output_widget("gauge_plot", height="260px"),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Advisory insight
        ui.output_ui("forecast_insight"),
        # Model transparency + pollutant mix
        ui.div(
            ui.div(
                ui.h4("How Accurate Is This?"),
                output_widget("accuracy_chart", height="320px"),
                ui.output_ui("accuracy_text"),
                class_="panel",
            ),
            ui.div(
                ui.h4("Feature Importance — What Drives the Prediction?"),
                output_widget("importance_plot", height="320px"),
                ui.output_ui("importance_insight"),
                class_="panel",
            ),
            class_="grid-2",
        ),
        # Validation
        ui.div(
            ui.h4("Model Validation — Recent Predictions vs Reality"),
            output_widget("validation_plot", height="340px"),
            ui.output_ui("validation_insight"),
            class_="panel",
        ),
    )


# ── Server ──────────────────────────────────────────────────────────────────────

@module.server
def forecast_server(
    input, output, session,
    *,
    prediction_context: Callable,
    get_model: Callable,
    snapshot: reactive.Value,
):
    @reactive.calc
    def current_model():
        target = "pm25" if input.target() == "PM2.5" else "aqi"
        horizon = HORIZONS[input.horizon()]
        return get_model(horizon, target)

    def current_prediction_context() -> dict[str, Any]:
        target = "pm25" if input.target() == "PM2.5" else "aqi"
        horizon = HORIZONS[input.horizon()]
        return prediction_context(horizon, target)

    @output
    @render.ui
    def prediction_hero():
        ctx = current_prediction_context()
        pred = ctx.get("pred")
        baseline = ctx.get("baseline")
        delta = ctx.get("delta", 0)
        horizon = HORIZONS[input.horizon()]

        if pred is None or pd.isna(pred):
            return ui.div(
                ui.h4("No prediction available"),
                ui.p("Enable realtime API or wait for data to load.", style="color:#6b7280;"),
            )

        color = aqi_color(pred)
        category = aqi_category(pred)
        direction = "higher" if delta >= 0 else "lower"

        return ui.div(
            ui.div(f"+{horizon}h Forecast", style="font-size:0.75rem;font-weight:700;color:#9aa0a6;text-transform:uppercase;letter-spacing:0.08em;"),
            ui.div(
                ui.tags.span(f"{pred:.0f}", style=f"font-size:3.5rem;font-weight:900;color:{color};line-height:1;"),
                ui.tags.span(f" {input.target()}", style="font-size:1.2rem;color:#6b7280;font-weight:600;"),
            ),
            ui.div(category, style=f"font-size:1.3rem;font-weight:700;color:{color};margin:4px 0;"),
            ui.div(
                f"{'↑' if delta >= 0 else '↓'} {abs(delta):.0f} {direction} than current ({baseline:.0f})",
                style=f"color:{'#d1495b' if delta >= 0 else '#2bb673'};font-weight:600;font-size:0.9rem;",
            ),
            ui.div(
                aqi_advisory(pred),
                style="color:#9aa0a6;margin-top:12px;font-size:0.9rem;line-height:1.5;",
            ),
        )

    @output
    @render_widget
    def gauge_plot():
        ctx = current_prediction_context()
        pred = ctx.get("pred")
        if pred is None or pd.isna(pred):
            return _blank("No forecast available")
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=float(pred),
            number={"suffix": f" {input.target()}", "font": {"size": 24, "color": "#e8eaed"}},
            gauge={
                "axis": {"range": [0, 500], "tickfont": {"size": 10, "color": "#6b7280"}},
                "bar": {"color": aqi_color(pred), "thickness": 0.75},
                "bgcolor": "#282c34",
                "bordercolor": "#363b44",
                "steps": [
                    {"range": [0, 50], "color": "rgba(43,182,115,0.15)"},
                    {"range": [50, 100], "color": "rgba(245,183,0,0.15)"},
                    {"range": [100, 150], "color": "rgba(242,143,59,0.15)"},
                    {"range": [150, 200], "color": "rgba(209,73,91,0.15)"},
                    {"range": [200, 300], "color": "rgba(123,44,191,0.15)"},
                    {"range": [300, 500], "color": "rgba(90,24,154,0.12)"},
                ],
            },
            domain={"x": [0.05, 0.95], "y": [0.1, 0.9]},
        ))
        fig.update_layout(
            height=260,
            margin={"l": 20, "r": 20, "t": 30, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            font={"family": "Inter, system-ui, sans-serif"},
        )
        return sanitize_figure(fig)

    @output
    @render.ui
    def forecast_insight():
        ctx = current_prediction_context()
        pred = ctx.get("pred")
        model = ctx.get("model")
        horizon = HORIZONS[input.horizon()]
        if pred is None or pd.isna(pred):
            return ui.div()
        model_info = ""
        if model is not None:
            improvement = 100 * (model.baseline_mae - model.mae) / model.baseline_mae if model.baseline_mae else 0
            model_info = f"Our {model.model_name} model is {improvement:.0f}% more accurate than simply assuming no change."
        return ui.div(
            ui.div("HOW WE PREDICT THIS", class_="insight-label"),
            ui.p(f"This {horizon}-hour forecast uses the latest air quality measurements, weather data (temperature, humidity, pressure), "
                 f"and time-of-day patterns. {model_info}"),
            class_="insight-box",
        )

    @output
    @render_widget
    def accuracy_chart():
        model = current_model()
        if model is None:
            return _blank("No model available")
        df = pd.DataFrame({
            "Metric": ["MAE", "MAE", "RMSE", "RMSE"],
            "Method": ["Our Model", "No-Change Baseline", "Our Model", "No-Change Baseline"],
            "Error": [model.mae, model.baseline_mae, model.rmse, model.baseline_rmse],
        })
        fig = px.bar(df, x="Metric", y="Error", color="Method", barmode="group",
                     color_discrete_map={"Our Model": "#1f9d8a", "No-Change Baseline": "#d1495b"})
        fig.update_layout(xaxis_title="", yaxis_title="Prediction Error", legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#9aa0a6"}})
        return _dark_fig(fig, height=320)

    @output
    @render.ui
    def accuracy_text():
        model = current_model()
        if model is None:
            return ui.div()
        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(f"Lower bars = better predictions. Our model predicts {input.target()} within ±{model.mae:.0f} points on average, "
                 f"compared to ±{model.baseline_mae:.0f} for the no-change baseline."),
            class_="insight-box",
        )

    @output
    @render_widget
    def importance_plot():
        model = current_model()
        if model is None or model.feature_importance.empty:
            return _blank("No feature data")
        imp = model.feature_importance.sort_values("importance", ascending=True).tail(10)
        imp["feature"] = imp["feature"].str.replace("_", " ").str.title()
        fig = px.bar(imp, x="importance", y="feature", orientation="h",
                     color="importance", color_continuous_scale="Tealgrn")
        fig.update_layout(xaxis_title="Importance Score", yaxis_title="", coloraxis_showscale=False)
        return _dark_fig(fig, height=320)

    @output
    @render.ui
    def importance_insight():
        model = current_model()
        if model is None or model.feature_importance.empty:
            return ui.div()
        top_feat = model.feature_importance.nlargest(3, "importance")["feature"].tolist()
        top_names = [f.replace("_", " ").title() for f in top_feat]
        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(f"The top predictors are: {', '.join(top_names)}. "
                 "These features have the strongest correlation with future air quality levels."),
            class_="insight-box",
        )

    @output
    @render_widget
    def validation_plot():
        model = current_model()
        if model is None or model.validation.empty:
            return _blank()
        val = model.validation.tail(24 * 30).copy()
        val["local_time"] = pd.to_datetime(val["local_time"], errors="coerce")
        val = val.dropna(subset=["local_time", "actual", "predicted"])
        if val.empty:
            return _blank()
        # Safe datetime conversion for strict JSON serialization.
        val["plot_time"] = val["local_time"].dt.tz_localize(None).dt.strftime("%Y-%m-%dT%H:%M:%S")
        x = list(val["plot_time"])
        # Replace any remaining NaN/inf with None for JSON safety
        actual = [float(v) if np.isfinite(v) else None for v in val["actual"]]
        predicted = [float(v) if np.isfinite(v) else None for v in val["predicted"]]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=actual, mode="lines", name="Actual", line={"color": "#e8eaed", "width": 1.5}))
        fig.add_trace(go.Scatter(x=x, y=predicted, mode="lines", name="Model Prediction", line={"color": "#1f9d8a", "width": 2}))
        if "baseline" in val.columns:
            baseline = [float(v) if np.isfinite(v) else None for v in val["baseline"]]
            fig.add_trace(go.Scatter(x=x, y=baseline, mode="lines", name="No-Change Baseline", line={"color": "#d1495b", "width": 1, "dash": "dot"}))
        fig.update_xaxes(type="date", tickformat="%b %d", title="")
        fig.update_yaxes(title=input.target())
        fig.update_layout(hovermode="x unified", legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "font": {"color": "#9aa0a6"}})
        return _dark_fig(fig, height=340)

    @output
    @render.ui
    def validation_insight():
        model = current_model()
        if model is None:
            return ui.div()
        return ui.div(
            ui.div("WHAT THIS SHOWS", class_="insight-label"),
            ui.p(f"White line = actual values, teal line = model predictions. "
                 f"Our model (MAE: {model.mae:.1f}) tracks the actual values more closely than the no-change baseline (MAE: {model.baseline_mae:.1f})."),
            class_="insight-box",
        )
