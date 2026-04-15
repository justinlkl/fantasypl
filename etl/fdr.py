"""
etl/fdr.py  —  Fixture Difficulty Ratings & 5-GW schedule builder

Changes from v3:
  - Moved into etl/ module
  - DATA_DIR resolved via FPL_DATA_DIR env var (same as data_loader)
  - Path resolution helpers shared with data_loader._data_dir()
  - fetch_live_fixtures() now first; inferred schedule is the fallback
  - No hardcoded /mnt/user-data paths

Production note:
  The live FPL API endpoint is tried first on every call:
    GET https://fantasy.premierleague.com/api/fixtures/?future=1
  If unreachable, the Berger round-robin inference runs as fallback.
  Replace fetch_live_fixtures() body when deploying with network access.
"""

import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

# ── FDR display constants ──────────────────────────────────────────────────────

FDR_COLOURS = {1: "#00ff85", 2: "#01fc7a", 3: "#e7e7e7", 4: "#ff1751", 5: "#800742"}
FDR_LABELS  = {1: "Very Easy", 2: "Easy", 3: "Medium", 4: "Hard", 5: "Very Hard"}


def _data_dir() -> Path:
    """Mirror of etl.data_loader._data_dir() — avoids circular import."""
    env = os.environ.get("FPL_DATA_DIR")
    return Path(env) if env else Path(__file__).parent.parent / "data"


# ── FDR table ──────────────────────────────────────────────────────────────────

def build_fdr_table(season: str = "2526") -> pd.DataFrame:
    """
    Convert team strength ratings into FDR scores (1 = easy → 5 = hard).

    Returns a DataFrame indexed by team_code with columns:
        name, short_name, elo, fdr,
        attack_fdr_home, attack_fdr_away,
        defence_fdr_home, defence_fdr_away,
        elo_diff_norm
    """
    data_dir  = _data_dir()
    fname     = f"teams{season}.csv"
    path      = data_dir / fname

    if not path.exists():
        # Fallback: try current working directory
        path = Path.cwd() / fname
    if not path.exists():
        raise FileNotFoundError(f"Teams file not found: {path}")

    tm = pd.read_csv(path)

    def to_fdr(series: pd.Series) -> pd.Series:
        s = pd.to_numeric(series, errors="coerce").fillna(series.mean())
        q = s.rank(pct=True)
        return pd.cut(q, bins=[0, .2, .4, .6, .8, 1.0],
                      labels=[1, 2, 3, 4, 5], include_lowest=True).astype(int)

    fdr = tm[["code", "id", "name", "short_name", "elo",
              "strength_attack_home", "strength_attack_away",
              "strength_defence_home", "strength_defence_away"]].copy()

    fdr["attack_fdr_home"]  = to_fdr((fdr["strength_defence_home"] + fdr["strength_defence_away"]) / 2)
    fdr["attack_fdr_away"]  = fdr["attack_fdr_home"]
    fdr["defence_fdr_home"] = to_fdr((fdr["strength_attack_home"] + fdr["strength_attack_away"]) / 2)
    fdr["defence_fdr_away"] = fdr["defence_fdr_home"]
    fdr["fdr"]              = to_fdr(
        (fdr["strength_attack_home"] + fdr["strength_attack_away"] +
         fdr["strength_defence_home"] + fdr["strength_defence_away"]) / 4
    )

    elo_mean    = fdr["elo"].mean()
    elo_std     = fdr["elo"].std()
    fdr["elo_diff_norm"] = ((fdr["elo"] - elo_mean) / (elo_std + 1e-6)).round(3)

    return fdr.set_index("code")


def get_team_fdr(team_code: int, opponent_code: int, is_home: bool,
                 fdr_table: pd.DataFrame) -> dict:
    """Return FDR info for a specific matchup."""
    if opponent_code not in fdr_table.index:
        return {"attack_fdr": 3, "defence_fdr": 3, "fdr": 3,
                "is_home": is_home, "opponent_short": "UNK",
                "opponent_name": "Unknown", "elo_diff": 0.0}

    opp    = fdr_table.loc[opponent_code]
    ha_adj = -0.5 if is_home else 0.5

    return {
        "attack_fdr":     int(np.clip(round(float(opp["attack_fdr_home"])  + ha_adj), 1, 5)),
        "defence_fdr":    int(np.clip(round(float(opp["defence_fdr_home"]) + ha_adj), 1, 5)),
        "fdr":            int(opp["fdr"]),
        "is_home":        is_home,
        "opponent_short": str(opp.get("short_name", "UNK")),
        "opponent_name":  str(opp.get("name", "Unknown")),
        "elo_diff":       float(opp.get("elo_diff_norm", 0)),
    }


# ── Live fixture fetch ─────────────────────────────────────────────────────────

def fetch_live_fixtures(timeout: int = 10) -> pd.DataFrame:
    """
    Fetch future fixtures from the official FPL API.

    Returns same schema as build_fixture_schedule().
    Raises on network error — caller should catch and fall back.
    """
    url = "https://fantasy.premierleague.com/api/fixtures/?future=1"
    req = urllib.request.Request(url, headers={"User-Agent": "fpl-model/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        fixtures = json.load(resp)

    fdr_tbl = build_fdr_table("2526")
    rows    = []

    for fx in fixtures:
        gw = fx.get("event")
        if gw is None:
            continue
        team_h = fx.get("team_h")
        team_a = fx.get("team_a")
        th_diff = fx.get("team_h_difficulty")
        ta_diff = fx.get("team_a_difficulty")

        for tc, oppc, is_home, diff in [
            (team_h, team_a, True,  th_diff),
            (team_a, team_h, False, ta_diff),
        ]:
            if tc is None:
                continue
            if tc in fdr_tbl.index and oppc in fdr_tbl.index:
                info = get_team_fdr(tc, oppc, is_home, fdr_tbl)
            else:
                info = {"attack_fdr": diff or 3, "defence_fdr": diff or 3,
                        "fdr": diff or 3, "opponent_short": str(oppc or "UNK"),
                        "opponent_name": str(oppc or "Unknown"), "elo_diff": 0.0}
            rows.append({
                "gw":            int(gw),
                "team_code":     int(tc),
                "opponent_code": int(oppc) if oppc else None,
                "opponent":      info["opponent_short"],
                "opponent_name": info["opponent_name"],
                "is_home":       bool(is_home),
                "fdr":           int(info["fdr"]),
                "attack_fdr":    int(info["attack_fdr"]),
                "defence_fdr":   int(info["defence_fdr"]),
                "elo_diff":      float(info["elo_diff"]),
            })

    return pd.DataFrame(rows)


# ── Inferred schedule (fallback) ───────────────────────────────────────────────

def _infer_fixture_schedule(season: str = "2526",
                             n_future_gws: int = 5) -> pd.DataFrame:
    """
    Reconstruct upcoming fixtures from the Berger round-robin algorithm.
    Used when the live FPL API is unreachable.
    """
    data_dir = _data_dir()
    ps_path  = data_dir / f"playerstats{season}.csv"
    pl_path  = data_dir / f"players{season}.csv"
    tm_path  = data_dir / f"teams{season}.csv"

    for p in [ps_path, pl_path, tm_path]:
        if not p.exists():
            raise FileNotFoundError(f"Cannot build inferred schedule — missing: {p}")

    ps = pd.read_csv(ps_path)
    ps.rename(columns={"id": "player_id"}, inplace=True, errors="ignore")
    pl = pd.read_csv(pl_path)
    tm = pd.read_csv(tm_path)
    ps = ps.merge(pl[["player_id", "team_code"]], on="player_id", how="left")

    latest_gw  = int(ps["gw"].max())
    future_gws = list(range(latest_gw + 1, latest_gw + n_future_gws + 1))
    fdr_tbl    = build_fdr_table(season)

    team_codes = sorted(tm["code"].unique().tolist())
    n_teams    = len(team_codes)
    fixed      = team_codes[0]
    rotors     = team_codes[1:]
    n_rounds   = n_teams - 1

    rows = []
    for future_idx, gw in enumerate(future_gws):
        round_idx = (latest_gw + future_idx) % n_rounds
        r         = rotors[round_idx:] + rotors[:round_idx]
        pairs     = [(fixed, r[0])] + [
            (r[i], r[n_teams - 2 - i]) for i in range(1, n_teams // 2)
        ]
        for home_code, away_code in pairs:
            for tc, opp, is_home in [(home_code, away_code, True),
                                     (away_code, home_code, False)]:
                if tc not in fdr_tbl.index or opp not in fdr_tbl.index:
                    continue
                info = get_team_fdr(tc, opp, is_home, fdr_tbl)
                rows.append({
                    "gw":            gw,
                    "team_code":     tc,
                    "opponent_code": opp,
                    "opponent":      info["opponent_short"],
                    "opponent_name": info["opponent_name"],
                    "is_home":       is_home,
                    "fdr":           info["fdr"],
                    "attack_fdr":    info["attack_fdr"],
                    "defence_fdr":   info["defence_fdr"],
                    "elo_diff":      info["elo_diff"],
                })

    return pd.DataFrame(rows)


def build_fixture_schedule(season: str = "2526",
                           n_future_gws: int = 5) -> pd.DataFrame:
    """
    Return the next n_future_gws fixture schedule.

    Tries the live FPL API first; falls back to Berger round-robin inference.
    """
    try:
        live = fetch_live_fixtures()
        if isinstance(live, pd.DataFrame) and not live.empty:
            return live
    except Exception as e:
        print(f"  Live fixtures fetch failed (using inference): {e}")

    return _infer_fixture_schedule(season=season, n_future_gws=n_future_gws)


# ── FDR multiplier → prediction scaling ───────────────────────────────────────

def fdr_to_multiplier(fdr: int, position: str) -> float:
    """Convert FDR (1-5) into a points multiplier for predictions."""
    base = {
        "GK":  {1: 1.22, 2: 1.11, 3: 1.00, 4: 0.89, 5: 0.78},
        "DEF": {1: 1.20, 2: 1.10, 3: 1.00, 4: 0.90, 5: 0.80},
        "MID": {1: 1.15, 2: 1.07, 3: 1.00, 4: 0.93, 5: 0.85},
        "FWD": {1: 1.15, 2: 1.07, 3: 1.00, 4: 0.93, 5: 0.85},
    }
    return base.get(position, base["MID"]).get(max(1, min(5, int(fdr))), 1.0)


def add_fdr_to_predictions(preds: pd.DataFrame,
                            schedule: pd.DataFrame) -> pd.DataFrame:
    """
    Merge fixture schedule onto predictions and compute FDR-adjusted
    per-GW point estimates.

    Adds columns:
        gw{N}_pred, gw{N}_opp, gw{N}_fdr, gw{N}_home
        pts_next5
    """
    if schedule.empty:
        return preds

    preds = preds.copy()
    gws   = sorted(schedule["gw"].unique())

    for gw in gws:
        gw_fix = schedule[schedule["gw"] == gw].set_index("team_code")

        fdr_pts, opps, fdrs, homes = [], [], [], []

        for _, row in preds.iterrows():
            tc   = row.get("team_code")
            pos  = row.get("position", "MID")
            base = float(row.get("predicted_pts", 0))

            if tc in gw_fix.index:
                fx = gw_fix.loc[tc]
                if isinstance(fx, pd.DataFrame):
                    fx = fx.iloc[0]
                fdr_val = int(fx["defence_fdr"] if pos in ("MID", "FWD") else fx["attack_fdr"])
                mult    = fdr_to_multiplier(fdr_val, pos)
                fdr_pts.append(round(base * mult, 2))
                opps.append(str(fx["opponent"]) + (" (H)" if fx["is_home"] else " (A)"))
                fdrs.append(fdr_val)
                homes.append(bool(fx["is_home"]))
            else:
                fdr_pts.append(0.0)
                opps.append("BGW")
                fdrs.append(None)
                homes.append(None)

        preds[f"gw{gw}_pred"]  = fdr_pts
        preds[f"gw{gw}_opp"]   = opps
        preds[f"gw{gw}_fdr"]   = fdrs
        preds[f"gw{gw}_home"]  = homes

    gw_cols = [f"gw{g}_pred" for g in gws if f"gw{g}_pred" in preds.columns]
    if gw_cols:
        preds["pts_next5"] = preds[gw_cols[:5]].sum(axis=1).round(1)

    return preds
