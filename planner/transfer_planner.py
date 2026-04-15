"""
planner/transfer_planner.py  —  Transfer planner and squad optimiser

This module provides the business logic for the transfer planner.
The API routes in api/routes/planner.py call these functions directly.

Phase 2 features (per the roadmap):
  - squad_by_gw:        project squad state GW by GW
  - suggest_transfers:  rank best available transfers given budget + FDR
  - optimise_squad:     ILP/greedy solver for best 15 given a budget
  - chip_analysis:      simulate WC/BB/FH/TC impact on projected points

Dependencies:
    models.predict      — for per-player point projections
    etl.fdr             — for fixture difficulty context
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger("fpl_planner")

POSITION_LIMITS   = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
SQUAD_SIZE        = 15
XI_SIZE           = 11
CLUB_LIMIT        = 3
TRANSFER_HIT      = -4   # points deducted per extra transfer
VALID_CHIPS       = {"wc", "bb", "fh", "tc"}


# ── Squad state ────────────────────────────────────────────────────────────────

@dataclass
class SquadState:
    """Mutable squad state for a single gameweek."""
    player_ids:     list[int]          # 15 player_ids
    bank:           float              # £M remaining
    free_transfers: int                = 1
    chip:           Optional[str]      = None   # "wc" | "bb" | "fh" | "tc" | None
    gw:             int                = 0
    transfer_log:   list[dict]         = field(default_factory=list)

    def copy(self) -> "SquadState":
        return SquadState(
            player_ids     = list(self.player_ids),
            bank           = self.bank,
            free_transfers = self.free_transfers,
            chip           = self.chip,
            gw             = self.gw,
            transfer_log   = list(self.transfer_log),
        )


# ── Projection helpers ─────────────────────────────────────────────────────────

def get_player_gw_projection(player_id: int, gw: int,
                              predictions: pd.DataFrame) -> float:
    """
    Return projected points for a player in a specific GW.
    `predictions` is the output of models.predict.build_5gw_projections().
    """
    if predictions is None or predictions.empty:
        return 0.0

    row = predictions[predictions["player_id"] == player_id]
    if row.empty:
        return 0.0

    col = f"gw{gw}_pred"
    if col in row.columns and not pd.isna(row.iloc[0][col]):
        return float(row.iloc[0][col])

    return float(row.iloc[0].get("predicted_pts", 0.0))


def squad_gw_points(state: SquadState, gw: int,
                    predictions: pd.DataFrame,
                    captain_id: Optional[int] = None,
                    bench_ids: Optional[list[int]] = None) -> float:
    """
    Project total points for a squad in a GW.

    XI = top 11 by projected points (respecting GK constraint).
    Captain = highest projected player (double points).
    Bench Boost = all 15 play.
    Triple Captain = 3× instead of 2×.
    """
    pts = {pid: get_player_gw_projection(pid, gw, predictions)
           for pid in state.player_ids}

    # Determine XI (auto-pick: GK + best 10 outfield)
    gk  = [pid for pid in state.player_ids if _is_gk(pid, predictions)]
    out = [pid for pid in state.player_ids if not _is_gk(pid, predictions)]

    # Sort by pts
    gk_sorted  = sorted(gk,  key=lambda x: pts.get(x, 0), reverse=True)
    out_sorted = sorted(out, key=lambda x: pts.get(x, 0), reverse=True)

    xi_gk  = gk_sorted[:1]
    xi_out = out_sorted[:10]
    xi     = set(xi_gk + xi_out)

    if state.chip == "bb":
        xi = set(state.player_ids)    # all 15 play

    xi_total = sum(pts.get(pid, 0) for pid in xi)

    # Captain bonus
    if captain_id and captain_id in xi:
        cap_pts = pts.get(captain_id, 0)
    else:
        cap_pts = max((pts.get(pid, 0) for pid in xi), default=0)

    if state.chip == "tc":
        xi_total += cap_pts * 2   # triple → extra ×2 on top of normal score
    else:
        xi_total += cap_pts       # normal double (cap plays once in xi_total, add 1×)

    return round(xi_total, 2)


def _is_gk(player_id: int, predictions: pd.DataFrame) -> bool:
    if predictions is None or predictions.empty:
        return False
    row = predictions[predictions["player_id"] == player_id]
    return not row.empty and row.iloc[0].get("position") == "GK"


# ── Transfer suggestion ────────────────────────────────────────────────────────

def suggest_transfers(state: SquadState,
                      predictions: pd.DataFrame,
                      n_transfers: int = 1,
                      gw_horizon: int = 5,
                      max_price:  Optional[float] = None) -> list[dict]:
    """
    Rank the best available transfers for the current squad.

    For each player in the squad, compute:
        gain = best_replacement_pts - current_player_pts  (over gw_horizon)

    Returns a list of suggested swaps sorted by projected points gain.
    """
    if predictions is None or predictions.empty:
        log.warning("No predictions available for transfer suggestions.")
        return []

    # Candidates not already in squad
    candidates = predictions[~predictions["player_id"].isin(state.player_ids)].copy()

    if max_price is not None:
        candidates = candidates[candidates.get("price_m", 0) <= max_price]

    # Score each player over the horizon
    horizon_cols = [f"gw{gw}_pred" for gw in range(state.gw + 1, state.gw + gw_horizon + 1)
                    if f"gw{gw}_pred" in predictions.columns]

    def _horizon_pts(pid: int) -> float:
        row = predictions[predictions["player_id"] == pid]
        if row.empty:
            return 0.0
        if horizon_cols:
            return float(row.iloc[0][horizon_cols].fillna(0).sum())
        return float(row.iloc[0].get("predicted_pts", 0))

    suggestions = []
    n_hits = max(0, n_transfers - state.free_transfers)
    hit_penalty = n_hits * TRANSFER_HIT

    for pid_out in state.player_ids:
        out_row = predictions[predictions["player_id"] == pid_out]
        if out_row.empty:
            continue

        pos_out   = out_row.iloc[0].get("position")
        price_out = out_row.iloc[0].get("price_m", 0) or 0
        budget    = price_out + state.bank

        out_pts   = _horizon_pts(pid_out)

        # Best replacement in same position within budget
        cands_pos = candidates[
            (candidates.get("position") == pos_out) &
            (candidates.get("price_m", 0) <= budget)
        ].copy() if "position" in candidates.columns else pd.DataFrame()

        if cands_pos.empty:
            continue

        # Club limit: can't have 3 from same club already (after removing pid_out)
        squad_without = [p for p in state.player_ids if p != pid_out]

        best_gain  = -999
        best_in_id = None

        for _, cand in cands_pos.iterrows():
            pid_in = int(cand["player_id"])
            # Club check
            club_in = cand.get("team_code")
            same_club = sum(
                1 for p in squad_without
                if _get_team_code(p, predictions) == club_in
            )
            if same_club >= CLUB_LIMIT:
                continue

            in_pts = _horizon_pts(pid_in)
            gain   = in_pts - out_pts + hit_penalty
            if gain > best_gain:
                best_gain  = gain
                best_in_id = pid_in

        if best_in_id is not None and best_gain > 0:
            in_row = predictions[predictions["player_id"] == best_in_id].iloc[0]
            suggestions.append({
                "player_out":    pid_out,
                "name_out":      out_row.iloc[0].get("web_name", str(pid_out)),
                "pos_out":       pos_out,
                "price_out":     price_out,
                "pts_out":       round(out_pts, 2),
                "player_in":     best_in_id,
                "name_in":       in_row.get("web_name", str(best_in_id)),
                "price_in":      in_row.get("price_m", 0),
                "pts_in":        round(_horizon_pts(best_in_id), 2),
                "net_gain":      round(best_gain, 2),
                "hit_deducted":  hit_penalty,
            })

    suggestions.sort(key=lambda x: x["net_gain"], reverse=True)
    return suggestions[:20]   # top 20 suggestions


def _get_team_code(player_id: int, predictions: pd.DataFrame) -> Optional[int]:
    row = predictions[predictions["player_id"] == player_id]
    if row.empty:
        return None
    return row.iloc[0].get("team_code")


# ── Multi-GW planner ───────────────────────────────────────────────────────────

def plan_gw_window(state: SquadState,
                   predictions: pd.DataFrame,
                   n_transfers_per_gw: list[int] = None,
                   chips_by_gw: dict[int, str]   = None) -> list[dict]:
    """
    Project squad + points for a window of GWs from state.gw onwards.

    `n_transfers_per_gw`: number of planned transfers per GW (list, one per GW)
    `chips_by_gw`:        {gw: chip_name} for chip scheduling

    Returns list of per-GW dicts with projected pts, squad, bank, chip.
    """
    if chips_by_gw is None:
        chips_by_gw = {}

    n_gws  = len(n_transfers_per_gw) if n_transfers_per_gw else 5
    result = []

    current = state.copy()

    for i in range(n_gws):
        gw    = state.gw + i
        chip  = chips_by_gw.get(gw, current.chip if i == 0 else None)
        n_tr  = (n_transfers_per_gw[i] if n_transfers_per_gw
                 and i < len(n_transfers_per_gw) else 0)

        # Transfer hits
        hits       = max(0, n_tr - current.free_transfers)
        hit_pts    = hits * TRANSFER_HIT
        next_free  = min(2, current.free_transfers - n_tr + 1)  # 1 rolls over, max 2

        current.chip           = chip
        projected_pts          = squad_gw_points(current, gw, predictions)
        projected_pts_with_hit = projected_pts + hit_pts

        result.append({
            "gw":              gw,
            "chip":            chip,
            "n_transfers":     n_tr,
            "hit_deducted":    hit_pts,
            "free_transfers":  current.free_transfers,
            "bank":            current.bank,
            "projected_pts":   round(projected_pts_with_hit, 1),
            "squad":           list(current.player_ids),
        })

        current.free_transfers = next_free
        current.chip = None   # chip is one-time use

    return result
