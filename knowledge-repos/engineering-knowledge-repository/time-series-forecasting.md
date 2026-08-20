---
id: time-series-forecasting
tags: [pattern, ai-ml, backend, data]
surfaces-at: [application-design, functional-design]
related: [anomaly-detection, feature-engineering, cross-validation, model-evaluation-metrics, hyperparameter-tuning]
complexity: intermediate
---

# Time Series Forecasting

## What It Is
Predicting future values of a variable based on its historical pattern over time. Time series forecasting is distinct from standard regression because observations are temporally ordered and correlated — future values depend on past values, and this temporal structure must be preserved in modeling and evaluation. Common applications: demand forecasting, financial time series, energy consumption, traffic prediction, capacity planning.

## When to Apply
- Predicting future values of any temporally ordered metric
- Demand planning, inventory optimization, capacity forecasting
- Anomaly detection on time series (forecast + flag deviations from forecast)
- Any problem where "what will this value be at time T" is the question

## Key Concepts
- **Stationarity**: A time series is stationary if its statistical properties (mean, variance) don't change over time. Many classical methods require stationarity. Apply differencing or log transformation to achieve it. Test with Augmented Dickey-Fuller
- **Trend and Seasonality**: Trend is the long-term direction; seasonality is repeating patterns (daily, weekly, yearly). Decompose and model these components explicitly — they're often the dominant signal
- **Classical Methods**:
  - *ARIMA*: Autoregressive Integrated Moving Average — models the time series as a function of its own past values and past errors. Effective for univariate stationary series
  - *SARIMA*: ARIMA with seasonal components. Good for data with strong seasonality
  - *Exponential Smoothing (ETS)*: Weighted average of past observations with exponentially decaying weights. Simple, interpretable, strong baseline
- **Prophet (Meta)**: Additive model with automatic trend, seasonality, and holiday components. Handles missing data and outliers well. Minimal tuning required. Excellent practical baseline for business forecasting
- **Gradient Boosted Trees (LightGBM/XGBoost)**: Powerful for multivariate forecasting — incorporate many lag features, rolling statistics, and external regressors. Often outperforms ARIMA in practice on real-world data with complex patterns
- **LSTM / Temporal Convolutional Networks**: Deep learning approaches for complex sequential patterns. Higher data requirements; harder to tune than gradient boosted trees. Use when dataset is large and patterns are non-linear
- **Feature Engineering for Time Series**: Lag features (value at T-1, T-7, T-30), rolling statistics (7-day average, 30-day std), calendar features (day of week, month, holiday flags), difference features. Essential for tree-based models
- **Temporal Train/Test Split**: Never shuffle time series data for evaluation. Split by time — train on past, evaluate on future. Use `TimeSeriesSplit` for cross-validation
- **Forecast Horizon**: How far ahead to forecast affects model selection. Short-horizon (hours, days) forecasts are more accurate; long-horizon forecasts degrade quickly. Multi-step forecasting can be direct (separate model per horizon) or recursive (feed predictions as inputs)
- **Evaluation Metrics**: MAE, RMSE for point forecasts. MAPE (mean absolute percentage error) for relative error — avoid when actuals approach zero. Prediction intervals for uncertainty quantification

## In Practice
Method uses Prophet as the default baseline for business time series forecasting (demand, revenue). LightGBM with lag features is applied when multivariate data and higher accuracy are required. Temporal cross-validation is mandatory — no shuffling. Forecast accuracy is evaluated on a held-out future period matching the intended forecast horizon.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Time Series Forecasting**: Start with Prophet — it handles trend, seasonality, and holidays with minimal configuration and produces good baselines for business forecasting. For multivariate data, LightGBM with lag features and rolling statistics often outperforms classical methods and LSTM with far less tuning. Never shuffle time series for train/test split — always split by time, train on past, evaluate on future. Match your evaluation horizon to your deployment horizon — a model evaluated on 1-day-ahead forecasts may be terrible at 30-day-ahead. Stationarity matters for ARIMA; Prophet and tree models handle non-stationarity automatically. → `engineering-knowledge-repository/time-series-forecasting.md`

## Related Entries
- [Anomaly Detection](anomaly-detection.md) — time series anomaly detection identifies deviations from forecasted behavior
- [Feature Engineering](feature-engineering.md) — lag features, rolling statistics, and calendar features are critical for tree-based time series models
- [Cross-Validation](cross-validation.md) — temporal cross-validation (TimeSeriesSplit) is required for time series evaluation
- [Model Evaluation Metrics](model-evaluation-metrics.md) — MAE, RMSE, MAPE are the standard time series forecast metrics
- [Hyperparameter Tuning](hyperparameter-tuning.md) — ARIMA order and LightGBM hyperparameters require tuning for time series models
