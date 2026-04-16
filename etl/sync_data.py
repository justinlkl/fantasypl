"""
etl/sync_data.py  —  Download all source CSVs the pipeline needs.

Called by GitHub Actions before run_pipeline.py.
Downloads 2025-26 files from olbauday/FPL-Core-Insights.
2024-25 files must be committed to the repo (not available upstream).

Usage:
    python -m etl.sync_data
    FPL_DATA_DIR=/path/to/data python -m etl.sync_data
"""

import hashlib
import os
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("FPL_DATA_DIR", Path(__file__).resolve().parent))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Confirmed paths from olbauday/FPL-Core-Insights repo
BASE_URL = "https://raw.githubusercontent.com/olbauday/FPL-Core-Insights/main/data/2025-2026"

REMOTE_FILES = {
    "players2526.csv":     f"{BASE_URL}/players.csv",
    "teams2526.csv":       f"{BASE_URL}/teams.csv",
    "playerstats2526.csv": f"{BASE_URL}/playerstats.csv",
}

# These must be committed to your repo — not available from upstream
LOCAL_REQUIRED = [
    "players2425.csv",
    "playerstats2425.csv",
    "teams2425.csv",
    "playermatchstats2425.csv",  # optional — pipeline skips gracefully if missing
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def sync_remote() -> dict[str, str]:
    """Download 2526 CSVs. Returns {filename: status}."""
    results = {}
    for local_name, url in REMOTE_FILES.items():
        dest = DATA_DIR / local_name
        old_hash = _sha256(dest)
        print(f"  Fetching {local_name}...", end=" ", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "fpl-sync/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            new_hash = hashlib.sha256(data).hexdigest()
            if new_hash == old_hash:
                print("unchanged")
                results[local_name] = "unchanged"
            else:
                dest.write_bytes(data)
                print(f"updated ({len(data):,} bytes)")
                results[local_name] = "updated"
        except Exception as e:
            print(f"FAILED: {e}")
            results[local_name] = f"error: {e}"
    return results


def check_local() -> list[str]:
    """Report which local-only files are present/missing."""
    missing = []
    for fname in LOCAL_REQUIRED:
        path = DATA_DIR / fname
        fallback = PROJECT_ROOT / fname
        if path.exists():
            print(f"  {fname}: present in data dir ({path.stat().st_size:,} bytes)")
        elif fallback.exists():
            print(f"  {fname}: present in repo root ({fallback.stat().st_size:,} bytes)")
        else:
            status = "optional — pipeline will skip" if "matchstats" in fname else "MISSING — pipeline will fail"
            print(f"  {fname}: {status}")
            if "matchstats" not in fname:
                missing.append(fname)
    return missing


if __name__ == "__main__":
    print(f"\nData directory: {DATA_DIR}\n")

    print("Downloading 2025-26 files from olbauday/FPL-Core-Insights...")
    results = sync_remote()

    print("\nChecking 2024-25 local files (must be committed to repo)...")
    missing = check_local()

    print()
    if missing:
        print(f"ERROR: {len(missing)} required file(s) missing: {missing}")
        print("Commit these to your repo or set FPL_DATA_DIR to a location that has them.")
        sys.exit(1)
    else:
        updated = [k for k, v in results.items() if v == "updated"]
        print(f"Sync complete. {len(updated)} file(s) updated.")
