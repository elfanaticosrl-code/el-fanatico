import json, re, os, sys, hashlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

NOW = datetime.now(timezone.utc)
CFG = json.load(open("feeds.json", encoding="utf-8"))
STOP = set("with from that this have will after about their over into says said para como pero esta este sobre desde entre cuando tras sus los las del una uno more than when what your".split())

def get(url, data=None, headers=None):
    h = {"User-Agent": "Mozilla/5.0 ElFanatico/1.0", **(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=20) as r:
        return r.read()

def tag(e): return e.tag.split("}")[-1]

def when(s):
    if not s: return NOW
    try: d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return NOW
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def parse_feed(raw, f):
    out = []
    for it in ET.fromstring(raw).iter():
        if tag(it) not in ("item", "entry"): continue
        t = l = d = img = None; blob = ""
        for c in it:
            k = tag(c)
            if k == "title": t = (c.text or "").strip()
            elif k == "link": l = c.get("href") or (c.text or "").strip()
            elif k in ("pubDate", "published", "updated", "date"): d = d or c.text
            elif k in ("thumbnail", "content") and c.get("url") and "image" in (c.get("type") or c.get("medium") or "image"): img = img or c.get("url")
            elif k == "enclosure" and "image" in (c.get("type") or ""): img = img or c.get("url")
            elif k in ("description", "summary", "encoded"): blob += c.text or ""
        if not img:
            m = re.search(r'<img[^>]+src="([^"]+)"', blob); img = m.group(1) if m else None
        if t and l: out.append(dict(s=f["sport"], t=re.sub(r"<[^>]+>", "", t), src=f["src"], u=l, img=img, ts=when(d)))
    return out

def bsky(a):
    q = urllib.parse.urlencode({"actor": a["handle"], "limit": 15, "filter": "posts_no_replies"})
    out = []
    for p in json.loads(get("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?" + q)).get("feed", []):
        if p.get("reason"): continue
        po = p["post"]; txt = po["record"].get("text", "").strip()
        if not txt: continue
        emb = po.get("embed", {}); img = None
        if emb.get("images"): img = emb["images"][0].get("thumb")
        elif emb.get("external"): img = emb["external"].get("thumb")
        out.append(dict(s=a["sport"], t=txt.split("\n")[0][:160], src=a["name"], rep=True, img=img,
                        u=f"https://bsky.app/profile/{a['handle']}/post/{po['uri'].split('/')[-1]}", ts=when(po["record"].get("createdAt"))))
    return out

def toks(t): return {w for w in re.findall(r"[a-záéíóúñ0-9]{4,}", t.lower()) if w not in STOP}

def push(i):
    msg = {"topic": os.environ["NTFY_TOPIC"], "title": "🔥 " + i["src"], "message": i["t"], "click": i["u"], "tags": ["fire"]}
    if i.get("img"): msg["attach"] = i["img"]
    try: get("https://ntfy.sh", data=json.dumps(msg).encode(), headers={"Content-Type": "application/json"})
    except Exception as e: print("ntfy:", e, file=sys.stderr)

def main():
    items = []
    for f in CFG["feeds"]:
        try: items += parse_feed(get(f["url"]), f)
        except Exception as e: print("fallo", f["src"], f["url"], e, file=sys.stderr)
    for a in CFG.get("bluesky", []):
        try: items += bsky(a)
        except Exception as e: print("fallo", a["handle"], e, file=sys.stderr)
    items = [i for i in items if i["ts"] > NOW - timedelta(hours=48)]
    uniq, seen_u = [], set()
    for i in sorted(items, key=lambda x: x["ts"], reverse=True):
        if i["u"] in seen_u: continue
        seen_u.add(i["u"]); i["id"] = hashlib.md5(i["u"].encode()).hexdigest()[:10]; uniq.append(i)
    tk = {i["id"]: toks(i["t"]) for i in uniq}
    for i in uniq:
        srcs = {i["src"]}
        for j in uniq:
            if j is i or abs((i["ts"] - j["ts"]).total_seconds()) > 43200: continue
            a, b = tk[i["id"]], tk[j["id"]]
            if len(a & b) >= 3 and len(a & b) / max(1, len(a | b)) >= .3: srcs.add(j["src"])
        kw = any(k in i["t"].lower() for k in CFG["hot_keywords"])
        i["n"] = len(srcs)
        i["hot"] = bool(i["ts"] > NOW - timedelta(hours=12) and (i["n"] >= 3 or (kw and i["n"] >= 2) or (i.get("rep") and kw)))
    out, cnt = [], {}
    for i in uniq:
        cnt[i["s"]] = cnt.get(i["s"], 0) + 1
        if cnt[i["s"]] <= 25 or i["hot"]:
            out.append({**i, "ts": i["ts"].isoformat()})
    json.dump({"updated": NOW.isoformat(), "items": out}, open("news.json", "w", encoding="utf-8"), ensure_ascii=False)
    seen = json.load(open("seen.json")) if os.path.exists("seen.json") else None
    hot = [i for i in out if i["hot"]]
    if seen is not None and os.environ.get("NTFY_TOPIC"):
        for i in hot:
            if i["id"] not in seen: push(i)
    json.dump(list(dict.fromkeys([i["id"] for i in hot] + (seen or [])))[:500], open("seen.json", "w"))
    print(len(out), "noticias,", len(hot), "en tendencia")

if __name__ == "__main__": main()
