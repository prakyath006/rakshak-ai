/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f7ff',
          100: '#e0effe',
          500: '#0055ff',
          600: '#0044cc',
          700: '#003399',
          900: '#0a1930',
        },
        slate: {
          850: '#151f32',
          900: '#0b1329',
          950: '#050b18',
        }
      }
    },
  },
  plugins: [],
}
