"""
models/train.py  v3  —  Multi-model training with time-series CV + GridSearchCV tuning

Models trained per position:
  1. GradientBoostingRegressor  (primary — best for tabular FPL data)
  2. RandomForestRegressor       (secondary — good variance reduction)
  3. Ridge regression            (baseline — interpretable)
  4. Weighted ensemble of the three

Validation: TimeSeriesSplit by GW — never shuffles, always trains on past.
Hyperparameter tuning: GridSearchCV on GBM with tscv splits.
Best model selected by val MAE; all saved with joblib.
"""

import pandas as pd
import numpy as np
import joblib
import os
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, make_scorer

try:
    from scipy.stats import spearmanr
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

OUTPUT_DIR = Path(os.environ.get("FPL_ARTIFACTS_DIR",
                                Path.cwd() / "artifacts"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VAL_GWS  = 5     # Last N GWs of 2526 used for validation
MIN_ROWS = 200   # Minimum training rows to fit a model

# ── Default GBM params (before tuning) ────────────────────────────────────────
GBM_DEFAULTS = {
    "GK":  dict(n_estimators=200, learning_rate=0.05, max_depth=3,
                subsample=0.8, min_samples_leaf=15, random_state=42),
    "DEF": dict(n_estimators=400, learning_rate=0.04, max_depth=4,
                subsample=0.8, min_samples_leaf=10, random_state=42),
    "MID": dict(n_estimators=500, learning_rate=0.04, max_depth=4,
                subsample=0.8, min_samples_leaf=8,  random_state=42),
    "FWD": dict(n_estimators=300, learning_rate=0.05, max_depth=3,
                subsample=0.8, min_samples_leaf=12, random_state=42),
    "ALL": dict(n_estimators=500, learning_rate=0.04, max_depth=4,
                subsample=0.8, min_samples_leaf=8,  random_state=42),
}

# ── GridSearch param grid ──────────────────────────────────────────────────────
# Kept small to finish in reasonable time; expand for production
GBM_GRID = {
    "gbm__n_estimators":    [200, 400],
    "gbm__learning_rate":   [0.03, 0.06],
    "gbm__max_depth":       [3, 4],
    "gbm__min_samples_leaf":[8, 15],
}

RF_GRID = {
    "rf__n_estimators":   [200, 400],
    "rf__max_depth":      [6, 10, None],
    "rf__min_samples_leaf":[5, 12],
}


# ── Pipelines ─────────────────────────────────────────────────────────────────

def _gbm_pipe(params):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("gbm",     GradientBoostingRegressor(**params)),
    ])


def _rf_pipe():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf",      RandomForestRegressor(n_estimators=300, max_depth=8,
                                          min_samples_leaf=8, random_state=42,
                                          n_jobs=-1)),
    ])


def _ridge_pipe():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("ridge",   Ridge(alpha=10.0)),
    ])


# ── Time-series split ──────────────────────────────────────────────────────────

def _tscv_splits(df, n_splits=4):
    """
    Build TimeSeriesSplit indices keyed on gameweek order.
    Returns (train_idx, val_idx) pairs as INTEGER positions (0-based).
    """
    df = df.reset_index(drop=True)   # ensure 0-based integer index
    gws = sorted(df["gw"].unique())
    tscv = TimeSeriesSplit(n_splits=n_splits)
    result = []
    for tr_gw_idx, va_gw_idx in tscv.split(gws):
        tr_gws = {gws[i] for i in tr_gw_idx}
        va_gws = {gws[i] for i in va_gw_idx}
        tr_pos = df.index[df["gw"].isin(tr_gws)].tolist()
        va_pos = df.index[df["gw"].isin(va_gws)].tolist()
        if len(tr_pos) >= MIN_ROWS and len(va_pos) >= 20:
            result.append((tr_pos, va_pos))
    return result


def _holdout_split(df, val_gws=VAL_GWS):
    latest_s  = df["season"].max()
    latest_gw = df[df["season"] == latest_s]["gw"].max()
    cutoff    = latest_gw - val_gws
    train = df[(df["season"] != latest_s) | (df["gw"] <= cutoff)]
    val   = df[(df["season"] == latest_s) & (df["gw"] >  cutoff)]
    return train, val


def _rho(y_true, y_pred):
    if not _HAS_SCIPY or len(y_true) < 5:
        return float("nan")
    return float(spearmanr(y_true, y_pred)[0])


# ── GridSearchCV wrapper ───────────────────────────────────────────────────────

def _tune_gbm(X_tr, y_tr, base_params, splits, pos):
    """Run GridSearchCV on GBM with time-series splits. Returns best estimator."""
    print(f"    GridSearchCV ({len(splits)} splits)...", end=" ", flush=True)

    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("gbm",     GradientBoostingRegressor(random_state=42, subsample=0.8)),
    ])

    if not splits:
        print("no splits — using defaults")
        return _gbm_pipe(base_params).fit(X_tr, y_tr)

    neg_mae = make_scorer(mean_absolute_error, greater_is_better=False)

    gs = GridSearchCV(
        pipe, GBM_GRID, cv=splits, scoring=neg_mae,
        refit=True, n_jobs=1, verbose=0,   # n_jobs=1 avoids index issues in sandbox
    )
    # X_tr/y_tr must be numpy arrays with 0-based indexing
    if hasattr(X_tr, "values"):
        X_tr = X_tr.values
    if hasattr(y_tr, "values"):
        y_tr = y_tr.values

    gs.fit(X_tr, y_tr)
    best = gs.best_params_
    print(f"best: depth={best['gbm__max_depth']} lr={best['gbm__learning_rate']} "
          f"n={best['gbm__n_estimators']} leaf={best['gbm__min_samples_leaf']}")
    return gs.best_estimator_


# ── Ensemble weighting ────────────────────────────────────────────────────────

def _weighted_ensemble_predict(models, weights, X):
    """Weighted average of multiple model predictions."""
    preds = np.stack([m.predict(X) for m in models], axis=1)  # (n, 3)
    w = np.array(weights) / sum(weights)
    return preds @ w


def _optimise_weights(models, X_val, y_val):
    """Grid-search ensemble weights on validation set."""
    best_w, best_mae = (0.6, 0.3, 0.1), float("inf")
    for w0 in np.arange(0.3, 0.8, 0.1):
        for w1 in np.arange(0.1, 0.6, 0.1):
            w2 = max(1.0 - w0 - w1, 0.0)
            if abs(w0 + w1 + w2 - 1.0) > 0.05:
                continue
            p = _weighted_ensemble_predict(models, [w0, w1, w2], X_val)
            mae = mean_absolute_error(y_val, p)
            if mae < best_mae:
                best_mae = mae
                best_w = (round(w0, 1), round(w1, 1), round(w2, 1))
    return best_w, best_mae


# ── Main trainer ───────────────────────────────────────────────────────────────

def train_models(df: pd.DataFrame, feature_cols: dict,
                 tune: bool = True) -> tuple:
    """
    Train GBM + RF + Ridge per position.
    If tune=True, runs GridSearchCV for GBM (adds ~2-3 mins).
    Returns (models_dict, metrics_dict).
    """
    target   = "next_gw_points"
    played   = df[df["gw_minutes"] > 0].dropna(subset=[target]).copy()
    played   = played.sort_values(["player_id", "gw"]).reset_index(drop=True)

    print(f"\nTraining on {len(played):,} played rows "
          f"(of {len(df):,} total, val = last {VAL_GWS} GWs of 2526)")

    all_models  = {}   # {pos: {"gbm": pipe, "rf": pipe, "ridge": pipe, "weights": (w0,w1,w2)}}
    metrics     = {}

    for pos in ["GK", "DEF", "MID", "FWD", "ALL"]:
        print(f"\n  {'─'*56}")
        print(f"  Position: {pos}")

        feats  = feature_cols[pos]
        subset = played if pos == "ALL" else played[played["position"] == pos]
        if len(subset) < MIN_ROWS:
            print(f"  Skipping — only {len(subset)} rows")
            continue

        train_df, val_df = _holdout_split(subset)
        if len(train_df) < MIN_ROWS:
            print(f"  Skipping — {len(train_df)} training rows after split")
            continue

        print(f"  Train: {len(train_df):,}  Val: {len(val_df):,}  "
              f"Features: {len(feats)}")

        X_tr = train_df[feats];  y_tr = train_df[target]
        X_va = val_df[feats];    y_va = val_df[target]

        # Build time-series CV splits from training data only
        cv_splits = _tscv_splits(train_df, n_splits=4)

        # ── GBM ──────────────────────────────────────────────────────────
        print("    Training GBM...", end=" ", flush=True)
        if tune and len(cv_splits) >= 2:
            gbm_model = _tune_gbm(X_tr.values, y_tr.values, GBM_DEFAULTS[pos],
                                  cv_splits, pos)
        else:
            gbm_model = _gbm_pipe(GBM_DEFAULTS[pos]).fit(X_tr, y_tr)
            print("(no tuning)")

        # ── RF ───────────────────────────────────────────────────────────
        print("    Training RF...", end=" ", flush=True)
        rf_model = _rf_pipe().fit(X_tr, y_tr)
        print("done")

        # ── Ridge ────────────────────────────────────────────────────────
        print("    Training Ridge...", end=" ", flush=True)
        ridge_model = _ridge_pipe().fit(X_tr, y_tr)
        print("done")

        # ── Optimise ensemble weights ──────────────────────────────────
        models_list = [gbm_model, rf_model, ridge_model]
        best_w, ens_mae_val = _optimise_weights(models_list, X_va, y_va)
        print(f"    Ensemble weights (GBM/RF/Ridge): {best_w}  val_MAE={ens_mae_val:.3f}")

        # Individual val metrics
        for name, m in [("GBM", gbm_model), ("RF", rf_model), ("Ridge", ridge_model)]:
            va_pred = m.predict(X_va)
            va_mae  = mean_absolute_error(y_va, va_pred)
            va_rho  = _rho(y_va, va_pred)
            tr_mae  = mean_absolute_error(y_tr, m.predict(X_tr))
            print(f"    {name:6s}: train_MAE={tr_mae:.3f}  val_MAE={va_mae:.3f}  "
                  f"val_ρ={va_rho:.3f}")

        ens_rho = _rho(y_va, _weighted_ensemble_predict(models_list, best_w, X_va))
        print(f"    Ensemble val_MAE={ens_mae_val:.3f}  val_ρ={ens_rho:.3f}")

        all_models[pos] = {
            "gbm": gbm_model, "rf": rf_model, "ridge": ridge_model,
            "weights": best_w, "features": feats,
        }
        metrics[pos] = {
            "val_mae": ens_mae_val, "val_rho": ens_rho,
            "n_train": len(train_df), "n_val": len(val_df),
            "n_features": len(feats), "ensemble_weights": best_w,
        }

        # Save each model
        path = OUTPUT_DIR / f"model_{pos}.joblib"
        joblib.dump(all_models[pos], str(path))
        print(f"    Saved → {path.name}")

    joblib.dump({"feature_cols": feature_cols, "val_gws": VAL_GWS,
                 "metrics": metrics},
                str(OUTPUT_DIR / "metadata.joblib"))
    print(f"\n  All artefacts saved to {OUTPUT_DIR}/")
    return all_models, metrics


def feature_importance(models: dict, feature_cols: dict) -> pd.DataFrame:
    rows = []
    for pos, obj in models.items():
        if pos == "ALL":
            continue
        feats = obj["features"]
        for model_name, step_name in [("gbm", "gbm"), ("rf", "rf")]:
            m = obj.get(model_name)
            if m is None:
                continue
            try:
                imp = m.named_steps[step_name].feature_importances_
                for feat, score in zip(feats, imp):
                    rows.append({"position": pos, "model": model_name,
                                 "feature": feat, "importance": score})
            except Exception:
                pass

    if not rows:
        return pd.DataFrame()

    df_imp = pd.DataFrame(rows)
    # Average across GBM and RF
    avg = (df_imp.groupby(["position", "feature"])["importance"]
           .mean().reset_index()
           .sort_values(["position", "importance"], ascending=[True, False]))
    return avg
