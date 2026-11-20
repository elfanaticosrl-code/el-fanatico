import json, re, os, sys, hashlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

NOW = datetime.now(timezone.utc)
CFG = json.load(open("feeds.json", encoding="utf-8"))
STOP = set("with from that this have will after about their over into says said para como pero esta este sobre desde entre cuando tras sus los las del una uno more than when what your".split())
LANG = {"en": ("en-US", "US:en"), "es": ("es-419", "MX:es-419"), "fr": ("fr", "FR:fr"), "de": ("de", "DE:de"), "pt": ("pt-BR", "BR:pt-419")}

def get(url, data=None, headers=None):
    h = {"User-Agent": "Mozilla/5.0 ElFanatico/2.0", **(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=15) as r:
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
        if t and l: out.append(dict(s=f["sport"], t=re.sub(r"<[^>]+>", "", t), src=f["src"], u=l, img=img, ts=when(d), w=f.get("w", 2), rep=bool(f.get("rep"))))
    return out

def feed_url(f):
    if "q" in f:
        hl, ce = LANG[f.get("lang", "en")]
        return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": f["q"] + " when:1d", "hl": hl, "gl": ce[:2], "ceid": ce})
    return f["url"]

def job(f):
    try:
        its = parse_feed(get(feed_url(f)), f)
        if "q" in f:
            for i in its: i["t"] = i["t"].rsplit(" - ", 1)[0]
        return f, its, None if its else "sin datos"
    except Exception as e:
        return f, [], str(e)[:60]

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
        out.append(dict(s=a["sport"], t=txt.split("\n")[0][:160], src=a["name"], rep=True, w=3, img=img,
                        u=f"https://bsky.app/profile/{a['handle']}/post/{po['uri'].split('/')[-1]}", ts=when(po["record"].get("createdAt"))))
    return out

def has(text, words): return any(re.search(r"\b" + re.escape(k) + r"\b", text) for k in words)

def classify(text):
    best, top = None, 0
    for sp, ws in CFG["classify"].items():
        n = sum(1 for k in ws if re.search(r"\b" + re.escape(k) + r"\b", text))
        if n > top: best, top = sp, n
    return best

def toks(t): return {w for w in re.findall(r"[a-záéíóúñ0-9]{4,}", t.lower()) if w not in STOP}
def similar(a, b): return len(a & b) >= 3 and len(a & b) / max(1, len(a | b)) >= .3

def push(i):
    head = "🔥 En tendencia" if i["hot"] else "⚡ Podría ser viral"
    msg = {"topic": os.environ["NTFY_TOPIC"], "title": f"{head} · {i['src']}", "message": i["t"], "click": i["u"], "tags": ["fire" if i["hot"] else "zap"]}
    if i.get("img"): msg["attach"] = i["img"]
    try: get("https://ntfy.sh", data=json.dumps(msg).encode(), headers={"Content-Type": "application/json"})
    except Exception as e: print("ntfy:", e, file=sys.stderr)

def main():
    items, fail = [], []
    with ThreadPoolExecutor(16) as ex:
        for f, its, err in ex.map(job, CFG["feeds"]):
            items += its
            if err: fail.append(f"{f['src']} ({err})")
    total = len(CFG["feeds"]) + len(CFG.get("bluesky", []))
    for a in CFG.get("bluesky", []):
        try: items += bsky(a)
        except Exception as e: fail.append(f"{a['name']} ({str(e)[:40]})")
    items = [i for i in items if i["ts"] > NOW - timedelta(hours=48)]
    for i in items:
        if i["s"] == "auto": i["s"] = classify(i["t"].lower())
    items = [i for i in items if i["s"]]
    uniq, seen_u = [], set()
    for i in sorted(items, key=lambda x: x["ts"], reverse=True):
        if i["u"] in seen_u: continue
        seen_u.add(i["u"]); i["id"] = hashlib.md5(i["u"].encode()).hexdigest()[:10]; uniq.append(i)
    tk = {i["id"]: toks(i["t"]) for i in uniq}
    for i in uniq:
        tl = i["t"].lower(); age = (NOW - i["ts"]).total_seconds() / 3600
        srcs = {i["src"]}
        for j in uniq:
            if j is not i and abs((i["ts"] - j["ts"]).total_seconds()) <= 43200 and similar(tk[i["id"]], tk[j["id"]]): srcs.add(j["src"])
        n = len(srcs); kw = has(tl, CFG["hot_keywords"]); star = has(tl, CFG["stars"]); vt = has(tl, CFG["viral_terms"])
        i["n"] = n
        i["hot"] = bool(age < 12 and (n >= 3 or (kw and n >= 2) or (i["rep"] and kw)))
        vs = 2 * star + 2 * vt + 2 * kw + min(n - 1, 3) + (i["src"] == "TMZ Sports") + i["rep"] + bool(i["img"]) + (i["w"] == 3)
        i["viral"] = bool(age < 4 and not i["hot"] and vs >= 4 and (star or vt or n >= 2))
        i["score"] = round(i["w"] * 10 + min(n, 6) * 6 + 30 * i["hot"] + 18 * i["viral"] + max(0, 20 - age * 1.2) + 3 * bool(i["img"]) + 12 * i["rep"], 1)
    kept = []
    for i in sorted(uniq, key=lambda x: -x["score"]):
        if any(abs((i["ts"] - k["ts"]).total_seconds()) <= 43200 and similar(tk[i["id"]], tk[k["id"]]) for k in kept): continue
        kept.append(i)
    out, cnt = [], {}
    for i in kept:
        cnt[i["s"]] = cnt.get(i["s"], 0) + 1
        if cnt[i["s"]] <= 40 or i["hot"] or i["viral"]:
            out.append({k: v for k, v in i.items() if k != "w"} | {"ts": i["ts"].isoformat()})
    json.dump({"updated": NOW.isoformat(), "total": total, "ok": total - len(fail), "fail": fail, "items": out}, open("news.json", "w", encoding="utf-8"), ensure_ascii=False)
    seen = json.load(open("seen.json")) if os.path.exists("seen.json") else None
    alerts = sorted([i for i in out if i["hot"] or i["viral"]], key=lambda i: -i["score"])
    if seen is not None and os.environ.get("NTFY_TOPIC"):
        sent = 0
        for i in alerts:
            if i["id"] not in seen and sent < 5 and (i["hot"] or CFG.get("notify_viral", True)): push(i); sent += 1
    json.dump(list(dict.fromkeys([i["id"] for i in alerts] + (seen or [])))[:500], open("seen.json", "w"))
    print(len(out), "noticias;", sum(i["hot"] for i in out), "tendencia;", sum(i["viral"] for i in out), "posible viral;", len(fail), "fuentes con falla")

if __name__ == "__main__": main()
