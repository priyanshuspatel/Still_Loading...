/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        graphite: {
          950: '#090b0c',
          900: '#0f1215',
          850: '#14181c',
          800: '#1b2025',
          700: '#262d34',
          600: '#39424c',
          500: '#525d6b',
          400: '#8491a0',
          300: '#b0bcc8',
          200: '#dbe1e7',
          100: '#f1f4f6',
        },
        led: {
          blue: '#38bdf8',
          'blue-dim': '#0369a1',
          'blue-off': '#10161d',
          amber: '#fbbf24',
          red: '#f87171',
          green: '#4ade80',
          teal: '#2dd4bf',
        },
        accent: {
          lime: '#bef264',
          'lime-dim': '#65a30d',
        },
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Inter"',
          'system-ui',
          'sans-serif',
        ],
        mono: [
          '"SF Mono"',
          '"JetBrains Mono"',
          '"Fira Code"',
          'ui-monospace',
          'monospace',
        ],
      },
      boxShadow: {
        'led-glow': '0 0 12px rgba(56, 189, 248, 0.55), 0 0 24px rgba(56, 189, 248, 0.25)',
        'led-amber-glow': '0 0 12px rgba(251, 191, 36, 0.55)',
        'led-red-glow': '0 0 12px rgba(248, 113, 113, 0.55)',
        'led-green-glow': '0 0 12px rgba(74, 222, 128, 0.55)',
        'matrix-case': 'inset 0 2px 4px rgba(0, 0, 0, 0.8), 0 8px 30px rgba(0, 0, 0, 0.7)',
        'panel': '0 10px 30px -10px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.08)',
      },
      animation: {
        'pulse-subtle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'blink-cursor': 'blink 1s step-end infinite',
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
};
