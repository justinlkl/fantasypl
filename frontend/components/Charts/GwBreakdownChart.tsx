'use client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from 'recharts'
import { FDR_COLOURS, FDR_TEXT } from '@/lib/utils'
import type { Prediction } from '@/lib/types'

interface GwBreakdownChartProps {
  prediction: Prediction
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="stat-card text-xs mono" style={{ minWidth: 110, fontSize: 11 }}>
      <div className="font-bold mb-1" style={{ color: 'var(--accent)' }}>GW {label}</div>
      <div style={{ color: 'var(--text)' }}>Projected: <span className="font-medium">{d.pred?.toFixed(2)}</span></div>
      <div style={{ color: 'var(--muted)' }}>vs {d.opp}</div>
      <div className="mt-1" style={{
        background: FDR_COLOURS[d.fdr] ?? '#888',
        color: FDR_TEXT[d.fdr] ?? '#fff',
        padding: '1px 6px',
        display: 'inline-block',
        fontSize: 10,
      }}>FDR {d.fdr}</div>
    </div>
  )
}

export default function GwBreakdownChart({ prediction }: GwBreakdownChartProps) {
  const bd = prediction.gw_breakdown ?? {}
  const data = Object.entries(bd)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([gw, v]) => ({ gw: Number(gw), ...v }))

  if (!data.length) return (
    <div className="flex items-center justify-center h-24 text-xs mono" style={{ color: 'var(--muted)' }}>
      No 5-GW breakdown available
    </div>
  )

  return (
    <ResponsiveContainer width="100%" height={140}>
      <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="gw"
          tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'DM Mono' }}
          tickLine={false} axisLine={false}
          tickFormatter={v => `GW${v}`}
        />
        <YAxis
          tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'DM Mono' }}
          tickLine={false} axisLine={false} width={24}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="pred" name="Proj pts" radius={[2, 2, 0, 0]}>
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={FDR_COLOURS[d.fdr] ?? 'var(--accent)'}
              fillOpacity={0.85}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
