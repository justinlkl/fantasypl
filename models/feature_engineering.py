"""
models/feature_engineering.py  v4
Full feature set for FPL prediction.
Moved into models/ module — no logic changes from root feature_engineering.py v4.

KEY IMPROVEMENTS over v3 (informed by FPL Review research):
  - FPL Review analysis shows 5-game xG has 38% mean error; 20-game window cuts this to ~19%
  - Added 20-GW rolling window (WINDOWS now [3, 5, 10, 20])
  - Added xgi_20gw_per90: stable long-term attacking signal (most predictive per article)
  - Added finishing_surplus_5gw: goals-above-xG luck indicator (regress towards zero)
  - Added minutes_reliability_10gw: fraction of last 10 GWs with 45+ mins (availability)
  - Added xgi_consistency: inverse of xGI coefficient of variation (reliable performers)
  - Reduced reliance on raw short-window goal counts (article: "terrible predictors")
  - Added 20-GW versions to outfield/FWD feature lists

Reference: FPL Review "Ultimate Truth" and "xG Data" articles — optimal window ≈ 40 games,
20 GW is the practical compromise balancing recency and sample size.
"""

import pandas as pd
import numpy as np

GOAL_PTS   = {"GK": 6, "DEF": 6, "MID": 5, "FWD": 4}
CS_PTS     = {"GK": 4, "DEF": 4, "MID": 1, "FWD": 0}
ASSIST_PTS = 3
APP_PTS_60 = 2
APP_PTS_1  = 1
SAVE_BONUS = 1 / 3

# v4: added 20-GW window — article shows 20-game xG has ~19% error vs 38% for 5-game
WINDOWS = [3, 5, 10, 20]

BASE_ROLL = [
    "event_points", "gw_minutes", "gw_expected_goals", "gw_expected_assists",
    "gw_expected_goal_involvements", "gw_expected_goals_conceded",
    "gw_goals_scored", "gw_assists", "gw_clean_sheets", "gw_bonus",
    "gw_influence", "gw_creativity", "gw_threat", "gw_ict_index",
    "gw_goals_conceded",
]
GK_ROLL  = ["gw_saves", "gw_goals_conceded", "gw_clean_sheets"]
DEF_ROLL = ["gw_tackles", "gw_clearances_blocks_interceptions",
            "gw_defensive_contribution", "gw_clean_sheets"]
MID_ROLL = ["gw_goals_scored", "gw_assists", "gw_defensive_contribution"]
FWD_ROLL = ["gw_goals_scored", "gw_assists"]
OPTA_ROLL = [
    "opta_minutes_played", "opta_xg", "opta_xa", "opta_xgot",
    "opta_total_shots", "opta_shots_on_target", "opta_chances_created",
    "opta_touches_opposition_box", "opta_tackles", "opta_interceptions",
    "opta_clearances", "opta_saves", "opta_goals_conceded",
]


def _rolling(df, cols, windows):
    df = df.sort_values(["player_id", "gw"]).copy()
    for col in cols:
        if col not in df.columns:
            continue
        for w in windows:
            df[f"r{w}_{col}"] = (
                df.groupby("player_id")[col]
                  .transform(lambda x: x.shift(1).rolling(w, min_periods=1).mean())
            )
    return df


def _lags(df, cols, lags=(1, 2)):
    df = df.sort_values(["player_id", "gw"]).copy()
    for col in cols:
        if col not in df.columns:
            continue
        for lag in lags:
            df[f"lag{lag}_{col}"] = df.groupby("player_id")[col].shift(lag)
    return df


def _add_position_dummies(df):
    dum = pd.get_dummies(df["position"], prefix="pos", dtype=float)
    for p in ["pos_GK", "pos_DEF", "pos_MID", "pos_FWD"]:
        if p not in dum.columns:
            dum[p] = 0.0
    return pd.concat([df, dum[["pos_GK", "pos_DEF", "pos_MID", "pos_FWD"]]], axis=1)


def _add_availability(df):
    df = df.copy()
    for col in ["chance_of_playing_next_round", "chance_of_playing_this_round"]:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            df[col] = (s.fillna(100.0) / 100.0).clip(0, 1)
    for col in ["penalties_order", "corners_and_indirect_freekicks_order",
                "direct_freekicks_order"]:
        if col in df.columns:
            flag = col.replace("_order", "")
            df[f"is_{flag}_taker"] = (
                pd.to_numeric(df[col], errors="coerce").fillna(99) == 1
            ).astype(float)
    return df


def _add_minutes_features(df):
    df = df.copy()
    if "gw_minutes" in df.columns:
        df["gw_min_frac"]  = (df["gw_minutes"] / 90.0).clip(0, 2)
        df["played_60plus"] = (df["gw_minutes"] >= 60).astype(float)
        df["played_any"]    = (df["gw_minutes"] > 0).astype(float)
    return df


def _add_ownership_features(df):
    df = df.copy()
    if "selected_by_percent" not in df.columns:
        return df
    s = pd.to_numeric(df["selected_by_percent"], errors="coerce")
    pos_med = df.groupby("position")["selected_by_percent"].transform("median")
    df["ownership_vs_pos"] = (s / (pos_med + 0.1)).clip(0, 20)
    df["ownership_log"]    = np.log1p(s.fillna(0))
    df["ownership_change"] = df.groupby("player_id")["selected_by_percent"].diff().fillna(0)
    return df


def _add_form_momentum(df):
    df = df.copy()
    if "r3_event_points" in df.columns and "r10_event_points" in df.columns:
        df["form_momentum"] = df["r3_event_points"] - df["r10_event_points"]
    # v4: also compare to 20-GW baseline
    if "r3_event_points" in df.columns and "r20_event_points" in df.columns:
        df["form_vs_longterm"] = df["r3_event_points"] - df["r20_event_points"]
    if "r3_gw_minutes" in df.columns and "r10_gw_minutes" in df.columns:
        df["minutes_trend"] = df["r3_gw_minutes"] - df["r10_gw_minutes"]
    if "event_points" in df.columns:
        df["form_consistency"] = -(
            df.groupby("player_id")["event_points"]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=2).std())
              .fillna(0)
        )
    return df


def _add_long_term_signals(df):
    """
    v4 NEW: Article-informed long-term stability features.

    FPL Review xG research findings:
      - 5-game xGI: MAE 38.7% of true potential (very noisy)
      - 20-game xGI: MAE ~19% (usable signal)
      - 40-game xGI: MAE ~13.7% (good signal)
      - Goals over same window are ~2x noisier than xG

    Practical implication: use 20-GW rolling xGI as primary long-run signal,
    and treat 5-GW goals as a high-noise / luck indicator, not a strength signal.
    """
    df = df.copy()

    if "gw_minutes" not in df.columns:
        return df

    mins = df["gw_minutes"].replace(0, np.nan)

    # ── 1. 20-GW rolling xGI per 90 (most stable attacking signal) ──────
    if "gw_expected_goal_involvements" in df.columns:
        xgi_sum_20 = (
            df.groupby("player_id")["gw_expected_goal_involvements"]
              .transform(lambda x: x.shift(1).rolling(20, min_periods=5).sum())
        )
        mins_sum_20 = (
            df.groupby("player_id")["gw_minutes"]
              .transform(lambda x: x.shift(1).rolling(20, min_periods=5).sum())
        )
        df["xgi_20gw_per90"] = (xgi_sum_20 / (mins_sum_20 / 90)).clip(0, 3).fillna(0)

        # Consistency: low coefficient of variation = more predictable attacker
        roll_std_10 = (
            df.groupby("player_id")["gw_expected_goal_involvements"]
              .transform(lambda x: x.shift(1).rolling(10, min_periods=3).std())
              .fillna(0.1)
        )
        roll_mean_10 = (
            df.groupby("player_id")["gw_expected_goal_involvements"]
              .transform(lambda x: x.shift(1).rolling(10, min_periods=3).mean())
              .fillna(0.01)
        )
        df["xgi_consistency"] = (1 / (1 + roll_std_10 / (roll_mean_10 + 0.01))).clip(0, 1)

    # ── 2. Finishing surplus / deficit (luck indicator) ──────────────────
    # Article: goals are ~2x noisier than xG. Overperformance is mean-reverting.
    if "gw_goals_scored" in df.columns and "gw_expected_goals" in df.columns:
        goals_5 = (
            df.groupby("player_id")["gw_goals_scored"]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        )
        xg_5 = (
            df.groupby("player_id")["gw_expected_goals"]
              .transform(lambda x: x.shift(1).rolling(5, min_periods=1).sum())
        )
        # Positive = lucky finisher (expect regression), Negative = unlucky
        df["finishing_surplus_5gw"] = (goals_5 - xg_5).clip(-5, 5).fillna(0)

    # ── 3. Minutes reliability (availability signal) ─────────────────────
    # Fraction of last 10 GWs where player started (45+ mins)
    played_45 = (df["gw_minutes"] >= 45).astype(float)
    df["minutes_reliability_10gw"] = (
        played_45.groupby(df["player_id"])
                 .transform(lambda x: x.shift(1).rolling(10, min_periods=3).mean())
    ).fillna(0.5)

    # Also compute minutes reliability over 20 GWs (for season-long starters)
    df["minutes_reliability_20gw"] = (
        played_45.groupby(df["player_id"])
                 .transform(lambda x: x.shift(1).rolling(20, min_periods=5).mean())
    ).fillna(0.5)

    # ── 4. Long-run xG per 90 (season baseline, not just recent windows) ─
    if "gw_expected_goals" in df.columns:
        xg_sum_20 = (
            df.groupby("player_id")["gw_expected_goals"]
              .transform(lambda x: x.shift(1).rolling(20, min_periods=5).sum())
        )
        mins_sum_20 = (
            df.groupby("player_id")["gw_minutes"]
              .transform(lambda x: x.shift(1).rolling(20, min_periods=5).sum())
        )
        df["xg_20gw_per90"] = (xg_sum_20 / (mins_sum_20 / 90)).clip(0, 2).fillna(0)

    # ── 5. Hot streak: scored in each of last 3 GWs (binary signal) ──────
    if "gw_goals_scored" in df.columns:
        scored = (df["gw_goals_scored"] > 0).astype(float)
        df["hot_streak_3gw"] = (
            scored.groupby(df["player_id"])
                  .transform(lambda x: x.shift(1).rolling(3, min_periods=3).min())
        ).fillna(0)  # 1.0 only if scored in ALL of last 3

    return df


def _add_underlying_stats(df):
    """
    Per-90 underlying stats for the dashboard's 'underlying stats' tab.
    These are the key metrics FPL analysts use: xG, xA, xGI, key passes,
    shots on target, tackle rate, etc.
    """
    df = df.copy()

    if "gw_minutes" in df.columns:
        mins = df["gw_minutes"].replace(0, np.nan)

        for stat, col in [("gw_expected_goals", "xg_per90"),
                          ("gw_expected_assists", "xa_per90"),
                          ("gw_expected_goal_involvements", "xgi_per90"),
                          ("gw_goals_scored", "goals_per90"),
                          ("gw_assists", "assists_per90")]:
            if stat in df.columns:
                df[col] = (df[stat] / (mins / 90)).clip(0, 5).fillna(0)

        for stat, col in [("opta_total_shots", "shots_per90"),
                          ("opta_shots_on_target", "sot_per90"),
                          ("opta_chances_created", "chances_per90"),
                          ("opta_touches_opposition_box", "box_touches_per90"),
                          ("opta_tackles", "tackles_per90"),
                          ("opta_interceptions", "interceptions_per90"),
                          ("opta_clearances", "clearances_per90"),
                          ("opta_saves", "saves_per90_opta")]:
            if stat in df.columns:
                df[col] = (df[stat] / (mins / 90)).clip(0, 20).fillna(0)

    return df


def _add_price_features(df):
    df = df.copy()
    if "now_cost" in df.columns:
        df["price_m"] = pd.to_numeric(df["now_cost"], errors="coerce")
    if "value_season" in df.columns:
        df["value_season"] = pd.to_numeric(df["value_season"], errors="coerce")
    return df


def _add_xpts_proxy(df):
    """
    v4: Uses r20_gw_minutes for expected minutes estimate (more stable than r3).
    Article insight: 3-game sample for minutes is too noisy; longer window preferred.
    """
    df = df.copy()
    xg90  = pd.to_numeric(df.get("expected_goals_per_90",  0), errors="coerce").fillna(0)
    xa90  = pd.to_numeric(df.get("expected_assists_per_90", 0), errors="coerce").fillna(0)
    xgc90 = pd.to_numeric(df.get("expected_goals_conceded_per_90", 0), errors="coerce").fillna(0)
    sv90  = pd.to_numeric(df.get("saves_per_90",  0), errors="coerce").fillna(0)

    # v4: prefer 10-GW window for minutes estimate (less noisy than r3)
    exp_min_col = "r10_gw_minutes" if "r10_gw_minutes" in df.columns else "r3_gw_minutes"
    exp_min = df.get(exp_min_col, pd.Series(90.0, index=df.index))
    exp_min = pd.to_numeric(exp_min, errors="coerce").fillna(60.0).clip(0, 180)
    exp_90  = (exp_min / 90.0).clip(0, 2)

    app_pts  = np.where(exp_min >= 60, APP_PTS_60, np.where(exp_min > 0, APP_PTS_1, 0))
    gpts     = df["position"].map(GOAL_PTS).fillna(5)
    cs_pts   = df["position"].map(CS_PTS).fillna(0)

    xpts_goals   = xg90 * exp_90 * gpts
    xpts_assists = xa90 * exp_90 * ASSIST_PTS
    xcs_prob     = np.exp(-xgc90 * exp_90.clip(0, 1))
    xpts_cs      = xcs_prob * cs_pts
    xpts_saves   = sv90 * exp_90 * SAVE_BONUS

    df["xpts_proxy"] = (app_pts + xpts_goals + xpts_assists + xpts_cs + xpts_saves).clip(0)
    return df


def _add_team_strength(df):
    df = df.copy()
    for side in ["attack", "defence"]:
        h = f"strength_{side}_home"
        a = f"strength_{side}_away"
        if h in df.columns and a in df.columns:
            df[h] = pd.to_numeric(df[h], errors="coerce")
            df[a] = pd.to_numeric(df[a], errors="coerce")
            avg = (df[h].mean() + df[a].mean()) / 2
            df[f"team_{side}_rel"] = ((df[h] + df[a]) / 2 / avg).round(4)
    if "elo" in df.columns:
        df["elo"] = pd.to_numeric(df["elo"], errors="coerce")
    return df


def _add_position_signals(df):
    df = df.copy()
    is_gk  = (df["position"] == "GK").astype(float)
    is_def = (df["position"] == "DEF").astype(float)
    is_mid = (df["position"] == "MID").astype(float)
    is_fwd = (df["position"] == "FWD").astype(float)
    is_att = is_mid + is_fwd

    xgi90  = pd.to_numeric(df.get("expected_goal_involvements_per_90", 0), errors="coerce").fillna(0)
    xgc90  = pd.to_numeric(df.get("expected_goals_conceded_per_90",    0), errors="coerce").fillna(0)
    sv90   = pd.to_numeric(df.get("saves_per_90",    0), errors="coerce").fillna(0)
    cs90   = pd.to_numeric(df.get("clean_sheets_per_90", 0), errors="coerce").fillna(0)
    dc90   = pd.to_numeric(df.get("defensive_contribution_per_90", 0), errors="coerce").fillna(0)

    df["attacking_threat"]     = xgi90 * is_att
    df["defensive_solidity"]   = cs90  * (is_gk + is_def)
    df["gk_save_value"]        = sv90  * is_gk
    df["def_contribution"]     = dc90  * (is_gk + is_def + is_mid * 0.6)
    df["clean_sheet_exposure"] = (1 / (1 + xgc90)) * (is_gk + is_def)

    # v4: Long-run attacking threat using 20-GW window (more stable)
    xgi_20 = df.get("xgi_20gw_per90", pd.Series(0.0, index=df.index))
    df["stable_attacking_threat"] = pd.to_numeric(xgi_20, errors="coerce").fillna(0) * is_att

    return df


def _add_season_context(df):
    df = df.copy()
    total_gws = df.groupby("season")["gw"].transform("max")
    df["season_progress"] = df["gw"] / total_gws
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("Engineering features...")
    all_roll = list(dict.fromkeys(
        [c for c in BASE_ROLL + GK_ROLL + DEF_ROLL + MID_ROLL + FWD_ROLL + OPTA_ROLL
         if c in df.columns]
    ))
    print(f"  Rolling {WINDOWS} over {len(all_roll)} cols...")
    df = _rolling(df, all_roll, WINDOWS)

    print("  Lag features...")
    df = _lags(df, [c for c in ["event_points","gw_minutes","gw_expected_goal_involvements",
                                 "gw_expected_goals_conceded","gw_goals_scored","gw_assists"]
                    if c in df.columns], lags=(1,2))

    print("  Derived features...")
    df = _add_position_dummies(df)
    df = _add_availability(df)
    df = _add_minutes_features(df)
    df = _add_ownership_features(df)
    df = _add_form_momentum(df)
    df = _add_underlying_stats(df)
    df = _add_price_features(df)
    df = _add_team_strength(df)
    df = _add_xpts_proxy(df)
    df = _add_position_signals(df)
    df = _add_season_context(df)
    # v4: long-term stability signals (article-informed)
    print("  Long-term stability signals (v4)...")
    df = _add_long_term_signals(df)

    print(f"  Done — {df.shape[1]} total columns")
    return df


def get_feature_columns(df: pd.DataFrame) -> dict:
    def avail(cols):
        return [c for c in cols if c in df.columns]

    universal = avail([
        "form", "form_momentum", "form_consistency", "form_vs_longterm",
        "r3_event_points", "r5_event_points", "r10_event_points", "r20_event_points",
        "lag1_event_points", "lag2_event_points",
        "r3_gw_minutes", "r5_gw_minutes", "r10_gw_minutes", "r20_gw_minutes",
        "lag1_gw_minutes", "minutes_trend",
        "gw_min_frac", "played_60plus", "played_any",
        # v4: minutes reliability over 10 and 20 GWs (more stable than raw minutes)
        "minutes_reliability_10gw", "minutes_reliability_20gw",
        "chance_of_playing_next_round", "chance_of_playing_this_round",
        "is_unavailable",
        "price_m", "value_season",
        "ownership_vs_pos", "ownership_log", "ownership_change",
        "selected_by_percent",
        "strength", "team_attack_rel", "team_defence_rel", "elo",
        "strength_overall_home", "strength_overall_away",
        "pos_GK", "pos_DEF", "pos_MID", "pos_FWD",
        "season_progress", "team_changed", "is_new_player",
    ])

    gk_base = avail([
        "form", "form_momentum", "form_consistency",
        "r3_event_points", "r5_event_points", "r10_event_points",
        "lag1_event_points", "r3_gw_minutes", "r5_gw_minutes",
        "lag1_gw_minutes", "gw_min_frac",
        "minutes_reliability_10gw",
        "chance_of_playing_next_round", "chance_of_playing_this_round",
        "is_unavailable", "price_m", "selected_by_percent", "ownership_vs_pos",
        "strength", "team_defence_rel", "elo",
        "strength_defence_home", "strength_defence_away",
        "season_progress", "team_changed", "is_new_player",
    ])

    gk_extra = avail([
        "saves_per_90", "r3_gw_saves", "r5_gw_saves", "r10_gw_saves",
        "clean_sheets_per_90", "r3_gw_clean_sheets", "r5_gw_clean_sheets",
        "goals_conceded_per_90", "r3_gw_goals_conceded", "r5_gw_goals_conceded",
        "expected_goals_conceded_per_90", "gk_save_value",
        "defensive_solidity", "clean_sheet_exposure",
        "r5_opta_saves", "r5_opta_goals_conceded",
    ])

    outfield_extra = avail([
        "expected_goals_per_90", "expected_assists_per_90",
        "expected_goal_involvements_per_90",
        "r3_gw_expected_goal_involvements", "r5_gw_expected_goal_involvements",
        "r10_gw_expected_goal_involvements", "r20_gw_expected_goal_involvements",
        # v4: key long-term features from article
        "xgi_20gw_per90",         # 20-GW rolling xGI/90 — much more reliable signal
        "xgi_consistency",         # low CV = consistent attacker
        "finishing_surplus_5gw",   # goals above xG (luck indicator, negative for model)
        "stable_attacking_threat", # 20-GW xGI * is_att
        "r3_gw_ict_index", "r5_gw_ict_index",
        "r3_gw_influence", "r5_gw_influence",
        "r3_gw_creativity", "r5_gw_creativity",
        "r3_gw_threat", "r5_gw_threat",
        "is_penalties_taker", "is_corners_and_indirect_freekicks_taker",
        "is_direct_freekicks_taker",
        "xpts_proxy", "attacking_threat", "minutes_trend", "played_any",
        "hot_streak_3gw",
    ])

    def_extra = avail([
        "clean_sheets_per_90", "r3_gw_clean_sheets", "r5_gw_clean_sheets",
        "goals_conceded_per_90", "r3_gw_goals_conceded",
        "expected_goals_conceded_per_90", "defensive_contribution_per_90",
        "r3_gw_clearances_blocks_interceptions", "r5_gw_clearances_blocks_interceptions",
        "r3_gw_tackles", "r5_gw_tackles",
        "defensive_solidity", "clean_sheet_exposure", "def_contribution",
        # v4: include long-run xG even for defenders (set piece takers)
        "r20_gw_expected_goals", "r20_gw_expected_assists",
        "xgi_20gw_per90",
        "r3_gw_expected_goals", "r5_gw_expected_goals",
        "r5_opta_clearances", "r5_opta_tackles", "r5_opta_interceptions",
    ])

    mid_extra = avail([
        "r3_gw_expected_goals", "r5_gw_expected_goals", "r20_gw_expected_goals",
        "r3_gw_expected_assists", "r5_gw_expected_assists", "r20_gw_expected_assists",
        # v4: 20-GW xGI for mids — critical as article shows 5-GW is noise
        "xgi_20gw_per90", "xg_20gw_per90", "xgi_consistency",
        "finishing_surplus_5gw",
        "r3_gw_goals_scored", "r5_gw_goals_scored",
        "r3_gw_assists", "r5_gw_assists",
        "r3_gw_bonus", "r5_gw_bonus",
        "defensive_contribution_per_90",
        "r3_gw_defensive_contribution", "r5_gw_defensive_contribution",
        "def_contribution",
        "r5_opta_chances_created", "r5_opta_xg", "r5_opta_xa",
        "r5_opta_total_shots", "r5_opta_touches_opposition_box",
        "r5_opta_shots_on_target",
        "hot_streak_3gw",
    ])

    fwd_extra = avail([
        "r3_gw_expected_goals", "r5_gw_expected_goals", "r10_gw_expected_goals",
        "r20_gw_expected_goals",     # v4: long-run xG for FWDs (40% vs 13.7% MAE difference)
        "r3_gw_expected_assists", "r5_gw_expected_assists", "r20_gw_expected_assists",
        # v4: primary stable signal for FWDs per article
        "xgi_20gw_per90", "xg_20gw_per90", "xgi_consistency",
        "finishing_surplus_5gw",     # v4: luck normalisation
        "r3_gw_goals_scored", "r5_gw_goals_scored", "r10_gw_goals_scored",
        # Note: raw goals are noisy (article: "terrible predictor") — kept but low weight expected
        "r3_gw_assists", "r5_gw_assists",
        "r3_gw_bonus", "r5_gw_bonus",
        "lag1_gw_goals_scored", "lag2_gw_goals_scored",
        "r5_opta_xg", "r5_opta_xa",
        "r5_opta_total_shots", "r5_opta_shots_on_target",
        "r5_opta_touches_opposition_box", "r5_opta_chances_created",
        "hot_streak_3gw",            # v4: binary hot-streak flag
    ])

    def dedup(lst):
        seen = set(); out = []
        for x in lst:
            if x not in seen: seen.add(x); out.append(x)
        return out

    outfield_base = dedup(universal + outfield_extra)

    return {
        "GK":  dedup(gk_base + gk_extra),
        "DEF": dedup(outfield_base + def_extra),
        "MID": dedup(outfield_base + mid_extra),
        "FWD": dedup(outfield_base + fwd_extra),
        "ALL": dedup(universal),
    }