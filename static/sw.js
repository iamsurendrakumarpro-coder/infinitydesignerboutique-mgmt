// ── Infinity Designer Boutique – Service Worker ──────────────────────────────
'use strict';

const CACHE_NAME = 'idb-boutique-v1';

const PRE_CACHE_URLS = [
  '/',
  '/login',
  '/static/css/app.css',
];

const OFFLINE_JSON = JSON.stringify({
  ok: false,
  error: 'You are offline. Please check your connection and try again.',
});

const OFFLINE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Offline – IDB Boutique</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:Inter,system-ui,sans-serif;display:flex;align-items:center;
         justify-content:center;min-height:100vh;background:#f5f3ff;color:#312e81;
         text-align:center;padding:2rem}
    h1{font-size:1.5rem;margin-bottom:.75rem}
    p{color:#6b7280;max-width:28rem;line-height:1.6}
    .icon{font-size:3rem;margin-bottom:1rem}
    button{margin-top:1.5rem;padding:.625rem 1.5rem;background:#4f46e5;color:#fff;
           border:none;border-radius:.5rem;font-size:.875rem;font-weight:600;
           cursor:pointer}
    button:active{background:#4338ca}
  </style>
</head>
<body>
  <div>
    <div class="icon">📡</div>
    <h1>You're Offline</h1>
    <p>It looks like you've lost your internet connection.
       Please reconnect and try again.</p>
    <button onclick="location.reload()">Retry</button>
  </div>
</body>
</html>`;

// ── Install: pre-cache core assets ───────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRE_CACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean up old caches ────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

// ── Fetch strategies ─────────────────────────────────────────────────────────

function networkFirst(request) {
  return fetch(request)
    .then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    })
    .catch(() =>
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return new Response(OFFLINE_JSON, {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        });
      })
    );
}

function cacheFirst(request) {
  return caches.match(request).then((cached) => {
    if (cached) return cached;
    return fetch(request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    });
  });
}

function staleWhileRevalidate(request) {
  return caches.open(CACHE_NAME).then((cache) =>
    cache.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response.ok) cache.put(request, response.clone());
          return response;
        })
        .catch(() => {
          if (cached) return cached;
          // Navigation request – return offline page
          if (request.mode === 'navigate') {
            return new Response(OFFLINE_HTML, {
              status: 503,
              headers: { 'Content-Type': 'text/html' },
            });
          }
          return new Response(OFFLINE_JSON, {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
          });
        });
      return cached || network;
    })
  );
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin requests; let the browser handle them natively
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // API calls → network-first
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Static assets → cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML pages → stale-while-revalidate
  event.respondWith(staleWhileRevalidate(request));
});

// ── Background Sync placeholder for offline punch-ins ────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-punch') {
    event.waitUntil(syncPendingPunches());
  }
});

async function syncPendingPunches() {
  // TODO: Implement once the IndexedDB helper module is ready.
  // Flow: open 'pending-punches' store → POST each to /api/staff/punch →
  //       delete on success, keep on failure for next sync.
  return Promise.resolve();
}
