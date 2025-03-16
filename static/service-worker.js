// Service Worker for WiFi File Transfer PWA
const CACHE_NAME = 'wifi-file-transfer-v1';
const ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js'
];

// Install event - cache assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cache opened');
        return cache.addAll(ASSETS);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(cacheName => {
          return cacheName !== CACHE_NAME;
        }).map(cacheName => {
          return caches.delete(cacheName);
        })
      );
    })
  );
});

// Fetch event - respond with cached assets when offline
self.addEventListener('fetch', event => {
  // Skip non-GET requests and API/file operations
  if (event.request.method !== 'GET' || 
      event.request.url.includes('/api/') ||
      event.request.url.includes('/download/') ||
      event.request.url.includes('/delete/') ||
      event.request.url.includes('/upload')) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached response if found
        if (response) {
          return response;
        }
        
        // Otherwise fetch from network
        return fetch(event.request).then(networkResponse => {
          // Don't cache if response is not valid
          if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
            return networkResponse;
          }
          
          // Clone the response to cache it and return it
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
            
          return networkResponse;
        });
      })
      .catch(() => {
        // If both cache and network fail, show fallback
        if (event.request.url.includes('.html')) {
          return caches.match('/');
        }
      })
  );
}); 