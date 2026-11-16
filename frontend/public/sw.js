// Service worker: makes the app installable and lets it open without a connection to the backend.
// Network first for everything (so a new version is used as soon as it is there); the cache is only
// a fallback. GET /api answers are cached too, so the last pages you opened can be read offline.
// Answers you send (POST) always need the backend.
const CACHE = 'study-lab-v1'
const SHELL = ['/', '/manifest.webmanifest', '/icon.svg', '/icon-192.png', '/icon-512.png']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()))
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  const url = new URL(req.url)
  if (req.method !== 'GET' || url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/progress/export') || url.pathname.startsWith('/api/labs')) return
  e.respondWith((async () => {
    try {
      const res = await fetch(req)
      if (res.ok && res.type === 'basic') {
        const copy = res.clone()
        caches.open(CACHE).then((c) => c.put(req, copy))
      }
      return res
    } catch (err) {
      const hit = await caches.match(req)
      if (hit) return hit
      if (req.mode === 'navigate') return (await caches.match('/')) || Response.error()
      throw err
    }
  })())
})
