import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In docker compose the backend is reachable as http://backend:8000
const target = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': target } },
})
