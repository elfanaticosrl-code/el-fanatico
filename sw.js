const C="elf-v1";
self.addEventListener("install",e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(["./","index.html","manifest.webmanifest","icon-192.png"])))});
self.addEventListener("fetch",e=>{
  if(e.request.method!=="GET")return;
  const u=new URL(e.request.url);
  if(u.origin!==location.origin)return;
  if(u.pathname.endsWith("news.json")){
    e.respondWith(fetch(e.request).then(r=>{const k=r.clone();caches.open(C).then(c=>c.put("news.json",k));return r}).catch(()=>caches.match("news.json")));
  }else{
    e.respondWith(fetch(e.request).catch(()=>caches.match(e.request).then(r=>r||caches.match("index.html"))));
  }
});
