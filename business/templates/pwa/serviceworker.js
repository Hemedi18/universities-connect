{% load static %}
const staticCacheName = "u-connect-v2";
const filesToCache = [
    '{% static "css/style.css" %}',
    '{% static "js/main.js" %}',
    '{% static "images/uconnect_192.png" %}',
    '{% static "images/uconnect_512.png" %}',
    '{% static "images/uconnect.ico" %}',
];

self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(staticCacheName).then((cache) => cache.addAll(filesToCache))
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) =>
            Promise.all(
                cacheNames
                    .filter((name) => name.startsWith("u-connect-"))
                    .filter((name) => name !== staticCacheName)
                    .map((name) => caches.delete(name))
            )
        ).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") return;

    const url = new URL(event.request.url);
    // Never intercept media / uploads — broken SW was returning HTML for images
    if (url.pathname.startsWith("/media/")) return;

    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request).catch(() => caches.match("/"))
        );
        return;
    }

    event.respondWith(
        caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
});
