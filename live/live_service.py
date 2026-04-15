"""
live/live_service.py  —  Live match data service

Handles fetching, caching, and processing of live FPL event data.
This is the backend worker that the /live API routes consume.

In production this runs as an APScheduler or Celery Beat job that:
  1. Polls the FPL live endpoint every 15–60 seconds during active matches
  2. Writes results to Redis (TTL 60s) for the API to serve instantly
  3. Persists final GW stats to PostgreSQL after each match finishes

Architecture:
    live_service.py         ← this file (poller + processor)
    api/routes/live.py      ← FastAPI routes that read from the cache

Redis keys used:
    live:gw:{gw}            — raw FPL event/live JSON (TTL: 60s)
    live:fixtures:{gw}      — fixture scorelines (TTL: 60s)
    live:bonus:{gw}         — BPS/bonus projection (TTL: 60s)
    live:current_gw         — current GW number (TTL: 3600s)
"""

import json
import logging
import os
import time
import urllib.request
from datetime import datetime
from typing import Optional

log = logging.getLogger("fpl_live")

FPL_API  = "https://fantasy.premierleague.com/api"
_UA      = "fpl-app/1.0"

# Redis is optional — if not available, falls back to in-process dict cache.
try:
    import redis as _redis_lib
    _REDIS: Optional[_redis_lib.Redis] = _redis_lib.Redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    _REDIS.ping()
    _HAS_REDIS = True
    log.info("Redis connected.")
except Exception:
    _REDIS     = None
    _HAS_REDIS = False
    log.warning("Redis not available — using in-process cache (not suitable for multi-worker).")

_IN_PROCESS_CACHE: dict[str, tuple[float, str]] = {}


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_get(key: str) -> Optional[str]:
    if _HAS_REDIS and _REDIS:
        return _REDIS.get(key)
    entry = _IN_PROCESS_CACHE.get(key)
    if entry:
        ts, val = entry
        if time.time() - ts < 60:
            return val
    return None


def _cache_set(key: str, value: str, ttl: int = 60):
    if _HAS_REDIS and _REDIS:
        _REDIS.setex(key, ttl, value)
    else:
        _IN_PROCESS_CACHE[key] = (time.time(), value)


# ── FPL API fetch ──────────────────────────────────────────────────────────────

def _fetch_json(url: str, timeout: int = 10):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


# ── Current GW ────────────────────────────────────────────────────────────────

def get_current_gw() -> int:
    key    = "live:current_gw"
    cached = _cache_get(key)
    if cached:
        return int(cached)

    data   = _fetch_json(f"{FPL_API}/bootstrap-static/")
    events = data.get("events", [])
    for ev in events:
        if ev.get("is_current"):
            gw = int(ev["id"])
            _cache_set(key, str(gw), ttl=3600)
            return gw
    # Fallback: last finished GW + 1
    for ev in reversed(events):
        if ev.get("finished"):
            gw = int(ev["id"]) + 1
            _cache_set(key, str(gw), ttl=3600)
            return gw
    return 1


# ── Live event data ────────────────────────────────────────────────────────────

def fetch_live_event(gw: Optional[int] = None, force: bool = False) -> dict:
    """
    Fetch and cache live player stats for a GW.
    Returns the raw FPL event/live response dict.
    """
    gw  = gw or get_current_gw()
    key = f"live:gw:{gw}"

    if not force:
        cached = _cache_get(key)
        if cached:
            return json.loads(cached)

    data = _fetch_json(f"{FPL_API}/event/{gw}/live/")
    _cache_set(key, json.dumps(data), ttl=60)
    return data


def fetch_live_fixtures(gw: Optional[int] = None, force: bool = False) -> list:
    """Fetch and cache live fixture scores for a GW."""
    gw  = gw or get_current_gw()
    key = f"live:fixtures:{gw}"

    if not force:
        cached = _cache_get(key)
        if cached:
            return json.loads(cached)

    data = _fetch_json(f"{FPL_API}/fixtures/?event={gw}")
    _cache_set(key, json.dumps(data), ttl=60)
    return data


# ── Processed outputs ──────────────────────────────────────────────────────────

def get_live_player_points(gw: Optional[int] = None) -> list[dict]:
    """
    Return processed live points per player.
    Enriches raw element data with a clean dict per player.
    """
    data     = fetch_live_event(gw)
    elements = data.get("elements", [])
    result   = []
    for el in elements:
        stats = el.get("stats", {})
        result.append({
            "player_id":        el["id"],
            "live_pts":         stats.get("total_points", 0),
            "minutes":          stats.get("minutes", 0),
            "goals_scored":     stats.get("goals_scored", 0),
            "assists":          stats.get("assists", 0),
            "clean_sheets":     stats.get("clean_sheets", 0),
            "goals_conceded":   stats.get("goals_conceded", 0),
            "own_goals":        stats.get("own_goals", 0),
            "penalties_saved":  stats.get("penalties_saved", 0),
            "penalties_missed": stats.get("penalties_missed", 0),
            "yellow_cards":     stats.get("yellow_cards", 0),
            "red_cards":        stats.get("red_cards", 0),
            "saves":            stats.get("saves", 0),
            "bonus":            stats.get("bonus", 0),
            "bps":              stats.get("bps", 0),
            "in_dreamteam":     stats.get("in_dreamteam", False),
        })
    return result


def get_bonus_projection(gw: Optional[int] = None) -> list[dict]:
    """
    Return provisional bonus projection sorted by BPS.
    Top BPS per match → 3 pts, 2nd → 2 pts, 3rd → 1 pt.
    """
    data     = fetch_live_event(gw)
    elements = data.get("elements", [])

    bonus = [
        {"player_id": el["id"],
         "bps":       el["stats"].get("bps", 0),
         "bonus":     el["stats"].get("bonus", 0)}
        for el in elements
        if el["stats"].get("bps", 0) > 0 or el["stats"].get("bonus", 0) > 0
    ]
    bonus.sort(key=lambda x: x["bps"], reverse=True)
    return bonus


def get_squad_impact(player_ids: list[int], gw: Optional[int] = None) -> dict:
    """
    Return live impact for a specific squad — total pts + per-player breakdown.
    """
    all_pts   = {p["player_id"]: p for p in get_live_player_points(gw)}
    squad_pts = []

    for pid in player_ids:
        entry = all_pts.get(pid, {"player_id": pid, "live_pts": 0, "minutes": 0})
        squad_pts.append(entry)

    total = sum(p.get("live_pts", 0) for p in squad_pts)
    return {
        "gw":             gw or get_current_gw(),
        "squad_live_pts": total,
        "players":        squad_pts,
    }


# ── Polling loop ───────────────────────────────────────────────────────────────

def run_live_poller(poll_interval: int = 60):
    """
    Background poller: refresh live data every `poll_interval` seconds.
    Run this in a separate thread or as a Celery Beat task.

    In production:
        Thread:  threading.Thread(target=run_live_poller, daemon=True).start()
        Celery:  @app.on_after_configure.connect → celery.beat schedule
    """
    log.info(f"Live poller started (interval={poll_interval}s)")
    while True:
        try:
            gw = get_current_gw()
            fetch_live_event(gw, force=True)
            fetch_live_fixtures(gw, force=True)
            log.debug(f"Live data refreshed for GW{gw} at {datetime.utcnow().isoformat()}")
        except Exception as e:
            log.error(f"Live poller error: {e}")
        time.sleep(poll_interval)


if __name__ == "__main__":
    # Quick smoke test
    gw  = get_current_gw()
    pts = get_live_player_points(gw)
    print(f"GW{gw}: {len(pts)} players with live data")
    bonus = get_bonus_projection(gw)
    print(f"Top 5 bonus projection: {bonus[:5]}")
