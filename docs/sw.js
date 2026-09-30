// Service worker: deixa o app abrir offline e mantém os editais atualizados.
const V = "radar-v2";
const SHELL = ["./", "index.html", "manifest.json", "icons/icon-192.png", "icons/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(V).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // Dados: rede primeiro (sempre o mais novo); sem internet, usa a última cópia.
  if (url.pathname.endsWith("editais.json")) {
    e.respondWith(
      fetch(req, { cache: "no-store" })
        .then((r) => { const c = r.clone(); caches.open(V).then((x) => x.put(req, c)); return r; })
        .catch(() => caches.match(req))
    );
    return;
  }
  // Arquivos do app: usa a cópia guardada e atualiza em segundo plano.
  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req)
        .then((r) => { const c = r.clone(); caches.open(V).then((x) => x.put(req, c)); return r; })
        .catch(() => hit);
      return net.then(function(resposta){return resposta || hit});
    })
  );
});
