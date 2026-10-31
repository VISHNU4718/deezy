/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: '#2563eb', hover: '#1d4ed8', light: '#dbeafe' },
        secondary: '#64748b',
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        background: '#f8fafc',
        surface: '#ffffff',
        border: '#e2e8f0',
        muted: '#64748b',
      },
    },
  },
  plugins: [],
};
