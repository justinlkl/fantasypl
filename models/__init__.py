"""
models/  —  Feature engineering, training, and prediction.

Modules:
    feature_engineering  — rolling stats, lag features, xPts proxy, position signals
    train                — GBM + RF + Ridge ensemble with TimeSeriesSplit CV
    predict              — next-GW and 5-GW FDR-adjusted projections
"""
