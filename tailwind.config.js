/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f5f5f5',
          100: '#e5e5e5',
          200: '#d4d4d4',
          500: '#171717',
          600: '#0a0a0a',
          700: '#000000',
          900: '#000000',
        },
        surface: {
          DEFAULT: '#FAFAFA',
          raised: '#FFFFFF',
          border: '#E5E5E5',
          borderStrong: '#D4D4D4',
        },
        textPrimary: '#0A0A0A',
        textSecondary: '#6B6B6B',
        textTertiary: '#A3A3A3',
        statusSuccess: '#16A34A',
        statusWarning: '#D97706',
        statusCritical: '#DC2626',
        statusInfo: '#2563EB',
      },
      fontFamily: {
        sans: ['Inter', 'Geist', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
