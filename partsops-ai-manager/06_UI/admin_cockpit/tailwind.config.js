/** @type {import('tailwindcss').Config} */
/**
 * Admin Cockpit theme — maps Tailwind utilities to CSS design tokens
 * defined in src/index.css. Prefer token classes over hard-coded slate/hex.
 */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        /* Surfaces */
        surface: {
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
          4: 'var(--surface-4)',
          5: 'var(--surface-5)',
        },
        app: {
          bg: 'var(--bg-app)',
          canvas: 'var(--bg-canvas)',
          shell: 'var(--bg-shell)',
        },
        /* Text — use as text-ink-primary (avoids clashing with text-* utilities) */
        ink: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        /* Borders */
        line: {
          DEFAULT: 'var(--border-default)',
          subtle: 'var(--border-subtle)',
          strong: 'var(--border-strong)',
        },
        /* Accents */
        accent: {
          primary: 'var(--accent-primary)',
          strong: 'var(--accent-primary-strong)',
          success: 'var(--accent-success)',
          warning: 'var(--accent-warning)',
          danger: 'var(--accent-danger)',
          info: 'var(--accent-info)',
        },
        /* State fills */
        state: {
          hover: 'var(--state-hover)',
          selected: 'var(--state-selected)',
          active: 'var(--state-active)',
          disabled: 'var(--state-disabled)',
        },
      },
      borderRadius: {
        panel: 'var(--radius-panel)',
        card: 'var(--radius-card)',
        control: 'var(--radius-control)',
        modal: 'var(--radius-modal)',
      },
      boxShadow: {
        'ds-sm': 'var(--shadow-sm)',
        'ds-md': 'var(--shadow-md)',
        'ds-lg': 'var(--shadow-lg)',
        'ds-modal': 'var(--shadow-modal)',
        'ds-focus': 'var(--focus-ring)',
      },
      transitionDuration: {
        ds: '220ms',
      },
      transitionTimingFunction: {
        ds: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
  plugins: [],
};
