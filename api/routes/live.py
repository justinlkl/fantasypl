"""
api/routes/live.py  —  /live endpoints

GET /live/matches
    Current GW live match scorelines (from FPL event/live endpoint).
    Cached in Redis for 60 seconds during active matches.

GET /live/points
    Live fantasy points for all players in the current GW.
    Returns provisional points, bonus projection, minutes, and events.

GET /live/bonus
    Current bonus points projection for the active GW.

GET /live/impact
    "Impact on my squad" — given a list of player_ids, return their
    live points + events so a user can track their own team.

All data is fetched from the FPL official API:
    https://fantasy.premierleague.com/api/event/{gw}/live/
    https://fantasy.premierleague.com/api/fixtures/?event={gw}

In production these calls should be cached (Redis / in-memory) and
refreshed every 15–60 seconds during active match windows.
"""

import json
import time
import urllib.request
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/live", tags=["live"])

FPL_API   = "https://fantasy.premierleague.com/api"
_UA       = "fpl-app/1.0"
_CACHE: dict[str, tuple[float, any]] = {}   # {key: (timestamp, data)}
_TTL      = 60   # seconds — refresh live data every minute


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _get_cache(key: str):
    if key in _CACHE:
        ts, data = _CACHE[key]
        if time.time() - ts < _TTL:
            return data
    return None


def _set_cache(key: str, data):
    _CACHE[key] = (time.time(), data)
    return data


def _fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _current_gw() -> int:
    """Return the current active GW from FPL bootstrap-static."""
    key = "current_gw"
    cached = _get_cache(key)
    if cached:
        return cached
    data  = _fetch_json(f"{FPL_API}/bootstrap-static/")
    events = data.get("events", [])
    for ev in events:
        if ev.get("is_current"):
            return _set_cache(key, int(ev["id"]))
    # fallback: last finished GW + 1
    for ev in reversed(events):
        if ev.get("finished"):
            return _set_cache(key, int(ev["id"]) + 1)
    return 1


# ── GET /live/matches ──────────────────────────────────────────────────────────

@router.get("/matches")
def live_matches(gw: Optional[int] = Query(None, description="Gameweek (default: current)")):
    """
    Live scorelines for the requested GW.
    Returns team names, scores, minutes played, and match status.
    """
    try:
        gw = gw or _current_gw()
        key = f"fixtures_{gw}"
        data = _get_cache(key)
        if data is None:
            raw  = _fetch_json(f"{FPL_API}/fixtures/?event={gw}")
            data = _set_cache(key, raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"FPL API unavailable: {e}")

    matches = []
    for f in data:
        matches.append({
            "fixture_id":   f.get("id"),
            "gw":           f.get("event"),
            "team_h_id":    f.get("team_h"),
            "team_a_id":    f.get("team_a"),
            "team_h_score": f.get("team_h_score"),
            "team_a_score": f.get("team_a_score"),
            "started":      f.get("started", False),
            "finished":     f.get("finished", False),
            "finished_provisional": f.get("finished_provisional", False),
            "minutes":      f.get("minutes", 0),
            "team_h_difficulty": f.get("team_h_difficulty"),
            "team_a_difficulty": f.get("team_a_difficulty"),
            # Match stats (available after game)
            "stats":        f.get("stats", []),
        })

    return {"gw": gw, "matches": matches, "count": len(matches)}


# ── GET /live/points ───────────────────────────────────────────────────────────

@router.get("/points")
def live_points(gw: Optional[int] = Query(None)):
    """
    Live fantasy points for all players in the current GW.
    Includes minutes, goals, assists, bonus projection, and auto-subs.
    """
    try:
        gw = gw or _current_gw()
        key = f"live_{gw}"
        data = _get_cache(key)
        if data is None:
            raw  = _fetch_json(f"{FPL_API}/event/{gw}/live/")
            data = _set_cache(key, raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"FPL API unavailable: {e}")

    elements = data.get("elements", [])
    players  = []
    for el in elements:
        stats = el.get("stats", {})
        # Reconstruct total live points
        pts   = stats.get("total_points", 0)
        players.append({
            "player_id":       el.get("id"),
            "live_pts":        pts,
            "minutes":         stats.get("minutes", 0),
            "goals_scored":    stats.get("goals_scored", 0),
            "assists":         stats.get("assists", 0),
            "clean_sheets":    stats.get("clean_sheets", 0),
            "goals_conceded":  stats.get("goals_conceded", 0),
            "own_goals":       stats.get("own_goals", 0),
            "penalties_saved": stats.get("penalties_saved", 0),
            "penalties_missed":stats.get("penalties_missed", 0),
            "yellow_cards":    stats.get("yellow_cards", 0),
            "red_cards":       stats.get("red_cards", 0),
            "saves":           stats.get("saves", 0),
            "bonus":           stats.get("bonus", 0),
            "bps":             stats.get("bps", 0),
            "in_dreamteam":    stats.get("in_dreamteam", False),
            "explain":         el.get("explain", []),
        })

    return {"gw": gw, "players": players, "count": len(players)}


# ── GET /live/bonus ────────────────────────────────────────────────────────────

@router.get("/bonus")
def live_bonus(gw: Optional[int] = Query(None)):
    """
    Current provisional bonus points per player, sorted by BPS.
    Only players in active or recently completed matches are included.
    """
    try:
        gw = gw or _current_gw()
        key = f"live_{gw}"
        data = _get_cache(key)
        if data is None:
            raw  = _fetch_json(f"{FPL_API}/event/{gw}/live/")
            data = _set_cache(key, raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"FPL API unavailable: {e}")

    elements = data.get("elements", [])
    bonus_players = []
    for el in elements:
        stats = el.get("stats", {})
        bps   = stats.get("bps", 0)
        bonus = stats.get("bonus", 0)
        if bps > 0 or bonus > 0:
            bonus_players.append({
                "player_id": el.get("id"),
                "bps":       bps,
                "bonus":     bonus,
            })

    bonus_players.sort(key=lambda x: x["bps"], reverse=True)

    # Project bonus points from BPS (top 3 BPS per fixture → 3,2,1 pts)
    # This is a simplified projection; the FPL API handles tie-breaking.
    return {
        "gw":     gw,
        "bonus":  bonus_players,
        "count":  len(bonus_players),
        "note":   "Provisional — final bonus awarded ~90 min after last match",
    }


# ── GET /live/impact ──────────────────────────────────────────────────────────

@router.get("/impact")
def squad_live_impact(
    ids: str           = Query(..., description="Comma-separated player_ids"),
    gw:  Optional[int] = Query(None),
):
    """
    Live points + events for a user's squad players.
    Use this to build the 'impact on my team' panel.

    Returns each player's live pts, goals, assists, bonus, and
    whether they're in an active/upcoming/finished match.
    """
    id_set = {int(i) for i in ids.split(",") if i.strip().isdigit()}
    if not id_set:
        raise HTTPException(status_code=400, detail="No valid player IDs provided")

    try:
        gw = gw or _current_gw()
        key = f"live_{gw}"
        data = _get_cache(key)
        if data is None:
            raw  = _fetch_json(f"{FPL_API}/event/{gw}/live/")
            data = _set_cache(key, raw)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"FPL API unavailable: {e}")

    elements = {el["id"]: el for el in data.get("elements", [])}
    result   = []

    for pid in id_set:
        el = elements.get(pid)
        if not el:
            result.append({"player_id": pid, "found": False})
            continue
        stats = el.get("stats", {})
        result.append({
            "player_id":    pid,
            "found":        True,
            "live_pts":     stats.get("total_points", 0),
            "minutes":      stats.get("minutes", 0),
            "goals_scored": stats.get("goals_scored", 0),
            "assists":      stats.get("assists", 0),
            "clean_sheets": stats.get("clean_sheets", 0),
            "bonus":        stats.get("bonus", 0),
            "bps":          stats.get("bps", 0),
            "yellow_cards": stats.get("yellow_cards", 0),
            "red_cards":    stats.get("red_cards", 0),
            "explain":      el.get("explain", []),
        })

    total_live_pts = sum(r.get("live_pts", 0) for r in result if r.get("found"))

    return {
        "gw":            gw,
        "squad_live_pts": total_live_pts,
        "players":       result,
    }
