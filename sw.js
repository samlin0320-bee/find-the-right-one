const CACHE_NAME = 'find-the-right-one-v71-cache-v2';
const urlsToCache = [
  '/find-the-right-one/v65.html',
  '/find-the-right-one/v71.html',
  '/find-the-right-one/kangxi_db.json',
  '/find-the-right-one/manifest.json',
  '/find-the-right-one/icons/icon-192x192.png',
  '/find-the-right-one/icons/icon-512x512.png'
];

// Install event - cache essential resources
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

// Activate event - clean up ALL old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - NETWORK FIRST strategy (always get latest version)
self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // Network failed, fallback to cache
        return caches.match(event.request);
      })
  );
});
