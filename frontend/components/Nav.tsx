'use client'
import Link from 'next/link'
import { Activity, BarChart2, Shield, Users, RefreshCw, Sliders } from 'lucide-react'

const modules = [
  { label: 'GW Results', icon: Activity },
  { label: 'Player Analytics', icon: BarChart2 },
  { label: 'Fixtures', icon: Shield },
  { label: 'Compare', icon: Users },
  { label: 'Transfer Planner', icon: RefreshCw },
  { label: 'Team Builder', icon: Sliders },
]

export default function Nav() {
  return (
    <header style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-14 flex items-center gap-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 mr-2 shrink-0">
          <div style={{ background: 'var(--accent)', width: 8, height: 8, borderRadius: 1 }} />
          <span className="display font-bold text-sm tracking-widest uppercase" style={{ color: 'var(--accent)' }}>
            FPL Core Dashboard
          </span>
        </Link>

        {/* Module strip */}
        <nav className="flex items-center gap-1 overflow-x-auto">
          {modules.map(({ label, icon: Icon }) => (
            <span
              key={label}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded whitespace-nowrap"
              style={{
                color: 'var(--muted)',
                border: '1px solid rgba(100,116,139,0.25)',
                background: 'transparent',
                fontFamily: 'DM Mono, monospace',
                letterSpacing: '0.04em',
              }}
            >
              <Icon size={12} />
              {label}
            </span>
          ))}
        </nav>

        {/* Right side — GW indicator */}
        <div className="ml-auto flex items-center gap-3 shrink-0">
          <span className="text-2xs mono" style={{ color: 'var(--muted)' }}>Unified Experience</span>
          <div className="w-px h-4" style={{ background: 'var(--border)' }} />
          <span className="text-2xs mono" style={{ color: 'var(--muted)' }}>2025-26</span>
        </div>
      </div>
    </header>
  )
}
