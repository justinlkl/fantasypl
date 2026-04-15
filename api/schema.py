"""
api/schema.py  —  SQLAlchemy ORM models (database schema).

Tables:
    users           — FPL accounts that use the app
    teams           — 20 PL teams with strength ratings & ELO
    players         — player registry (position, team, price, flags)
    fixtures        — GW fixture schedule with FDR ratings
    player_stats    — per-GW rolling stats for each player (both seasons)
    predictions     — model output: next-GW and 5-GW FDR-adjusted points
    plans           — user transfer plans per GW

Run `python -m api.schema` to create all tables.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey,
    Integer, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base


# ── users ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id           : Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
    email        : Mapped[str]           = mapped_column(String(255), unique=True, index=True)
    fpl_team_id  : Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    display_name : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at   : Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    is_active    : Mapped[bool]          = mapped_column(Boolean, default=True)

    plans: Mapped[list["Plan"]] = relationship("Plan", back_populates="user")


# ── teams ──────────────────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id                    : Mapped[int]            = mapped_column(Integer, primary_key=True)
    code                  : Mapped[int]            = mapped_column(Integer, unique=True, index=True)
    name                  : Mapped[str]            = mapped_column(String(80))
    short_name            : Mapped[str]            = mapped_column(String(10))
    season                : Mapped[str]            = mapped_column(String(6), index=True)  # "2526"

    # Strength ratings (from FPL bootstrap-static)
    strength              : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    strength_overall_home : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    strength_overall_away : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    strength_attack_home  : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    strength_attack_away  : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    strength_defence_home : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    strength_defence_away : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    elo                   : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Derived FDR (1–5)
    fdr           : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attack_fdr    : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    defence_fdr   : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    players  : Mapped[list["Player"]]  = relationship("Player",  back_populates="team")
    fixtures_home: Mapped[list["Fixture"]] = relationship(
        "Fixture", foreign_keys="Fixture.team_h_code", back_populates="team_home")
    fixtures_away: Mapped[list["Fixture"]] = relationship(
        "Fixture", foreign_keys="Fixture.team_a_code", back_populates="team_away")

    __table_args__ = (UniqueConstraint("code", "season", name="uq_team_season"),)


# ── players ────────────────────────────────────────────────────────────────────

class Player(Base):
    __tablename__ = "players"

    id           : Mapped[int]            = mapped_column(Integer, primary_key=True)
    player_id    : Mapped[int]            = mapped_column(Integer, index=True)
    web_name     : Mapped[str]            = mapped_column(String(100))
    season       : Mapped[str]            = mapped_column(String(6), index=True)
    position     : Mapped[str]            = mapped_column(String(4))  # GK/DEF/MID/FWD
    team_code    : Mapped[int]            = mapped_column(Integer, ForeignKey("teams.code"), index=True)

    # Current-GW snapshot (updated each GW)
    now_cost                  : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selected_by_percent       : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    chance_of_playing_next_round: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status                    : Mapped[Optional[str]]   = mapped_column(String(2), nullable=True)
    is_unavailable            : Mapped[bool]            = mapped_column(Boolean, default=False)

    # Player flags
    team_changed  : Mapped[bool] = mapped_column(Boolean, default=False)
    is_new_player : Mapped[bool] = mapped_column(Boolean, default=False)

    # Set-piece flags (updated each GW)
    is_penalties_taker           : Mapped[bool] = mapped_column(Boolean, default=False)
    is_corners_taker             : Mapped[bool] = mapped_column(Boolean, default=False)
    is_freekicks_taker           : Mapped[bool] = mapped_column(Boolean, default=False)

    team   : Mapped["Team"]               = relationship("Team", back_populates="players")
    stats  : Mapped[list["PlayerStat"]]   = relationship("PlayerStat",  back_populates="player")
    preds  : Mapped[list["Prediction"]]   = relationship("Prediction",  back_populates="player")

    __table_args__ = (UniqueConstraint("player_id", "season", name="uq_player_season"),)


# ── fixtures ───────────────────────────────────────────────────────────────────

class Fixture(Base):
    __tablename__ = "fixtures"

    id            : Mapped[int]            = mapped_column(Integer, primary_key=True)
    gw            : Mapped[int]            = mapped_column(Integer, index=True)
    season        : Mapped[str]            = mapped_column(String(6), index=True)

    team_h_code   : Mapped[int]            = mapped_column(Integer, ForeignKey("teams.code"))
    team_a_code   : Mapped[int]            = mapped_column(Integer, ForeignKey("teams.code"))

    team_h_score  : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    team_a_score  : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    finished      : Mapped[bool]           = mapped_column(Boolean, default=False)

    # FDR from home team's perspective
    team_h_difficulty : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # FPL official
    team_a_difficulty : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attack_fdr_h  : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)  # derived
    defence_fdr_h : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)
    elo_diff      : Mapped[Optional[float]]= mapped_column(Float, nullable=True)

    team_home: Mapped["Team"] = relationship("Team", foreign_keys=[team_h_code],
                                             back_populates="fixtures_home")
    team_away: Mapped["Team"] = relationship("Team", foreign_keys=[team_a_code],
                                             back_populates="fixtures_away")

    __table_args__ = (UniqueConstraint("gw", "team_h_code", "team_a_code", "season",
                                       name="uq_fixture"),)


# ── player_stats ───────────────────────────────────────────────────────────────

class PlayerStat(Base):
    """
    Per-GW stats for each player (both raw and rolling engineered features).
    Populated by the ETL pipeline after each gameweek.
    """
    __tablename__ = "player_stats"

    id        : Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id : Mapped[int] = mapped_column(Integer, ForeignKey("players.player_id"), index=True)
    gw        : Mapped[int] = mapped_column(Integer, index=True)
    season    : Mapped[str] = mapped_column(String(6))

    # Raw per-GW stats
    event_points     : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    minutes          : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    goals_scored     : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assists          : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clean_sheets     : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    goals_conceded   : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    saves            : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bonus            : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bps              : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Expected stats
    xg               : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    xa               : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    xgi              : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    xgc              : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Per-90 rates (forward-filled)
    xg_per90         : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    xa_per90         : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    xgi_per90        : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    saves_per90      : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cs_per90         : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    xgc_per90        : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Rolling averages (stored as JSON for flexibility)
    rolling_features : Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Price / ownership snapshot
    now_cost         : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selected_by_pct  : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    player: Mapped["Player"] = relationship("Player", back_populates="stats")

    __table_args__ = (UniqueConstraint("player_id", "gw", "season", name="uq_stat"),)


# ── predictions ────────────────────────────────────────────────────────────────

class Prediction(Base):
    """
    Model predictions for a player for a given target GW.
    One row per (player, prediction_gw, model_run_at) tuple.
    """
    __tablename__ = "predictions"

    id              : Mapped[int]   = mapped_column(Integer, primary_key=True)
    player_id       : Mapped[int]   = mapped_column(Integer, ForeignKey("players.player_id"), index=True)
    season          : Mapped[str]   = mapped_column(String(6))
    target_gw       : Mapped[int]   = mapped_column(Integer, index=True)  # GW being predicted
    model_run_at    : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Core outputs
    predicted_pts   : Mapped[float] = mapped_column(Float)
    xpts_proxy      : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 5-GW breakdown (stored as JSON: {gw: {pred, opp, fdr, is_home}})
    gw_breakdown    : Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    pts_next5       : Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Availability at prediction time
    chance_of_playing: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_unavailable  : Mapped[bool]             = mapped_column(Boolean, default=False)

    player: Mapped["Player"] = relationship("Player", back_populates="preds")

    __table_args__ = (UniqueConstraint("player_id", "target_gw", "model_run_at",
                                       name="uq_prediction"),)


# ── plans ──────────────────────────────────────────────────────────────────────

class Plan(Base):
    """
    User transfer plan for a future GW window.
    Stores squad, transfers in/out, bank, chip, and projected points as JSON.
    """
    __tablename__ = "plans"

    id          : Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id     : Mapped[int]      = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name        : Mapped[str]      = mapped_column(String(100), default="My Plan")
    created_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow,
                                                    onupdate=datetime.utcnow)

    # Planning window
    from_gw     : Mapped[int]      = mapped_column(Integer)
    to_gw       : Mapped[int]      = mapped_column(Integer)

    # Squad state — list of player_ids (15 players)
    squad       : Mapped[list]     = mapped_column(JSON)           # [player_id, ...]
    bank        : Mapped[float]    = mapped_column(Float, default=0.0)   # £M remaining
    free_transfers: Mapped[int]    = mapped_column(Integer, default=1)
    chip        : Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "wc","bb","fh","tc"

    # Transfer history [{gw, transfers_in: [id], transfers_out: [id], hit: int}]
    transfer_log: Mapped[list]     = mapped_column(JSON, default=list)

    # Projected points per GW [{gw, pts, captain_id, vc_id}]
    gw_projections: Mapped[list]   = mapped_column(JSON, default=list)

    user: Mapped["User"] = relationship("User", back_populates="plans")


# ── Table creation ─────────────────────────────────────────────────────────────

def create_all_tables():
    """Create all tables (run once on first deploy or after schema changes)."""
    from api.database import engine
    Base.metadata.create_all(bind=engine)
    print("All tables created.")


if __name__ == "__main__":
    create_all_tables()
