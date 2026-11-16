import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(<App />)

// Installable app (PWA). Browsers allow a service worker only on https:// or on localhost.
if ('serviceWorker' in navigator && (window.isSecureContext)) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
}
