/* Service worker for the Meal Planner home-screen app.
 *
 * Goals, in order:
 *   1. The app opens instantly and works with no signal (e.g. in the shop).
 *   2. It still picks up changes without the user reinstalling anything.
 *
 * VERSION is replaced at build time with a hash of the built page, so every
 * deploy creates a fresh cache and retires the previous one.
 *
 * The page itself is fetched network-first: when there is a connection the user
 * always gets the current build, and the cached copy is only a fallback. Icons
 * and the manifest are cache-first because they rarely change and are replaced
 * wholesale when the version does.
 */
const VERSION = "__VERSION__";
const CACHE = `meal-planner-${VERSION}`;
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      // Not addAll: one 404 would reject the whole install and leave the app
      // with no offline copy at all.
      .then((cache) => Promise.all(CORE.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

/* Static assets that are safe to serve from cache and cheap to re-fetch.
 * Anything else is left alone, so the cache cannot grow without bound from,
 * say, URLs that differ only by query string. */
const CACHEABLE = /\.(?:png|svg|ico|css|js|webmanifest|json)$/;

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put("./index.html", copy));
          return response;
        })
        .catch(() => caches.match("./index.html").then((hit) => hit || caches.match("./"))),
    );
    return;
  }

  if (!CACHEABLE.test(url.pathname)) return;

  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }),
    ),
  );
});
