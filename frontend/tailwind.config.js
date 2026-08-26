/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Ground and surfaces. A near-black with a faint blue-violet bias rather
        // than Tailwind's stock slate — chosen so the data colours sit on a
        // neutral field instead of competing with a blue one.
        ink: {
          950: '#08090d',
          900: '#0b0d13',
          850: '#0f121a',
          800: '#12151f',
          750: '#171b27',
          700: '#1d2230',
          600: '#2a3040',
          500: '#3d4457',
          400: '#5b6478',
          300: '#8a93a6',
          200: '#b8c0d0',
          100: '#e2e6ee',
        },
        // Single accent. Validated against surface #12151f by the data-viz
        // validator (contrast, chroma, CVD separation all pass).
        signal: {
          900: '#0d2847',
          800: '#12386a',
          700: '#184f95',
          600: '#2a78d6',
          500: '#3987e5',
          400: '#5598e7',
          300: '#86b6ef',
          200: '#b7d3f6',
        },
        // The marketing site is printed matter: paper, ink, hairline rules.
        // Deliberately not the dark-glow palette the app uses — the two are
        // different rooms, and a document should not glow.
        paper: {
          DEFAULT: '#f2f4f6',
          raised: '#ffffff',
          sunk: '#e8ecef',
          rule: '#d3dae1',
          'rule-soft': '#e2e7ec',
        },
        graphite: {
          900: '#0f1319',
          700: '#2c3540',
          500: '#5a6675',
          400: '#7d8895',
          300: '#a3adb8',
        },
        // Printed-ink accents, not screen colours.
        press: '#1b4d8f',
        loss: '#a6303c',
        gain: '#1f6b4a',

        // Reserved status colours. Never reused as a series colour, and always
        // paired with an icon or label so hue never carries meaning alone.
        good: '#0ca30c',
        warn: '#fab219',
        serious: '#ec835a',
        critical: '#d03b3b',
      },
      fontFamily: {
        sans: ['Archivo', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Newsreader', 'Georgia', 'Times New Roman', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        lift: '0 1px 2px rgba(0,0,0,.4), 0 12px 32px -18px rgba(0,0,0,.9)',
        glow: '0 0 0 1px rgba(57,135,229,.25), 0 8px 32px -12px rgba(57,135,229,.35)',
      },
      keyframes: {
        rise: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        fade: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        sweep: {
          '100%': { transform: 'translateX(100%)' },
        },
        breathe: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '.45' },
        },
      },
      animation: {
        rise: 'rise .5s cubic-bezier(.16,1,.3,1) both',
        fade: 'fade .4s ease-out both',
        breathe: 'breathe 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
