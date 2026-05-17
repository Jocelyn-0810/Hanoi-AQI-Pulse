"""Tests for src/model.py — feature engineering, training, prediction."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from src.data import load_bundle
from src.model import ModelArtifacts, _build_features, train_city_model, predict_next, load_model_artifact

PROJECT_ROOT = DASHBOARD_ROOT.parent
DATA_ROOT = PROJECT_ROOT / "data"
MODEL_DIR = DASHBOARD_ROOT / "models"


@pytest.fixture(scope="module")
def city_data():
    bundle = load_bundle(DATA_ROOT)
    return bundle.city_hourly


class TestBuildFeatures:
    def test_output_shape(self, city_data):
        X, y, cols, times = _build_features(city_data, horizon_hours=1)
        assert len(X) == len(y) == len(times)
        assert len(X) > 100

    def test_feature_cols_include_lags(self, city_data):
        _, _, cols, _ = _build_features(city_data, horizon_hours=1)
        assert "aqi_lag_1" in cols
        assert "pm25_roll_mean_24" in cols

    def test_feature_cols_include_time(self, city_data):
        _, _, cols, _ = _build_features(city_data, horizon_hours=1)
        assert "hour" in cols
        assert "dow" in cols

    def test_pm25_target(self, city_data):
        _, y, _, _ = _build_features(city_data, horizon_hours=1, target_col="pm25")
        assert y.name == "target"
        assert not y.isna().all()


class TestLoadModel:
    def test_loads_existing_aqi_1h(self):
        artifact = load_model_artifact(MODEL_DIR, 1, target_col="aqi")
        if artifact is not None:  # May not exist if models not trained
            assert isinstance(artifact, ModelArtifacts)
            assert artifact.horizon_hours == 1
            assert artifact.mae > 0

    def test_loads_pm25(self):
        artifact = load_model_artifact(MODEL_DIR, 1, target_col="pm25")
        if artifact is not None:
            assert artifact.target_col == "pm25"


class TestPrediction:
    def test_predict_returns_float(self, city_data):
        artifact = load_model_artifact(MODEL_DIR, 1, target_col="aqi")
        if artifact is None:
            pytest.skip("No model artifact available")
        result = predict_next(city_data, artifact)
        assert isinstance(result, float)
        assert not np.isnan(result)
        assert 0 <= result <= 500  # Reasonable AQI range
