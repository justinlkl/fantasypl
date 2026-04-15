import type { Position } from './types'

export const FDR_COLOURS: Record<number, string> = {
  1: '#00ff85', 2: '#01fc7a', 3: '#b0b0b0', 4: '#ff1751', 5: '#800742',
}
export const FDR_TEXT: Record<number, string> = {
  1: '#000', 2: '#000', 3: '#000', 4: '#fff', 5: '#fff',
}
export const FDR_LABELS: Record<number, string> = {
  1: 'Very Easy', 2: 'Easy', 3: 'Medium', 4: 'Hard', 5: 'Very Hard',
}

export const POS_COLOURS: Record<Position, string> = {
  GK: '#facc15', DEF: '#4ade80', MID: '#60a5fa', FWD: '#f87171',
}
export const POS_BG: Record<Position, string> = {
  GK: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/30',
  DEF: 'bg-green-400/10 text-green-400 border-green-400/30',
  MID: 'bg-blue-400/10 text-blue-400 border-blue-400/30',
  FWD: 'bg-red-400/10 text-red-400 border-red-400/30',
}

export function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—'
  return n.toFixed(decimals)
}

export function availColor(chance: number | null): string {
  if (chance == null || chance >= 1) return ''
  if (chance >= 0.75) return 'text-amber-400'
  if (chance >= 0.5) return 'text-orange-400'
  return 'text-red-500'
}

export function availLabel(chance: number | null): string {
  if (chance == null || chance >= 1) return 'Available'
  if (chance >= 0.75) return '75%'
  if (chance >= 0.5) return '50%'
  if (chance >= 0.25) return '25%'
  return 'Doubtful'
}

// Map team_code to short name (fallback for when teams API hasn't loaded)
const TEAM_SHORT: Record<number, string> = {
  3: 'ARS', 7: 'AVL', 36: 'BHA', 94: 'BRE', 90: 'BOU',
  8: 'CHE', 31: 'CRY', 11: 'EVE', 54: 'FUL', 40: 'IPS',
  13: 'LEI', 14: 'LIV', 43: 'MCI', 1: 'MUN', 4: 'NEW',
  17: 'NFO', 49: 'SOU', 6: 'TOT', 21: 'WHU', 39: 'WOL',
  91: 'FUL',
}
export function teamShort(code: number): string {
  return TEAM_SHORT[code] ?? String(code)
}
