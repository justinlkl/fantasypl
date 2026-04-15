"""
etl/data_loader.py  v4
Loads and merges FPL source files into a clean per-GW dataset.

Changes from v3:
  - Moved into etl/ module (app-oriented, not pipeline-oriented)
  - DATA_DIR now read from FPL_DATA_DIR env var (defaults to ./data)
  - PATHS dict is now built dynamically so the app and scheduler both
    resolve the same files regardless of working directory
  - update_2526_from_github() always writes to the resolved DATA_DIR
"""

import os
import json
import hashlib
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

# ── Path resolution ────────────────────────────────────────────────────────────

def _data_dir() -> Path:
    """
    Return the data directory.  Priority:
      1. FPL_DATA_DIR environment variable
      2. project root (if CSVs are stored there)
      3. ./data  (relative to project root)
    """
    env = os.environ.get("FPL_DATA_DIR")
    if env:
        return Path(env)

    root = Path(__file__).parent.parent
    if (root / "players2526.csv").exists() and (root / "playerstats2526.csv").exists():
        return root

    return root / "data"


def _build_paths(data_dir: Path) -> dict:
    return {
        "players_2425":     data_dir / "players2425.csv",
        "players_2526":     data_dir / "players2526.csv",
        "playerstats_2425": data_dir / "playerstats2425.csv",
        "playerstats_2526": data_dir / "playerstats2526.csv",
        "matchstats_2425":  data_dir / "playermatchstats2425.csv",
        "teams_2425":       data_dir / "teams2425.csv",
        "teams_2526":       data_dir / "teams2526.csv",
    }


# ── Column definitions (unchanged from v3) ────────────────────────────────────

CUMULATIVE_COLS = [
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_conceded", "minutes", "goals_scored", "assists",
    "clean_sheets", "goals_conceded", "saves", "tackles",
    "clearances_blocks_interceptions", "defensive_contribution",
    "total_points", "bonus", "bps", "recoveries",
    "own_goals", "yellow_cards", "red_cards",
    "penalties_saved", "penalties_missed", "starts",
    "influence", "creativity", "threat", "ict_index",
]

PER_GW_COLS = [
    "event_points", "form", "now_cost", "selected_by_percent",
    "chance_of_playing_next_round", "chance_of_playing_this_round",
    "expected_goals_per_90", "expected_assists_per_90",
    "expected_goal_involvements_per_90", "expected_goals_conceded_per_90",
    "saves_per_90", "clean_sheets_per_90", "goals_conceded_per_90",
    "defensive_contribution_per_90",
    "points_per_game", "value_form", "value_season",
    "penalties_order", "corners_and_indirect_freekicks_order",
    "direct_freekicks_order", "set_piece_threat",
]

DROP_COLS = [
    "ep_next", "ep_this",
    "now_cost_rank", "now_cost_rank_type", "selected_rank", "selected_rank_type",
    "form_rank", "form_rank_type", "influence_rank", "influence_rank_type",
    "creativity_rank", "creativity_rank_type", "threat_rank", "threat_rank_type",
    "ict_index_rank", "ict_index_rank_type",
    "points_per_game_rank", "points_per_game_rank_type",
    "dreamteam_count", "transfers_in", "transfers_in_event",
    "transfers_out", "transfers_out_event",
    "cost_change_event", "cost_change_event_fall",
    "cost_change_start", "cost_change_start_fall",
    "news", "news_added",
    "corners_and_indirect_freekicks_text", "direct_freekicks_text", "penalties_text",
    "first_name", "second_name",
]

TEAM_STRENGTH_COLS = [
    "strength", "strength_overall_home", "strength_overall_away",
    "strength_attack_home", "strength_attack_away",
    "strength_defence_home", "strength_defence_away", "elo",
]

MATCH_KEEP_COLS = [
    "player_id", "match_id", "minutes_played",
    "goals", "assists", "xg", "xa", "xgot",
    "total_shots", "shots_on_target", "touches_opposition_box",
    "chances_created", "successful_dribbles",
    "tackles", "interceptions", "clearances", "blocks", "recoveries",
    "tackles_won", "duels_won", "aerial_duels_won",
    "saves", "goals_conceded", "xgot_faced", "goals_prevented",
    "team_goals_conceded", "penalties_scored", "penalties_missed",
]

POS_MAP = {
    "goalkeeper": "GK", "defender": "DEF",
    "midfielder": "MID", "forward": "FWD",
}

GITHUB_BASE = (
    "https://raw.githubusercontent.com/olbauday/FPL-Core-Insights"
    "/main/data/2025-2026"
)

GITHUB_FILE_MAP = {
    "players2526.csv": "players.csv",
    "teams2526.csv": "teams.csv",
    "playerstats2526.csv": "playerstats.csv",
}


# ── Remote update ──────────────────────────────────────────────────────────────

def update_2526_from_github(force: bool = False, timeout: int = 20) -> dict:
    """
    Fetch the latest 2025-26 CSVs from GitHub and write them to DATA_DIR.
    Only overwrites files when content has changed (unless force=True).
    Returns a dict of {filename: {"ok": bool, "updated": bool, "path": str}}.
    """
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    paths    = _build_paths(data_dir)

    files = {
        "players2526.csv": paths["players_2526"],
        "teams2526.csv": paths["teams_2526"],
        "playerstats2526.csv": paths["playerstats_2526"],
    }

    results = {}
    for local_name, dest in files.items():
        remote_name = GITHUB_FILE_MAP.get(local_name, local_name)
        url = f"{GITHUB_BASE}/{remote_name}"
        try:
            req  = urllib.request.Request(url, headers={"User-Agent": "fpl-model/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
        except Exception as e:
            results[local_name] = {"ok": False, "error": str(e), "url": url}
            continue

        write_file = True
        if dest.exists() and not force:
            try:
                old = dest.read_bytes()
                if old == data:
                    write_file = False
            except Exception:
                write_file = True

        try:
            if write_file:
                dest.write_bytes(data)
                results[local_name] = {"ok": True, "updated": True, "path": str(dest), "url": url}
            else:
                results[local_name] = {"ok": True, "updated": False, "path": str(dest), "url": url}
        except Exception as e:
            results[local_name] = {"ok": False, "error": str(e), "url": url}

    return results


# Keep old alias for backward compatibility with scheduler.py
update_data_from_github = update_2526_from_github


# ── Internal helpers ───────────────────────────────────────────────────────────

def _norm_pos(series: pd.Series) -> pd.Series:
    return series.str.lower().str.strip().map(POS_MAP).fillna("UNK")


def _derive_per_gw(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    df = df.sort_values(["player_id", "gw"]).copy()
    for col in cols:
        if col not in df.columns:
            continue
        diff = df.groupby("player_id")[col].diff()
        gw1  = df.groupby("player_id")["gw"].transform("min") == df["gw"]
        diff = diff.where(~gw1, df[col]).clip(lower=0)
        df[f"gw_{col}"] = diff
    return df


def _ffill_per90(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if "_per_90" in c]
    df   = df.sort_values(["player_id", "gw"])
    df[cols] = df.groupby("player_id")[cols].transform(lambda x: x.ffill().bfill())
    return df


def _load_teams(season: str, paths: dict) -> pd.DataFrame:
    tm   = pd.read_csv(paths[f"teams_{season}"])
    keep = ["code"] + [c for c in TEAM_STRENGTH_COLS if c in tm.columns]
    return tm[keep].rename(columns={"code": "team_code"}).copy()


def _load_player_lookup(paths: dict) -> tuple:
    p25 = pd.read_csv(paths["players_2425"])
    p26 = pd.read_csv(paths["players_2526"])
    for df in [p25, p26]:
        df["position"] = _norm_pos(df["position"])

    both    = p25.merge(p26[["player_id", "team_code"]], on="player_id",
                        suffixes=("_25", "_26"), how="inner")
    changed = set(both[both["team_code_25"] != both["team_code_26"]]["player_id"])
    new_26  = set(p26["player_id"]) - set(p25["player_id"])

    p25["team_changed"]  = False
    p25["is_new_player"] = False
    p26["team_changed"]  = p26["player_id"].isin(changed)
    p26["is_new_player"] = p26["player_id"].isin(new_26)

    cols = ["player_id", "team_code", "position", "web_name",
            "team_changed", "is_new_player"]
    return p25[cols].copy(), p26[cols].copy()


def _load_opta(paths: dict) -> pd.DataFrame:
    pm  = pd.read_csv(paths["matchstats_2425"])
    pm  = pm[[c for c in MATCH_KEEP_COLS if c in pm.columns]].copy()
    ps  = pd.read_csv(paths["playerstats_2425"])
    ps.rename(columns={"id": "player_id"}, inplace=True, errors="ignore")
    gw_order = (ps[["player_id", "gw"]].drop_duplicates()
                  .sort_values(["player_id", "gw"]).copy())
    gw_order["match_rank"] = gw_order.groupby("player_id").cumcount() + 1
    pm = pm.sort_values(["player_id", "match_id"])
    pm["match_rank"] = pm.groupby("player_id").cumcount() + 1
    pm = pm.merge(gw_order[["player_id", "match_rank", "gw"]],
                  on=["player_id", "match_rank"], how="left")
    stat_cols = [c for c in pm.columns if c not in {"player_id", "gw", "match_id", "match_rank"}]
    pm_gw = (pm.dropna(subset=["gw"])
               .groupby(["player_id", "gw"])[stat_cols].sum().reset_index())
    pm_gw["gw"] = pm_gw["gw"].astype(int)
    pm_gw.rename(columns={c: f"opta_{c}" for c in stat_cols}, inplace=True)
    return pm_gw


# ── Public API ─────────────────────────────────────────────────────────────────

def build_dataset() -> pd.DataFrame:
    """
    Load, clean, and merge all FPL source data into one per-GW DataFrame.
    Reads CSVs from FPL_DATA_DIR (default: ./data/).
    """
    data_dir = _data_dir()
    paths    = _build_paths(data_dir)

    # Validate required files exist
    missing = [str(p) for p in paths.values() if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing data files:\n  " + "\n  ".join(missing) +
            f"\n\nSet FPL_DATA_DIR env var or run: python -m etl.data_loader --download"
        )

    print(f"Loading source files from {data_dir} ...")
    lk25, lk26 = _load_player_lookup(paths)
    results = []

    for season, lookup, ps_key in [
        ("2425", lk25, "playerstats_2425"),
        ("2526", lk26, "playerstats_2526"),
    ]:
        print(f"  Processing {season}...")
        ps = pd.read_csv(paths[ps_key])
        ps.rename(columns={"id": "player_id"}, inplace=True, errors="ignore")
        ps["season"] = season

        ps.drop(columns=[c for c in DROP_COLS if c in ps.columns], inplace=True)

        if "status" in ps.columns:
            ps["is_unavailable"] = ps["status"].isin({"u", "n"}).astype(float)
        else:
            ps["is_unavailable"] = 0.0

        has_webname = "web_name" in ps.columns
        meta_cols   = ["player_id", "team_code", "position", "team_changed", "is_new_player"]
        if not has_webname:
            meta_cols.append("web_name")
        ps = ps.merge(lookup[meta_cols], on="player_id", how="left")

        tm = _load_teams(season, paths)
        ps = ps.merge(tm, on="team_code", how="left")

        ps = _ffill_per90(ps)
        cum = [c for c in CUMULATIVE_COLS if c in ps.columns]
        ps  = _derive_per_gw(ps, cum)
        ps.drop(columns=[c for c in cum if c in ps.columns], inplace=True)

        if "gw_minutes" not in ps.columns:
            ps["gw_minutes"] = np.where(ps["event_points"] > 0, 60.0, 0.0)

        n_played = int((ps["gw_minutes"] > 0).sum())
        print(f"    {ps.shape[0]:,} rows | {ps['player_id'].nunique()} players | "
              f"GW {int(ps['gw'].min())}-{int(ps['gw'].max())} | {n_played:,} played")
        results.append(ps)

    print("  Merging Opta match stats...")
    try:
        opta = _load_opta(paths)
        results[0] = results[0].merge(opta, on=["player_id", "gw"], how="left")
        n_opta = len([c for c in opta.columns if c.startswith("opta_")])
        print(f"    {n_opta} opta columns added")
    except FileNotFoundError:
        print("    Opta match stats not found — skipping")

    df = pd.concat(results, ignore_index=True, sort=False)
    df = df.sort_values(["player_id", "season", "gw"]).reset_index(drop=True)
    df["next_gw_points"] = df.groupby(["player_id", "season"])["event_points"].shift(-1)

    print(f"  Final: {df.shape[0]:,} rows × {df.shape[1]} cols | "
          f"{df['player_id'].nunique()} players")
    return df


# ── CLI convenience ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FPL data loader")
    parser.add_argument("--download", action="store_true",
                        help="Download latest 2025-26 CSVs from GitHub first")
    args = parser.parse_args()

    if args.download:
        print("Downloading latest 25-26 CSVs...")
        res = update_2526_from_github()
        for fname, r in res.items():
            status = "UPDATED" if r.get("updated") else ("OK" if r.get("ok") else f"FAILED: {r.get('error')}")
            print(f"  {fname}: {status}")

    df = build_dataset()
    print(df.dtypes)
    print(df.head())
