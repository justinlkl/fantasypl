export type Position = 'GK' | 'DEF' | 'MID' | 'FWD'
export type Chip = 'wc' | 'bb' | 'fh' | 'tc'

export interface Player {
  player_id: number
  web_name: string
  position: Position
  team_code: number
  price_m: number | null
  selected_by_pct: number | null
  is_unavailable: boolean
  chance_of_playing: number | null
  team_changed: boolean
  is_new_player: boolean
  is_penalties_taker: boolean
}

export interface Prediction {
  player_id: number
  web_name: string
  position: Position
  team_code: number
  price_m: number | null
  selected_by_pct: number | null
  is_unavailable: boolean
  chance_of_playing: number | null
  predicted_pts: number
  pts_next5: number | null
  xpts_proxy: number | null
  target_gw: number
  model_run_at: string
  gw_breakdown?: Record<string, { pred: number; opp: string; fdr: number; is_home: boolean }>
}

export interface PlayerStat {
  gw: number
  pts: number | null
  minutes: number | null
  goals: number | null
  assists: number | null
  clean_sheets: number | null
  saves: number | null
  bonus: number | null
  xg: number | null
  xa: number | null
  xgi: number | null
  xg_per90: number | null
  xa_per90: number | null
  xgi_per90: number | null
}

export interface PlayerDetail {
  player: Player
  latest_stat: PlayerStat | null
  prediction: Prediction | null
}

export interface PlayerHistory {
  player_id: number
  season: string
  history: { gw: number; pts: number | null; minutes: number | null; xg: number | null; xa: number | null; xgi: number | null }[]
}

export interface Team {
  code: number
  name: string
  short_name: string
  fdr: number | null
  attack_fdr: number | null
  defence_fdr: number | null
  elo: number | null
  strength_attack_home: number | null
  strength_attack_away: number | null
  strength_defence_home: number | null
  strength_defence_away: number | null
}

export interface FixtureTicker {
  team_code: number
  short_name: string
  name: string
  fixtures: {
    gw: number
    is_home: boolean
    fdr: number
    colour: string
    opponent_code: number
  }[]
}

export interface FdrResponse {
  ticker: FixtureTicker[]
  from_gw: number
  num_gws: number
}

export interface LiveMatch {
  fixture_id: number
  gw: number
  team_h_id: number
  team_a_id: number
  team_h_score: number | null
  team_a_score: number | null
  started: boolean
  finished: boolean
  finished_provisional: boolean
  minutes: number
  stats: unknown[]
}

export interface LivePlayer {
  player_id: number
  live_pts: number
  minutes: number
  goals_scored: number
  assists: number
  clean_sheets: number
  goals_conceded: number
  bonus: number
  bps: number
  yellow_cards: number
  red_cards: number
  saves: number
}

export interface CompareEntry {
  player: Player
  latest_stat: PlayerStat | null
  prediction: Prediction | null
  history: { gw: number; pts: number | null; xgi: number | null; minutes: number | null }[]
}
