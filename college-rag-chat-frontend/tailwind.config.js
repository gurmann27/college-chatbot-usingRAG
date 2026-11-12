import typography from '@tailwindcss/typography';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Text"',
          '"SF Pro Display"',
          '"Helvetica Neue"',
          'system-ui',
          'sans-serif',
        ],
        mono: ['"SF Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'monospace'],
      },
      colors: {
        canvas: 'var(--bg-canvas)',
        surface: 'var(--bg-surface)',
        secondary: 'var(--bg-secondary)',
        ink: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        accent: {
          DEFAULT: 'var(--accent-fill)',
          text: 'var(--accent-text)',
          tint: 'var(--accent-tint)',
          hover: 'var(--accent-fill-hover)',
        },
        tone: {
          secondary: 'var(--tone-secondary-text)',
          secondaryTint: 'var(--tone-secondary-tint)',
        },
        separator: 'var(--separator)',
      },
      boxShadow: {
        apple: 'var(--shadow-card)',
        glass: 'var(--shadow-glass)',
        sheet: 'var(--shadow-sheet)',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.2s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
    },
  },
  plugins: [typography],
};
