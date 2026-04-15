"""
etl/scheduler.py  —  Cron-style pipeline scheduler for local / VPS deployment.

Unchanged job logic from v3 scheduler.py; updated to import from etl/ and
models/ modules instead of root-level scripts.

Usage:
    python -m etl.scheduler --once            # run once immediately
    python -m etl.scheduler --once --force    # force even if data unchanged
    python -m etl.scheduler                   # run daily at 05:00 and 17:00 UTC
    python -m etl.scheduler --times 05:00,17:00
    python -m etl.scheduler --no-tune         # skip GridSearchCV
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from etl.db_sync import sync_predictions_to_db, sync_season_to_db

try:
    import schedule as _schedule_lib
    _HAS_SCHEDULE = True
except ImportError:
    _HAS_SCHEDULE = False

# ── Configuration ──────────────────────────────────────────────────────────────

PROJECT_DIR    = Path(__file__).parent.parent.resolve()
DATA_DIR       = Path(os.environ.get("FPL_DATA_DIR", str(PROJECT_DIR))).resolve()
ARTIFACTS_DIR  = PROJECT_DIR / "artifacts"
LOGS_DIR       = PROJECT_DIR / "logs"
STATE_FILE     = PROJECT_DIR / ".pipeline_state.json"

GITHUB_BASE    = (
    "https://raw.githubusercontent.com/olbauday/FPL-Core-Insights"
    "/main/data/2025-2026"
)
REMOTE_FILES   = {
    "players2526.csv": {
        "remote_name": "players.csv",
        "dest": DATA_DIR / "players2526.csv",
    },
    "teams2526.csv": {
        "remote_name": "teams.csv",
        "dest": DATA_DIR / "teams2526.csv",
    },
    "playerstats2526.csv": {
        "remote_name": "playerstats.csv",
        "dest": DATA_DIR / "playerstats2526.csv",
    },
}

DEFAULT_SCHEDULE_TIMES = os.environ.get("FPL_SCHEDULE_TIMES", "05:00,17:00")

# ── Logging ────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "scheduler.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("fpl_scheduler")


# ── State persistence ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    except Exception:
        return {}


def _save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Download helpers ───────────────────────────────────────────────────────────

def download_latest_csvs() -> dict:
    """Download 25-26 CSVs from GitHub. Returns {filename: was_updated}."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state  = _load_state()
    hashes = state.get("file_hashes", {})
    result = {}

    for local_name, cfg in REMOTE_FILES.items():
        remote_name = cfg.get("remote_name", local_name)
        dest = cfg["dest"]
        url = f"{GITHUB_BASE}/{remote_name}"
        log.info(f"  Fetching {local_name} (source: {remote_name})...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fpl-scheduler/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            new_hash  = hashlib.sha256(data).hexdigest()
            old_hash  = hashes.get(local_name)
            was_updated = new_hash != old_hash
            hashes[local_name] = new_hash
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            result[local_name] = was_updated
            log.info(f"    {local_name}: {'UPDATED' if was_updated else 'unchanged'} ({len(data):,} B)")
        except Exception as e:
            log.error(f"    Failed to fetch {local_name}: {e}")
            result[local_name] = False

    state["file_hashes"] = hashes
    _save_state(state)
    return result


def data_has_changed(updated: dict) -> bool:
    return any(bool(v) for v in updated.values())


# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_pipeline(tune: bool = True) -> bool:
    """
    Execute run_pipeline.py in a subprocess.
    Env vars FPL_DATA_DIR and FPL_ARTIFACTS_DIR are forwarded.
    """
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["FPL_DATA_DIR"]      = str(DATA_DIR)
    env["FPL_ARTIFACTS_DIR"] = str(ARTIFACTS_DIR)

    cmd = [sys.executable, str(PROJECT_DIR / "run_pipeline.py")]
    if not tune:
        cmd.append("--no-tune")

    log.info(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), env=env)

    success = result.returncode == 0
    log.info("  Pipeline completed." if success else f"  Pipeline FAILED (exit {result.returncode})")
    return success


def _log_run_result(success: bool, updated: dict):
    state = _load_state()
    runs  = state.get("run_history", [])
    now   = datetime.now(UTC).isoformat()
    runs.append({
        "timestamp":     now,
        "success":       success,
        "files_updated": [k for k, v in updated.items() if v],
    })
    state["run_history"]  = runs[-30:]
    state["last_run"]     = now
    if success:
        state["last_success"] = now
    _save_state(state)


# ── Main job ───────────────────────────────────────────────────────────────────

def run_job(tune: bool = True, force: bool = False):
    log.info("=" * 60)
    log.info("FPL SCHEDULED JOB STARTED")
    log.info(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC | tune={tune} force={force}")
    log.info("=" * 60)

    log.info("\n[1/4] Downloading latest 25-26 CSVs...")
    updated = download_latest_csvs()

    if not force and not data_has_changed(updated):
        log.info("\n[SKIP] No 25-26 CSV changes detected — no retraining needed.")
        return

    log.info("\n[2/4] Syncing 25-26 CSVs into DB tables...")
    sync_result = sync_season_to_db(
        season="2526",
        refresh_from_github=False,
        force_refresh=False,
        sync_fixtures=True,
    )
    for k, v in sync_result.get("counts", {}).items():
        log.info(f"    {k}: {v}")

    log.info("\n[3/4] Running FPL pipeline...")
    success = run_pipeline(tune=tune)

    pred_rows = 0
    if success:
        log.info("\n[4/4] Syncing latest predictions artifact into DB...")
        pred_rows = sync_predictions_to_db(season="2526")
        log.info(f"    Predictions inserted: {pred_rows}")

    log.info("\nLogging result...")
    _log_run_result(success, updated)

    if success:
        pred_path = ARTIFACTS_DIR / "predictions_top.csv"
        if pred_path.exists():
            import pandas as pd
            df   = pd.read_csv(pred_path, index_col=0)
            cols = [c for c in ["web_name", "position", "price_m", "predicted_pts", "pts_next5"]
                    if c in df.columns]
            log.info(f"\n  Top 5 predictions:\n{df[cols].head(5).to_string()}")

    log.info("\n" + "=" * 60)
    log.info("JOB COMPLETE" if success else "JOB FAILED")
    log.info("=" * 60 + "\n")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FPL pipeline scheduler")
    parser.add_argument("--once",    action="store_true", help="Run once then exit")
    parser.add_argument("--force",   action="store_true", help="Run even if data unchanged")
    parser.add_argument("--no-tune", action="store_true", help="Skip GridSearchCV")
    parser.add_argument(
        "--times",
        default=DEFAULT_SCHEDULE_TIMES,
        help=f"Comma-separated UTC run times HH:MM (default {DEFAULT_SCHEDULE_TIMES})",
    )
    args = parser.parse_args()

    tune  = not args.no_tune
    force = args.force

    if args.once:
        run_job(tune=tune, force=force)
        return

    if not _HAS_SCHEDULE:
        log.error("'schedule' package not installed. Run: pip install schedule")
        sys.exit(1)

    times = [t.strip() for t in args.times.split(",") if t.strip()]
    if not times:
        log.error("No valid schedule times provided")
        sys.exit(1)

    for t in times:
        _schedule_lib.every().day.at(t).do(run_job, tune=tune, force=force)

    log.info(f"Scheduler started — daily at {', '.join(times)} UTC. Press Ctrl+C to stop.\n")

    while True:
        _schedule_lib.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
