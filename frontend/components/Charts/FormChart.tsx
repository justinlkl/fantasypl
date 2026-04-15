'use client'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'

interface FormChartProps {
  history: { gw: number; pts: number | null; xgi: number | null; minutes: number | null }[]
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="stat-card text-xs mono" style={{ minWidth: 100, fontSize: 11 }}>
      <div className="font-bold mb-1" style={{ color: 'var(--accent)' }}>GW {label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex justify-between gap-3" style={{ color: p.color }}>
          <span>{p.name}</span>
          <span className="font-medium">{typeof p.value === 'number' ? p.value.toFixed(2) : '—'}</span>
        </div>
      ))}
    </div>
  )
}

export default function FormChart({ history }: FormChartProps) {
  const data = history.slice(-20).map(h => ({
    gw:   h.gw,
    pts:  h.pts ?? 0,
    xgi:  h.xgi ?? 0,
    played: (h.minutes ?? 0) > 0,
  }))

  const avgPts = data.length ? data.reduce((s, d) => s + d.pts, 0) / data.length : 0

  return (
    <ResponsiveContainer width="100%" height={180}>
      <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="gw" tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'DM Mono' }}
          tickLine={false} axisLine={false}
        />
        <YAxis
          tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'DM Mono' }}
          tickLine={false} axisLine={false} width={28}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={avgPts} stroke="var(--muted)" strokeDasharray="3 3" strokeOpacity={0.5} />
        <Bar dataKey="xgi" name="xGI" fill="rgba(56,189,248,0.25)" stroke="rgba(56,189,248,0.5)" strokeWidth={1} radius={[1,1,0,0]} />
        <Line
          type="monotone" dataKey="pts" name="Pts"
          stroke="var(--accent)" strokeWidth={2} dot={{ fill: 'var(--accent)', r: 2, strokeWidth: 0 }}
          activeDot={{ r: 4, fill: 'var(--accent)' }}
        />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
