"""
etl/db_sync.py

Sync the latest 25-26 CSV data into SQL tables used by the FastAPI routes.

What this sync updates:
- teams
- players
- player_stats
- fixtures (from official FPL fixtures API, mapped to team codes)
- predictions (optional, from artifacts/predictions_all.csv)

Run manually:
    python -m etl.db_sync --season 2526 --refresh-from-github --sync-predictions
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from api.database import Base, SessionLocal, engine
from api.schema import Fixture, Player, PlayerStat, Prediction, Team
from etl.data_loader import update_2526_from_github
from etl.fdr import build_fdr_table, get_team_fdr

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
FPL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/"

POSITION_MAP = {
    "goalkeeper": "GK",
    "defender": "DEF",
    "midfielder": "MID",
    "forward": "FWD",
}

UNAVAILABLE_STATUSES = {"u", "n", "i"}

ROLLING_FEATURE_KEYS = [
    "form",
    "points_per_game",
    "value_form",
    "value_season",
    "influence",
    "creativity",
    "threat",
    "ict_index",
    "defensive_contribution",
    "defensive_contribution_per_90",
    "tackles",
    "clearances_blocks_interceptions",
    "recoveries",
    "starts",
    "set_piece_threat",
    "total_points",
    "selected_by_percent",
]


def _default_data_dir() -> Path:
    env = os.environ.get("FPL_DATA_DIR")
    if env:
        return Path(env)

    if (PROJECT_ROOT / "players2526.csv").exists() and (PROJECT_ROOT / "playerstats2526.csv").exists():
        return PROJECT_ROOT

    return PROJECT_ROOT / "data"


def _csv_path(file_name: str, data_dir: Path) -> Path:
    primary = data_dir / file_name
    if primary.exists():
        return primary

    fallback = PROJECT_ROOT / file_name
    if fallback.exists():
        return fallback

    raise FileNotFoundError(f"Missing CSV file: {file_name} (checked {primary} and {fallback})")


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        val = float(v)
    except Exception:
        return None
    if pd.isna(val):
        return None
    return val


def _i(v: Any) -> int | None:
    val = _f(v)
    if val is None:
        return None
    return int(round(val))


def _b(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _cost_to_tenths(v: Any) -> float | None:
    val = _f(v)
    if val is None:
        return None
    if val <= 30:
        return round(val * 10, 1)
    return round(val, 1)


def _norm_pos(pos: Any) -> str:
    if pos is None:
        return "UNK"
    s = str(pos).strip().lower()
    if s in POSITION_MAP:
        return POSITION_MAP[s]
    if s in {"gk", "def", "mid", "fwd"}:
        return s.upper()
    return "UNK"


def _team_changed_maps(players_2525_path: Path, players_2526_df: pd.DataFrame) -> tuple[set[int], set[int]]:
    if not players_2525_path.exists():
        return set(), set()

    old_df = pd.read_csv(players_2525_path)
    if "player_id" not in old_df.columns:
        return set(), set()

    old_team = (
        old_df[["player_id", "team_code"]]
        .dropna(subset=["player_id", "team_code"])
        .astype({"player_id": int, "team_code": int})
        .set_index("player_id")["team_code"]
        .to_dict()
    )

    new_team = (
        players_2526_df[["player_id", "team_code"]]
        .dropna(subset=["player_id", "team_code"])
        .astype({"player_id": int, "team_code": int})
        .set_index("player_id")["team_code"]
        .to_dict()
    )

    changed = {pid for pid, tc in new_team.items() if pid in old_team and old_team[pid] != tc}
    new_players = {pid for pid in new_team if pid not in old_team}
    return changed, new_players


def _fetch_fpl_fixtures(timeout: int = 20) -> list[dict]:
    req = urllib.request.Request(FPL_FIXTURES_URL, headers={"User-Agent": "fpl-db-sync/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    if isinstance(data, list):
        return data
    return []


def _ensure_schema() -> None:
    """Create any missing tables so sync can run on a fresh database file."""
    Base.metadata.create_all(bind=engine)


def _replace_teams(db, teams_df: pd.DataFrame, season: str, fdr_df: pd.DataFrame) -> int:
    fdr_map = {}
    if not fdr_df.empty:
        if "code" in fdr_df.columns:
            fdr_map = fdr_df.set_index("code").to_dict(orient="index")
        else:
            fdr_map = {
                int(idx): row
                for idx, row in fdr_df.to_dict(orient="index").items()
            }

    rows = []
    for row in teams_df.to_dict(orient="records"):
        code = _i(row.get("code"))
        if code is None:
            continue
        fdr = fdr_map.get(code, {})

        rows.append(
            {
                "code": code,
                "name": str(row.get("name") or "").strip(),
                "short_name": str(row.get("short_name") or "").strip(),
                "season": season,
                "strength": _i(row.get("strength")),
                "strength_overall_home": _i(row.get("strength_overall_home")),
                "strength_overall_away": _i(row.get("strength_overall_away")),
                "strength_attack_home": _i(row.get("strength_attack_home")),
                "strength_attack_away": _i(row.get("strength_attack_away")),
                "strength_defence_home": _i(row.get("strength_defence_home")),
                "strength_defence_away": _i(row.get("strength_defence_away")),
                "elo": _f(row.get("elo")) if _f(row.get("elo")) is not None else _f(fdr.get("elo")),
                "fdr": _i(fdr.get("fdr")),
                "attack_fdr": _i(fdr.get("attack_fdr_home")),
                "defence_fdr": _i(fdr.get("defence_fdr_home")),
            }
        )

    db.query(Team).filter(Team.season == season).delete(synchronize_session=False)
    if rows:
        db.bulk_insert_mappings(Team, rows)
    return len(rows)


def _replace_players(
    db,
    players_df: pd.DataFrame,
    latest_stats: pd.DataFrame,
    season: str,
    changed_players: set[int],
    new_players: set[int],
) -> int:
    latest_map = {int(r["id"]): r for r in latest_stats.to_dict(orient="records") if _i(r.get("id")) is not None}

    rows = []
    for row in players_df.to_dict(orient="records"):
        pid = _i(row.get("player_id"))
        team_code = _i(row.get("team_code"))
        if pid is None or team_code is None:
            continue

        stat = latest_map.get(pid, {})
        status = str(stat.get("status") or "a").strip().lower()
        penalties_order = _i(stat.get("penalties_order"))
        corners_order = _i(stat.get("corners_and_indirect_freekicks_order"))
        freekicks_order = _i(stat.get("direct_freekicks_order"))

        rows.append(
            {
                "player_id": pid,
                "web_name": str(row.get("web_name") or stat.get("web_name") or f"P{pid}"),
                "season": season,
                "position": _norm_pos(row.get("position")),
                "team_code": team_code,
                "now_cost": _cost_to_tenths(stat.get("now_cost")),
                "selected_by_percent": _f(stat.get("selected_by_percent")),
                "chance_of_playing_next_round": _f(stat.get("chance_of_playing_next_round")),
                "status": status,
                "is_unavailable": status in UNAVAILABLE_STATUSES,
                "team_changed": pid in changed_players,
                "is_new_player": pid in new_players,
                "is_penalties_taker": penalties_order == 1,
                "is_corners_taker": corners_order == 1,
                "is_freekicks_taker": freekicks_order == 1,
            }
        )

    db.query(Player).filter(Player.season == season).delete(synchronize_session=False)
    if rows:
        db.bulk_insert_mappings(Player, rows)
    return len(rows)


def _replace_player_stats(db, stats_df: pd.DataFrame, season: str) -> int:
    rows = []
    for row in stats_df.to_dict(orient="records"):
        pid = _i(row.get("id"))
        gw = _i(row.get("gw"))
        if pid is None or gw is None:
            continue

        rolling = {k: _f(row.get(k)) for k in ROLLING_FEATURE_KEYS if _f(row.get(k)) is not None}

        rows.append(
            {
                "player_id": pid,
                "gw": gw,
                "season": season,
                "event_points": _f(row.get("event_points")),
                "minutes": _f(row.get("minutes")),
                "goals_scored": _f(row.get("goals_scored")),
                "assists": _f(row.get("assists")),
                "clean_sheets": _f(row.get("clean_sheets")),
                "goals_conceded": _f(row.get("goals_conceded")),
                "saves": _f(row.get("saves")),
                "bonus": _f(row.get("bonus")),
                "bps": _f(row.get("bps")),
                "xg": _f(row.get("expected_goals")),
                "xa": _f(row.get("expected_assists")),
                "xgi": _f(row.get("expected_goal_involvements")),
                "xgc": _f(row.get("expected_goals_conceded")),
                "xg_per90": _f(row.get("expected_goals_per_90")),
                "xa_per90": _f(row.get("expected_assists_per_90")),
                "xgi_per90": _f(row.get("expected_goal_involvements_per_90")),
                "saves_per90": _f(row.get("saves_per_90")),
                "cs_per90": _f(row.get("clean_sheets_per_90")),
                "xgc_per90": _f(row.get("expected_goals_conceded_per_90")),
                "rolling_features": rolling or None,
                "now_cost": _f(row.get("now_cost")),
                "selected_by_pct": _f(row.get("selected_by_percent")),
            }
        )

    db.query(PlayerStat).filter(PlayerStat.season == season).delete(synchronize_session=False)
    if rows:
        db.bulk_insert_mappings(PlayerStat, rows)
    return len(rows)


def _replace_fixtures(db, teams_df: pd.DataFrame, season: str, fdr_table: pd.DataFrame) -> int:
    id_to_code = {}
    if "id" in teams_df.columns:
        for row in teams_df[["id", "code"]].dropna().to_dict(orient="records"):
            tid = _i(row.get("id"))
            tcode = _i(row.get("code"))
            if tid is not None and tcode is not None:
                id_to_code[tid] = tcode

    raw_fixtures = _fetch_fpl_fixtures()
    rows = []

    for fx in raw_fixtures:
        gw = _i(fx.get("event"))
        home_id = _i(fx.get("team_h"))
        away_id = _i(fx.get("team_a"))
        if gw is None or home_id is None or away_id is None:
            continue

        home_code = id_to_code.get(home_id)
        away_code = id_to_code.get(away_id)
        if home_code is None or away_code is None:
            continue

        info = get_team_fdr(home_code, away_code, True, fdr_table)

        rows.append(
            {
                "gw": gw,
                "season": season,
                "team_h_code": home_code,
                "team_a_code": away_code,
                "team_h_score": _i(fx.get("team_h_score")),
                "team_a_score": _i(fx.get("team_a_score")),
                "finished": _b(fx.get("finished")),
                "team_h_difficulty": _i(fx.get("team_h_difficulty")) or _i(info.get("fdr")) or 3,
                "team_a_difficulty": _i(fx.get("team_a_difficulty")) or 3,
                "attack_fdr_h": _i(info.get("attack_fdr")) or 3,
                "defence_fdr_h": _i(info.get("defence_fdr")) or 3,
                "elo_diff": _f(info.get("elo_diff")) or 0.0,
            }
        )

    if not rows:
        return 0

    db.query(Fixture).filter(Fixture.season == season).delete(synchronize_session=False)
    db.bulk_insert_mappings(Fixture, rows)
    return len(rows)


def _prediction_gws(df: pd.DataFrame) -> list[int]:
    gws = []
    for col in df.columns:
        if col.startswith("gw") and col.endswith("_pred"):
            mid = col[2:-5]
            if mid.isdigit():
                gws.append(int(mid))
    return sorted(set(gws))


def sync_predictions_to_db(
    season: str = "2526",
    predictions_csv: str | Path | None = None,
    run_at: datetime | None = None,
) -> int:
    _ensure_schema()

    path = Path(predictions_csv) if predictions_csv else (PROJECT_ROOT / "artifacts" / "predictions_all.csv")
    if not path.exists():
        return 0

    df = pd.read_csv(path)
    if "player_id" not in df.columns or "predicted_pts" not in df.columns:
        return 0

    gws = _prediction_gws(df)
    default_target = gws[0] if gws else None
    run_dt = run_at or datetime.utcnow()

    with SessionLocal() as db:
        valid_players = {
            r[0]
            for r in db.query(Player.player_id)
            .filter(Player.season == season)
            .all()
        }

        rows = []
        for row in df.to_dict(orient="records"):
            pid = _i(row.get("player_id"))
            if pid is None or pid not in valid_players:
                continue

            target_gw = default_target
            if target_gw is None:
                target_gw = (_i(row.get("gw")) or 0) + 1

            breakdown = {}
            for gw in gws:
                pred = _f(row.get(f"gw{gw}_pred"))
                opp = row.get(f"gw{gw}_opp")
                fdr = _i(row.get(f"gw{gw}_fdr"))
                home = row.get(f"gw{gw}_home")

                if pred is None and opp is None and fdr is None:
                    continue

                breakdown[str(gw)] = {
                    "pred": pred or 0.0,
                    "opp": str(opp) if opp is not None else "BGW",
                    "fdr": fdr or 3,
                    "is_home": _b(home),
                }

            rows.append(
                {
                    "player_id": pid,
                    "season": season,
                    "target_gw": target_gw,
                    "model_run_at": run_dt,
                    "predicted_pts": _f(row.get("predicted_pts")) or 0.0,
                    "xpts_proxy": _f(row.get("xpts_proxy")),
                    "gw_breakdown": breakdown or None,
                    "pts_next5": _f(row.get("pts_next5")),
                    "chance_of_playing": _f(row.get("chance_of_playing_next_round")),
                    "is_unavailable": _b(row.get("is_unavailable")),
                }
            )

        if not rows:
            return 0

        db.bulk_insert_mappings(Prediction, rows)
        db.commit()
        return len(rows)


def sync_season_to_db(
    season: str = "2526",
    refresh_from_github: bool = False,
    force_refresh: bool = False,
    sync_fixtures: bool = True,
) -> dict:
    _ensure_schema()

    data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    refresh_result = None
    if refresh_from_github:
        refresh_result = update_2526_from_github(force=force_refresh)

    teams_path = _csv_path(f"teams{season}.csv", data_dir)
    players_path = _csv_path(f"players{season}.csv", data_dir)
    stats_path = _csv_path(f"playerstats{season}.csv", data_dir)
    old_players_path = data_dir / "players2425.csv"
    if not old_players_path.exists():
        old_players_path = PROJECT_ROOT / "players2425.csv"

    teams_df = pd.read_csv(teams_path)
    players_df = pd.read_csv(players_path)
    stats_df = pd.read_csv(stats_path)

    changed_players, new_players = _team_changed_maps(old_players_path, players_df)
    latest_stats = (
        stats_df.sort_values("gw")
        .groupby("id", as_index=False)
        .tail(1)
        .copy()
    )

    fdr_table = build_fdr_table(season)

    with SessionLocal() as db:
        counts = {
            "teams": _replace_teams(db, teams_df, season, fdr_table),
            "players": _replace_players(db, players_df, latest_stats, season, changed_players, new_players),
            "player_stats": _replace_player_stats(db, stats_df, season),
        }

        if sync_fixtures:
            counts["fixtures"] = _replace_fixtures(db, teams_df, season, fdr_table)

        db.commit()

    return {
        "season": season,
        "data_dir": str(data_dir),
        "refresh": refresh_result,
        "counts": counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync latest season CSVs into DB")
    parser.add_argument("--season", default="2526", help="Season code, default 2526")
    parser.add_argument("--refresh-from-github", action="store_true", help="Download latest 25-26 CSVs from GitHub before DB sync")
    parser.add_argument("--force-refresh", action="store_true", help="Force overwrite local CSVs when downloading")
    parser.add_argument("--skip-fixtures", action="store_true", help="Skip fixtures table sync")
    parser.add_argument("--sync-predictions", action="store_true", help="Also load artifacts/predictions_all.csv into predictions table")
    parser.add_argument("--predictions-csv", default=None, help="Optional path to predictions CSV")
    args = parser.parse_args()

    result = sync_season_to_db(
        season=args.season,
        refresh_from_github=args.refresh_from_github,
        force_refresh=args.force_refresh,
        sync_fixtures=not args.skip_fixtures,
    )

    print(f"DB sync complete for season {result['season']}")
    print(f"Data dir: {result['data_dir']}")
    print("Counts:")
    for k, v in result["counts"].items():
        print(f"  - {k}: {v}")

    if result.get("refresh"):
        print("Refresh result:")
        for fname, info in result["refresh"].items():
            print(f"  - {fname}: {info}")

    if args.sync_predictions:
        n = sync_predictions_to_db(
            season=args.season,
            predictions_csv=args.predictions_csv,
        )
        print(f"Predictions inserted: {n}")


if __name__ == "__main__":
    main()
