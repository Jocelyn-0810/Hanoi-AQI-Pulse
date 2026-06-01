"""Offline model training — trains AQI and PM2.5 models for all horizons."""
from __future__ import annotations

import sys
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DASHBOARD_ROOT.parent
if str(DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_ROOT))

from src.data import load_bundle
from src.model import save_model_artifact, train_city_model

DATA_ROOT = PROJECT_ROOT / "data"
MODEL_DIR = DASHBOARD_ROOT / "models"
HORIZONS = [1, 6, 24]
TARGETS = ["aqi", "pm25"]
DATA_MODES = ["raw", "cleaned"]


def main() -> None:
    bundle = load_bundle(DATA_ROOT)
    for data_mode in DATA_MODES:
        for target in TARGETS:
            for horizon in HORIZONS:
                print(f"\nTraining {target.upper()} +{horizon}h [{data_mode}] ...")
                artifact = train_city_model(
                    bundle.city_hourly,
                    horizon_hours=horizon,
                    target_col=target,
                    data_mode=data_mode,
                )
                path = save_model_artifact(artifact, MODEL_DIR)
                size_mb = path.stat().st_size / 1e6
                print(
                    f"  saved {path.name}: model={artifact.model_name}, "
                    f"MAE={artifact.mae:.2f}, RMSE={artifact.rmse:.2f}, "
                    f"baseline_MAE={artifact.baseline_mae:.2f}, "
                    f"size={size_mb:.1f}MB"
                )


if __name__ == "__main__":
    main()
