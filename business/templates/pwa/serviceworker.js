/* {% load static %} */
const staticCacheName = "u-connect-v5";
const coreAssets = [
    "/offline/",
    '{% static "css/style.css" %}',
    '{% static "css/shop.css" %}',
    '{% static "css/ae.css" %}',
    '{% static "css/checkout-flow.css" %}',
    '{% static "css/product-detail.css" %}',
    '{% static "css/deal-rating.css" %}',
    '{% static "js/main.js" %}',
    '{% static "images/uconnect_192.png" %}',
    '{% static "images/uconnect_512.png" %}',
    '{% static "images/uconnect.ico" %}',
];

// Install: pre-cache core assets gracefully (don't fail install if an asset is missing)
self.addEventListener("install", (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(staticCacheName).then(async (cache) => {
            for (const asset of coreAssets) {
                try {
                    await cache.add(asset);
                } catch (err) {
                    // Non-fatal if an optional asset fails
                }
            }
        })
    );
});

// Activate: clean up ALL older caches immediately and claim clients
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches
            .keys()
            .then((cacheNames) =>
                Promise.all(
                    cacheNames
                        .filter((name) => name !== staticCacheName)
                        .map((name) => caches.delete(name))
                )
            )
            .then(() => self.clients.claim())
    );
});

// Fetch: Network-First for HTML & Static Assets so CSS is ALWAYS fresh
self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") return;

    const url = new URL(event.request.url);

    // Bypass uploads, Django admin, and real-time live support APIs
    if (
        url.pathname.startsWith("/media/") ||
        url.pathname.startsWith("/admin/") ||
        url.pathname.startsWith("/support-chat/api/") ||
        url.pathname.includes("/api/")
    ) {
        return;
    }

    // 1. Navigation requests (HTML pages) -> Network first, fallback to offline page
    if (event.request.mode === "navigate") {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    if (response && response.status === 200) {
                        const copy = response.clone();
                        caches.open(staticCacheName).then((cache) => cache.put(event.request, copy));
                    }
                    return response;
                })
                .catch(async () => {
                    const cached = await caches.match(event.request);
                    if (cached) return cached;
                    const offline = await caches.match("/offline/");
                    return (
                        offline ||
                        new Response("Offline", {
                            status: 503,
                            headers: { "Content-Type": "text/html" },
                        })
                    );
                })
        );
        return;
    }

    // 2. Static CSS / JS / Font requests -> Network first, update cache, fallback to cache
    const isStaticAsset =
        url.pathname.startsWith("/static/") ||
        url.hostname.includes("cdn.jsdelivr.net") ||
        event.request.destination === "style" ||
        event.request.destination === "script" ||
        event.request.destination === "font";

    if (isStaticAsset) {
        // While online, do NOT hijack static CSS/JS requests.
        // Let the browser's native network engine handle standard HTTP caching,
        // ETag revalidation, and HTTP 304 responses natively so CSS never renders empty.
        if (navigator.onLine) {
            return;
        }

        // When offline, serve from pre-cached assets
        event.respondWith(
            caches.match(event.request, { ignoreSearch: true }).then((cached) => {
                if (cached) return cached;

                if (event.request.destination === "style" || url.pathname.endsWith(".css")) {
                    return new Response("/* Offline CSS */", {
                        headers: { "Content-Type": "text/css" },
                    });
                }
                if (event.request.destination === "script" || url.pathname.endsWith(".js")) {
                    return new Response("// Offline JS", {
                        headers: { "Content-Type": "application/javascript" },
                    });
                }
                return new Response("Not found", { status: 404 });
            })
        );
        return;
    }

    // 3. All other requests -> Network first, fallback to cache
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request, { ignoreSearch: true }))
    );
});

