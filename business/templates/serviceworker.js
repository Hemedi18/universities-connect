{% load static %}
const CACHE_NAME = 'u-connect-v2';
const urlsToCache = [
    '/',
    "{% static 'css/style.css' %}",
    "{% static 'js/main.js' %}",
    "{% static 'images/uconnect.ico' %}",
    "{% static 'images/uconnect_192.png' %}",
    "{% static 'images/uconnect_512.png' %}"
];

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});