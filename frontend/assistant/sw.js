const CACHE = 'munshi-v1';
const PRECACHE = [
  '/assistant/',
  '/assistant/app.js',
  '/assistant/app.css',
  '/assistant/shell.js',
  '/assistant/kit.js',
  '/assistant/net.js',
  '/assistant/i18n.js',
  '/assistant/listener.js',
  '/assistant/photo.js',
  '/lab/ui.js',
  '/lab/api.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/') || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok) { const c = r.clone(); caches.open(CACHE).then((cache) => cache.put(e.request, c)); }
      return r;
    }).catch(() => caches.match(e.request))
  );
});
