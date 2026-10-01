const CACHE = "radar-auto-v5";
const SHELL = ["./", "index.html", "manifest.json", "icons/icon-180.png", "icons/icon-192.png", "icons/icon-512.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith("radar-") && key !== CACHE).map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(req, {cache: "no-store", signal: controller.signal});
      if (!response.ok) throw new Error("HTTP " + response.status);
      const copy = response.clone();
      event.waitUntil(cache.put(req, copy).catch(() => {}));
      return response;
    } catch (err) {
      return (await cache.match(req)) || new Response("Sem conexão. Tente novamente.", {
        status: 503, headers: {"Content-Type": "text/plain; charset=utf-8"}
      });
    } finally {
      clearTimeout(timer);
    }
  })());
});
