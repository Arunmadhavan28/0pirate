// tailwind.config.mjs

/** @type {import('tailwindcss').Config} */
const config = {
  content: [
  "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
  "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
],

  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)'],
        mono: ['var(--font-fira-code)'],
      },
      colors: {
        'background-dark': 'var(--background-dark)',
        'background-card': 'var(--background-card)',
        'background-light': 'var(--background-light)',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-tertiary': 'var(--text-tertiary)',
        'accent-primary': 'var(--accent-primary)',
        'accent-primary-hover': 'var(--accent-primary-hover)',
        'accent-destructive': 'var(--accent-destructive)',
        'accent-destructive-hover': 'var(--accent-destructive-hover)',
        'border-primary': 'var(--border-primary)',
        'border-secondary': 'var(--border-secondary)',
        'status-success': 'var(--status-success)',
        'status-warning': 'var(--status-warning)',
        'status-info': 'var(--status-info)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
};

export default config;