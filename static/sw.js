/* OrderMama service worker — হালকা, নিরাপদ।
   নীতি: HTML/API কখনো ক্যাশ নয় (সবসময় নেটওয়ার্ক), শুধু স্ট্যাটিক ফাইল ক্যাশ।
   নেটওয়ার্ক না পেলে আগের ক্যাশ থেকে স্ট্যাটিক (css/js/ফন্ট/ছবি) দেখানো হয়। */
const VERSION = "om-v1";
const STATIC_CACHE = `${VERSION}-static`;
const PRECACHE = ["/static/css/customer.css", "/static/js/common.js", "/static/js/cart.js", "/static/js/menu.js", "/static/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(STATIC_CACHE).then((c) => c.addAll(PRECACHE)).catch(() => {}).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;              // CDN/Fonts: ব্রাউজার নিজেই সামলাবে
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/payments/")) return; // ডাইনামিক: ক্যাশ নয়
  const isStatic = url.pathname.startsWith("/static/") || url.pathname.startsWith("/media/");
  if (!isStatic) return;                                   // HTML পেজ সবসময় নেটওয়ার্ক থেকে (তাজা ডেটা)

  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req).then((res) => {
        if (res && res.ok && res.type === "basic") {
          const copy = res.clone();
          caches.open(STATIC_CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
