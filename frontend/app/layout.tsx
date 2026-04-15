import type { Metadata } from 'next'
import './globals.css'
import Nav from '@/components/Nav'

export const metadata: Metadata = {
  title: 'FPL Analytics',
  description: 'Machine-learning predictions, live scores, and transfer planning for Fantasy Premier League.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen" style={{ background: 'var(--bg)' }}>
        <Nav />
        <main className="max-w-[1440px] mx-auto px-4 sm:px-6 pb-16 pt-4">
          {children}
        </main>
      </body>
    </html>
  )
}
