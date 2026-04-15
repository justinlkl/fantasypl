"""
api/routes/players.py  —  /players endpoints

GET /players
    List all players (with optional filters).
    Query params: position, team_code, season, limit

GET /players/{player_id}
    Full player detail: bio, current-GW stats, rolling features, prediction.

GET /players/{player_id}/history
    Per-GW points history for sparklines / trend charts.

GET /compare
    Side-by-side comparison of 2–4 players.
    Query param: ids=123,456,789
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.schema import Player, PlayerStat, Prediction

router = APIRouter(prefix="/players", tags=["players"])


# ── GET /players ───────────────────────────────────────────────────────────────

@router.get("/")
def list_players(
    position:  Optional[str] = Query(None),
    team_code: Optional[int] = Query(None),
    season:    str           = Query("2526"),
    limit:     int           = Query(100, ge=1, le=1000),
    db:        Session       = Depends(get_db),
):
    q = db.query(Player).filter(Player.season == season)
    if position:
        q = q.filter(Player.position == position.upper())
    if team_code:
        q = q.filter(Player.team_code == team_code)

    players = q.order_by(Player.web_name).limit(limit).all()
    return {"players": [_player_summary(p) for p in players], "count": len(players)}


# ── GET /players/{player_id} ──────────────────────────────────────────────────

@router.get("/{player_id}")
def player_detail(player_id: int, season: str = "2526", db: Session = Depends(get_db)):
    """Full player profile: bio + latest stats + latest prediction."""
    player = (db.query(Player)
                .filter(Player.player_id == player_id, Player.season == season)
                .first())
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    # Latest stat row
    stat = (db.query(PlayerStat)
              .filter(PlayerStat.player_id == player_id, PlayerStat.season == season)
              .order_by(PlayerStat.gw.desc())
              .first())

    # Latest prediction
    pred_run = db.query(Prediction.model_run_at).order_by(
        Prediction.model_run_at.desc()
    ).scalar()
    pred = None
    if pred_run:
        pred = (db.query(Prediction)
                  .filter(Prediction.player_id == player_id,
                          Prediction.model_run_at == pred_run)
                  .first())

    return {
        "player":     _player_summary(player),
        "latest_stat": _stat_dict(stat) if stat else None,
        "prediction":  _pred_dict(pred) if pred else None,
    }


# ── GET /players/{player_id}/history ──────────────────────────────────────────

@router.get("/{player_id}/history")
def player_history(player_id: int, season: str = "2526", db: Session = Depends(get_db)):
    """Per-GW points + minutes history for a player (for sparklines)."""
    rows = (db.query(PlayerStat)
              .filter(PlayerStat.player_id == player_id, PlayerStat.season == season)
              .order_by(PlayerStat.gw)
              .all())
    if not rows:
        raise HTTPException(status_code=404, detail="No history found")

    return {
        "player_id": player_id,
        "season":    season,
        "history": [
            {
                "gw":      r.gw,
                "pts":     r.event_points,
                "minutes": r.minutes,
                "xg":      r.xg,
                "xa":      r.xa,
                "xgi":     r.xgi,
                "bonus":   r.bonus,
            }
            for r in rows
        ],
    }


# ── GET /compare ──────────────────────────────────────────────────────────────

@router.get("/compare/")
def compare_players(
    ids:    str      = Query(..., description="Comma-separated player_ids, e.g. 123,456"),
    season: str      = Query("2526"),
    db:     Session  = Depends(get_db),
):
    """
    Return side-by-side stats + predictions for 2–4 players.
    Used by the player comparison page.
    """
    id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not 2 <= len(id_list) <= 4:
        raise HTTPException(status_code=400,
                            detail="Provide 2–4 comma-separated player IDs")

    pred_run = db.query(Prediction.model_run_at).order_by(
        Prediction.model_run_at.desc()
    ).scalar()

    result = []
    for pid in id_list:
        player = (db.query(Player)
                    .filter(Player.player_id == pid, Player.season == season)
                    .first())
        if not player:
            continue

        stat = (db.query(PlayerStat)
                  .filter(PlayerStat.player_id == pid, PlayerStat.season == season)
                  .order_by(PlayerStat.gw.desc()).first())

        pred = None
        if pred_run:
            pred = (db.query(Prediction)
                      .filter(Prediction.player_id == pid,
                               Prediction.model_run_at == pred_run)
                      .first())

        # Per-GW history for mini-chart
        history = (db.query(PlayerStat.gw, PlayerStat.event_points,
                            PlayerStat.xgi, PlayerStat.minutes)
                     .filter(PlayerStat.player_id == pid, PlayerStat.season == season)
                     .order_by(PlayerStat.gw)
                     .all())

        result.append({
            "player":     _player_summary(player),
            "latest_stat": _stat_dict(stat) if stat else None,
            "prediction":  _pred_dict(pred) if pred else None,
            "history":    [{"gw": h.gw, "pts": h.event_points,
                            "xgi": h.xgi, "minutes": h.minutes}
                           for h in history],
        })

    return {"comparison": result, "count": len(result)}


# ── Serialisers ────────────────────────────────────────────────────────────────

def _player_summary(p: Player) -> dict:
    return {
        "player_id":        p.player_id,
        "web_name":         p.web_name,
        "position":         p.position,
        "team_code":        p.team_code,
        "price_m":          round(p.now_cost / 10, 1) if p.now_cost else None,
        "selected_by_pct":  p.selected_by_percent,
        "is_unavailable":   p.is_unavailable,
        "chance_of_playing":p.chance_of_playing_next_round,
        "team_changed":     p.team_changed,
        "is_new_player":    p.is_new_player,
        "is_penalties_taker": p.is_penalties_taker,
    }


def _stat_dict(s: Optional[PlayerStat]) -> Optional[dict]:
    if s is None:
        return None
    return {
        "gw":        s.gw,
        "pts":       s.event_points,
        "minutes":   s.minutes,
        "goals":     s.goals_scored,
        "assists":   s.assists,
        "clean_sheets": s.clean_sheets,
        "goals_conceded": s.goals_conceded,
        "own_goals": s.own_goals,
        "penalties_saved": s.penalties_saved,
        "penalties_missed": s.penalties_missed,
        "saves":     s.saves,
        "bonus":     s.bonus,
        "bps":       s.bps,
        "xg":        s.xg,
        "xa":        s.xa,
        "xgi":       s.xgi,
        "xgc":       s.xgc,
        "xg_per90":  s.xg_per90,
        "xa_per90":  s.xa_per90,
        "xgi_per90": s.xgi_per90,
        "xgc_per90": s.xgc_per90,
        "rolling":   s.rolling_features,
    }


def _pred_dict(p: Optional[Prediction]) -> Optional[dict]:
    if p is None:
        return None
    return {
        "predicted_pts":  round(p.predicted_pts, 2),
        "pts_next5":      round(p.pts_next5, 1) if p.pts_next5 else None,
        "xpts_proxy":     round(p.xpts_proxy, 2) if p.xpts_proxy else None,
        "gw_breakdown":   p.gw_breakdown or {},
        "target_gw":      p.target_gw,
        "model_run_at":   p.model_run_at.isoformat(),
    }
