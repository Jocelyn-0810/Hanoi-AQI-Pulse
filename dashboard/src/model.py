"""ML pipeline — feature engineering, model selection, training, inference, persistence.

Supports both AQI and PM2.5 targets with multiple forecast horizons.
Uses permutation importance for feature ranking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.anomaly import metric_col_for_mode


@dataclass
class ModelArtifacts:
    horizon_hours: int
    model: HistGradientBoostingRegressor
    feature_cols: list[str]
    mae: float
    rmse: float
    baseline_mae: float
    baseline_rmse: float
    validation: pd.DataFrame
    feature_importance: pd.DataFrame
    model_name: str
    trained_rows: int
    target_col: str = "aqi"
    data_mode: str = "raw"


FEATURE_BASE = [
    "aqi", "pm25", "pm10", "co", "no2", "o3", "so2",
    "clouds", "precipitation", "pressure", "relative_humidity",
    "temperature", "uv_index", "wind_speed",
]


def _safe_numeric(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _build_features(
    city_hourly: pd.DataFrame,
    horizon_hours: int,
    target_col: str = "aqi",
    data_mode: str = "raw",
) -> tuple[pd.DataFrame, pd.Series, list[str], pd.Series]:
    df = city_hourly.sort_values("local_time").copy()
    df = _safe_numeric(df, FEATURE_BASE)
    if data_mode == "cleaned":
        for col in FEATURE_BASE:
            clean_col = metric_col_for_mode(df, col, data_mode)
            if clean_col in df.columns:
                df[col] = pd.to_numeric(df[clean_col], errors="coerce")

    # Time features
    df["hour"] = df["local_time"].dt.hour
    df["dow"] = df["local_time"].dt.dayofweek
    df["month"] = df["local_time"].dt.month
    df["is_weekend"] = (df["dow"] >= 5).astype(int)

    # Lag and rolling windows
    for c in ["aqi", "pm25"]:
        if c not in df.columns:
            continue
        for lag in [1, 6, 24]:
            df[f"{c}_lag_{lag}"] = df[c].shift(lag)
        for w in [3, 6, 24]:
            df[f"{c}_roll_mean_{w}"] = df[c].rolling(w).mean()
            df[f"{c}_roll_max_{w}"] = df[c].rolling(w).max()

    df["target"] = df[target_col].shift(-horizon_hours)

    feature_cols = [
        c for c in df.columns
        if c in FEATURE_BASE
        or c in {"hour", "dow", "month", "is_weekend"}
        or c.startswith("aqi_lag_") or c.startswith("pm25_lag_")
        or c.startswith("aqi_roll_") or c.startswith("pm25_roll_")
    ]
    model_df = df.dropna(subset=feature_cols + ["target"]).copy()
    X = model_df[feature_cols]
    y = model_df["target"]
    times = model_df["local_time"]
    return X, y, feature_cols, times


def _candidate_models(horizon_hours: int) -> dict[str, object]:
    """All candidates are HistGradientBoosting variants for deployment-friendly size."""
    candidates: dict[str, object] = {
        "HistGB-Squared": HistGradientBoostingRegressor(
            loss="squared_error", max_depth=6, max_iter=300,
            learning_rate=0.05, l2_regularization=0.01, random_state=42,
        ),
        "HistGB-Absolute": HistGradientBoostingRegressor(
            loss="absolute_error", max_depth=6, max_iter=300,
            learning_rate=0.05, l2_regularization=0.02, random_state=42,
        ),
        "HistGB-Deep": HistGradientBoostingRegressor(
            loss="squared_error", max_depth=8, max_iter=400,
            learning_rate=0.04, l2_regularization=0.005,
            min_samples_leaf=10, random_state=42,
        ),
    }
    # Prefer absolute loss for short horizons (handles abrupt jumps)
    if horizon_hours <= 1:
        return {"HistGB-Absolute": candidates["HistGB-Absolute"], **candidates}
    # Prefer deeper model for long horizons
    if horizon_hours >= 24:
        return {"HistGB-Deep": candidates["HistGB-Deep"], **candidates}
    return candidates


def _compute_permutation_importance(
    model, X_test: pd.DataFrame, y_test: pd.Series, feature_cols: list[str], n_repeats: int = 5,
) -> pd.DataFrame:
    """Compute permutation-based feature importance on the test set."""
    try:
        result = permutation_importance(model, X_test, y_test, n_repeats=n_repeats, random_state=42, n_jobs=-1)
        imp = pd.DataFrame({
            "feature": feature_cols,
            "importance": result.importances_mean,
        }).sort_values("importance", ascending=False).head(14)
        return imp
    except Exception:
        # Fallback: tree-based importance if available
        if hasattr(model, "feature_importances_"):
            imp = pd.DataFrame({
                "feature": feature_cols,
                "importance": model.feature_importances_,
            }).sort_values("importance", ascending=False).head(14)
            return imp
        return pd.DataFrame(columns=["feature", "importance"])


def train_city_model(
    city_hourly: pd.DataFrame,
    horizon_hours: int = 1,
    target_col: str = "aqi",
    data_mode: str = "raw",
) -> ModelArtifacts:
    X, y, feature_cols, times = _build_features(
        city_hourly,
        horizon_hours=horizon_hours,
        target_col=target_col,
        data_mode=data_mode,
    )
    if len(X) < 200:
        raise ValueError("Not enough rows after feature engineering to train model.")

    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    t_test = times.iloc[split_idx:]

    best_name = ""
    best_model_obj = None
    best_preds: np.ndarray | None = None
    best_mae = float("inf")
    best_rmse = float("inf")

    for name, candidate in _candidate_models(horizon_hours).items():
        model_for_eval = clone(candidate)
        model_for_eval.fit(X_train, y_train)
        candidate_preds = model_for_eval.predict(X_test)
        candidate_mae = float(mean_absolute_error(y_test, candidate_preds))
        candidate_rmse = float(np.sqrt(mean_squared_error(y_test, candidate_preds)))
        if candidate_mae < best_mae:
            best_name = name
            best_model_obj = model_for_eval
            best_preds = candidate_preds
            best_mae = candidate_mae
            best_rmse = candidate_rmse

    if best_model_obj is None or best_preds is None:
        raise RuntimeError("No model candidate was trained successfully.")

    # Final model trained on all data
    final_model = clone(best_model_obj)
    final_model.fit(X, y)

    # Persistence baseline
    baseline_col = target_col if target_col in X_test.columns else "aqi"
    baseline = X_test[baseline_col].to_numpy()
    baseline_mae = float(mean_absolute_error(y_test, baseline))
    baseline_rmse = float(np.sqrt(mean_squared_error(y_test, baseline)))

    validation = pd.DataFrame({
        "local_time": pd.to_datetime(t_test).to_numpy(),
        "actual": y_test.to_numpy(dtype=float),
        "predicted": best_preds.astype(float),
        "baseline": baseline.astype(float),
    })

    # Permutation importance
    importance = _compute_permutation_importance(best_model_obj, X_test, y_test, feature_cols)

    return ModelArtifacts(
        horizon_hours=horizon_hours,
        model=final_model,
        feature_cols=feature_cols,
        mae=best_mae,
        rmse=best_rmse,
        baseline_mae=baseline_mae,
        baseline_rmse=baseline_rmse,
        validation=validation,
        feature_importance=importance,
        model_name=best_name,
        trained_rows=len(X),
        target_col=target_col,
        data_mode=data_mode,
    )


def predict_next(
    city_hourly: pd.DataFrame,
    artifacts: ModelArtifacts,
    overrides: dict[str, float] | None = None,
) -> float:
    """Predict next AQI or PM2.5 value."""
    df = city_hourly.sort_values("local_time").copy()
    if getattr(artifacts, "data_mode", "raw") == "cleaned":
        for col in FEATURE_BASE:
            clean_col = metric_col_for_mode(df, col, "cleaned")
            if clean_col in df.columns:
                df[col] = pd.to_numeric(df[clean_col], errors="coerce")
    row = df.iloc[-1:].copy()
    now = pd.Timestamp.now()
    row["hour"] = now.hour
    row["dow"] = now.dayofweek
    row["month"] = now.month
    row["is_weekend"] = int(now.dayofweek >= 5)

    for c in ["aqi", "pm25"]:
        if c not in df.columns:
            continue
        for lag in [1, 6, 24]:
            row[f"{c}_lag_{lag}"] = df[c].shift(lag).iloc[-1]
        for w in [3, 6, 24]:
            roll = df[c].rolling(w)
            row[f"{c}_roll_mean_{w}"] = roll.mean().iloc[-1]
            row[f"{c}_roll_max_{w}"] = roll.max().iloc[-1]

    if overrides:
        for k, v in overrides.items():
            if k in row.columns:
                row[k] = v

    row = row[artifacts.feature_cols].copy()
    row = row.ffill(axis=0).fillna(0.0)
    pred = artifacts.model.predict(row)[0]
    return float(pred)


# Backward-compatible alias
predict_next_aqi = predict_next


def model_path(model_dir: Path, horizon_hours: int, target_col: str = "aqi", data_mode: str = "raw") -> Path:
    suffix = "" if data_mode == "raw" else f"_{data_mode}"
    return model_dir / f"{target_col}_horizon_{horizon_hours}h{suffix}.joblib"


def save_model_artifact(artifact: ModelArtifacts, model_dir: Path) -> Path:
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_path(model_dir, artifact.horizon_hours, artifact.target_col, getattr(artifact, "data_mode", "raw"))
    joblib.dump(artifact, path, compress=5)
    return path


def load_model_artifact(model_dir: Path, horizon_hours: int, target_col: str = "aqi", data_mode: str = "raw") -> ModelArtifacts | None:
    path = model_path(model_dir, horizon_hours, target_col, data_mode)
    if not path.exists():
        return None
    try:
        artifact = joblib.load(path)
        if not isinstance(artifact, ModelArtifacts):
            return None
        if not hasattr(artifact, "data_mode"):
            artifact.data_mode = data_mode
        return artifact
    except Exception:
        return None
