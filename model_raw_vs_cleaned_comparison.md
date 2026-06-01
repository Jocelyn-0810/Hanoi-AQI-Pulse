# Raw vs Cleaned Model Comparison

Validation uses the saved model artifacts currently in `dashboard/models`.
Lower MAE/RMSE is better. The no-change baseline predicts that the future value equals the latest observed value.

| Target | Horizon | Raw MAE | Cleaned MAE | MAE Change | Raw RMSE | Cleaned RMSE | RMSE Change | Cleaned Takeaway |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| AQI | +1h | 18.70 | 18.80 | +0.11 | 29.17 | 29.39 | +0.22 | Similar; cleaning does not help very short AQI prediction. |
| AQI | +6h | 30.42 | 30.33 | -0.09 | 40.35 | 40.18 | -0.17 | Slightly better after cleaning. |
| AQI | +24h | 35.05 | 35.37 | +0.32 | 45.92 | 46.89 | +0.97 | Slightly worse; AQI extreme episodes may contain useful signal. |
| PM2.5 | +1h | 12.05 | 11.89 | -0.15 | 21.82 | 21.36 | -0.46 | Better after cleaning. |
| PM2.5 | +6h | 21.12 | 20.82 | -0.30 | 31.93 | 31.35 | -0.58 | Better after cleaning. |
| PM2.5 | +24h | 24.87 | 24.59 | -0.29 | 36.70 | 36.06 | -0.63 | Better after cleaning. |

## Presenter Notes

Cleaned mode is conservative: it smooths isolated sensor-like spikes and physically invalid values, while preserving likely real multi-pollutant pollution episodes.

The results show that cleaning is not a cosmetic step. It improves PM2.5 forecasts across all horizons and slightly improves AQI at +6h, but AQI +1h and +24h are similar or slightly worse. This is useful because it shows we did not blindly remove outliers. Some AQI spikes are real pollution signals, so the dashboard keeps both Raw and Cleaned modes for transparent comparison.

Best short explanation:

> Cleaning helps stabilize noisy pollutant measurements, especially PM2.5, but we keep raw mode because some extreme AQI events are meaningful pollution episodes rather than errors.

## How We Detect and Filter Outliers

We use a conservative anomaly pipeline instead of simply deleting high AQI/PM2.5 values.

1. **Physical validity check:** values outside plausible physical ranges are flagged, for example negative pollutant values, humidity outside 0-100%, or impossible AQI values.
2. **Robust local anomaly score:** for each pollutant, we compare the current hourly value against a rolling local median using MAD/robust z-score. This is less sensitive to extreme spikes than mean/std.
3. **Sensor-like spike vs pollution episode:** if only one pollutant suddenly spikes and nearby hours do not support it, it is treated as likely sensor/API noise. If multiple pollutants rise together, we treat it as a possible real pollution episode and keep it.
4. **Cleaned mode:** only physically invalid or isolated sensor-like spikes are smoothed using nearby valid values. Real multi-pollutant episodes remain in the data.
5. **Dashboard transparency:** users can switch between Raw and Cleaned modes, and flagged days are available as optional markers.

Short presentation line:

> We do not remove outliers blindly. We separate likely sensor noise from real pollution episodes, then only smooth isolated or physically invalid spikes while preserving extreme events that may be environmentally meaningful.
