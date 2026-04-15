"""
api/  —  FastAPI backend.

    database.py     — SQLAlchemy engine + session dependency
    schema.py       — ORM models (players, teams, fixtures, stats, predictions, plans, users)
    main.py         — FastAPI app with all routes mounted
    routes/
        predictions.py  — /predictions, /predictions/{player_id}
        players.py      — /players, /players/{id}, /compare
        teams.py        — /teams, /teams/{id}
        fixtures.py     — /fixtures, /fixtures/{gw}
        live.py         — /live  (live scores + fantasy points)
        planner.py      — /planner  (transfer plan CRUD)
"""
