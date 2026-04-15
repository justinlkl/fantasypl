"""
etl/  —  Data ingestion, loading, FDR computation, and scheduling.

Modules:
    data_loader  — loads & merges FPL CSVs into a clean per-GW DataFrame
    fdr          — builds FDR table and fixture schedule (live + inferred)
    scheduler    — cron-style pipeline scheduler (local / VPS)
"""
