"""
api/routes/teams.py  —  /teams endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from api.database import get_db
from api.schema import Team, Fixture

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/")
def list_teams(season: str = Query("2526"), db: Session = Depends(get_db)):
    """All teams with strength and FDR ratings."""
    teams = db.query(Team).filter(Team.season == season).order_by(Team.name).all()
    return {"teams": [_team_dict(t) for t in teams]}


@router.get("/{team_code}")
def team_detail(team_code: int, season: str = "2526", db: Session = Depends(get_db)):
    """Single team detail + their next 5 fixtures."""
    team = db.query(Team).filter(Team.code == team_code, Team.season == season).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team {team_code} not found")

    fixtures = (db.query(Fixture)
                  .filter(
                      ((Fixture.team_h_code == team_code) | (Fixture.team_a_code == team_code)),
                      Fixture.season == season,
                      Fixture.finished == False,
                  )
                  .order_by(Fixture.gw)
                  .limit(5)
                  .all())

    return {
        "team":     _team_dict(team),
        "fixtures": [_fixture_dict(f, team_code) for f in fixtures],
    }


def _team_dict(t: Team) -> dict:
    return {
        "code":       t.code,
        "name":       t.name,
        "short_name": t.short_name,
        "fdr":        t.fdr,
        "attack_fdr": t.attack_fdr,
        "defence_fdr":t.defence_fdr,
        "elo":        t.elo,
        "strength_attack_home":  t.strength_attack_home,
        "strength_attack_away":  t.strength_attack_away,
        "strength_defence_home": t.strength_defence_home,
        "strength_defence_away": t.strength_defence_away,
    }


def _fixture_dict(f: Fixture, pov_team: int) -> dict:
    is_home = f.team_h_code == pov_team
    return {
        "gw":        f.gw,
        "is_home":   is_home,
        "opponent":  f.team_a_code if is_home else f.team_h_code,
        "fdr":       f.team_h_difficulty if is_home else f.team_a_difficulty,
    }
