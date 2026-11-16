import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In docker compose the backend is reachable as http://backend:8000
const target = process.env.VITE_API_TARGET || 'http://localhost:8000'
// Host names allowed besides localhost and IP addresses, e.g. a Tailscale HTTPS name for the phone
// (comma-separated in ALLOWED_HOSTS). *.ts.net and *.local are allowed by default.
const allowedHosts = ['.ts.net', '.local', ...(process.env.ALLOWED_HOSTS || '').split(',').filter(Boolean)]

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': target }, allowedHosts },
})
