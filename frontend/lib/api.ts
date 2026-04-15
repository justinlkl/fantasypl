import type {
  Prediction, PlayerDetail, PlayerHistory,
  Team, FdrResponse, LiveMatch, LivePlayer, CompareEntry,
} from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${BASE}${path}`, { next: { revalidate: 60 } })
    if (!res.ok) return fallback
    return res.json()
  } catch {
    return fallback
  }
}

// ── Predictions ───────────────────────────────────────────────────────────────

export async function getPredictions(params: {
  position?: string
  max_price?: number
  available?: boolean
  limit?: number
  sort?: string
} = {}): Promise<{ predictions: Prediction[]; count: number; model_run_at: string | null }> {
  const q = new URLSearchParams()
  if (params.position)  q.set('position',  params.position)
  if (params.max_price) q.set('max_price', String(params.max_price))
  if (params.available !== undefined) q.set('available', String(params.available))
  if (params.limit)     q.set('limit',     String(params.limit))
  if (params.sort)      q.set('sort',      params.sort)

  return apiFetch(`/predictions?${q}`, MOCK_PREDICTIONS)
}

export async function getPlayerPrediction(playerId: number): Promise<Prediction | null> {
  const res = await apiFetch<Prediction | null>(`/predictions/${playerId}`, null)
  return res
}

// ── Players ───────────────────────────────────────────────────────────────────

export async function getPlayerDetail(playerId: number): Promise<PlayerDetail | null> {
  return apiFetch(`/players/${playerId}`, MOCK_PLAYER_DETAIL)
}

export async function getPlayerHistory(playerId: number): Promise<PlayerHistory | null> {
  return apiFetch(`/players/${playerId}/history`, null)
}

export async function comparePlayers(ids: number[]): Promise<{ comparison: CompareEntry[]; count: number }> {
  return apiFetch(`/players/compare/?ids=${ids.join(',')}`, { comparison: [], count: 0 })
}

// ── Teams ─────────────────────────────────────────────────────────────────────

export async function getTeams(): Promise<{ teams: Team[] }> {
  return apiFetch('/teams/', MOCK_TEAMS)
}

export async function getTeam(code: number): Promise<{ team: Team; fixtures: unknown[] } | null> {
  return apiFetch(`/teams/${code}`, null)
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

export async function getFixtureTicker(numGws = 5): Promise<FdrResponse> {
  return apiFetch(`/fixtures/fdr?num_gws=${numGws}`, MOCK_FDR)
}

// ── Live ──────────────────────────────────────────────────────────────────────

export async function getLiveMatches(gw?: number): Promise<{ gw: number; matches: LiveMatch[] }> {
  const q = gw ? `?gw=${gw}` : ''
  return apiFetch(`/live/matches${q}`, { gw: 32, matches: [] })
}

export async function getLivePoints(gw?: number): Promise<{ gw: number; players: LivePlayer[] }> {
  const q = gw ? `?gw=${gw}` : ''
  return apiFetch(`/live/points${q}`, { gw: 32, players: [] })
}

// ── Mock data (used when API is unreachable) ──────────────────────────────────

const MOCK_PREDICTIONS = {
  count: 10,
  model_run_at: new Date().toISOString(),
  predictions: [
    { player_id: 1, web_name: 'Salah',      position: 'MID' as const, team_code: 14, price_m: 13.2, selected_by_pct: 48.1, is_unavailable: false, chance_of_playing: 1, predicted_pts: 8.7, pts_next5: 38.2, xpts_proxy: 7.9, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 8.7, opp: 'BHA (H)', fdr: 2, is_home: true }, '33': { pred: 7.1, opp: 'MCI (A)', fdr: 5, is_home: false }, '34': { pred: 8.3, opp: 'WOL (H)', fdr: 1, is_home: true }, '35': { pred: 6.9, opp: 'CHE (A)', fdr: 3, is_home: false }, '36': { pred: 7.2, opp: 'ARS (H)', fdr: 4, is_home: true } } },
    { player_id: 2, web_name: 'Haaland',    position: 'FWD' as const, team_code: 43, price_m: 15.1, selected_by_pct: 52.3, is_unavailable: false, chance_of_playing: 1, predicted_pts: 8.2, pts_next5: 35.1, xpts_proxy: 7.5, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 8.2, opp: 'EVE (H)', fdr: 1, is_home: true }, '33': { pred: 6.8, opp: 'TOT (A)', fdr: 3, is_home: false }, '34': { pred: 7.9, opp: 'IPS (H)', fdr: 1, is_home: true }, '35': { pred: 6.1, opp: 'LIV (A)', fdr: 5, is_home: false }, '36': { pred: 6.1, opp: 'NFO (H)', fdr: 2, is_home: true } } },
    { player_id: 3, web_name: 'Mbeumo',     position: 'MID' as const, team_code: 94, price_m: 8.3,  selected_by_pct: 22.7, is_unavailable: false, chance_of_playing: 1, predicted_pts: 7.4, pts_next5: 33.8, xpts_proxy: 6.8, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 7.4, opp: 'NFO (H)', fdr: 2, is_home: true }, '33': { pred: 6.9, opp: 'ARS (A)', fdr: 4, is_home: false }, '34': { pred: 7.1, opp: 'SOU (H)', fdr: 1, is_home: true }, '35': { pred: 6.3, opp: 'CHE (A)', fdr: 3, is_home: false }, '36': { pred: 6.1, opp: 'EVE (H)', fdr: 1, is_home: true } } },
    { player_id: 4, web_name: 'Saka',       position: 'MID' as const, team_code: 3,  price_m: 10.4, selected_by_pct: 31.2, is_unavailable: false, chance_of_playing: 1, predicted_pts: 7.1, pts_next5: 32.4, xpts_proxy: 6.5, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 7.1, opp: 'BRE (A)', fdr: 2, is_home: false }, '33': { pred: 7.3, opp: 'WOL (H)', fdr: 1, is_home: true }, '34': { pred: 5.9, opp: 'MCI (A)', fdr: 5, is_home: false }, '35': { pred: 6.8, opp: 'EVE (H)', fdr: 1, is_home: true }, '36': { pred: 5.3, opp: 'TOT (A)', fdr: 3, is_home: false } } },
    { player_id: 5, web_name: 'Alexander-Arnold', position: 'DEF' as const, team_code: 14, price_m: 7.4, selected_by_pct: 19.8, is_unavailable: false, chance_of_playing: 0.75, predicted_pts: 6.8, pts_next5: 29.7, xpts_proxy: 6.1, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 6.8, opp: 'BHA (H)', fdr: 2, is_home: true }, '33': { pred: 5.2, opp: 'MCI (A)', fdr: 5, is_home: false }, '34': { pred: 6.9, opp: 'WOL (H)', fdr: 1, is_home: true }, '35': { pred: 5.5, opp: 'CHE (A)', fdr: 3, is_home: false }, '36': { pred: 5.3, opp: 'ARS (H)', fdr: 4, is_home: true } } },
    { player_id: 6, web_name: "Isak",       position: 'FWD' as const, team_code: 4,  price_m: 8.9,  selected_by_pct: 17.4, is_unavailable: false, chance_of_playing: 1, predicted_pts: 6.7, pts_next5: 29.1, xpts_proxy: 6.0, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 6.7, opp: 'EVE (H)', fdr: 1, is_home: true }, '33': { pred: 5.8, opp: 'CHE (A)', fdr: 3, is_home: false }, '34': { pred: 6.1, opp: 'BOU (H)', fdr: 2, is_home: true }, '35': { pred: 5.6, opp: 'MCI (A)', fdr: 5, is_home: false }, '36': { pred: 4.9, opp: 'BRE (H)', fdr: 2, is_home: true } } },
    { player_id: 7, web_name: 'Watkins',    position: 'FWD' as const, team_code: 7,  price_m: 8.8,  selected_by_pct: 14.2, is_unavailable: false, chance_of_playing: 1, predicted_pts: 6.5, pts_next5: 28.3, xpts_proxy: 5.9, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 6.5, opp: 'LEI (H)', fdr: 1, is_home: true }, '33': { pred: 5.7, opp: 'BRE (A)', fdr: 2, is_home: false }, '34': { pred: 6.2, opp: 'NFO (H)', fdr: 2, is_home: true }, '35': { pred: 4.8, opp: 'ARS (A)', fdr: 4, is_home: false }, '36': { pred: 5.1, opp: 'WOL (H)', fdr: 1, is_home: true } } },
    { player_id: 8, web_name: 'Pedro Porro', position: 'DEF' as const, team_code: 6, price_m: 5.9, selected_by_pct: 13.9, is_unavailable: false, chance_of_playing: 1, predicted_pts: 6.2, pts_next5: 27.6, xpts_proxy: 5.5, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 6.2, opp: 'MCI (A)', fdr: 5, is_home: false }, '33': { pred: 5.4, opp: 'BOU (H)', fdr: 2, is_home: true }, '34': { pred: 6.8, opp: 'WOL (A)', fdr: 1, is_home: false }, '35': { pred: 4.7, opp: 'LIV (H)', fdr: 4, is_home: true }, '36': { pred: 4.5, opp: 'SOU (A)', fdr: 1, is_home: false } } },
    { player_id: 9, web_name: 'Flekken',    position: 'GK' as const,  team_code: 94, price_m: 4.5,  selected_by_pct: 6.3,  is_unavailable: false, chance_of_playing: 1, predicted_pts: 5.8, pts_next5: 26.1, xpts_proxy: 5.2, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 5.8, opp: 'NFO (H)', fdr: 2, is_home: true }, '33': { pred: 4.9, opp: 'ARS (A)', fdr: 4, is_home: false }, '34': { pred: 6.1, opp: 'SOU (H)', fdr: 1, is_home: true }, '35': { pred: 4.5, opp: 'CHE (A)', fdr: 3, is_home: false }, '36': { pred: 4.8, opp: 'EVE (H)', fdr: 1, is_home: true } } },
    { player_id: 10, web_name: 'Pedro',     position: 'MID' as const, team_code: 91, price_m: 6.1,  selected_by_pct: 8.7,  is_unavailable: true,  chance_of_playing: 0.25, predicted_pts: 5.5, pts_next5: 23.1, xpts_proxy: 5.0, target_gw: 32, model_run_at: new Date().toISOString(), gw_breakdown: { '32': { pred: 5.5, opp: 'TOT (H)', fdr: 3, is_home: true }, '33': { pred: 4.8, opp: 'CHE (A)', fdr: 3, is_home: false }, '34': { pred: 5.1, opp: 'IPS (H)', fdr: 1, is_home: true }, '35': { pred: 3.9, opp: 'ARS (A)', fdr: 4, is_home: false }, '36': { pred: 3.8, opp: 'NFO (H)', fdr: 2, is_home: true } } },
  ]
}

const MOCK_PLAYER_DETAIL = {
  player: { player_id: 1, web_name: 'Salah', position: 'MID' as const, team_code: 14, price_m: 13.2, selected_by_pct: 48.1, is_unavailable: false, chance_of_playing: 1, team_changed: false, is_new_player: false, is_penalties_taker: true },
  latest_stat: { gw: 31, pts: 12, minutes: 90, goals: 1, assists: 1, clean_sheets: 0, saves: 0, bonus: 3, xg: 0.82, xa: 0.61, xgi: 1.43, xg_per90: 0.82, xa_per90: 0.61, xgi_per90: 1.43 },
  prediction: MOCK_PREDICTIONS.predictions[0],
}

const MOCK_TEAMS = {
  teams: [
    { code: 3,  name: 'Arsenal',           short_name: 'ARS', fdr: 4, attack_fdr: 4, defence_fdr: 5, elo: 1820, strength_attack_home: 1290, strength_attack_away: 1270, strength_defence_home: 1300, strength_defence_away: 1280 },
    { code: 94, name: 'Brentford',         short_name: 'BRE', fdr: 2, attack_fdr: 2, defence_fdr: 2, elo: 1580, strength_attack_home: 1170, strength_attack_away: 1140, strength_defence_home: 1150, strength_defence_away: 1120 },
    { code: 43, name: 'Manchester City',   short_name: 'MCI', fdr: 5, attack_fdr: 5, defence_fdr: 5, elo: 1890, strength_attack_home: 1360, strength_attack_away: 1340, strength_defence_home: 1320, strength_defence_away: 1300 },
    { code: 14, name: 'Liverpool',         short_name: 'LIV', fdr: 4, attack_fdr: 4, defence_fdr: 4, elo: 1850, strength_attack_home: 1330, strength_attack_away: 1310, strength_defence_home: 1290, strength_defence_away: 1270 },
    { code: 6,  name: 'Tottenham',         short_name: 'TOT', fdr: 3, attack_fdr: 3, defence_fdr: 3, elo: 1690, strength_attack_home: 1240, strength_attack_away: 1210, strength_defence_home: 1200, strength_defence_away: 1180 },
    { code: 7,  name: 'Aston Villa',       short_name: 'AVL', fdr: 3, attack_fdr: 3, defence_fdr: 3, elo: 1710, strength_attack_home: 1250, strength_attack_away: 1220, strength_defence_home: 1210, strength_defence_away: 1190 },
    { code: 4,  name: 'Newcastle',         short_name: 'NEW', fdr: 3, attack_fdr: 3, defence_fdr: 3, elo: 1700, strength_attack_home: 1240, strength_attack_away: 1220, strength_defence_home: 1220, strength_defence_away: 1200 },
    { code: 91, name: 'Fulham',            short_name: 'FUL', fdr: 2, attack_fdr: 2, defence_fdr: 2, elo: 1610, strength_attack_home: 1180, strength_attack_away: 1150, strength_defence_home: 1160, strength_defence_away: 1140 },
    { code: 36, name: 'Brighton',          short_name: 'BHA', fdr: 3, attack_fdr: 3, defence_fdr: 3, elo: 1670, strength_attack_home: 1230, strength_attack_away: 1200, strength_defence_home: 1190, strength_defence_away: 1170 },
    { code: 8,  name: 'Chelsea',           short_name: 'CHE', fdr: 3, attack_fdr: 3, defence_fdr: 3, elo: 1720, strength_attack_home: 1250, strength_attack_away: 1230, strength_defence_home: 1220, strength_defence_away: 1200 },
  ]
}

const MOCK_FDR: FdrResponse = {
  from_gw: 32,
  num_gws: 5,
  ticker: [
    { team_code: 3,  short_name: 'ARS', name: 'Arsenal',         fixtures: [{ gw:32, is_home:false, fdr:2, colour:'#01fc7a', opponent_code:94 }, { gw:33, is_home:true,  fdr:1, colour:'#00ff85', opponent_code:91 }, { gw:34, is_home:false, fdr:5, colour:'#800742', opponent_code:43 }, { gw:35, is_home:true, fdr:1, colour:'#00ff85', opponent_code:36 }, { gw:36, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:6 }] },
    { team_code: 43, short_name: 'MCI', name: 'Manchester City',  fixtures: [{ gw:32, is_home:true,  fdr:1, colour:'#00ff85', opponent_code:36 }, { gw:33, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:6  }, { gw:34, is_home:true,  fdr:4, colour:'#ff1751', opponent_code:3  }, { gw:35, is_home:false, fdr:2, colour:'#01fc7a', opponent_code:91 }, { gw:36, is_home:true, fdr:2, colour:'#01fc7a', opponent_code:94 }] },
    { team_code: 14, short_name: 'LIV', name: 'Liverpool',        fixtures: [{ gw:32, is_home:true,  fdr:2, colour:'#01fc7a', opponent_code:36 }, { gw:33, is_home:false, fdr:5, colour:'#800742', opponent_code:43 }, { gw:34, is_home:true,  fdr:1, colour:'#00ff85', opponent_code:91 }, { gw:35, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:8  }, { gw:36, is_home:true, fdr:4, colour:'#ff1751', opponent_code:3  }] },
    { team_code: 94, short_name: 'BRE', name: 'Brentford',        fixtures: [{ gw:32, is_home:true,  fdr:2, colour:'#01fc7a', opponent_code:91 }, { gw:33, is_home:false, fdr:4, colour:'#ff1751', opponent_code:3  }, { gw:34, is_home:true,  fdr:1, colour:'#00ff85', opponent_code:36 }, { gw:35, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:8  }, { gw:36, is_home:true, fdr:2, colour:'#01fc7a', opponent_code:43 }] },
    { team_code: 6,  short_name: 'TOT', name: 'Tottenham',        fixtures: [{ gw:32, is_home:false, fdr:5, colour:'#800742', opponent_code:43 }, { gw:33, is_home:true,  fdr:3, colour:'#c5c5c5', opponent_code:14 }, { gw:34, is_home:false, fdr:1, colour:'#00ff85', opponent_code:91 }, { gw:35, is_home:true, fdr:4, colour:'#ff1751', opponent_code:3  }, { gw:36, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:7  }] },
    { team_code: 7,  short_name: 'AVL', name: 'Aston Villa',      fixtures: [{ gw:32, is_home:true,  fdr:1, colour:'#00ff85', opponent_code:91 }, { gw:33, is_home:false, fdr:2, colour:'#01fc7a', opponent_code:94 }, { gw:34, is_home:true,  fdr:2, colour:'#01fc7a', opponent_code:91 }, { gw:35, is_home:false, fdr:4, colour:'#ff1751', opponent_code:3  }, { gw:36, is_home:true, fdr:3, colour:'#c5c5c5', opponent_code:6  }] },
    { team_code: 4,  short_name: 'NEW', name: 'Newcastle',        fixtures: [{ gw:32, is_home:true,  fdr:1, colour:'#00ff85', opponent_code:91 }, { gw:33, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:8  }, { gw:34, is_home:true,  fdr:2, colour:'#01fc7a', opponent_code:36 }, { gw:35, is_home:false, fdr:5, colour:'#800742', opponent_code:43 }, { gw:36, is_home:true, fdr:2, colour:'#01fc7a', opponent_code:94 }] },
    { team_code: 91, short_name: 'FUL', name: 'Fulham',           fixtures: [{ gw:32, is_home:false, fdr:1, colour:'#00ff85', opponent_code:7  }, { gw:33, is_home:true,  fdr:4, colour:'#ff1751', opponent_code:14 }, { gw:34, is_home:false, fdr:5, colour:'#800742', opponent_code:43 }, { gw:35, is_home:true, fdr:2, colour:'#01fc7a', opponent_code:94 }, { gw:36, is_home:false, fdr:3, colour:'#c5c5c5', opponent_code:6  }] },
    { team_code: 36, short_name: 'BHA', name: 'Brighton',         fixtures: [{ gw:32, is_home:false, fdr:4, colour:'#ff1751', opponent_code:43 }, { gw:33, is_home:true,  fdr:2, colour:'#01fc7a', opponent_code:91 }, { gw:34, is_home:false, fdr:1, colour:'#00ff85', opponent_code:94 }, { gw:35, is_home:true, fdr:3, colour:'#c5c5c5', opponent_code:14 }, { gw:36, is_home:false, fdr:4, colour:'#ff1751', opponent_code:7  }] },
    { team_code: 8,  short_name: 'CHE', name: 'Chelsea',          fixtures: [{ gw:32, is_home:true,  fdr:3, colour:'#c5c5c5', opponent_code:6  }, { gw:33, is_home:true,  fdr:3, colour:'#c5c5c5', opponent_code:4  }, { gw:34, is_home:false, fdr:2, colour:'#01fc7a', opponent_code:91 }, { gw:35, is_home:true, fdr:4, colour:'#ff1751', opponent_code:14 }, { gw:36, is_home:false, fdr:4, colour:'#ff1751', opponent_code:3  }] },
  ]
}
