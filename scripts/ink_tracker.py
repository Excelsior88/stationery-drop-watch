#!/usr/bin/env python3
"""Limited-edition fountain pen ink tracker: stock checks, discovery and approval.

Only shop + brand pairs on the brand's own dealer list are in scope (inks.json "brands").
Every store_id must already be a shop in stores.json, so the site's shop count comes from data.

  python3 scripts/ink_tracker.py check      # every run: data/inks/stock.json, changes.json, retired.json
  python3 scripts/ink_tracker.py discover   # daily: data/inks/discovery.json, pending.json, new_finds.json
  python3 scripts/ink_tracker.py approve <find_id> --ink <ink_id> [--name "..."] [--color "..."]

check
  Same polite fetcher, robots rules and status words as checker.py. An unavailable product that the
  shop files under its own coming-soon collection is "coming_soon", not "sold_out". A failed check is
  "unknown" ("Couldn't check" on the site), never guessed. The first observation of a listing only sets
  first_seen: it never writes a change, so a new ink can't look like a restock. Ink changes go to
  data/inks/changes.json, which new_in_stock.py reads for the drop-alert webhook (changes to in_stock, tracker=inks).
  Pending finds are checked too, but their rows carry "hidden": true and no page shows them.
  An ink whose every listing has been sold out for RETIRE_DAYS days is retired: it stops being
  checked and the page lists it under "No longer tracked".

discover
  Reads each verified shop's public /products.json catalog. A product counts when its vendor is the
  brand, it is ink (or an ink advent calendar), and its title, type or tags say limited, exclusive,
  seasonal, anniversary, Inkvent, advent and so on. The first scan of a shop is a baseline: matches are
  only remembered, except ones that are coming soon or on preorder. After that, every new match becomes
  a pending find. Each find is checked from then on, stays hidden until the owner approves it, and is
  listed in data/inks/new_finds.json for that day's owner note (empty list = no note).
"""
import argparse, datetime as dt, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checker  # noqa: E402  (Host, classify_*, note_transition, now)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "inks.json"
DATA = ROOT / "data" / "inks"
RETIRE_DAYS = 60
MAX_PAGES = 120           # 250 products a page; the biggest verified catalog is about 16,000 products
SECTION = "inks"
ET = ZoneInfo("America/New_York")  # only for date labels; stored times stay ISO UTC

# Never tracked, whatever a catalog says (Designphil brands; Milligram is not an ink shop here).
BANNED_RX = re.compile(r"midori|traveler'?s|designphil", re.I)
BANNED_STORES = {"milligram"}
INK_RX = re.compile(r"\binks?\b|inkvent|ink-vent|advent calendar", re.I)
NOT_INK_RX = re.compile(r"fountain pens?\b(?!\s*ink)|ballpoint|rollerball", re.I)
NEVER_INK_RX = re.compile(r"cartridge|converter|\bnibs?\b|pen case|pen pouch|sample|swatch", re.I)
LIMITED_RX = re.compile(r"limited|exclusive|inkvent|ink-vent|advent|anniversary|special edition|seasonal|ink of the year|"
                        r"usa state|state series|tea ?time|holiday|christmas|festival|pen show", re.I)


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def stores_by_id():
    return {s["id"]: s for s in json.loads((ROOT / "stores.json").read_text())["stores"]}


def base_url(url):
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def handle_of(url):
    m = re.search(r"/products/([^/?#]+)", url)
    return m.group(1) if m else None


def validate(cfg, shops):
    """Every listing is a verified pair at a shop we already list. Raises on anything else."""
    errors = []
    for b, info in cfg["brands"].items():
        for sid in info["shops"]:
            if sid not in shops:
                errors.append(f"brand {b}: shop {sid} is not in stores.json")
            if sid in BANNED_STORES:
                errors.append(f"brand {b}: shop {sid} is banned")
    seen = set()
    for ink in cfg["inks"]:
        if BANNED_RX.search(ink["name"]):
            errors.append(f"{ink['id']}: banned brand")
        if ink["brand"] not in cfg["brands"]:
            errors.append(f"{ink['id']}: unknown brand {ink['brand']}")
            continue
        for l in ink["listings"]:
            if l["store_id"] not in cfg["brands"][ink["brand"]]["shops"]:
                errors.append(f"{ink['id']}: {l['store_id']} is not on the {ink['brand']} dealer list")
            if base_url(l["url"]) != base_url(shops[l["store_id"]]["url"].rstrip("/")):
                errors.append(f"{ink['id']}: {l['url']} is not on {l['store_id']}'s site")
            if l["url"] in seen:
                errors.append(f"duplicate listing {l['url']}")
            seen.add(l["url"])
    if errors:
        raise SystemExit("inks.json problems:\n  " + "\n  ".join(errors))


def tracked(cfg, pending, retired):
    """(public listings, hidden listings), each with ink metadata attached. Retired inks are skipped."""
    out = []
    for ink in cfg["inks"]:
        if ink["id"] in retired:
            continue
        for l in ink["listings"]:
            out.append(dict(l, ink_id=ink["id"], ink=ink["name"], brand=ink["brand"], hidden=False))
    for f in pending:
        if f.get("status") != "pending" or f["id"] in retired:
            continue
        out.append(dict(store_id=f["store_id"], url=f["url"], source_title=f.get("title"), ink_id=f["id"],
                        ink=f.get("title"), brand=f["brand"], hidden=True))
    return out


def collection_handles(h, base, names):
    """Handles in a shop's own collections (all pages). None when any page fails, so nothing is guessed."""
    found = set()
    for name in names:
        for page in range(1, 20):
            r = h.get(f"{base}/collections/{name}/products.json?limit=250&page={page}")
            if not r.ok:
                return None
            prods = r.json().get("products") or []
            if not prods:
                break
            found.update(p["handle"] for p in prods)
    return found


def apply_collections(status, handle, soon, pre):
    """Shop's own coming-soon / pre-order collections refine an unavailable or available read."""
    if status == "sold_out" and soon and handle in soon:
        return "coming_soon"
    if status == "in_stock" and pre and handle in pre:
        return "preorder"
    return status


def check_shop(sid, store, listings, cfg):
    base = store["url"].rstrip("/")
    h = checker.Host(base)
    out, cache = [], {}

    def colls(kind):
        if kind not in cache:
            names = cfg.get(kind, {}).get(sid) or []
            try:
                cache[kind] = collection_handles(h, base, names) if names else set()
            except Exception:
                cache[kind] = None
        return cache[kind]

    for l in listings:
        rec = dict(store_id=sid, store=store["name"], ink_id=l["ink_id"], ink=l["ink"], brand=l["brand"],
                   label=l.get("color") or l["ink"], type="Ink", url=l["url"], section=SECTION,
                   checked_at=None, status="unknown", method=None, title=l.get("source_title"), error=None,
                   **({"color": l["color"]} if l.get("color") else {}), **({"hidden": True} if l["hidden"] else {}))
        try:
            vid = l.get("variant_id")
            r = h.get(l["url"].split("?")[0] + ".js")
            rec["checked_at"] = checker.now()
            if r.ok and r.headers.get("content-type", "").startswith(("application/json", "text/javascript", "application/javascript")):
                js = r.json()
                res = checker.classify_shopify_variant(js, vid) if vid else checker.classify_shopify(js)
                if res is None:
                    rec["error"] = f"variant {vid} no longer on this product"
                else:
                    st, a, t, title = res
                    method = "shopify .js variant" if vid else "shopify .js"
                    kind = "coming_soon_collections" if st == "sold_out" else "preorder_collections" if st == "in_stock" else None
                    if kind and cfg.get(kind, {}).get(sid):
                        c = colls(kind)
                        if c is None:
                            st, rec["error"] = "unknown", f"couldn't read {sid}'s {kind.split('_')[0]} collection"
                        else:
                            new = apply_collections(st, handle_of(l["url"]), c if kind.startswith("coming") else None,
                                                    c if kind.startswith("preorder") else None)
                            if new != st:
                                method += " + shop's " + ("coming-soon" if new == "coming_soon" else "pre-order") + " collection"
                            st = new
                    rec.update(status=st, available_variants=a, total_variants=t, title=title, method=method)
            else:
                rec["error"] = f"HTTP {r.status_code} on .js"
        except Exception as e:
            rec["checked_at"] = checker.now()
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        out.append(rec)
    return out


def retire(rows, retired, now_iso, days=RETIRE_DAYS):
    """Retire inks whose every row is sold out and has been since at least `days` ago."""
    cutoff = dt.datetime.fromisoformat(now_iso) - dt.timedelta(days=days)
    by = {}
    for r in rows:
        by.setdefault(r["ink_id"], []).append(r)
    newly = []
    for ink_id, rs in by.items():
        if ink_id in retired or not rs:
            continue
        if all(r["status"] == "sold_out" and r.get("status_since")
               and dt.datetime.fromisoformat(r["status_since"]) <= cutoff for r in rs):
            retired[ink_id] = dict(retired_at=now_iso, name=rs[0]["ink"], brand=rs[0]["brand"],
                                   hidden=any(r.get("hidden") for r in rs),
                                   sold_out_since=min(r["status_since"] for r in rs),
                                   shops=sorted({r["store_id"] for r in rs}))
            newly.append(ink_id)
    return newly


def check(argv=None):
    cfg = load(CONFIG, None)
    shops = stores_by_id()
    validate(cfg, shops)
    pending = load(DATA / "pending.json", [])
    retired = load(DATA / "retired.json", {})
    skip = checker.link_only_ids()  # link-only shops are never requested
    listings = [l for l in tracked(cfg, pending, retired) if l["store_id"] not in skip]
    started = checker.now()
    by = {}
    for l in listings:
        by.setdefault(l["store_id"], []).append(l)
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = [r for rs in ex.map(lambda sid: check_shop(sid, shops[sid], by[sid], cfg), by) for r in rs]
    prev = {checker.canonical_stock_url(p["url"]) + "|" + str(p.get("color", "")): p
            for p in load(DATA / "stock.json", {"products": []})["products"]}
    changes = load(DATA / "changes.json", [])
    for r in results:
        before = len(changes)
        checker.note_transition(prev.get(checker.canonical_stock_url(r["url"]) + "|" + str(r.get("color", ""))), r, changes)
        for c in changes[before:]:
            c.update(ink_id=r["ink_id"], **({"hidden": True} if r.get("hidden") else {}))
    finished = checker.now()
    newly = retire(results, retired, finished)
    summary = {k: sum(1 for r in results if r["status"] == k) for k in ("in_stock", "preorder", "coming_soon", "sold_out", "unknown")}
    dump(DATA / "stock.json", dict(run_started=started, run_finished=finished, summary=summary, products=results))
    dump(DATA / "changes.json", changes)
    dump(DATA / "retired.json", retired)
    print(f"inks: checked {len(results)} listings -> {summary}; retired now: {newly or 'none'}")
    for r in results:
        if r["status"] == "unknown":
            print("  FAIL", r["store_id"], r["url"], r["error"])
    return 0


# ---- discovery -------------------------------------------------------------------------------

def is_candidate(p, vendor_rx):
    title = p.get("title") or ""
    tags = p.get("tags") or []
    tags = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",")]
    blob = " ".join([title, p.get("product_type") or "", " ".join(tags)])
    if BANNED_RX.search(" ".join([title, p.get("vendor") or ""])):
        return False
    if not re.search(vendor_rx, p.get("vendor") or "", re.I) and not re.search(vendor_rx, title, re.I):
        return False
    if not (INK_RX.search(title) or INK_RX.search(p.get("product_type") or "")):
        return False
    if NEVER_INK_RX.search(title):
        return False
    if NOT_INK_RX.search(title) and not re.search(r"\bink\b|inkvent|advent", title, re.I):
        return False
    return bool(LIMITED_RX.search(blob))


def upcoming_kind(p, soon_handles):
    """'coming_soon' or 'preorder' from the catalog row and the shop's own collection, else None."""
    variants = p.get("variants") or []
    avail = any(v.get("available") for v in variants)
    tags = p.get("tags") or []
    text = " ".join([p.get("title") or ""] + [v.get("title") or "" for v in variants] + list(tags if isinstance(tags, list) else [tags]))
    if avail:
        return "preorder" if checker.PREORDER_RX.search(text) else None
    if checker.UNRELEASED_RX.search(text) or (soon_handles and p.get("handle") in soon_handles):
        return "coming_soon"
    return None


def scan_shop(sid, store, brands, cfg):
    """Every catalog row for one shop, or an error. Rows aren't kept in memory past the scan."""
    base = store["url"].rstrip("/")
    h = checker.Host(base)
    found, err, n = [], None, 0
    try:
        soon = set()
        names = cfg.get("coming_soon_collections", {}).get(sid) or []
        if names:
            soon = collection_handles(h, base, names) or set()
        h.cache.clear()
        for page in range(1, MAX_PAGES + 1):
            r = h.get(f"{base}/products.json?limit=250&page={page}")
            h.cache.clear()  # catalog pages are big; nothing else re-reads them
            if not r.ok:
                err = f"HTTP {r.status_code} on page {page}"
                break
            prods = r.json().get("products") or []
            if not prods:
                break
            n += len(prods)
            for p in prods:
                for b in brands:
                    if is_candidate(p, cfg["brands"][b]["vendor_rx"]):
                        found.append(dict(brand=b, handle=p["handle"], title=p.get("title"),
                                          url=f"{base}/products/{p['handle']}",
                                          upcoming=upcoming_kind(p, soon),
                                          published_at=p.get("published_at")))
                        break
        else:
            err = f"stopped at {MAX_PAGES} pages"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:200]
    return sid, found, err, n


def discover(argv=None):
    cfg = load(CONFIG, None)
    shops = stores_by_id()
    validate(cfg, shops)
    state = load(DATA / "discovery.json", {"seen": {}, "shops": {}})
    pending = load(DATA / "pending.json", [])
    tracked_urls = {l["url"] for ink in cfg["inks"] for l in ink["listings"]} | {f["url"] for f in pending}
    shop_brands = {}
    skip = checker.link_only_ids()  # link-only shops are never scanned
    for b, info in cfg["brands"].items():
        for sid in info["shops"]:
            if sid in skip:
                continue
            shop_brands.setdefault(sid, []).append(b)
    run_at = checker.now()
    with ThreadPoolExecutor(max_workers=9) as ex:
        results = list(ex.map(lambda sid: scan_shop(sid, shops[sid], shop_brands[sid], cfg), shop_brands))
    finds = []
    for sid, found, err, n in results:
        if err:  # a failed or partial scan never adds or forgets anything for that shop
            state["shops"][sid] = dict(state["shops"].get(sid, {}), last_error=err, last_error_at=run_at)
            print(f"  {sid}: scan failed ({err}); nothing changed for this shop")
            continue
        baseline = sid not in state["seen"]
        seen = set(state["seen"].get(sid, []))
        for f in found:
            if f["handle"] in seen:
                continue
            seen.add(f["handle"])
            if f["url"] in tracked_urls:
                continue
            if baseline and not f["upcoming"]:
                continue  # first scan: remember it, don't report the whole back catalog
            find = dict(id=f"find-{sid}-{f['handle']}"[:120], status="pending", store_id=sid, brand=f["brand"],
                        url=f["url"], title=f["title"], found_at=run_at, upcoming=f["upcoming"],
                        published_at=f["published_at"], baseline=baseline)
            pending.append(find)
            tracked_urls.add(f["url"])
            finds.append(find)
        state["seen"][sid] = sorted(seen)
        state["shops"][sid] = dict(last_ok=run_at, products_scanned=n, candidates=len(found),
                                   **({"baseline_at": run_at} if baseline else
                                      {"baseline_at": state["shops"].get(sid, {}).get("baseline_at")}))
    state["last_run"] = run_at
    dump(DATA / "discovery.json", state)
    dump(DATA / "pending.json", pending)
    dump(DATA / "new_finds.json", dict(run_at=run_at, date=dt.datetime.fromisoformat(run_at).astimezone(ET).date().isoformat(),
                                       finds=finds, note=owner_note(finds, cfg, shops)))
    print(f"inks discover: {len(finds)} new finds; shops ok: {sum(1 for r in results if not r[2])}/{len(results)}")
    for f in finds:
        print("  NEW", f["store_id"], f["brand"], f["upcoming"] or "", f["title"], f["url"])
    return 0


def owner_note(finds, cfg, shops):
    """Plain text for the owner, only when there are finds. Empty string means send nothing."""
    if not finds:
        return ""
    lines = [f"Ink tracker: {len(finds)} new limited ink listing{'s' if len(finds) != 1 else ''} found. "
             "They're being checked but stay off the site until you approve them."]
    for f in finds:
        tag = {"coming_soon": " (coming soon)", "preorder": " (preorder)"}.get(f["upcoming"], "")
        lines.append(f"- {cfg['brands'][f['brand']]['name']} at {shops[f['store_id']]['name']}: {f['title']}{tag} {f['url']}")
    return "\n".join(lines)


def approve(argv):
    ap = argparse.ArgumentParser(prog="ink_tracker.py approve")
    ap.add_argument("find_id")
    ap.add_argument("--ink", required=True, help="existing ink id to add the listing to, or a new id")
    ap.add_argument("--name", help="display name, required for a new ink")
    ap.add_argument("--kind", default="Bottled ink")
    ap.add_argument("--color")
    a = ap.parse_args(argv)
    cfg = load(CONFIG, None)
    pending = load(DATA / "pending.json", [])
    f = next((x for x in pending if x["id"] == a.find_id and x["status"] == "pending"), None)
    if not f:
        raise SystemExit(f"no pending find {a.find_id}")
    ink = next((i for i in cfg["inks"] if i["id"] == a.ink), None)
    if ink is None:
        if not a.name:
            raise SystemExit("--name is required for a new ink")
        ink = dict(id=a.ink, brand=f["brand"], name=a.name, kind=a.kind,
                   added=dt.datetime.now(ET).date().isoformat(), listings=[])
        cfg["inks"].append(ink)
    elif ink["brand"] != f["brand"]:
        raise SystemExit(f"{a.ink} is a {ink['brand']} ink; this find is {f['brand']}")
    ink["listings"].append(dict(store_id=f["store_id"], url=f["url"], source_title=f["title"],
                                **({"color": a.color} if a.color else {})))
    f["status"] = "approved"
    f["approved_into"] = ink["id"]
    validate(cfg, stores_by_id())
    dump(CONFIG, cfg)
    dump(DATA / "pending.json", pending)
    print(f"approved {a.find_id} into {ink['id']}; it shows on the site after the next check")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "check"
    if cmd == "check":
        return check(argv[1:])
    if cmd == "discover":
        return discover(argv[1:])
    if cmd == "approve":
        return approve(argv[1:])
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
