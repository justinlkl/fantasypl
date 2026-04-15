"""
run_pipeline.py  v4
Full FPL prediction pipeline — now module-oriented.

Imports from:
    etl/data_loader.py        — data loading
    etl/fdr.py                — FDR + fixture schedule
    models/feature_engineering.py — feature engineering
    models/train.py           — model training
    models/predict.py         — predictions

Data directory:   FPL_DATA_DIR      env var (default: ./data)
Artifacts:        FPL_ARTIFACTS_DIR env var (default: ./artifacts)

Usage:
    python run_pipeline.py              # full run with GridSearchCV
    python run_pipeline.py --no-tune   # skip GridSearchCV (~5 mins faster)
    python run_pipeline.py --no-save   # don't write CSVs (useful for testing)
"""

import argparse
import os
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

# Add project root to path (enables `python run_pipeline.py` from project root)
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ── Module imports ─────────────────────────────────────────────────────────────
from etl.data_loader         import build_dataset, update_2526_from_github
from etl.fdr                 import build_fdr_table, build_fixture_schedule
from models.feature_engineering import engineer_features, get_feature_columns
from models.train            import train_models, feature_importance
from models.predict          import top_picks, format_table

OUT = Path(os.environ.get("FPL_ARTIFACTS_DIR", PROJECT_ROOT / "artifacts"))
OUT.mkdir(parents=True, exist_ok=True)


def run_pipeline(tune_gbm: bool = True, save_csv: bool = True):
    bar = "═" * 66

    print(f"\n{bar}")
    print("  FPL PREDICTION PIPELINE  v4")
    print(bar)

    # ── 1. Update remote data ──────────────────────────────────────────────
    print("\n[1/5]  Ensuring latest 25-26 CSVs...")
    try:
        res     = update_2526_from_github()
        updated = [k for k, v in res.items() if v.get("updated")]
        print(f"  {'Updated: ' + ', '.join(updated) if updated else 'No changes.'}")
    except Exception as e:
        print(f"  Remote update failed (continuing with local data): {e}")

    # ── 2. Load data ──────────────────────────────────────────────────────
    print("\n[2/5]  Loading & cleaning data...")
    df = build_dataset()

    s26 = df[df["season"] == "2526"]
    s25 = df[df["season"] == "2425"]
    current_gw = int(s26["gw"].max())

    print(f"\n  Seasons: 24-25 ({len(s25):,} rows)  +  25-26 ({len(s26):,} rows)")
    print(f"  Current GW: {current_gw}  |  Next 5 GWs: {current_gw+1}–{current_gw+5}")
    print(f"  Players who changed clubs: {df[df['team_changed']==True]['player_id'].nunique()}")
    print(f"  New players (25-26 only):  {df[df['is_new_player']==True]['player_id'].nunique()}")

    # ── 3. Feature engineering ─────────────────────────────────────────────
    print("\n[3/5]  Engineering features...")
    df = engineer_features(df)
    fc = get_feature_columns(df)

    print("\n  Feature counts:")
    for pos, feats in fc.items():
        print(f"    {pos:4s}: {len(feats):3d}")

    # ── 4. FDR fixture schedule ────────────────────────────────────────────
    print("\n[4/5]  Building FDR fixture schedule (next 5 GWs)...")
    fdr_tbl  = build_fdr_table("2526")
    schedule = build_fixture_schedule(season="2526", n_future_gws=5)

    print(f"  FDR table: {len(fdr_tbl)} teams")
    print(f"  Fixture schedule: {len(schedule)} rows "
          f"(GWs {schedule['gw'].min()}–{schedule['gw'].max()})")

    print("\n  Team FDR overview (fdr | att | def | ELO):")
    for _, r in fdr_tbl.sort_values("fdr").iterrows():
        print(f"    {str(r['name']):<18} fdr={r['fdr']}  "
              f"att={int(r['attack_fdr_home'])}  def={int(r['defence_fdr_home'])}  "
              f"ELO={int(r['elo'])}")

    # ── 5. Train ───────────────────────────────────────────────────────────
    print(f"\n[5/5]  Training models (tune_gbm={tune_gbm})...")
    models, metrics = train_models(df, fc, tune=tune_gbm)

    print(f"\n  {'Pos':5} {'Val MAE':>8} {'Val ρ':>7} {'Wts (G/R/L)':>14} {'#Train':>8}")
    print("  " + "─" * 48)
    for pos, m in metrics.items():
        vm  = f"{m['val_mae']:.3f}" if m.get("val_mae")  else "  —"
        vr  = f"{m['val_rho']:.3f}" if m.get("val_rho")  else "  —"
        wts = str(m.get("ensemble_weights", "—"))
        print(f"  {pos:5} {vm:>8} {vr:>7} {wts:>14} {m['n_train']:>8,}")

    imp = feature_importance(models, fc)
    if not imp.empty:
        print("\n  Top 5 features by position:")
        for pos in ["GK", "DEF", "MID", "FWD"]:
            top = imp[imp["position"] == pos].head(5)["feature"].tolist()
            print(f"    {pos}: {', '.join(top)}")

    # ── Predict ────────────────────────────────────────────────────────────
    print("\n  Generating 5-GW projections...")
    picks = top_picks(df, schedule=schedule)

    for pos in ["GK", "DEF", "MID", "FWD"]:
        format_table(picks[pos], title=f"Top {pos}s", n=8)
    format_table(picks["ALL"], title="Overall Top 25 (available players)", n=25)

    # 5-GW breakdown table
    gw_cols  = sorted([c for c in picks["ALL"].columns if c.startswith("gw") and c.endswith("_pred")])
    fdr_cols = sorted([c for c in picks["ALL"].columns if c.endswith("_fdr")])

    if gw_cols:
        print(f"\n{'═'*74}")
        print("  5-GW Breakdown — Top 15")
        print(f"{'═'*74}")
        gw_labels = [c.replace("_pred", "").upper() for c in gw_cols[:5]]
        header = (f"  {'#':>4}  {'Player':<14}  {'Pos':<4}  {'£M':<5}  {'Next':>5}  "
                  + "  ".join(f"{g:>7}" for g in gw_labels))
        print(header)
        print("  " + "─" * 68)
        for rank, row in picks["ALL"].head(15).iterrows():
            line = (f"  {rank:>4}.  {str(row.get('web_name','')):<14}  "
                    f"{str(row.get('position','')):<4}  "
                    f"£{row.get('price_m', 0):.1f}  "
                    f"{row.get('predicted_pts', 0):>5.2f}  ")
            gw_vals = "  ".join(
                f"{row.get(c, 0):>7.2f}" if pd.notna(row.get(c)) else f"{'BGW':>7}"
                for c in gw_cols[:5]
            )
            fdr_str = " [" + " ".join(
                str(int(row.get(f, 3))) if pd.notna(row.get(f)) else "-"
                for f in fdr_cols[:5]
            ) + "]"
            print(line + gw_vals + fdr_str)

    # ── Save ───────────────────────────────────────────────────────────────
    if save_csv:
        full = picks.get("FULL", picks["ALL"])
        p1   = OUT / "predictions_all.csv"
        full.to_csv(str(p1))
        print(f"\n  Full predictions ({len(full)} players)   → {p1}")

        top_df = pd.concat(
            [picks[p] for p in ["GK", "DEF", "MID", "FWD"]], ignore_index=True
        )
        sort_col = "pts_next5" if "pts_next5" in top_df.columns else "predicted_pts"
        top_df = top_df.sort_values(sort_col, ascending=False).reset_index(drop=True)
        top_df.index += 1
        p2 = OUT / "predictions_top.csv"
        top_df.to_csv(str(p2))
        print(f"  Top picks ({len(top_df)} players)          → {p2}")

        schedule.to_csv(str(OUT / "fixture_schedule.csv"), index=False)
        print(f"  Fixture schedule                    → {OUT / 'fixture_schedule.csv'}")

        fdr_tbl.reset_index().to_csv(str(OUT / "fdr_table.csv"))
        print(f"  FDR table                           → {OUT / 'fdr_table.csv'}")

    print(f"\n{bar}")
    print("  PIPELINE COMPLETE")
    print(bar)
    return df, models, metrics, picks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FPL prediction pipeline v4")
    parser.add_argument("--no-tune", action="store_true",
                        help="Skip GridSearchCV (faster, ~5 mins saved)")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't write CSV output files")
    args = parser.parse_args()

    run_pipeline(tune_gbm=not args.no_tune, save_csv=not args.no_save)
