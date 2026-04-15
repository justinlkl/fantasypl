# frontend/  —  React / Next.js Dashboard

This directory will contain the React dashboard that consumes the FastAPI backend.

## Reference sites
- https://fplform.com  (predictions + fixture ticker)
- https://elevenify.com  (player comparison + charts)

## Planned pages (MVP vertical slice)

| Page | Route | Key components |
|------|-------|----------------|
| Predictions table | `/` | Sortable player table, position filter, price filter |
| Player detail | `/players/[id]` | xG/xA charts, form sparkline, 5-GW breakdown |
| Player compare | `/compare` | Side-by-side stats, radar chart, GW history |
| Fixtures ticker | `/fixtures` | FDR colour-coded grid, all 20 teams × 5 GWs |
| Live scores | `/live` | Live match strip, live player pts, bonus projection |
| Transfer planner | `/planner` | Drag-and-drop squad, bank/FT tracker, chip toggle |

## Tech stack

```
Next.js 14 (App Router)
Tailwind CSS
Plotly.js or Recharts (player charts)
ECharts (fixture ticker heatmap)
SWR (data fetching + real-time refresh)
```

## Quick start

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app
npm install recharts plotly.js-dist swr
npm run dev
```

## API base URL

Set in `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Key API calls

```javascript
// Prediction table
GET /predictions?position=MID&available=true&limit=50

// 5-GW breakdown for one player
GET /predictions/123

// Fixture ticker
GET /fixtures/fdr?num_gws=5

// Live points (poll every 60s during matches)
GET /live/points

// Player comparison
GET /players/compare/?ids=123,456,789
```

## Dashboard wiring (SWR example)

```typescript
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then(r => r.json())

export function usePredictions(position?: string) {
  const url = `/api/predictions${position ? `?position=${position}` : ''}`
  return useSWR(url, fetcher, { refreshInterval: 300_000 })  // refresh every 5 min
}

export function useLivePoints(gw: number) {
  return useSWR(`/api/live/points?gw=${gw}`, fetcher, {
    refreshInterval: 60_000,   // refresh every 60s during matches
  })
}
```

## Build order (follow roadmap)

1. Prediction table (consumes `/predictions`)
2. Fixture ticker (consumes `/fixtures/fdr`)
3. Player detail + charts (consumes `/players/{id}` + `/predictions/{id}`)
4. Player compare page (consumes `/players/compare/`)
5. Live scores strip (consumes `/live/matches` + `/live/points`)
6. Transfer planner (consumes `/planner/*`)
