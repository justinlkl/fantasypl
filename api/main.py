"""
api/main.py  —  FastAPI application entry point.

Routes mounted:
    /predictions    — model predictions (next GW + 5-GW breakdown)
    /players        — player registry, stats, history, comparison
    /teams          — team strength and FDR
    /fixtures       — fixture schedule and FDR ticker
    /live           — live match scores and fantasy points
    /planner        — transfer planning CRUD

Run locally:
    uvicorn api.main:app --reload --port 8000

Environment variables:
    DATABASE_URL      — SQLAlchemy connection string (default: SQLite ./fpl_app.db)
    FPL_DATA_DIR      — path to CSV data directory (default: ./data)
    FPL_ARTIFACTS_DIR — path to model artifacts (default: ./artifacts)
    FPL_ADMIN_KEY     — API key for /predictions/refresh (default: changeme)
    FPL_SQL_ECHO      — set any value to log SQL queries
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import engine
from api.schema import Base
from api.routes import predictions, players, teams, fixtures, live, planner

# ── Create tables on startup (idempotent) ──────────────────────────────────────
Base.metadata.create_all(bind=engine)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title        = "FPL Prediction API",
    description  = "Machine-learning predictions, live scores, and transfer planning for FPL.",
    version      = "1.0.0",
    docs_url     = "/docs",
    redoc_url    = "/redoc",
)

# ── CORS (open during dev; restrict to your domain in production) ──────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],     # TODO: restrict to your frontend domain
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Mount routers ──────────────────────────────────────────────────────────────
app.include_router(predictions.router)
app.include_router(players.router)
app.include_router(teams.router)
app.include_router(fixtures.router)
app.include_router(live.router)
app.include_router(planner.router)


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": app.version}


@app.get("/", tags=["meta"])
def root():
    return {
        "app":     "FPL Prediction API",
        "docs":    "/docs",
        "health":  "/health",
        "routes": [
            "/predictions", "/players", "/teams",
            "/fixtures", "/live", "/planner",
        ],
    }
