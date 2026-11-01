#!/usr/bin/env python3
"""Captions for a drop alert: X, plus one shared body used for Instagram, Threads and Bluesky.

Hashtag rules follow social/hashtags.md: X 1-2 tags, Instagram max 5, Threads 1 topic tag,
Bluesky 2-3 tags and 300 characters. Never #bulletjournal or #DotGrid; say "dot grid".
"""
import re
import unicodedata

X_LIMIT, X_URL_LEN, BSKY_LIMIT = 280, 23, 300
PRICE_RE = re.compile(r"(US\$|C\$|CA\$|S\$|A\$|\$|€|£|¥|₹)\s?\d|\b\d[\d,]*(\.\d{1,2})?\s?(USD|CAD|EUR|GBP|SGD|AUD|JPY)\b|\bprice", re.I)
BANNED_RE = re.compile(r"bullet\s*journal|#dotgrid\b|\bdotgrid\b", re.I)
BRAND_TAGS = {"leuchtturm": "#Leuchtturm1917", "archer": "#ArcherAndOlive", "scribbles": "#ScribblesThatMatter"}


class AlertTextError(ValueError):
    pass


def check_text(text, kind, where="text"):
    """Guards shared by the image and the captions."""
    low = text.lower()
    if kind == "new" and ("back in stock" in low or "restock" in low):
        raise AlertTextError(f"{where}: kind is 'new' but the text says back in stock/restock: {text!r}")
    if PRICE_RE.search(text):
        raise AlertTextError(f"{where}: prices are not allowed in alerts: {text!r}")
    if BANNED_RE.search(text):
        raise AlertTextError(f"{where}: banned wording (bullet journal / #DotGrid / dotgrid): {text!r}")


def x_len(text, urls):
    """X weighted length: each URL counts 23, CJK/emoji count 2."""
    for u in sorted(set(urls), key=len, reverse=True):
        text = text.replace(u, "x" * X_URL_LEN)
    n = 0
    for ch in unicodedata.normalize("NFC", text):
        o = ord(ch)
        n += 1 if (o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037) else 2
    return n


def grapheme_len(text):
    # Close enough for Bluesky's grapheme count with Latin text; combining marks don't add.
    return sum(1 for ch in unicodedata.normalize("NFC", text) if not unicodedata.combining(ch))


def topic_tags(product, variant, store):
    blob = f"{product} {variant or ''}".lower()
    brand = next((t for k, t in BRAND_TAGS.items() if k in blob or k in store.lower()), None)
    if "hobonichi" in blob:
        y = "#Hobonichi2027" if "2027" in blob else "#Hobonichi"
        return dict(x=[y], ig=["#Hobonichi", "#Hobonichi2027" if "2027" in blob else "#HobonichiTecho",
                              "#HobonichiTecho" if "2027" in blob else "#PlannerCommunity", "#Stationery", "#PlannerCommunity"],
                    threads="Hobonichi", bsky=["#hobonichi", "#stationery"])
    if any(k in blob for k in ("dot grid", "dotted", "journal", "notebook")) or brand:
        b = brand or "#Leuchtturm1917"
        return dict(x=["#DotGridJournal"] + ([brand] if brand else []), ig=["#DotGridJournal", "#Journaling", b, "#Stationery", "#PlannerCommunity"],
                    threads="Journaling", bsky=["#journaling", "#stationery"])
    if "planner" in blob:
        return dict(x=["#2027Planner" if "2027" in blob else "#PlannerCommunity"],
                    ig=["#Stationery", "#Journaling", "#PlannerCommunity", "#2027Planner" if "2027" in blob else "#PlannerAddict", "#WeeklyPlanner"],
                    threads="Planners", bsky=["#planner", "#stationery"])
    return dict(x=["#Stationery"], ig=["#Stationery", "#Journaling", "#PlannerCommunity", "#Hobonichi", "#DotGridJournal"],
                threads="Stationery", bsky=["#stationery", "#journaling"])


def _dedupe(tags):
    out = []
    for t in tags:
        if t.lower() not in (o.lower() for o in out):
            out.append(t)
    return out


def _short(s, n):
    return s if len(s) <= n else s[: n - 1].rstrip(" ,:;·-(") + "…"


def build(product, variant, store, page_url, local_dt, kind, from_label):
    """Return dict of captions. local_dt must be in America/Detroit."""
    head = "Back in stock" if kind == "restock" else "Now available"
    zone = local_dt.tzname()
    t = local_dt.strftime("%-I:%M %p")
    day_short = local_dt.strftime("%a %b %-d")
    day_long = local_dt.strftime("%A, %B %-d")
    item = f"{product}, {variant}" if variant else product
    item_in = f"the {product} in {variant}" if variant else f"the {product}"
    to_label = "in stock" if kind == "restock" else "orderable"
    tags = topic_tags(product, variant, store)
    tags["ig"] = _dedupe(tags["ig"])[:5]
    tags["x"] = _dedupe(tags["x"])[:2]

    # ---- X: shrink until it fits 280 (URL counts 23)
    went = f"It went from {from_label} to {to_label} {day_short} at {t} {zone}." if from_label else f"Spotted {day_short} at {t} {zone}."
    x_variants = []
    for tg in (tags["x"], tags["x"][:1]):
        for w in (went, f"Spotted {day_short}, {t} {zone}.", ""):
            for prod_n in (None, 90, 60, 40):
                it = item if prod_n is None else _short(item, prod_n)
                body = f"{head} at {store}: {it}" + ("" if it.endswith(("…", ".", "!")) else ".")
                if w:
                    body += f" {w}"
                x_variants.append(f"{body} Details: {page_url}\n\n{' '.join(tg)}")
    x = next((c for c in x_variants if x_len(c, [page_url]) <= X_LIMIT), None)
    if x is None:
        raise AlertTextError("could not fit the X caption in 280 characters")

    # ---- shared body (Instagram / Threads / Bluesky)
    verb = "is back in stock" if kind == "restock" else "is now available"
    lead = f"Drop alert: {item_in} {verb} at {store}."
    when = (f"We caught it going from {from_label} to {to_label} on {day_long}, at {t} {zone}." if from_label
            else f"We caught it on {day_long}, at {t} {zone}.")
    body = f"{lead}\n\n{when}"
    ig = f"{body}\n\nAll the details are on our page.\n\n{' '.join(tags['ig'])}\n\nLink in bio."
    threads = f"{body}\n\nDetails: {page_url}\n\n#{tags['threads'].replace(' ', '')}"
    bsky_opts = []
    for b in (body, lead, f"Drop alert: {_short(item, 120)} {verb} at {store}.", f"Drop alert: {_short(item, 70)} {verb} at {_short(store, 40)}."):
        for tg in (tags["bsky"], tags["bsky"][:1]):
            bsky_opts.append(f"{b}\n\n{page_url} {' '.join(tg)}")
    bsky = next((c for c in bsky_opts if grapheme_len(c) <= BSKY_LIMIT), None)
    if bsky is None:
        raise AlertTextError("could not fit the Bluesky caption in 300 characters")

    out = dict(x=x, x_weighted_len=x_len(x, [page_url]), shared_body=body, instagram=ig, threads=threads,
               threads_topic=tags["threads"], bluesky=bsky, bluesky_len=grapheme_len(bsky))
    for k in ("x", "instagram", "threads", "bluesky"):
        check_text(out[k], kind, where=f"{k} caption")
    assert out["instagram"].endswith("Link in bio.")
    assert out["x_weighted_len"] <= X_LIMIT and out["bluesky_len"] <= BSKY_LIMIT
    assert 1 <= len(tags["x"]) <= 2 and len(tags["ig"]) <= 5
    return out
