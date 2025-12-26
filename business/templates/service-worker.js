{% load static %}
const CACHE_NAME = 'u-connect-v1';
const urlsToCache = [
    '/',
    "{% static 'css/style.css' %}",
    "{% static 'js/main.js' %}",
    "{% static 'images/uconnect.ico' %}",
    "{% static 'images/uconnect (192x192).png' %}",
    "{% static 'images/uconnect (512x512).png' %}"
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                return cache.addAll(urlsToCache);
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