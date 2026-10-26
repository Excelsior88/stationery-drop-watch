#!/usr/bin/env python3
"""Stationery Drop Watch stock checker.

Reads stores.json, checks every product politely, writes:
  data/stock.json    current status of every tracked product (with timestamps)
  data/changes.json  append-only log of status changes between runs

Politeness: identifies itself with a real User-Agent, obeys robots.txt,
waits >= DELAY seconds between requests to the same host, one worker per host.

Status values: in_stock | sold_out | preorder | coming_soon | unknown (+ error)
"""
import json, re, time, threading, urllib.robotparser, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; StationeryDropWatch/0.1; restock tracker; +https://excelsior88.github.io/stationery-drop-watch/; contact: stationerydropwatch@gmail.com)"
DELAY = 2.5          # seconds between requests to one host
TIMEOUT = 25
PREORDER_RX = re.compile(r"pre[- ]?order|preorder", re.I)
COMING_RX = re.compile(r"\bpreview\b|coming soon|order starts", re.I)

def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

class Host:
    """Per-host session + robots.txt + rate limit."""
    def __init__(self, base):
        self.base = base; self.s = requests.Session(); self.s.headers["User-Agent"] = UA
        self.last = 0.0; self.rp = urllib.robotparser.RobotFileParser()
        try:
            r = self.get(f"{base}/robots.txt", check_robots=False)
            self.rp.parse(r.text.splitlines() if r.ok else [])
        except Exception:
            self.rp.parse([])
    def allowed(self, url): return self.rp.can_fetch(UA, url)
    def get(self, url, check_robots=True):
        if check_robots and not self.allowed(url):
            raise PermissionError("disallowed by robots.txt")
        wait = self.last + DELAY - time.time()
        if wait > 0: time.sleep(wait)
        try: return self.s.get(url, timeout=TIMEOUT)
        finally: self.last = time.time()

def classify_shopify(js):
    variants = js.get("variants") or []
    avail = [v for v in variants if v.get("available")]
    text = " ".join([js.get("title", "")] + [v.get("title") or "" for v in variants] + list(js.get("tags") or []))
    if js.get("available") or avail:
        status = "preorder" if PREORDER_RX.search(text) else "in_stock"
    else:
        status = "coming_soon" if COMING_RX.search(text) else "sold_out"
    return status, len(avail), len(variants), re.sub(r"<[^>]+>", "", js.get("title", ""))

def classify_html(html):
    """Fallback: schema.org availability in JSON-LD / microdata."""
    m = re.findall(r'schema\.org/(InStock|OutOfStock|SoldOut|PreOrder|BackOrder|LimitedAvailability)', html)
    if not m: return None
    if "PreOrder" in m or "BackOrder" in m: return "preorder"
    if "InStock" in m or "LimitedAvailability" in m: return "in_stock"
    return "sold_out"

def check_shopify_store(store):
    base = store["url"].rstrip("/"); h = Host(base); out = []
    for p in store["products"]:
        rec = dict(store_id=store["id"], store=store["name"], canonical=p.get("canonical"), label=p["label"],
                   type=p["type"], url=p["url"], checked_at=None, status="unknown", method=None,
                   available_variants=None, total_variants=None, title=p.get("source_title"), error=None)
        try:
            r = h.get(p["url"] + ".js"); rec["checked_at"] = now()
            if r.ok and r.headers.get("content-type", "").startswith(("application/json", "text/javascript", "application/javascript")):
                st, a, t, title = classify_shopify(r.json())
                rec.update(status=st, available_variants=a, total_variants=t, title=title, method="shopify .js")
            else:
                r2 = h.get(p["url"]); rec["checked_at"] = now()
                st = classify_html(r2.text) if r2.ok else None
                if st: rec.update(status=st, method="html schema.org")
                else: rec["error"] = f"HTTP {r.status_code} on .js, HTTP {r2.status_code} on page, no availability markup"
        except Exception as e:
            rec["checked_at"] = now(); rec["error"] = f"{type(e).__name__}: {e}"[:200]
        out.append(rec)
    return out

def check_hobonichi(store):
    """Official 1101.com store: one public JSON feed covers every 2027 item."""
    h = Host("https://www.1101.com"); out = []
    try:
        feed = h.get("https://www.1101.com/store/techo/2027/items.json").json()["items"]; err = None
    except Exception as e:
        feed, err = {}, f"{type(e).__name__}: {e}"[:200]
    t = now()
    for p in store["products"]:
        rec = dict(store_id=store["id"], store=store["name"], canonical=p.get("canonical"), label=p["label"],
                   type=p["type"], url=p["url"], checked_at=t, status="unknown", method="1101 items.json",
                   available_variants=None, total_variants=None, title=p.get("source_title"), error=err)
        it = feed.get(p["source_key"])
        if it is not None:
            sales = list((it.get("sales") or {}).values())
            live = [s for s in sales if not s.get("soldout") and not s.get("unreleased")]
            rec["available_variants"], rec["total_variants"] = len(live), len(sales)
            if it.get("soldout") or (sales and all(s.get("soldout") for s in sales)): rec["status"] = "sold_out"
            elif sales and all(s.get("unreleased") for s in sales): rec["status"] = "coming_soon"
            elif live: rec["status"] = "in_stock"
        elif not err:
            rec["error"] = "item key not in feed"
        out.append(rec)
    return out

def check_store(store):
    if store["platform"] == "shopify": return check_shopify_store(store)
    if store["platform"] == "hobonichi": return check_hobonichi(store)
    return []  # blocked / robots-disallowed stores are link-only

def main():
    cfg = json.loads((ROOT / "stores.json").read_text())
    started = now()
    with ThreadPoolExecutor(max_workers=8) as ex:   # one worker per host, hosts in parallel
        results = [r for rs in ex.map(check_store, cfg["stores"]) for r in rs]
    data_dir = ROOT / "data"; data_dir.mkdir(exist_ok=True)
    stock_f, changes_f = data_dir / "stock.json", data_dir / "changes.json"
    prev = {r["url"]: r for r in json.loads(stock_f.read_text())["products"]} if stock_f.exists() else {}
    changes = json.loads(changes_f.read_text()) if changes_f.exists() else []
    for r in results:
        old = prev.get(r["url"])
        r["first_seen"] = old.get("first_seen", r["checked_at"]) if old else r["checked_at"]
        r["status_since"] = old.get("status_since") if old and old["status"] == r["status"] else r["checked_at"]
        if old and r["status"] != "unknown" and old["status"] not in ("unknown", r["status"]):
            changes.append(dict(at=r["checked_at"], store_id=r["store_id"], store=r["store"], label=r["label"],
                                url=r["url"], **{"from": old["status"], "to": r["status"]}))
        elif old and r["status"] == "unknown" and old["status"] != "unknown":
            r["status_since"] = old.get("status_since")  # transient failure: don't reset the clock
    summary = {k: sum(1 for r in results if r["status"] == k) for k in ("in_stock", "preorder", "coming_soon", "sold_out", "unknown")}
    blocked = [dict(id=s["id"], name=s["name"], url=s["url"], reason=s.get("note")) for s in cfg["stores"] if s["platform"] not in ("shopify", "hobonichi")]
    stock_f.write_text(json.dumps(dict(run_started=started, run_finished=now(), summary=summary,
                                       not_checked=blocked, products=results), indent=1, ensure_ascii=False))
    changes_f.write_text(json.dumps(changes, indent=1, ensure_ascii=False))
    ok = len(results) - summary["unknown"]
    print(f"checked {len(results)} products: {ok} classified, {summary['unknown']} failed -> {summary}")
    for r in results:
        if r["status"] == "unknown": print("  FAIL", r["store_id"], r["url"], r["error"])
    print(f"new status changes this run: {sum(1 for c in changes if c['at'] >= started)}")

if __name__ == "__main__":
    main()
