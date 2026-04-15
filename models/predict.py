"""
models/predict.py  v4
Generates next-5-GW predictions with FDR-adjusted per-GW breakdowns.

Changes from v3:
  - Moved into models/ module
  - Imports fdr helpers from etl.fdr (not root fdr)
  - MODEL_DIR resolved via FPL_ARTIFACTS_DIR env var
  - predict_all_players / build_5gw_projections / top_picks / format_table
    are all unchanged in logic
"""

import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MODEL_DIR = Path(os.environ.get("FPL_ARTIFACTS_DIR", Path.cwd() / "artifacts"))

# ── Model loading ──────────────────────────────────────────────────────────────

def _load():
    models, meta = {}, {}
    for pos in ["GK", "DEF", "MID", "FWD", "ALL"]:
        p = MODEL_DIR / f"model_{pos}.joblib"
        if p.exists():
            models[pos] = joblib.load(str(p))
    p2 = MODEL_DIR / "metadata.joblib"
    if p2.exists():
        meta = joblib.load(str(p2))
    return models, meta


def _ensemble_predict(obj: dict, X) -> np.ndarray:
    """Weighted ensemble of GBM, RF, Ridge."""
    preds = []
    for name in ["gbm", "rf", "ridge"]:
        m = obj.get(name)
        if m is not None:
            preds.append(m.predict(X))
    if not preds:
        raise ValueError("No sub-models found in model object")
    weights = list(obj.get("weights", (0.6, 0.3, 0.1)))[: len(preds)]
    w = np.array(weights) / sum(weights)
    return np.stack(preds, axis=1) @ w


# ── Core prediction ────────────────────────────────────────────────────────────

DISPLAY_COLS = [
    "player_id", "web_name", "position", "team_code",
    "now_cost", "selected_by_percent",
    "form", "predicted_pts", "xpts_proxy",
    "r3_event_points", "r5_event_points", "r10_event_points",
    "chance_of_playing_next_round", "is_unavailable",
    # Underlying stats
    "expected_goals_per_90", "expected_assists_per_90",
    "expected_goal_involvements_per_90", "expected_goals_conceded_per_90",
    "r5_gw_expected_goals", "r5_gw_expected_assists",
    "r5_gw_expected_goal_involvements",
    "saves_per_90", "clean_sheets_per_90", "goals_conceded_per_90",
    "defensive_contribution_per_90",
    # Opta per-90 (2425 only)
    "xg_per90", "xa_per90", "xgi_per90",
    "shots_per90", "sot_per90", "chances_per90", "box_touches_per90",
    "tackles_per90", "interceptions_per90",
    # Flags
    "is_new_player", "team_changed",
    "is_penalties_taker", "is_corners_and_indirect_freekicks_taker",
    # Price / ownership
    "price_change", "ownership_vs_pos", "ownership_change",
    # Team strength
    "team_attack_rel", "team_defence_rel", "elo",
    "gw",
]


def predict_all_players(df: pd.DataFrame) -> pd.DataFrame:
    """
    Predict next-GW points for every player using their latest data.
    Returns one row per player sorted by predicted_pts.
    """
    models, meta = _load()
    if not models:
        raise RuntimeError("No trained models found. Run train first.")
    feature_cols = meta.get("feature_cols", {})

    latest = (df.sort_values(["player_id", "season", "gw"])
                .groupby("player_id").last().reset_index())

    pieces = []
    for pos in ["GK", "DEF", "MID", "FWD"]:
        sub   = latest[latest["position"] == pos].copy()
        if sub.empty:
            continue
        obj   = models.get(pos) or models.get("ALL")
        feats = feature_cols.get(pos, feature_cols.get("ALL", []))
        if not obj or not feats:
            continue
        sub["predicted_pts"] = _ensemble_predict(obj, sub[feats]).clip(min=0)
        pieces.append(sub)

    if not pieces:
        raise RuntimeError("No predictions produced.")

    out     = pd.concat(pieces, ignore_index=True)
    display = [c for c in DISPLAY_COLS if c in out.columns]

    out = (out[display]
             .sort_values("predicted_pts", ascending=False)
             .reset_index(drop=True))
    out.index += 1

    if "now_cost" in out.columns:
        out["price_m"] = out["now_cost"].round(1)

    return out


def build_5gw_projections(df: pd.DataFrame,
                           schedule: pd.DataFrame = None) -> pd.DataFrame:
    """
    Build the full 5-GW projection table for the dashboard.

    Each per-GW prediction is FDR-adjusted if schedule is provided.
    Adds columns: gw{N}_pred, gw{N}_opp, gw{N}_fdr, pts_next5.
    """
    from etl.fdr import add_fdr_to_predictions

    preds = predict_all_players(df)
    if schedule is not None and not schedule.empty:
        preds = add_fdr_to_predictions(preds, schedule)

    sort_col = "pts_next5" if "pts_next5" in preds.columns else "predicted_pts"
    preds = preds.sort_values(sort_col, ascending=False).reset_index(drop=True)
    preds.index += 1
    return preds


def top_picks(df: pd.DataFrame,
              schedule: pd.DataFrame = None,
              n_each: dict = None,
              max_price: float = None,
              available_only: bool = True) -> dict:
    """
    Top picks per position + overall. Returns a dict keyed by position.
    """
    if n_each is None:
        n_each = {"GK": 6, "DEF": 12, "MID": 15, "FWD": 10}

    preds = build_5gw_projections(df, schedule)

    if available_only and "chance_of_playing_next_round" in preds.columns:
        cop   = preds["chance_of_playing_next_round"].fillna(1.0)
        preds = preds[cop >= 0.25]

    if max_price is not None and "price_m" in preds.columns:
        preds = preds[preds["price_m"] <= max_price]

    sort_col = "pts_next5" if "pts_next5" in preds.columns else "predicted_pts"
    result   = {"ALL": preds.head(25), "FULL": preds}
    for pos, n in n_each.items():
        result[pos] = preds[preds["position"] == pos].head(n).copy()

    return result


# ── CLI formatting ─────────────────────────────────────────────────────────────

def format_table(preds: pd.DataFrame, title: str = "", n: int = 15) -> None:
    preds = preds.head(n)
    display_cols = {
        "web_name":       "Player",
        "position":       "Pos",
        "price_m":        "£M",
        "predicted_pts":  "Next GW",
        "pts_next5":      "5-GW Total",
        "r5_event_points":"Form5",
        "chance_of_playing_next_round": "Avail%",
        "expected_goal_involvements_per_90": "xGI/90",
        "xpts_proxy":     "xPts",
    }
    show = {k: v for k, v in display_cols.items() if k in preds.columns}

    print(f"\n{'═'*74}")
    print(f"  {title}")
    print(f"{'═'*74}")
    print("  " + "  ".join(f"{v:<11}" for v in show.values()))
    print("  " + "─" * 68)

    def fmt(v, col):
        if pd.isna(v):
            return "  —        "
        if col == "price_m":
            return f"£{v:.1f}m      "
        if col in ("predicted_pts", "pts_next5", "xpts_proxy", "r5_event_points"):
            return f"{v:.2f}       "
        if col == "chance_of_playing_next_round":
            return f"{v*100:.0f}%         "
        if col == "expected_goal_involvements_per_90":
            return f"{v:.3f}      "
        return f"{str(v):<11}"

    for rank, row in preds.iterrows():
        vals = "  ".join(fmt(row[c], c) for c in show)
        print(f"  {rank:>4}.  {vals}")
    print()
