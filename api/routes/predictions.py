"""
api/routes/predictions.py  —  /predictions endpoints

GET /predictions
    Query params:
        position    — filter by GK/DEF/MID/FWD
        max_price   — maximum player price in £M
        available   — bool, filter out injured/suspended (default true)
        limit       — max rows (default 50)
        sort        — "pts_next5" | "predicted_pts" (default pts_next5)

GET /predictions/{player_id}
    Full prediction detail for one player including 5-GW breakdown.

POST /predictions/refresh
    Trigger a new model run (admin / scheduler use only; protected by API key).
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from api.database import get_db
from api.schema import Prediction, Player, PlayerStat

router = APIRouter(prefix="/predictions", tags=["predictions"])

_ADMIN_KEY = os.environ.get("FPL_ADMIN_KEY", "changeme")


# ── GET /predictions ───────────────────────────────────────────────────────────

@router.get("/")
def list_predictions(
    position:  Optional[str]   = Query(None, description="GK | DEF | MID | FWD"),
    max_price: Optional[float] = Query(None, description="Max price in £M"),
    available: bool            = Query(True, description="Exclude unavailable players"),
    season:    str             = Query("2526", description="Season, e.g. 2526"),
    limit:     int             = Query(50,   ge=1, le=500),
    sort:      str             = Query("pts_next5", description="pts_next5 | predicted_pts"),
    include_breakdown: bool    = Query(False, description="Include gw_breakdown payload"),
    include_stats: bool        = Query(False, description="Include latest_stat payload"),
    db:        Session         = Depends(get_db),
):
    """
    Return the latest predictions for all (or filtered) players.
    Joins to Player for position/price/availability context.
    """
    # Get the most recent model_run_at timestamp
    latest_run = (db.query(Prediction.model_run_at)
                    .filter(Prediction.season == season)
                    .order_by(
        Prediction.model_run_at.desc()
    ).scalar())

    if latest_run is None:
        return {"predictions": [], "count": 0, "model_run_at": None}

    if include_stats:
        latest_stat_subq = (
            db.query(
                PlayerStat.player_id.label("player_id"),
                func.max(PlayerStat.gw).label("max_gw"),
            )
            .filter(PlayerStat.season == season)
            .group_by(PlayerStat.player_id)
            .subquery()
        )

        q = (
            db.query(Prediction, Player, PlayerStat)
            .join(
                Player,
                and_(
                    Prediction.player_id == Player.player_id,
                    Prediction.season == Player.season,
                ),
            )
            .outerjoin(latest_stat_subq, latest_stat_subq.c.player_id == Player.player_id)
            .outerjoin(
                PlayerStat,
                and_(
                    PlayerStat.player_id == latest_stat_subq.c.player_id,
                    PlayerStat.gw == latest_stat_subq.c.max_gw,
                    PlayerStat.season == season,
                ),
            )
            .filter(
                Prediction.model_run_at == latest_run,
                Prediction.season == season,
                Player.season == season,
            )
        )
    else:
        q = (
            db.query(Prediction, Player)
            .join(
                Player,
                and_(
                    Prediction.player_id == Player.player_id,
                    Prediction.season == Player.season,
                ),
            )
            .filter(
                Prediction.model_run_at == latest_run,
                Prediction.season == season,
                Player.season == season,
            )
        )

    if position:
        q = q.filter(Player.position == position.upper())
    if available:
        q = q.filter(Prediction.is_unavailable == False)
    if max_price is not None:
        q = q.filter(Player.now_cost <= max_price * 10)   # DB stores in tenths

    sort_col = (Prediction.pts_next5 if sort == "pts_next5"
                else Prediction.predicted_pts)
    rows = q.order_by(sort_col.desc()).limit(limit).all()

    if include_stats:
        predictions = [
            _row_to_dict(pred, player, stat, include_breakdown=include_breakdown)
            for pred, player, stat in rows
        ]
    else:
        predictions = [
            _row_to_dict(pred, player, None, include_breakdown=include_breakdown)
            for pred, player in rows
        ]

    return {
        "predictions": predictions,
        "count":        len(rows),
        "model_run_at": latest_run.isoformat() if latest_run else None,
    }


# ── GET /predictions/{player_id} ──────────────────────────────────────────────

@router.get("/{player_id}")
def player_prediction(player_id: int, db: Session = Depends(get_db)):
    """Full prediction detail including 5-GW FDR breakdown."""
    latest_run = db.query(Prediction.model_run_at).order_by(
        Prediction.model_run_at.desc()
    ).scalar()

    if latest_run is None:
        raise HTTPException(status_code=404, detail="No predictions found")

    season = (db.query(Prediction.season)
                .filter(Prediction.model_run_at == latest_run)
                .first())
    season = season[0] if season else "2526"

    latest_stat_subq = (
        db.query(
            PlayerStat.player_id.label("player_id"),
            func.max(PlayerStat.gw).label("max_gw"),
        )
        .filter(PlayerStat.season == season, PlayerStat.player_id == player_id)
        .group_by(PlayerStat.player_id)
        .subquery()
    )

    row = (
        db.query(Prediction, Player, PlayerStat)
        .join(
            Player,
            and_(
                Prediction.player_id == Player.player_id,
                Prediction.season == Player.season,
            ),
        )
        .outerjoin(latest_stat_subq, latest_stat_subq.c.player_id == Player.player_id)
        .outerjoin(
            PlayerStat,
            and_(
                PlayerStat.player_id == latest_stat_subq.c.player_id,
                PlayerStat.gw == latest_stat_subq.c.max_gw,
                PlayerStat.season == season,
            ),
        )
        .filter(
            Prediction.player_id == player_id,
            Prediction.model_run_at == latest_run,
            Prediction.season == season,
            Player.season == season,
        )
        .first()
    )

    if row is None:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")

    pred, player, stat = row
    return _row_to_dict(pred, player, stat, include_breakdown=True)


# ── POST /predictions/refresh ──────────────────────────────────────────────────

@router.post("/refresh")
def trigger_refresh(x_api_key: Optional[str] = Header(None)):
    """
    Trigger the ETL + model pipeline asynchronously.
    Protected by X-Api-Key header.

    In production, this enqueues a Celery task or APScheduler job.
    The response is immediate; the job runs in the background.
    """
    if x_api_key != _ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # TODO: enqueue Celery task → etl.scheduler.run_job()
    # For now, run synchronously (not suitable for production).
    try:
        import subprocess, sys
        subprocess.Popen([sys.executable, "-m", "etl.scheduler", "--once", "--force"])
        return {"status": "queued", "detail": "Pipeline job started in background"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Serialiser ─────────────────────────────────────────────────────────────────

def _stat_dict(s: Optional[PlayerStat]) -> Optional[dict]:
    if s is None:
        return None
    return {
        "gw": s.gw,
        "pts": s.event_points,
        "minutes": s.minutes,
        "goals": s.goals_scored,
        "assists": s.assists,
        "clean_sheets": s.clean_sheets,
        "goals_conceded": s.goals_conceded,
        "saves": s.saves,
        "bonus": s.bonus,
        "bps": s.bps,
        "xg": s.xg,
        "xa": s.xa,
        "xgi": s.xgi,
        "xgc": s.xgc,
        "xg_per90": s.xg_per90,
        "xa_per90": s.xa_per90,
        "xgi_per90": s.xgi_per90,
        "xgc_per90": s.xgc_per90,
        "rolling": s.rolling_features,
    }


def _row_to_dict(
    pred: Prediction,
    player: Player,
    stat: Optional[PlayerStat] = None,
    include_breakdown: bool = False,
) -> dict:
    payload = {
        "player_id":        player.player_id,
        "web_name":         player.web_name,
        "position":         player.position,
        "team_code":        player.team_code,
        "price_m":          round(player.now_cost / 10, 1) if player.now_cost else None,
        "selected_by_pct":  player.selected_by_percent,
        "is_unavailable":   pred.is_unavailable,
        "chance_of_playing":pred.chance_of_playing,
        "predicted_pts":    round(pred.predicted_pts, 2),
        "pts_next5":        round(pred.pts_next5, 1) if pred.pts_next5 is not None else None,
        "xpts_proxy":       round(pred.xpts_proxy, 2) if pred.xpts_proxy is not None else None,
        "target_gw":        pred.target_gw,
        "model_run_at":     pred.model_run_at.isoformat(),
        "latest_stat":      _stat_dict(stat),
    }

    if include_breakdown:
        payload["gw_breakdown"] = pred.gw_breakdown or {}

    return payload
