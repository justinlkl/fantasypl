'use client'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'

interface StatRadarProps {
  players: {
    name: string
    color: string
    stats: {
      xGI90: number; xG90: number; xA90: number
      form: number; minutes: number; bonus: number
    }
  }[]
}

const AXES = [
  { key: 'xGI90',   label: 'xGI/90',  max: 1.5 },
  { key: 'xG90',    label: 'xG/90',   max: 1.0 },
  { key: 'xA90',    label: 'xA/90',   max: 0.7 },
  { key: 'form',    label: 'Form',    max: 10  },
  { key: 'minutes', label: 'Mins',    max: 90  },
  { key: 'bonus',   label: 'Bonus',   max: 3   },
]

export default function StatRadar({ players }: StatRadarProps) {
  const data = AXES.map(axis => {
    const point: Record<string, number | string> = { axis: axis.label }
    players.forEach(p => {
      const raw = p.stats[axis.key as keyof typeof p.stats] ?? 0
      point[p.name] = Math.min(100, (raw / axis.max) * 100)
    })
    return point
  })

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis
          dataKey="axis"
          tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'DM Mono' }}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--surface)', border: '1px solid var(--border)',
            fontSize: 11, fontFamily: 'DM Mono', color: 'var(--text)',
          }}
          formatter={(v: number, name: string) => [`${v.toFixed(0)}`, name]}
        />
        {players.map(p => (
          <Radar
            key={p.name}
            name={p.name}
            dataKey={p.name}
            stroke={p.color}
            fill={p.color}
            fillOpacity={0.12}
            strokeWidth={1.5}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  )
}
