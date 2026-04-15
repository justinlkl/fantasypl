"""
api/database.py  —  Database connection and session factory.

Reads DATABASE_URL from environment (defaults to a local SQLite file
so the app runs without PostgreSQL during development).

Production: set DATABASE_URL=postgresql+asyncpg://user:pass@host/fpl
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or "sqlite:///./fpl_app.db"   # dev default — swap for PostgreSQL in prod
)

# ── Engine ─────────────────────────────────────────────────────────────────────
# connect_args is needed for SQLite only (not for PostgreSQL).
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    echo=bool(os.environ.get("FPL_SQL_ECHO", "")),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────────

def get_db():
    """Yield a database session; close it when the request is done."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
