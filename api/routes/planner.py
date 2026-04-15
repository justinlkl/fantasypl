"""
api/routes/planner.py  —  /planner endpoints (Phase 2)

Transfer planner: squad by GW, bank, free transfers, chip simulation,
and fixture difficulty view. Benchmarked against FPL Team's planner.

GET  /planner/{plan_id}         — load a saved plan
POST /planner                   — create a new plan
PUT  /planner/{plan_id}         — update squad / transfers / chip for a GW
DEL  /planner/{plan_id}         — delete a plan

POST /planner/{plan_id}/transfer
    Apply a transfer (one player out → one player in).
    Validates bank, free transfers, and squad rules (max 3 from same club).

GET  /planner/{plan_id}/projections
    GW-by-GW projected points for the planned squad,
    FDR-adjusted using the fixture schedule.

POST /planner/{plan_id}/simulate-chip
    Simulate a chip (Wildcard/Bench Boost/Free Hit/Triple Captain)
    and return the projected points impact.

NOTE: Auth is placeholder (user_id in request body).
      Replace with JWT / session token in production.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import get_db
from api.schema import Plan, Player, Prediction

router = APIRouter(prefix="/planner", tags=["planner"])

VALID_CHIPS  = {"wc", "bb", "fh", "tc", None}
POSITION_LIMITS = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}   # standard 15-man squad
CLUB_LIMIT   = 3


# ── Pydantic request models ────────────────────────────────────────────────────

class CreatePlanRequest(BaseModel):
    user_id:        int
    name:           str              = "My Plan"
    from_gw:        int
    to_gw:          int
    squad:          list[int]        = Field(..., min_length=15, max_length=15,
                                             description="15 player_ids")
    bank:           float            = 0.0
    free_transfers: int              = 1
    chip:           Optional[str]    = None


class UpdatePlanRequest(BaseModel):
    squad:          Optional[list[int]] = None
    bank:           Optional[float]     = None
    free_transfers: Optional[int]       = None
    chip:           Optional[str]       = None


class TransferRequest(BaseModel):
    user_id:    int
    player_out: int   = Field(..., description="player_id being sold")
    player_in:  int   = Field(..., description="player_id being bought")
    gw:         int   = Field(..., description="gameweek the transfer is for")


class SimulateChipRequest(BaseModel):
    chip: str = Field(..., description="wc | bb | fh | tc")
    gw:   int


# ── GET /planner/{plan_id} ─────────────────────────────────────────────────────

@router.get("/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = _get_or_404(plan_id, db)
    return _plan_dict(plan)


# ── POST /planner ──────────────────────────────────────────────────────────────

@router.post("/")
def create_plan(req: CreatePlanRequest, db: Session = Depends(get_db)):
    if req.chip not in VALID_CHIPS:
        raise HTTPException(status_code=400, detail=f"Invalid chip: {req.chip}")

    _validate_squad(req.squad, db)

    plan = Plan(
        user_id        = req.user_id,
        name           = req.name,
        from_gw        = req.from_gw,
        to_gw          = req.to_gw,
        squad          = req.squad,
        bank           = req.bank,
        free_transfers = req.free_transfers,
        chip           = req.chip,
        transfer_log   = [],
        gw_projections = [],
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _plan_dict(plan)


# ── PUT /planner/{plan_id} ────────────────────────────────────────────────────

@router.put("/{plan_id}")
def update_plan(plan_id: int, req: UpdatePlanRequest, db: Session = Depends(get_db)):
    plan = _get_or_404(plan_id, db)

    if req.squad is not None:
        _validate_squad(req.squad, db)
        plan.squad = req.squad
    if req.bank is not None:
        plan.bank = req.bank
    if req.free_transfers is not None:
        plan.free_transfers = req.free_transfers
    if req.chip is not None:
        if req.chip not in VALID_CHIPS:
            raise HTTPException(status_code=400, detail=f"Invalid chip: {req.chip}")
        plan.chip = req.chip

    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)
    return _plan_dict(plan)


# ── DELETE /planner/{plan_id} ─────────────────────────────────────────────────

@router.delete("/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = _get_or_404(plan_id, db)
    db.delete(plan)
    db.commit()
    return {"deleted": True, "plan_id": plan_id}


# ── POST /planner/{plan_id}/transfer ──────────────────────────────────────────

@router.post("/{plan_id}/transfer")
def apply_transfer(plan_id: int, req: TransferRequest, db: Session = Depends(get_db)):
    """
    Apply a transfer: swap player_out for player_in.

    Validates:
      - player_out is in current squad
      - player_in is not in current squad
      - position slots are respected after swap
      - max 3 players from same club
      - price difference charged against bank
    """
    plan = _get_or_404(plan_id, db)

    if req.player_out not in plan.squad:
        raise HTTPException(status_code=400, detail="player_out not in squad")
    if req.player_in in plan.squad:
        raise HTTPException(status_code=400, detail="player_in already in squad")

    # Lookup both players
    p_out = _get_player(req.player_out, db)
    p_in  = _get_player(req.player_in,  db)

    if p_out.position != p_in.position:
        raise HTTPException(status_code=400,
                            detail=f"Position mismatch: {p_out.position} → {p_in.position}")

    # Club limit check
    new_squad = [p for p in plan.squad if p != req.player_out] + [req.player_in]
    _validate_squad(new_squad, db)

    # Price delta
    cost_out = (p_out.now_cost or 0) / 10
    cost_in  = (p_in.now_cost  or 0) / 10
    delta    = cost_out - cost_in          # positive = money freed up
    new_bank = plan.bank + delta

    if new_bank < 0:
        raise HTTPException(status_code=400,
                            detail=f"Insufficient bank: need £{-delta:.1f}M more")

    # Deduct a transfer hit if no free transfers left
    hit = 0
    if plan.free_transfers < 1 and plan.chip not in ("wc", "fh"):
        hit = -4   # standard hit

    # Update plan
    plan.squad  = new_squad
    plan.bank   = round(new_bank, 1)
    plan.free_transfers = max(0, plan.free_transfers - 1)

    log = list(plan.transfer_log)
    log.append({
        "gw":         req.gw,
        "player_out": req.player_out,
        "player_in":  req.player_in,
        "cost_out":   cost_out,
        "cost_in":    cost_in,
        "hit":        hit,
        "timestamp":  datetime.utcnow().isoformat(),
    })
    plan.transfer_log = log
    plan.updated_at   = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    return {
        "plan":       _plan_dict(plan),
        "transfer":   {"player_out": req.player_out, "player_in": req.player_in,
                       "hit": hit, "new_bank": round(new_bank, 1)},
    }


# ── GET /planner/{plan_id}/projections ────────────────────────────────────────

@router.get("/{plan_id}/projections")
def plan_projections(plan_id: int, db: Session = Depends(get_db)):
    """
    GW-by-GW projected points for the planned squad.
    Uses the latest Prediction rows FDR-adjusted per fixture.

    Returns per-GW: total_pts, captain_pts, vice_pts, breakdown per player.
    """
    plan = _get_or_404(plan_id, db)

    pred_run = db.query(Prediction.model_run_at).order_by(
        Prediction.model_run_at.desc()
    ).scalar()

    if not pred_run:
        return {"gw_projections": [], "detail": "No predictions available yet"}

    preds = {
        p.player_id: p
        for p in db.query(Prediction)
                   .filter(Prediction.player_id.in_(plan.squad),
                           Prediction.model_run_at == pred_run)
                   .all()
    }

    gws = range(plan.from_gw, plan.to_gw + 1)
    projections = []

    for gw in gws:
        gw_str    = str(gw)
        gw_preds  = []
        for pid in plan.squad:
            pred = preds.get(pid)
            if pred and pred.gw_breakdown:
                breakdown = pred.gw_breakdown.get(gw_str, {})
                pts       = breakdown.get("pred", pred.predicted_pts)
            elif pred:
                pts = pred.predicted_pts
            else:
                pts = 0.0

            gw_preds.append({"player_id": pid, "pts": round(pts, 2)})

        # Best captain: highest pts × 2
        gw_preds_sorted = sorted(gw_preds, key=lambda x: x["pts"], reverse=True)
        captain_id = gw_preds_sorted[0]["player_id"] if gw_preds_sorted else None
        vc_id      = gw_preds_sorted[1]["player_id"] if len(gw_preds_sorted) > 1 else None
        captain_bonus = gw_preds_sorted[0]["pts"] if captain_id else 0

        # Bench Boost: include bench points
        chip_bonus = captain_bonus if plan.chip == "bb" else 0

        total = sum(p["pts"] for p in gw_preds[:11]) + captain_bonus + chip_bonus

        projections.append({
            "gw":         gw,
            "total_pts":  round(total, 1),
            "captain_id": captain_id,
            "vc_id":      vc_id,
            "chip":       plan.chip if plan.from_gw <= gw <= plan.to_gw else None,
            "players":    gw_preds,
        })

    return {
        "plan_id":        plan_id,
        "from_gw":        plan.from_gw,
        "to_gw":          plan.to_gw,
        "total_pts_5gw":  round(sum(g["total_pts"] for g in projections), 1),
        "gw_projections": projections,
    }


# ── POST /planner/{plan_id}/simulate-chip ─────────────────────────────────────

@router.post("/{plan_id}/simulate-chip")
def simulate_chip(plan_id: int, req: SimulateChipRequest, db: Session = Depends(get_db)):
    """
    Simulate the points impact of playing a chip in a given GW.
    Returns projected points with and without the chip applied.
    """
    if req.chip not in ("wc", "bb", "fh", "tc"):
        raise HTTPException(status_code=400, detail=f"Unknown chip: {req.chip}")

    plan = _get_or_404(plan_id, db)

    pred_run = db.query(Prediction.model_run_at).order_by(
        Prediction.model_run_at.desc()
    ).scalar()
    if not pred_run:
        raise HTTPException(status_code=503, detail="No predictions available")

    preds = {
        p.player_id: p
        for p in db.query(Prediction)
                   .filter(Prediction.player_id.in_(plan.squad),
                           Prediction.model_run_at == pred_run)
                   .all()
    }

    gw_str = str(req.gw)

    def _gw_pts(pid):
        pred = preds.get(pid)
        if not pred:
            return 0.0
        if pred.gw_breakdown and gw_str in pred.gw_breakdown:
            return pred.gw_breakdown[gw_str].get("pred", pred.predicted_pts)
        return pred.predicted_pts

    all_pts     = sorted([(pid, _gw_pts(pid)) for pid in plan.squad],
                         key=lambda x: x[1], reverse=True)
    base_pts    = sum(p for _, p in all_pts[:11])
    captain_pts = all_pts[0][1] if all_pts else 0
    bench_pts   = sum(p for _, p in all_pts[11:])

    simulated = base_pts
    if req.chip == "bb":
        simulated = base_pts + bench_pts     # all 15 play
    elif req.chip == "tc":
        simulated = base_pts + (captain_pts * 2)   # triple captain
    elif req.chip in ("wc", "fh"):
        simulated = base_pts   # squad replacement chips — can't simulate without new squad

    return {
        "chip":           req.chip,
        "gw":             req.gw,
        "base_pts":       round(base_pts + captain_pts, 1),
        "simulated_pts":  round(simulated + captain_pts, 1),
        "gain":           round(simulated - base_pts, 1),
        "bench_pts":      round(bench_pts, 1),
        "captain_id":     all_pts[0][0] if all_pts else None,
        "note":           "wc/fh chip simulation requires squad selection — gain shown as 0" if req.chip in ("wc","fh") else None,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_or_404(plan_id: int, db: Session) -> Plan:
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


def _get_player(player_id: int, db: Session) -> Player:
    p = db.query(Player).filter(Player.player_id == player_id,
                                Player.season == "2526").first()
    if not p:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    return p


def _validate_squad(squad: list[int], db: Session):
    """Validate position limits and club limit."""
    players = db.query(Player).filter(Player.player_id.in_(squad),
                                      Player.season == "2526").all()
    pl_map  = {p.player_id: p for p in players}

    pos_count  = {"GK": 0, "DEF": 0, "MID": 0, "FWD": 0}
    club_count: dict[int, int] = {}

    for pid in squad:
        p = pl_map.get(pid)
        if not p:
            raise HTTPException(status_code=404, detail=f"Player {pid} not found")
        pos_count[p.position] = pos_count.get(p.position, 0) + 1
        club_count[p.team_code] = club_count.get(p.team_code, 0) + 1

    for pos, limit in POSITION_LIMITS.items():
        if pos_count.get(pos, 0) > limit:
            raise HTTPException(status_code=400,
                                detail=f"Too many {pos}s: {pos_count[pos]} (max {limit})")

    for team_code, count in club_count.items():
        if count > CLUB_LIMIT:
            raise HTTPException(status_code=400,
                                detail=f"Too many players from team {team_code}: {count} (max {CLUB_LIMIT})")


def _plan_dict(plan: Plan) -> dict:
    return {
        "plan_id":        plan.id,
        "user_id":        plan.user_id,
        "name":           plan.name,
        "from_gw":        plan.from_gw,
        "to_gw":          plan.to_gw,
        "squad":          plan.squad,
        "bank":           plan.bank,
        "free_transfers": plan.free_transfers,
        "chip":           plan.chip,
        "transfer_log":   plan.transfer_log,
        "created_at":     plan.created_at.isoformat(),
        "updated_at":     plan.updated_at.isoformat(),
    }
