'use client'
import useSWR from 'swr'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const fetcher = (url: string) => fetch(url).then(r => r.json())
const api = (path: string) => `${BASE}${path}`

export function usePredictions(
  position?: string,
  maxPrice?: number,
  available = true,
  sort = 'pts_next5',
  options?: {
    season?: string
    limit?: number
    include_breakdown?: boolean
    include_stats?: boolean
  },
) {
  const params = new URLSearchParams({
    limit: String(options?.limit ?? 200),
    sort,
    available: String(available),
    season: options?.season ?? '2526',
  })
  if (position) params.set('position', position)
  if (maxPrice) params.set('max_price', String(maxPrice))
  if (options?.include_breakdown) params.set('include_breakdown', 'true')
  if (options?.include_stats) params.set('include_stats', 'true')
  return useSWR(api(`/predictions?${params}`), fetcher, { refreshInterval: 300_000, fallbackData: null })
}

export function usePlayerDetail(id: number | null) {
  return useSWR(id ? api(`/players/${id}`) : null, fetcher, { fallbackData: null })
}

export function usePlayerHistory(id: number | null) {
  return useSWR(id ? api(`/players/${id}/history`) : null, fetcher, { fallbackData: null })
}

export function usePlayerPrediction(id: number | null) {
  return useSWR(id ? api(`/predictions/${id}`) : null, fetcher, { refreshInterval: 300_000, fallbackData: null })
}

export function useFixtureTicker(numGws = 5) {
  return useSWR(api(`/fixtures/fdr?num_gws=${numGws}`), fetcher, { refreshInterval: 600_000, fallbackData: null })
}

export function useFixtures(params?: {
  season?: string
  from_gw?: number
  to_gw?: number
  finished?: boolean
}) {
  const q = new URLSearchParams({ season: params?.season ?? '2526' })
  if (params?.from_gw != null) q.set('from_gw', String(params.from_gw))
  if (params?.to_gw != null) q.set('to_gw', String(params.to_gw))
  if (params?.finished != null) q.set('finished', String(params.finished))
  return useSWR(api(`/fixtures?${q}`), fetcher, { refreshInterval: 300_000, fallbackData: null })
}

export function useTeams() {
  return useSWR(api('/teams/'), fetcher, { revalidateOnFocus: false, fallbackData: null })
}

export function useLiveMatches(gw?: number) {
  const q = gw ? `?gw=${gw}` : ''
  return useSWR(api(`/live/matches${q}`), fetcher, { refreshInterval: 60_000, fallbackData: null })
}

export function useLivePoints(gw?: number) {
  const q = gw ? `?gw=${gw}` : ''
  return useSWR(api(`/live/points${q}`), fetcher, { refreshInterval: 60_000, fallbackData: null })
}

export function useCompare(ids: number[]) {
  const key = ids.length >= 2 ? api(`/players/compare/?ids=${ids.join(',')}`) : null
  return useSWR(key, fetcher, { fallbackData: null })
}
