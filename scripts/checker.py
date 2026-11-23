#!/usr/bin/env python3
"""Stationery Drop Watch stock checker.

Reads stores.json, checks every product politely, writes:
  data/stock.json    current status of every tracked product (with timestamps)
  data/changes.json  append-only log of status changes between runs

Politeness: identifies itself with a real User-Agent, obeys robots.txt,
waits >= DELAY seconds between requests to the same host, one worker per host.

Status values: in_stock | sold_out | preorder | coming_soon | unknown (+ error)

Prices: Shopify listings also record the price from the same .js response (price_cents, and
price_max_cents when the product's variants differ), but only when the shop's own /meta.json
says it sells in USD (currency). Any other shop, a failed /meta.json, or a non-Shopify check
records no price, so pages can say "see price at the shop" instead of guessing.
"""
import json, re, time, threading, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; StationeryDropWatch/0.1; restock tracker; +https://stationerydropwatch.com/; contact: admin@stationerydropwatch.com)"
DELAY = 2.5          # seconds between requests to one host
TIMEOUT = 25
# Product token in the User-Agent. A robots.txt group with this name is used
# before the "*" group. Matching is case-insensitive and ignores a /version suffix.
ROBOTS_TOKEN = "stationerydropwatch"
# These three hosts 301 www to the apex. Stock history is keyed by URL, so a
# www row and the apex row are the same listing.
APEX_HOSTS = {
    "www.milligram.com": "milligram.com",
    "www.cultpens.com": "cultpens.com",
    "www.goldspot.com": "goldspot.com",
}


# ---- link-only shops -----------------------------------------------------------------------------
# A store with "link_only": true in stores.json is never requested: no listing check, no robots.txt, no
# /meta.json, no ink scan, no sitemap or discovery fetch. Its product rows stay on the site as plain links
# (build_site.py) with no status. To turn a shop back on after it gives written permission, delete its
# "link_only" and "link_only_reason" lines in stores.json. Nothing else needs to change.
class LinkOnlyHostError(RuntimeError):
    """Raised before any network request to a link-only shop's host."""

def link_only_stores(cfg):
    return [s for s in cfg.get("stores", []) if s.get("link_only")]

def link_only_ids(cfg=None):
    cfg = cfg or json.loads((ROOT / "stores.json").read_text())
    return {s["id"] for s in link_only_stores(cfg)}

def _host_variants(url):
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return set()
    bare = host[4:] if host.startswith("www.") else host
    return {bare, "www." + bare}

def link_only_hosts(cfg=None):
    """Every hostname (with and without www) of every link-only shop, from its shop URL and its listing URLs."""
    cfg = cfg or json.loads((ROOT / "stores.json").read_text())
    hosts = set()
    for s in link_only_stores(cfg):
        hosts |= _host_variants(s["url"])
        for p in s.get("products", []):
            hosts |= _host_variants(p["url"])
    return hosts

LINK_ONLY_HOSTS = link_only_hosts()

class GuardedSession(requests.Session):
    """requests.Session whose every send, redirect hops included, refuses a link-only host."""
    def send(self, request, **kwargs):
        host = (urlparse(request.url).hostname or "").lower()
        if host in LINK_ONLY_HOSTS:
            raise LinkOnlyHostError(f"{host} is link-only: no requests are made to it")
        return super().send(request, **kwargs)

PREORDER_RX = re.compile(r"pre[- ]?order|preorder", re.I)
# "coming soon" / "order starts" mean the shop is not taking orders yet.
# "preview" alone does not: Wonder Pens leaves PREVIEW in titles after launch,
# including on in-stock books, and tags sold-out books out-of-stock.
UNRELEASED_RX = re.compile(r"coming[\s_-]?soon|order starts", re.I)
PREVIEW_RX = re.compile(r"\bpreview\b", re.I)
_SOLD_OUT_TAGS = {"out-of-stock", "outofstock", "sold-out", "soldout"}

def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def canonical_stock_url(url):
    """Rewrite a redundant www host to the apex. Every other URL is unchanged.

    The checker looks up the previous stock row by this key, so a www to apex
    move keeps first_seen and status_since and does not open a new listing.
    """
    if not url:
        return url
    parts = urlparse(url)
    host = APEX_HOSTS.get(parts.netloc.lower())
    if not host:
        return url
    return urlunparse(parts._replace(netloc=host))

def normalize_fetch_url(url):
    """Cache key for one HTTP fetch: lowercased scheme and host, no fragment."""
    parts = urlparse(url)
    path = parts.path or "/"
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}{query}"

def _robots_path(url):
    """Path plus query, the part Google matches. The fragment is left out."""
    parts = urlparse(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return path

def _robots_pattern_matches(pattern, path):
    """Google-style match: anchored at the start, * is any sequence, $ ends the path.

    Without a trailing $, the pattern matches a prefix of the path.
    """
    end = pattern.endswith("$")
    body = pattern[:-1] if end else pattern
    pieces = ["^"]
    for ch in body:
        pieces.append(".*" if ch == "*" else re.escape(ch))
    if end:
        pieces.append("$")
    return re.match("".join(pieces), path) is not None

class Robots:
    """RFC 9309 / Google robots.txt rules.

    * and $ are wildcards. The longest matching pattern wins. An Allow and a
    Disallow of the same length: Allow wins. A StationeryDropWatch group is
    used when one is present; otherwise the * group. An empty file allows all.
    """
    def __init__(self, lines):
        self.groups = []
        agents, rules, started = [], [], False

        def flush():
            nonlocal agents, rules, started
            if agents:
                self.groups.append((agents, rules))
            agents, rules, started = [], [], False

        for raw in lines:
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip().lower(), val.strip()
            if key == "user-agent":
                if started:
                    flush()
                agents.append(val)
                continue
            if not agents:
                continue
            started = True
            if key not in ("allow", "disallow") or not val:
                continue
            rules.append((key == "allow", val))
        flush()

    def _rules_for(self, user_agent):
        specific = "stationerydropwatch" in (user_agent or "").lower()
        named, star, saw_named = [], [], False
        for agents, rules in self.groups:
            tokens = [a.split("/")[0].strip().lower() for a in agents]
            if specific and ROBOTS_TOKEN in tokens:
                saw_named = True
                named.extend(rules)
            if "*" in tokens:
                star.extend(rules)
        # A named group is used on its own, even when it has no rules.
        return named if saw_named else star

    def allowed(self, user_agent, url):
        path = _robots_path(url)
        best_len, best_allow = -1, True
        for allow, pattern in self._rules_for(user_agent):
            if not _robots_pattern_matches(pattern, path):
                continue
            length = len(pattern)
            if length > best_len or (length == best_len and allow):
                best_len, best_allow = length, allow
        return best_allow

class Host:
    """Per-host session, robots.txt, rate limit, and a per-run fetch cache.

    The cache is keyed by the normalized URL. Two listings that share a
    Shopify .js endpoint (or any other exact fetch URL) hit the network once.
    A cache hit does not wait out the host delay and does not retry an error.
    """
    def __init__(self, base):
        if (urlparse(base).hostname or "").lower() in LINK_ONLY_HOSTS:
            raise LinkOnlyHostError(f"{base} is link-only: no requests are made to it")
        self.base = base
        self.s = GuardedSession()
        self.s.headers["User-Agent"] = UA
        self.last = 0.0
        self.cache = {}
        try:
            r = self.get(f"{base}/robots.txt", check_robots=False)
            lines = r.text.splitlines() if r.ok else []
        except Exception:
            lines = []
        self.robots = Robots(lines)

    def allowed(self, url):
        return self.robots.allowed(UA, url)

    def get(self, url, check_robots=True):
        key = normalize_fetch_url(url)
        if key in self.cache:
            hit = self.cache[key]
            if isinstance(hit, BaseException):
                raise hit
            return hit
        if check_robots and not self.allowed(url):
            raise PermissionError("disallowed by robots.txt")
        wait = self.last + DELAY - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.s.get(url, timeout=TIMEOUT)
        except Exception as exc:
            self.cache[key] = exc
            self.last = time.time()
            raise
        self.cache[key] = resp
        self.last = time.time()
        return resp

def _sold_out_tag(tag):
    return re.sub(r"[\s_]+", "-", str(tag).strip().lower()) in _SOLD_OUT_TAGS

def unavailable_status(text, tags):
    """Status for a Shopify product or variant that cannot be bought.

    An out-of-stock tag wins over a leftover PREVIEW in the title. Wording that
    says the item is not released yet ("coming soon", "order starts") still
    means coming_soon, and a PREVIEW title with no sold-out tag does too.
    """
    tags = [str(t) for t in (tags or [])]
    if UNRELEASED_RX.search(text or "") or any(UNRELEASED_RX.search(t) for t in tags):
        return "coming_soon"
    if any(_sold_out_tag(t) for t in tags):
        return "sold_out"
    if PREVIEW_RX.search(text or "") or any(PREVIEW_RX.search(t) for t in tags):
        return "coming_soon"
    return "sold_out"

def named_variants_disagree(js):
    """True when one Shopify product lists different designs and they are not all available or all unavailable."""
    flags = []
    for v in js.get("variants") or []:
        name = (v.get("public_title") or v.get("title") or "").strip()
        if name and name not in ("Default Title", "-"):
            flags.append(bool(v.get("available")))
    return len(flags) > 1 and len(set(flags)) > 1

def classify_shopify(js):
    variants = js.get("variants") or []
    avail = [v for v in variants if v.get("available")]
    tags = list(js.get("tags") or [])
    text = " ".join([js.get("title", "")] + [v.get("title") or "" for v in variants] + tags)
    if named_variants_disagree(js):
        return "unknown", len(avail), len(variants), re.sub(r"<[^>]+>", "", js.get("title", ""))
    if js.get("available") or avail:
        status = "preorder" if PREORDER_RX.search(text) else "in_stock"
    else:
        status = unavailable_status(text, tags)
    return status, len(avail), len(variants), re.sub(r"<[^>]+>", "", js.get("title", ""))

def classify_shopify_variant(js, vid):
    """One size/paper option of a multi-variant product (e.g. a notebook sold in A5 and B5).
    Returns None if the variant id isn't on the product any more."""
    v = next((v for v in js.get("variants") or [] if v.get("id") == vid), None)
    if v is None: return None
    title = re.sub(r"<[^>]+>", "", js.get("title", "")) + " · " + (v.get("public_title") or v.get("title") or "")
    tags = list(js.get("tags") or [])
    if v.get("available"):
        status = "preorder" if PREORDER_RX.search(title) else "in_stock"
    else:
        status = unavailable_status(title + " " + " ".join(tags), tags)
    return status, int(bool(v.get("available"))), 1, title

def shopify_price(js, vid=None):
    """(price_cents, price_max_cents) from one product .js, or None. Prices are integer cents.
    For one tracked variant, that variant's price. For a whole product, the available
    variants' prices (all variants when none is available)."""
    variants = js.get("variants") or []
    if vid:
        vs = [v for v in variants if v.get("id") == vid]
    else:
        vs = [v for v in variants if v.get("available")] or variants
    cents = [v["price"] for v in vs if isinstance(v.get("price"), int) and v["price"] > 0]
    if not cents: return None
    return min(cents), max(cents)

def shop_currency(h, base):
    """The shop's selling currency from its public /meta.json, or None if it can't be read."""
    try:
        r = h.get(f"{base}/meta.json")
        cur = r.json().get("currency") if r.ok else None
        return cur if isinstance(cur, str) and re.fullmatch(r"[A-Z]{3}", cur) else None
    except Exception:
        return None

def classify_html(html):
    """Fallback: schema.org availability in JSON-LD / microdata."""
    m = re.findall(r'schema\.org/(InStock|OutOfStock|SoldOut|PreOrder|BackOrder|LimitedAvailability)', html)
    if not m: return None
    if "PreOrder" in m or "BackOrder" in m: return "preorder"
    if "InStock" in m or "LimitedAvailability" in m: return "in_stock"
    return "sold_out"

def check_shopify_store(store):
    base = store["url"].rstrip("/"); h = Host(base); out = []
    currency = shop_currency(h, base)  # prices are recorded only for USD shops
    for p in store["products"]:
        rec = dict(store_id=store["id"], store=store["name"], canonical=p.get("canonical"), label=p["label"],
                   type=p["type"], url=p["url"], checked_at=None, status="unknown", method=None,
                   available_variants=None, total_variants=None, title=p.get("source_title"), error=None,
                   **({"section": p["section"]} if p.get("section") else {}))
        try:
            vid = p.get("variant_id")   # optional: track one size/paper option, not the whole product
            r = h.get(p["url"].split("?")[0] + ".js"); rec["checked_at"] = now()
            if r.ok and r.headers.get("content-type", "").startswith(("application/json", "text/javascript", "application/javascript")):
                js = r.json()
                res = classify_shopify_variant(js, vid) if vid else classify_shopify(js)
                if res:
                    st, a, t, title = res
                    rec.update(status=st, available_variants=a, total_variants=t, title=title, method="shopify .js variant" if vid else "shopify .js")
                    pr = shopify_price(js, vid) if currency == "USD" else None
                    if pr:
                        rec.update(currency="USD", price_cents=pr[0], **({"price_max_cents": pr[1]} if pr[1] != pr[0] else {}))
                    if not vid and named_variants_disagree(js):
                        rec["error"] = "named variants do not share one availability"
                else:
                    rec["error"] = f"variant {vid} no longer on this product"
            elif vid:
                rec["error"] = f"HTTP {r.status_code} on .js"  # page markup can't say which size is in stock
            else:
                r2 = h.get(p["url"]); rec["checked_at"] = now()
                st = classify_html(r2.text) if r2.ok else None
                if st: rec.update(status=st, method="html schema.org")
                else: rec["error"] = f"HTTP {r.status_code} on .js, HTTP {r2.status_code} on page, no availability markup"
        except Exception as e:
            rec["checked_at"] = now(); rec["error"] = f"{type(e).__name__}: {e}"[:200]
        out.append(rec)
    return out

# Short notes from Hobonichi's own items.json, shown on sold-out official rows. Our wording, not theirs.
# Real feed values (Nov 19, 2026, all 745 items): message_lineup.en is 0 (no message), "Restock Coming",
# "Restock Undecided", "No Restock Planned", or an edition-only variant such as "Restock coming for the
# English edition" (seen only on items that are still partly on sale). sales_termination was 0 on every item;
# 1 is treated as ended in case Hobonichi starts using it. Edition-only messages get no note.
HOBO_NOTE_RESTOCK = "Official store notes a restock is planned"
HOBO_NOTE_UNDECIDED = "Restock undecided at official store"
HOBO_NOTE_ENDED = "Sales ended at official store"

def hobonichi_note(item, status):
    """The optional official_note for one 1101.com row, or None. Only for sold-out rows; never changes status."""
    if status != "sold_out" or not item:
        return None
    lineup = item.get("message_lineup")
    lineup = (lineup.get("en") or "") if isinstance(lineup, dict) else ""
    if item.get("sales_termination") == 1 or lineup.strip().lower() == "no restock planned":
        return HOBO_NOTE_ENDED
    if item.get("sales_termination") == 0 and lineup.strip().lower() == "restock coming":
        return HOBO_NOTE_RESTOCK
    if item.get("sales_termination") == 0 and lineup.strip().lower() == "restock undecided":
        return HOBO_NOTE_UNDECIDED
    return None

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
            note = hobonichi_note(it, rec["status"])
            if note: rec["official_note"] = note
        elif not err:
            rec["error"] = "item key not in feed"
        out.append(rec)
    return out

def note_transition(old, rec, changes):
    """Record one listing against its previous row.

    A first observation only sets first_seen. A later real status change is appended
    with no product, cover, or Weeks filter. Unknown reads do not become events.
    """
    rec["first_seen"] = old.get("first_seen", rec["checked_at"]) if old else rec["checked_at"]
    rec["status_since"] = old.get("status_since") if old and old["status"] == rec["status"] else rec["checked_at"]
    if old and rec["status"] != "unknown" and old["status"] not in ("unknown", rec["status"]):
        # Every real status change is logged. coming_soon -> sold_out is one of
        # those changes. It is not a restock: alerts and the restock feed only
        # take a flip to in_stock or preorder (see new_in_stock.fresh_in_stock
        # and build_site.is_restock_event).
        changes.append(dict(at=rec["checked_at"], store_id=rec["store_id"], store=rec["store"], label=rec["label"],
                            url=rec["url"], **({"section": rec["section"]} if rec.get("section") else {}),
                            **{"from": old["status"], "to": rec["status"]}))
    elif old and rec["status"] == "unknown" and old["status"] != "unknown":
        rec["status_since"] = old.get("status_since")  # transient failure: don't reset the clock
    return changes


def check_store(store):
    if store.get("link_only"): return []  # link-only: not requested at all (see LINK_ONLY_HOSTS)
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
    prev = {}
    if stock_f.exists():
        for old in json.loads(stock_f.read_text())["products"]:
            prev[canonical_stock_url(old["url"])] = old
    changes = json.loads(changes_f.read_text()) if changes_f.exists() else []
    for r in results:
        note_transition(prev.get(canonical_stock_url(r["url"])), r, changes)
    summary = {k: sum(1 for r in results if r["status"] == k) for k in ("in_stock", "preorder", "coming_soon", "sold_out", "unknown")}
    blocked = [dict(id=s["id"], name=s["name"], url=s["url"], reason=s.get("note")) for s in cfg["stores"] if s["platform"] not in ("shopify", "hobonichi")]
    link_only = [dict(id=s["id"], name=s["name"], url=s["url"], reason=s.get("link_only_reason")) for s in link_only_stores(cfg)]
    stock_f.write_text(json.dumps(dict(run_started=started, run_finished=now(), summary=summary,
                                       not_checked=blocked, link_only=link_only, products=results), indent=1, ensure_ascii=False))
    changes_f.write_text(json.dumps(changes, indent=1, ensure_ascii=False))
    ok = len(results) - summary["unknown"]
    print(f"checked {len(results)} products: {ok} classified, {summary['unknown']} failed -> {summary}")
    for r in results:
        if r["status"] == "unknown": print("  FAIL", r["store_id"], r["url"], r["error"])
    print(f"new status changes this run: {sum(1 for c in changes if c['at'] >= started)}")

if __name__ == "__main__":
    main()
