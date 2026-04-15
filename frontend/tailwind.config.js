/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:      '#080c14',
        surface: '#0f1620',
        panel:   '#131e2e',
        border:  '#1e2d3d',
        text:    '#e2e8f0',
        muted:   '#64748b',
        accent:  '#00ff87',
        blue:    '#38bdf8',
        red:     '#ef4444',
        amber:   '#f59e0b',
        fdr: {
          1: '#00ff85',
          2: '#01fc7a',
          3: '#c5c5c5',
          4: '#ff1751',
          5: '#800742',
        },
      },
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        mono:    ['DM Mono', 'JetBrains Mono', 'monospace'],
        body:    ['DM Sans', 'sans-serif'],
      },
      fontSize: {
        '2xs': '0.625rem',
      },
    },
  },
  plugins: [],
}
