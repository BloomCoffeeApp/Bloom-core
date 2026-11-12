/* Bloom service worker (generated at build time by the `pwa` plugin in vite.config.ts).
 *
 * Safe strategy for a POS whose data lives on the shop's PC:
 * - Only the app SHELL is cached: index.html, hashed /assets/* and icons/manifest.
 * - NEVER caches /api/* or /uploads/* (sales, cash, customers… always come from the server).
 * - Navigations: network first, cached shell when the PC can't be reached (the app then shows
 *   "Sin conexión con la PC del local").
 * - A new build = a new BUILD_ID = a new worker that WAITS until the user taps "Actualizar".
 */
const BUILD_ID = '__BUILD_ID__'
const CACHE = `bloom-shell-${BUILD_ID}`
const PRECACHE = __PRECACHE__
const SHELL = '/index.html'

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('bloom-shell-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting()
})

const neverCache = (url) => url.pathname.startsWith('/api/') || url.pathname.startsWith('/uploads/')

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  if (url.origin !== self.location.origin || neverCache(url)) return

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => caches.open(CACHE).then((c) => c.match(SHELL)).then((r) => r || Response.error())),
    )
    return
  }
  if (url.pathname.startsWith('/assets/')) {
    // Hashed file names: a cached copy is always the right one.
    event.respondWith(
      caches.open(CACHE).then((c) =>
        c.match(req).then(
          (hit) =>
            hit ||
            fetch(req).then((res) => {
              if (res.ok) c.put(req, res.clone())
              return res
            }),
        ),
      ),
    )
    return
  }
  if (PRECACHE.includes(url.pathname)) {
    // Icons, manifest, logo: network first so a new logo shows up, cache when offline.
    event.respondWith(fetch(req).catch(() => caches.open(CACHE).then((c) => c.match(url.pathname)).then((r) => r || Response.error())))
  }
})
