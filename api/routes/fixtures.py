"""
api/routes/fixtures.py  —  /fixtures endpoints

GET /fixtures
    All fixtures (optionally filtered by season / GW range).

GET /fixtures/{gw}
    All fixtures for a specific gameweek, with FDR colours and team names.

GET /fixtures/fdr
    Fixture difficulty ticker — next N GWs for all teams.
    Used by the fixture ticker widget.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.database import get_db
from api.schema import Fixture, Team

router = APIRouter(prefix="/fixtures", tags=["fixtures"])

FDR_COLOURS = {1: "#00ff85", 2: "#01fc7a", 3: "#e7e7e7", 4: "#ff1751", 5: "#800742"}


@router.get("/")
def list_fixtures(
    season:   str           = Query("2526"),
    from_gw:  Optional[int] = Query(None),
    to_gw:    Optional[int] = Query(None),
    finished: Optional[bool]= Query(None),
    db:       Session       = Depends(get_db),
):
    q = db.query(Fixture).filter(Fixture.season == season)
    if from_gw is not None:
        q = q.filter(Fixture.gw >= from_gw)
    if to_gw is not None:
        q = q.filter(Fixture.gw <= to_gw)
    if finished is not None:
        q = q.filter(Fixture.finished == finished)

    fixtures = q.order_by(Fixture.gw, Fixture.id).all()
    return {"fixtures": [_fixture_dict(f) for f in fixtures], "count": len(fixtures)}


@router.get("/fdr")
def fixture_difficulty_ticker(
    season:    str = Query("2526"),
    num_gws:   int = Query(5, ge=1, le=10, description="Number of future GWs"),
    db:        Session = Depends(get_db),
):
    """
    Returns a fixture ticker: for each team, their next N fixtures with FDR
    and opponent label. Used by the fixture ticker widget.

    Shape: { teams: [{team_code, short_name, fixtures: [{gw, opp, fdr, is_home, colour}]}] }
    """
    teams = db.query(Team).filter(Team.season == season).order_by(Team.name).all()

    # Determine latest GW that has finished
    latest_finished = (db.query(Fixture.gw)
                         .filter(Fixture.season == season, Fixture.finished == True)
                         .order_by(Fixture.gw.desc())
                         .scalar() or 0)

    result = []
    for team in teams:
        fixtures = (db.query(Fixture)
                      .filter(
                          ((Fixture.team_h_code == team.code) | (Fixture.team_a_code == team.code)),
                          Fixture.season == season,
                          Fixture.gw > latest_finished,
                          Fixture.finished == False,
                      )
                      .order_by(Fixture.gw)
                      .limit(num_gws)
                      .all())

        result.append({
            "team_code":  team.code,
            "short_name": team.short_name,
            "name":       team.name,
            "fixtures": [
                {
                    "gw":      f.gw,
                    "is_home": f.team_h_code == team.code,
                    "fdr":     (f.team_h_difficulty if f.team_h_code == team.code
                                else f.team_a_difficulty) or 3,
                    "attack_fdr": (
                        f.attack_fdr_h if f.team_h_code == team.code
                        else f.defence_fdr_h
                    ) or ((f.team_h_difficulty if f.team_h_code == team.code else f.team_a_difficulty) or 3),
                    "defence_fdr": (
                        f.defence_fdr_h if f.team_h_code == team.code
                        else f.attack_fdr_h
                    ) or ((f.team_h_difficulty if f.team_h_code == team.code else f.team_a_difficulty) or 3),
                    "colour":  FDR_COLOURS.get(
                        (f.team_h_difficulty if f.team_h_code == team.code
                         else f.team_a_difficulty) or 3, "#e7e7e7"
                    ),
                    "opponent_code": (f.team_a_code if f.team_h_code == team.code
                                      else f.team_h_code),
                }
                for f in fixtures
            ],
        })

    return {"ticker": result, "from_gw": latest_finished + 1, "num_gws": num_gws}


@router.get("/{gw}")
def fixtures_for_gw(gw: int, season: str = "2526", db: Session = Depends(get_db)):
    """All fixtures for a single GW."""
    fixtures = (db.query(Fixture)
                  .filter(Fixture.gw == gw, Fixture.season == season)
                  .all())
    return {"gw": gw, "fixtures": [_fixture_dict(f) for f in fixtures]}


def _fixture_dict(f: Fixture) -> dict:
    return {
        "gw":             f.gw,
        "team_h_code":    f.team_h_code,
        "team_a_code":    f.team_a_code,
        "team_h_score":   f.team_h_score,
        "team_a_score":   f.team_a_score,
        "finished":       f.finished,
        "team_h_fdr":     f.team_h_difficulty,
        "team_a_fdr":     f.team_a_difficulty,
        "team_h_colour":  FDR_COLOURS.get(f.team_h_difficulty or 3, "#e7e7e7"),
        "team_a_colour":  FDR_COLOURS.get(f.team_a_difficulty or 3, "#e7e7e7"),
    }
