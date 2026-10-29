#!/usr/bin/env python3
"""Build the static site in site/ from stores.json, data/*.json and content/*.json.
Never invents data: every status shown comes from data/stock.json written by checker.py."""
import json, html, re, datetime as dt, shutil
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ET = ZoneInfo("America/New_York")
E = html.escape

# Amazon Associates tracking ID. Every amazon.com product link on the site is rewritten to
# https://www.amazon.com/dp/<ASIN>?tag=<AMAZON_TAG> with rel="sponsored noopener" (see tag_amazon_links).
AMAZON_TAG = "excelsior88-20"
AMAZON_DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
# One affiliate statement, used in the footer and on About. Keep it true to how tag_amazon_links works.
AFFILIATE_NOTE = ("Amazon links on this site are affiliate links. " + AMAZON_DISCLOSURE +
                  " Links to the shops we track, and to my own books on Amazon, are plain links.")
_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
_AMAZON_A = re.compile(r'<a\b[^>]*\bhref="https?://(?:www\.)?amazon\.com/[^"]*"[^>]*>')

def own_amazon_link(url):
    """Plain amazon.com/dp/<ASIN> URL with no tag or ref params (for the owner's own products)."""
    m = _ASIN.search(url)
    return f"https://www.amazon.com/dp/{m.group(1)}" if m else url.split("?")[0]

def amazon_link(url):
    """Clean, tagged Amazon product URL; non-product Amazon URLs just get the tag added."""
    m = _ASIN.search(url)
    if m:
        return f"https://www.amazon.com/dp/{m.group(1)}?tag={AMAZON_TAG}"
    base = re.sub(r"([?&])tag=[^&]*&?", r"\1", url).rstrip("?&")
    return f"{base}{'&' if '?' in base else '?'}tag={AMAZON_TAG}"

def tag_amazon_links(doc):
    """Final pass over a rendered page: tag every amazon.com link and mark it sponsored."""
    def fix(m):
        a = m.group(0)
        if "data-own-product" in a:  # owner's own books: plain link, no Associates tag
            return a
        href = html.unescape(re.search(r'href="([^"]*)"', a).group(1))
        a = re.sub(r'href="[^"]*"', f'href="{E(amazon_link(href))}"', a)
        a = re.sub(r'\s(rel|data-todo)="[^"]*"', "", a)
        return a.replace("<a ", '<a rel="sponsored noopener" ', 1)
    return _AMAZON_A.sub(fix, doc)

stores = json.loads((ROOT / "stores.json").read_text())
stock = json.loads((ROOT / "data/stock.json").read_text())
changes = json.loads((ROOT / "data/changes.json").read_text())
picks = json.loads((ROOT / "content/editor_picks.json").read_text())
amz = json.loads((ROOT / "content/amazon_links.json").read_text())  # links only; never fetched by the checker

# Canonical products from other brands (e.g. Archer and Olive). They get no Amazon fallback link:
# the only Amazon brand link we have is Hobonichi's, and we don't link a brand to a product it isn't.
OTHER_BRAND = {c["id"] for c in stores["canonical"] if c.get("brand")}
HOBO_SHOPS = {s["id"] for s in stores["stores"] if not s.get("brand")}
# The site has two separate sections: Hobonichi (home tracker, calendar, Hobonichi product pages)
# and dot grid journaling (one page, every shop whose store entry has a "brand"). Never mixed.
DOTGRID_SHOPS = [s for s in stores["stores"] if s.get("brand")]

N_STORES = len({p["store_id"] for p in stock["products"]})  # stores the checker actually checks

def is_dotgrid(p):
    return p.get("canonical") in OTHER_BRAND or p["store_id"] not in HOBO_SHOPS

def hobo_products():
    return [p for p in stock["products"] if not is_dotgrid(p)]

def dotgrid_names():
    n = [s["name"] for s in DOTGRID_SHOPS]
    return ", ".join(n[:-1]) + " and " + n[-1] if len(n) > 1 else "".join(n)

def amazon_for(canonical, listing_url=""):
    """(tagged url, label) for a tracked listing: exact verified ASIN, else the Hobonichi brand link.
    ("", "") for other brands' products."""
    if canonical in OTHER_BRAND:  # exact verified listing only; no brand fallback for other brands
        m = amz.get("listings", {}).get(listing_url)
        return (amazon_link(f"https://www.amazon.com/dp/{m['asin']}"), "View on Amazon") if m else ("", "")
    m = amz["products"].get(canonical or "") or amz.get("listings", {}).get(listing_url)
    if m:
        return amazon_link(f"https://www.amazon.com/dp/{m['asin']}"), "View on Amazon"
    b = amz["brands"]["hobonichi"]
    return amazon_link(b["url"]), b["label"]

def brand_amazon(key):
    b = amz["brands"][key]
    return f'<a class="az" target="_blank" href="{E(b["url"])}">{E(b["label"])}</a>'

def fmt_et(iso):
    t = dt.datetime.fromisoformat(iso).astimezone(ET)
    return t.strftime("%b %-d, %Y, %-I:%M %p ") + t.tzname()

STATUS = {"in_stock": "In stock", "preorder": "Preorder", "coming_soon": "Not yet on sale",
          "sold_out": "Sold out", "unknown": "Couldn't check"}
DOTGRID_SLUG = "archer-and-olive-dot-grid-journal"
# Old slugs that now redirect (meta refresh + canonical) to their new page. Never listed in the sitemap.
REDIRECTS = {"archer-and-olive-bullet-journal": DOTGRID_SLUG}
NAV = [("index.html", "Hobonichi"), ("hobonichi-2027.html", "2027 calendar"), (DOTGRID_SLUG + "/", "Dot grid journals"), ("about.html", "About")]

# Public URL of the site (GitHub Pages custom domain, see site/CNAME). Used for canonical/OG URLs, JSON-LD and sitemap.xml.
BASE = "https://stationerydropwatch.com/"
CNAME = "stationerydropwatch.com"
OG_IMAGE = BASE + "assets/brand/og-image.png"  # 1200x630, made by scripts/brand/make_og.py (Hobonichi side)
OG_ALT = "Stationery Drop Watch: Hobonichi Techo 2027 restock tracker, books, Weeks and covers checked hourly across 13 shops"
OG_DOTGRID = BASE + "assets/brand/og-dotgrid.png"  # same script; used on the dot grid journaling page
OG_DOTGRID_ALT = "Stationery Drop Watch: dot grid journal restock tracker for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, checked hourly"
CONTENT_LASTMOD = "2026-10-27"  # last copy/structure change on the home and restock pages (sitemap lastmod floor)
X_HANDLE = "@stationerydrop"
LOCAL_LINK = re.compile(r'\b(href|src|srcset)="(?!https?:|mailto:|#|/|\.\./|data:)([^"]*)"')

def page(fname, title, desc, body, ld=(), og_type="website", og_image=OG_IMAGE, og_alt=OG_ALT, noindex=False):
    return tag_amazon_links(_page(fname, title, desc, body, ld, og_type, og_image, og_alt, noindex))

def pretty(path):
    """Public form of a local page path: 'index.html' -> '', 'about.html#x' -> 'about#x', 'slug/' unchanged.
    Files are still written as about.html etc.; GitHub Pages and Cloudflare Pages both serve /about from about.html,
    and Cloudflare 308-redirects /about.html -> /about, so canonicals, sitemap and links use the extensionless form."""
    if re.match(r"index\.html(?=[?#]|$)", path):
        return path[len("index.html"):]
    return re.sub(r"^([^?#]*?)\.html(?=[?#]|$)", r"\1", path)

def url_for(fname):
    """Absolute public URL: index.html -> BASE, 'slug/' -> BASE + 'slug/', 'about.html' -> BASE + 'about'."""
    return BASE + pretty(fname)

def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"

def _page(fname, title, desc, body, ld=(), og_type="website", og_image=OG_IMAGE, og_alt=OG_ALT, noindex=False):
    url = url_for(fname)
    hobo_page = fname.startswith(("hobonichi-techo-", "hobonichi-weeks-", "where-to-buy-hobonichi-"))  # Hobonichi product pages sit under the tracker
    nav = "".join(f'<a href="{h}"{" aria-current=page" if h == fname or (hobo_page and h == "index.html") else ""}>{E(t)}</a>' for h, t in NAV)
    ld_html = "".join(jsonld(x) for x in ld)
    doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
{'<meta name="robots" content="noindex">' if noindex else f'<link rel="canonical" href="{E(url)}">'}
<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="Stationery Drop Watch">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}"><meta property="og:locale" content="en_US">
<meta property="og:image" content="{og_image}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{E(og_alt)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="{X_HANDLE}">
<meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{og_image}"><meta name="twitter:image:alt" content="{E(og_alt)}">
<link rel="preload" href="assets/fonts/newsreader-var.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="assets/brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="assets/brand/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="assets/brand/apple-touch-icon.png" sizes="180x180">
<meta name="theme-color" content="#fbf6ec">
<meta name="google-site-verification" content="ehGQbmQs5JxWElUIdG8edUxqUYenrSKHsw-bf0v0YzU" />
<meta name="google-site-verification" content="TIX916oAoBcBQiw9fOlEYtdMJCR7GQYKtW67hfrmcA8" />
{ld_html}
</head><body>
<header class="masthead"><div class="wrap">
  <a class="brand" href="index.html" aria-label="Stationery Drop Watch home"><picture><source media="(max-width:340px)" srcset="assets/brand/icon.svg"><img class="brand-logo" src="assets/brand/logo.svg" alt="Stationery Drop Watch" width="248" height="44"></picture></a>
  <nav>{nav}</nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p><strong>Stationery Drop Watch</strong> checks independent and official stores for limited planner restocks so you don't have to refresh {N_STORES} tabs.</p>
  <p class="foot-links">Hobonichi: <a href="index.html">All listings</a> · {" · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS if not g.get("dotgrid"))} · <a href="hobonichi-2027.html">2027 calendar</a></p>
  <p class="foot-links">Guides: <a href="where-to-buy-hobonichi-2027/">Where to buy the Hobonichi Techo 2027</a> · <a href="hobonichi-techo-vs-cousin-vs-weeks/">Techo vs Cousin vs Weeks</a></p>
  <p class="foot-links">Dot grid journaling: <a href="{DOTGRID_SLUG}/">Dot grid journals</a> <span class="muted">({E(dotgrid_names())})</span></p>
  <p class="foot-links">Site: <a href="about.html">About</a> · <a href="about.html#sponsor">Featured shop slot</a> · <a href="mailto:stationerydropwatch@gmail.com">Contact</a></p>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it.</p>
  <p class="disclosure">{E(AFFILIATE_NOTE)}</p>
</div></footer>
<script src="assets/app.js" defer></script>
</body></html>"""
    # The site is served at the domain root, so make every local link root-relative ("assets/x" -> "/assets/x").
    # "index.html" becomes "/" and "about.html" becomes "/about" so internal links match the canonical URLs.
    doc = LOCAL_LINK.sub(lambda m: f'{m.group(1)}="/{pretty(m.group(2))}"', doc)
    return doc

NEWSLETTER = "dropwatch"  # Buttondown username (https://buttondown.com/dropwatch)

# Tracker pages share one sidebar, in this order: signup, Featured shop, gift pick, then page links.
# On one-column screens (<=900px, see style.css) the same elements are re-ordered with CSS, no duplicates:
# signup right after the hero stats (.m-top), then the first main section (.m-lead), then the Featured shop.
def signup_block(compact=False):
    # Buttondown's standard HTML embed form (docs.buttondown.com/building-your-subscriber-base):
    # a plain POST to embed-subscribe; don't submit via fetch, Buttondown may need to show a CAPTCHA.
    return f"""<section class="card signup{' compact m-top' if compact else ''}" id="alerts">
  <h2>Get restock alerts</h2>
  <p>One short email when a sold-out item comes back somewhere we track. No spam, unsubscribe anytime.</p>
  <form class="signup-form embeddable-buttondown-form" action="https://buttondown.com/api/emails/embed-subscribe/{NEWSLETTER}" method="post">
    <label class="sr" for="email{int(compact)}">Email address</label>
    <input id="email{int(compact)}" type="email" name="email" placeholder="you@example.com" required autocomplete="email">
    <input type="hidden" value="1" name="embed">
    <button type="submit">Notify me</button>
  </form>
  <p class="form-note">Sent via <a href="https://buttondown.com/{NEWSLETTER}" target="_blank" rel="noopener">Buttondown</a>.</p>
</section>"""

def sponsor_block():
    # TODO(sponsor): when a shop books this slot, replace the placeholder with their logo, line, and link (rel="sponsored").
    return """<aside class="card sponsor" aria-label="Featured shop">
  <p class="eyebrow">Featured shop</p>
  <div class="sponsor-slot">
    <p class="sponsor-title">This spot is available</p>
    <p>Run an independent stationery shop? Put your next restock in front of planner people who are actively hunting for it.</p>
    <p>Shops: want a featured restock slot? Email <a href="mailto:stationerydropwatch@gmail.com?subject=Featured%20restock%20slot">stationerydropwatch@gmail.com</a>.</p>
    <a class="btn-ghost" href="about.html#sponsor">Sponsor details</a>
  </div>
</aside>"""

def editor_block(page="home"):
    """Owner's own books for one page: "home" (Hobonichi side, the default) or "dotgrid"."""
    items = []
    for b in picks["books"]:
        if b.get("hidden") or page not in b.get("pages", ["home"]):
            continue
        if b.get("coming_soon"):
            items.append(f"""<article class="book coming-soon" data-book-id="{E(b['id'])}">
  <div class="book-cover placeholder" aria-hidden="true"><span>Coming soon</span></div>
  <div class="book-body">
    <p class="eyebrow">{E(b.get('kicker',''))}</p>
    <h3>{E(b['pitch'])}</h3>
    <p>{E(b['blurb'])}</p>
    <a class="btn" href="#alerts">{E(b.get('cta','Get notified'))}</a>
  </div>
</article>""")
            continue
        details = "".join(f"<li>{E(d)}</li>" for d in b.get("details", []))
        inside = ("<p class=\"book-inside-h\">What's inside</p><ul class=\"book-inside\">"
                  + "".join(f"<li>{E(x)}</li>" for x in b["inside"]) + "</ul>") if b.get("inside") else ""
        if b.get("cover"):
            cover = f'<img src="{E(b["cover"])}" alt="{E(b.get("cover_alt") or b["title"] + " cover")}" width="200" height="300" loading="lazy">'
            cover_cls = "book-cover"
        else:  # no verified cover image: a plain title tile, never an invented cover
            cover = f'<span>{E(b.get("cover_text", b["title"]))}</span>'
            cover_cls = "book-cover placeholder"
        items.append(f"""<article class="book" data-book-id="{E(b['id'])}">
  <a class="{cover_cls}" href="{E(own_amazon_link(b['url']))}" data-own-product rel="noopener" target="_blank">
    {cover}</a>
  <div class="book-body">
    <p class="eyebrow">{E(b.get('kicker',''))}</p>
    <h3>{E(b['pitch'])}</h3>
    <p class="book-title">{E(b['title'])} <span class="muted">· {E(b.get('format',''))}</span></p>
    {f"<p>{E(b['blurb'])}</p>" if b.get('blurb') else ""}
    <ul class="book-details">{details}</ul>{inside}
    <a class="btn" href="{E(own_amazon_link(b['url']))}" data-own-product rel="noopener" target="_blank">View on Amazon</a>
  </div>
</article>""")
    if not items:
        return ""
    return f"""<section class="card editor" aria-label="{E(picks['heading'])}">
  <p class="eyebrow">{E(picks['heading'])}</p>
  <div class="books">{''.join(items)}</div>
  <p class="muted small">Made by the person who runs this site.</p>
</section>"""

BUYABLE = ("in_stock", "preorder")
NOT_BUYABLE = ("sold_out", "coming_soon")  # coming_soon = preview page, no preorder

def product_key(p):
    """Group listings of the same product across stores: canonical id, else a normalized title."""
    if p.get("canonical"):
        return p["canonical"]
    t = re.sub(r"\[[^\]]*\]", " ", p["label"].lower())
    t = re.sub(r"\b(hobonichi|techo|2027|planner)\b", " ", t)
    return "t:" + " ".join(re.findall(r"[a-z0-9&]+", t))

def amazon_main(prods):
    """Products that no tracked shop can sell right now (every listing sold out / not yet on sale).
    Recomputed from data/stock.json on every build. A product with any listing we couldn't
    check ('unknown') is left out, since we can't honestly say it's unavailable everywhere."""
    groups = {}
    for p in prods:
        # Other brands are tracked size by size, so each listing is its own product here.
        groups.setdefault(p["url"] if p.get("canonical") in OTHER_BRAND else product_key(p), []).append(p)
    out = {}
    for k, ls in groups.items():
        other = ls[0].get("canonical") in OTHER_BRAND
        sts = {l["status"] for l in ls}
        if not sts <= set(NOT_BUYABLE):
            continue
        if other:  # match the exact size/paper listing only
            hit = amz.get("listings", {}).get(ls[0]["url"])
        else:
            hit = next((amz["products"].get(l.get("canonical") or "") or amz.get("listings", {}).get(l["url"]) for l in ls
                        if amz["products"].get(l.get("canonical") or "") or amz.get("listings", {}).get(l["url"])), None)
        if other and not hit:  # no verified Amazon listing of this exact item: offer nothing rather than a stand-in
            continue
        if hit:
            url, label, exact = amazon_link(f"https://www.amazon.com/dp/{hit['asin']}"), "View on Amazon", True
        else:
            url, label, exact = amazon_link(amz["brands"]["hobonichi"]["url"]), amz["brands"]["hobonichi"]["label"], False
        n = len({l["store_id"] for l in ls})
        if sts == {"sold_out"}:
            note = "Sold out at every shop we track" if n > 1 else "Sold out at the only shop we track"
        elif sts == {"coming_soon"}:
            note = "Not on sale yet at any shop we track" if n > 1 else "Not on sale yet at the only shop we track"
        else:
            note = "Sold out or not yet on sale at every shop we track"
        out[k] = dict(url=url, label=label, exact=exact, note=f"{note} ({n} shops)" if n > 1 else note, listings=ls)
    return out

def tracker_block(prods, rows, search_hint, other_opt="", extra=""):
    """Filterable table of every listing in `prods` (driven by assets/app.js)."""
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    sids = {p["store_id"] for p in prods}
    store_opts = "".join(f'<option value="{E(x["id"])}">{E(x["name"])}</option>' for x in stores["stores"] if x["id"] in sids)
    prod_opts = "".join(f'<option value="{E(k)}">{E(v)}</option>' for k, v in canon.items() if any(p.get("canonical") == k for p in prods))
    type_opts = "".join(f'<option value="{E(t)}">{E(t)}</option>' for t in sorted({p["type"] for p in prods}))
    status_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items() if any(p["status"] == k for p in prods))
    noscript_rows = "".join(f'<tr><td>{E(r["p"])}</td><td>{E(r["s"])}</td><td><span class="badge {r["st"]}">{STATUS[r["st"]]}</span></td></tr>' for r in rows)
    return f"""<section class="card" id="tracker">
      <div class="section-head"><h2>Every listing we track</h2><p class="muted small" id="count"></p></div>
      <form class="filters" onsubmit="return false">
        <label>Product<select id="f-product"><option value="">All products</option>{prod_opts}{other_opt}</select></label>
        <label>Type<select id="f-type"><option value="">All types</option>{type_opts}</select></label>
        <label>Store<select id="f-store"><option value="">All stores</option>{store_opts}</select></label>
        <label>Status<select id="f-status"><option value="">Any status</option>{status_opts}</select></label>
        <label class="grow">Search<input id="f-q" type="search" placeholder="{E(search_hint)}"></label>
      </form>
      <div class="table-wrap"><table class="stock">
        <thead><tr><th>Product</th><th>Store</th><th>Status</th><th class="hide-sm">Checked</th></tr></thead>
        <tbody id="rows"><noscript>{noscript_rows}</noscript></tbody>
      </table></div>
      <button type="button" id="more" class="btn-ghost more" hidden>Show all</button>
      <p class="muted small">"Not yet on sale" means the store has a preview page up but isn't taking orders yet.</p>
      {extra}
    </section>"""

def tracker_rows(prods, out_everywhere):
    rows = [dict(g=product_key(p), p=p["label"], c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], st=p["status"],
                 u=p["url"], at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 va=p.get("available_variants"), tv=p.get("total_variants"),
                 az=amazon_for(p.get("canonical"), p["url"])[0], azl=amazon_for(p.get("canonical"), p["url"])[1]) for p in prods]
    for r in rows:  # product unavailable at every tracked shop: Amazon becomes the main action
        m = out_everywhere.get(r["u"] if r["c"] in OTHER_BRAND else r["g"])
        if m:
            r.update(az=m["url"], azl=m["label"], azm=1)
    return rows

def tracking_start(ls):
    """When we started tracking these listings: the earliest first_seen in the data (never the current run)."""
    return min((l["first_seen"] for l in ls if l.get("first_seen")), default=stock["run_started"])

def count_line(ls, unit="listings"):
    """'X of N in stock or on preorder', counting only listings we actually checked this run.
    Failed checks are reported as their own number; we never fold them into "not in stock"."""
    n = len(ls)
    u = sum(l["status"] == "unknown" for l in ls)
    b = sum(l["status"] in BUYABLE for l in ls)
    if not u:
        return f"{b} of {n} {unit} in stock or on preorder"
    if u == n:
        return f"couldn't check {'this listing' if n == 1 else f'these {n} {unit}'} this run"
    return f"{b} of {n - u} checked {unit} in stock or on preorder · {u} couldn't be checked this run"

def stock_data(rows):
    return f'<script id="stock-data" type="application/json">{json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")}</script>'

def build_index():
    prods = hobo_products()  # Hobonichi section only; dot grid shops live on their own page
    s = {k: sum(p["status"] == k for p in prods) for k in STATUS}
    checked = sum(v for k, v in s.items() if k != "unknown")
    urls = {p["url"] for p in prods}
    restocks = [c for c in changes if c["url"] in urls and c["to"] in ("in_stock", "preorder") and c["from"] in ("sold_out", "coming_soon")]
    restocks.sort(key=lambda c: c["at"], reverse=True)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)
    recent = [c for c in restocks if dt.datetime.fromisoformat(c["at"]) >= cutoff][:12]
    if recent:
        feed = "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in recent)
        feed_html = f'<ol class="feed">{feed}</ol>'
    else:
        start = tracking_start(prods)
        lead = "No restocks spotted yet." if not restocks else "No restocks in the last 14 days."
        feed_html = f"""<div class="empty"><p><strong>{lead}</strong> Tracking started <time datetime="{E(start)}">{E(fmt_et(start))}</time>.
  A restock shows up here the moment a sold-out item flips back to in stock or preorder between two checks.</p>
  <p class="muted">Right now: {s['sold_out']} tracked listings are sold out and {s['coming_soon']} aren't on sale yet. Those are the ones we're watching.{f" {s['unknown']} couldn't be checked this run." if s['unknown'] else ""}</p></div>"""

    # table data (embedded so the page works without fetch)
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    out_everywhere = amazon_main(prods)
    rows = tracker_rows(prods, out_everywhere)
    def oe_card(m):
        l0 = m["listings"][0]
        name = canon.get(l0.get("canonical") or "", l0["label"])
        shops = "".join(f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["store"])}</a> <span class="badge {E(l["status"])}">{E(STATUS[l["status"]])}</span></li>' for l in m["listings"])
        return f"""<li class="oe-item"><div class="oe-text"><h3>{E(name)}</h3><p class="oe-note">{E(m['note'])}</p>
  <details class="muted small"><summary>Shops we checked</summary><ul class="oe-shops">{shops}</ul></details></div>
  <a class="btn btn-amz" href="{E(m['url'])}" target="_blank">{E(m['label'])}</a></li>"""
    oe_html = (f"""<section class="card" id="sold-out-everywhere">
      <div class="section-head"><h2>Sold out at every shop we track</h2></div>
      <p class="muted small">None of the shops we check can sell these right now. Amazon may still have them, so we link there. A product leaves this list as soon as any shop we track has it in stock or on preorder.</p>
      <ul class="oe-list">{"".join(oe_card(m) for m in sorted(out_everywhere.values(), key=lambda m: not m["exact"]))}</ul>
    </section>""" if out_everywhere else "")
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a>: <span class="muted">{E(n["reason"] or "")}</span></li>' for n in stock["not_checked"])

    faq_html, faq_ld = faq_block()
    tracker_html = tracker_block(prods, rows, "Moomin, Cousin, Midnight Blue…", '<option value="__other">Other 2027 items</option>',
        f'<details class="muted small"><summary>Stores we list but don\'t check automatically</summary><ul>{not_checked}</ul></details>')
    body = f"""
<section class="hero">
  <p class="eyebrow">Hobonichi Techo 2027 · {len({p['store_id'] for p in prods})} shops checked</p>
  <h1>Know the moment your planner is back.</h1>
  <p class="lede">We check the official Hobonichi store and independent shops for sold-out Hobonichi planners and covers, and tell you when they come back.</p>
  <p class="small section-switch">Also tracked: <a href="{DOTGRID_SLUG}/">Dot grid journals</a> <span class="muted">· {E(dotgrid_names())}</span></p>
  <div class="stats{' five' if s['unknown'] else ''}">
    <div><b>{s['in_stock']}</b><span>in stock</span></div>
    <div><b>{s['preorder']}</b><span>preorder</span></div>
    <div><b>{s['sold_out']}</b><span>sold out</span></div>
    <div><b>{s['coming_soon']}</b><span>not yet on sale</span></div>
    {f'<div class="unk"><b>{s["unknown"]}</b><span>couldn' + "'" + 't check this run</span></div>' if s['unknown'] else ''}
  </div>
  <p class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time> · {checked} of {len(prods)} listings checked successfully.</p>
</section>

<div class="layout">
  <div class="main-col">
    <div class="m-lead">
    <section class="card" id="restocked">
      <h2>Recent restocks</h2>
      {feed_html}
    </section>
    </div>

    {oe_html}

    {product_links_block()}

    {tracker_html}

    {faq_html}
  </div>
  <aside class="side-col">
    {signup_block(compact=True)}
    {sponsor_block()}
    {editor_block()}
    <section class="card soon">
      <p class="eyebrow">Coming to the tracker</p>
      <ul><li>Traveler's Company limited editions <span class="muted small">· {brand_amazon("travelers")}</span></li><li>MIDORI MD seasonal releases <span class="muted small">· {brand_amazon("midori")}</span></li></ul>
    </section>
  </aside>
</div>
{stock_data(rows)}
"""
    n_shops = len({p['store_id'] for p in prods if p['store_id'] in HOBO_SHOPS})
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Stationery Drop Watch", "url": BASE,
               "description": f"Hourly restock checks for Hobonichi Techo 2027 planners and covers across the official store and independent shops, and, in a separate section, dot grid journals from {dotgrid_names()}.",
               "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE,
                             "description": "Independent restock tracker for Hobonichi Techo 2027 planners and covers, and dot grid journals. Statuses come straight from each shop's public product data.",
                             "logo": BASE + "assets/brand/icon-512.png", "email": "stationerydropwatch@gmail.com",
                             "sameAs": ["https://x.com/stationerydrop"]}}
    return page("index.html", "Hobonichi Techo 2027 & dot grid journal restock tracker · Stationery Drop Watch",
                f"Is your Hobonichi Techo 2027 back in stock? Live status for Original A6, Cousin A5, Weeks and covers at {n_shops} shops, checked hourly. Plus a separate dot grid journal restock tracker.",
                body, ld=(site_ld, faq_ld))

def build_hobonichi():
    body = """
<article class="prose">
<p class="eyebrow">Guide · updated Oct 25, 2026</p>
<h1>Hobonichi Techo 2027 launch &amp; restock calendar</h1>
<p class="lede">Hobonichi sells its planners in two big drops a year, and popular covers can sell out within minutes. Here's how the 2027 season has gone so far and when stock usually comes back.</p>

<ol class="timeline">
  <li><time>Aug 25, 2026</time><div><h3>Previews go up</h3><p>Shops post the 2027 lineup as "out of stock" or "coming soon" pages. They aren't sold out; they're just not on sale yet. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Aug 31, 2026 · 10 PM ET</time><div><h3>Worldwide launch (January-start planners)</h3><p>Everything goes live at the same moment worldwide: 11 AM on September 1 in Japan, 10 PM ET / 9 PM CT the night before in the US. Atlas Stationers warned that popular styles and collaborations "often sell out within minutes." <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-atlas">[Atlas]</a></p></div></li>
  <li><time>Sep 30 – Oct 1, 2026</time><div><h3>Second fall wave</h3><p>Hobonichi notes that some products begin sales on October 1. At US shops that meant the ONE PIECE magazine collection and the Weeksdays 2027 desk calendar, plus a large restock of earlier sell-outs (as preorders at some shops). <a href="#s-1101">[Hobonichi]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Early–mid Oct 2026</time><div><h3>First restocks land at indie shops</h3><p>Atlas expected its first restock in early October. Paper Mouse's shipment arrived October 15 and preorders began shipping. <a href="#s-atlas">[Atlas]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Through December</time><div><h3>Last call for dated 2027 books</h3><p>Paper Mouse says it doesn't usually restock dated planners after December, so whatever is left is all that's left. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>February 2027</time><div><h3>Spring launch (April-start planners)</h3><p>The second yearly release, timed to Japan's April academic and fiscal year. Expect another rush on new covers. <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-1101">[Hobonichi]</a></p></div></li>
</ol>

<h2>Will it come back?</h2>
<p>Usually, but not always. Standard planner books and core colors tend to be restocked. Special collaborations may only be sold at launch <a href="#s-atlas">[Atlas]</a>. Paper Mouse says almost every item has been restocked at least once after launch in past years <a href="#s-papermouse">[Paper Mouse]</a>. Hobonichi's own restock emails are only for the Techo books and the Drawer Pouch, not accessories, and they don't promise you'll get one <a href="#s-1101">[Hobonichi]</a>.</p>

<h2>How to not miss it</h2>
<ul>
  <li>Check several shops. When one store sells out, another often still has stock. That's the whole point of the <a href="index.html#tracker">tracker</a>.</li>
  <li>Live stock by product: """ + " · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS) + """.</li>
  <li>Buying direct from Hobonichi is the only way to get store-exclusive extras, but it ships from Japan and tariffs may apply in the US <a href="#s-papermouse">[Paper Mouse]</a>.</li>
  <li>Which shops have it right now: <a href="where-to-buy-hobonichi-2027/">where to buy the Hobonichi Techo 2027</a>. Choosing a size: <a href="hobonichi-techo-vs-cousin-vs-weeks/">Techo vs Cousin vs Weeks</a>.</li>
  <li><a href="#alerts">Sign up for alerts</a> and we'll email you when something flips back to in stock.</li>
</ul>
""" + signup_block() + """
<h2>Sources</h2>
<ol class="sources">
  <li id="s-1101"><a href="https://www.1101.com/store/techo/en/2027/pc/shopping_guide/" rel="noopener" target="_blank">Hobonichi Techo 2027 shopping guide</a>, Hobonichi (official). Release dates, shipping, and restock notification rules.</li>
  <li id="s-papermouse"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Launch times, the Sept 30 preorder, the Oct 15 arrival, and restock history.</li>
  <li id="s-atlas"><a href="https://www.atlasstationers.com/blogs/news/hobonichi-faq-2027" rel="noopener" target="_blank">Hobonichi FAQ – 2027</a>, Atlas Stationers. Launch time, sell-out warning, and the early-October restock.</li>
</ol>
</article>"""
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "2027 calendar", "item": url_for("hobonichi-2027.html")}]}
    return page("hobonichi-2027.html", "Hobonichi Techo 2027 launch & restock calendar · Stationery Drop Watch",
                "When Hobonichi Techo 2027 planners launch, sell out and restock: launch times, the October wave, and when restocks usually land, with sources.", body, ld=(crumbs,))

def build_about():
    n_checked = len([s for s in stores["stores"] if s["platform"] in ("shopify", "hobonichi")])
    body = f"""
<article class="prose">
<h1>About Stationery Drop Watch</h1>
<p class="lede">Limited planners sell out fast, and every shop only posts its own restocks. This site checks them all in one place.</p>
<h2>How it works</h2>
<p>A small script visits the public product pages of {n_checked} stores on a schedule, at a polite pace and following each store's robots.txt. It reads whether each listing can be bought right now. The site has two sections: <a href="index.html">Hobonichi</a> (the official store and independent shops) and <a href="{DOTGRID_SLUG}/">dot grid journaling</a> ({E(dotgrid_names())}, each checked on its own store). When a sold-out listing becomes available again, it shows up in <a href="index.html#restocked">Recent restocks</a> and goes out to the alert list.</p>
<p>We only show what the stores report. If a check fails, we say so instead of guessing.</p>
<h2 id="sponsor">Featured shop slot</h2>
<p>Independent stationery shops can book the featured spot on the tracker to promote a restock or launch. It's clearly labeled as sponsored. Shops: want a featured restock slot? Email <a href="mailto:stationerydropwatch@gmail.com?subject=Featured%20restock%20slot">stationerydropwatch@gmail.com</a> for rates and dates.</p>
<h2>Affiliate links</h2>
<p>{E(AFFILIATE_NOTE)} Buying through an Amazon link costs you nothing extra, and it never changes what the tracker shows.</p>
<h2>Contact</h2>
<p>Questions, corrections, or a shop we should track? Email <a href="mailto:stationerydropwatch@gmail.com">stationerydropwatch@gmail.com</a>.</p>
</article>"""
    return page("about.html", "About Stationery Drop Watch: how we check stock", "How Stationery Drop Watch checks shops hourly for Hobonichi Techo 2027 and dot grid journal restocks, and why it never guesses stock.", body)

# --- Product restock pages (one indexable page per tracked product group) ---------------------
# Every status on these pages comes from data/stock.json exactly as the checker wrote it.
def _is_a6_book(p):
    return p["type"] == "Book" and (p.get("canonical") in ("original-a6-en", "original-a6-jp")
                                     or (not p.get("canonical") and "a6" in p["label"].lower()))

GROUPS = [
    dict(slug="hobonichi-techo-2027-original-a6", short="Original A6", product="Hobonichi Techo 2027 Original (A6)",
         match=_is_a6_book,
         desc="Is the Hobonichi Techo 2027 Original A6 book in stock? Live status for the English and Japanese A6 books at {shops} shops, checked hourly.",
         intro="The Original is Hobonichi's A6 one-page-a-day book, sold in an English and a Japanese edition. "
               "Below is what each shop we track reported at its last check: in stock, on preorder, sold out, or not on sale yet. "
               "If a check failed we say \"Couldn't check\" rather than guess."),
    dict(slug="hobonichi-techo-2027-cousin-a5", short="Cousin A5", product="Hobonichi Techo 2027 Cousin (A5)",
         match=lambda p: p.get("canonical") == "cousin-a5-en",
         desc="Is the Hobonichi Techo 2027 Cousin A5 book in stock? Live status for the English Cousin at {shops} shops, checked hourly, with every restock we spot.",
         intro="The Cousin is the A5 version of the Techo, with a page a day and more room to write. "
               "Here's what each shop we track reported for the English Cousin at its last check."),
    dict(slug="hobonichi-weeks-2027", short="Weeks", product="Hobonichi Weeks 2027",
         match=lambda p: p["type"] == "Weeks",
         desc="Is Hobonichi Weeks 2027 in stock? Live status for Midnight Blue, Canaria Yellow, Moomin, White Cat Wallpaper and more at {shops} shops, checked hourly.",
         intro="Weeks is Hobonichi's slim, wallet-size weekly planner, and the popular covers sell out fast. "
               "These are the 2027 Weeks listings we track, grouped by design, with the status each shop reported at its last check."),
    dict(slug="hobonichi-weeks-mega-2027", short="Weeks Mega", product="Hobonichi Weeks Mega 2027",
         match=lambda p: p["type"] == "Weeks Mega",
         desc="Is Hobonichi Weeks Mega 2027 in stock? Live status for Midnight Blue, Bow & Tie: Candy Dream and more at {shops} shops, checked hourly.",
         intro="Weeks Mega is the Weeks planner with extra blank pages at the back. "
               "Here's what each shop we track reported for the 2027 Weeks Mega listings at its last check."),
    dict(slug="hobonichi-techo-2027-covers", short="A6 covers", product="Hobonichi Techo 2027 A6 cover",
         match=lambda p: p["type"] == "Cover",
         desc="Are Hobonichi Techo 2027 A6 covers like Moomin: My Yard and Yumi Kitagishi: White Cat House in stock? Live status at {shops} shops, checked hourly.",
         intro="Popular Hobonichi covers can sell out within minutes of a drop. "
               "We track a handful of 2027 A6 covers; here's what each shop reported at its last check."),
    dict(slug=DOTGRID_SLUG, short="Dot grid journals", product="Dot grid journal", dotgrid=True,
         match=is_dotgrid,
         eyebrow="Dot grid journaling", unit="listings",
         open_hint="Open a row to go straight to that exact size and color on the shop's site",
         guide="Dot grid journals come in several sizes, papers and colors, and each one sells out on its own. "
               "We check the exact variant named in each row, so \"In stock\" means that size and color, not just some version of the journal.",
         desc="Are Archer and Olive, Leuchtturm1917, Scribbles That Matter and Tsuki dot grid journals in stock? Live size-by-size status, checked hourly.",
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Popular dot grid journals and limited editions sell out, and every brand only posts its own restocks. "
               "We track a focused set of flagship dot grid notebooks straight from each maker's own store, size by size and color by color. "
               "Archer and Olive is featured first. This covers dot grid journals only; we don't track pens or other paper here, and Hobonichi has its own section."),
]
for _g in GROUPS:  # one name per page: H1 is "<product> restock tracker"; the <title> adds the live shop count
    _g["h1"] = _g["product"] + " restock tracker"
for _g in GROUPS:  # Hobonichi pages never pick up dot grid listings
    if not _g.get("dotgrid"):
        _g["match"] = (lambda m: lambda p: not is_dotgrid(p) and m(p))(_g["match"])

def latest(*isos):
    return max(i for i in isos if i)

def group_listings(g):
    return [p for p in stock["products"] if g["match"](p)]

def row_amz(l, oe):
    """Per-size Amazon button for other brands' listings (their oe entries are keyed by listing URL)."""
    m = oe.get(l["url"]) if l.get("canonical") in OTHER_BRAND else None
    return f'<a class="btn btn-amz btn-sm" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a>' if m else ""

def status_rows(ls, oe):
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    rows = []
    for l in sorted(ls, key=lambda l: (order.get(l["status"], 9), l["store"])):
        since = l.get("status_since")
        since_html = f'<span class="sub">since {E(fmt_et(since).rsplit(",", 1)[0])}</span>' if since and l["status"] != "unknown" else ""
        rows.append(f"""<tr><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a><span class="sub">{E(l.get('title') or l['label'])}</span></td>
  <td><span class="badge {E(l['status'])}">{E(STATUS[l['status']])}</span>{since_html}{row_amz(l, oe)}</td>
  <td class="hide-sm">{"Tried " if l["status"] == "unknown" else ""}<time datetime="{E(l['checked_at'])}">{E(fmt_et(l['checked_at']))}</time></td></tr>""")
    return "".join(rows)

def build_group(g, oe):
    ls = group_listings(g)
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    shops = len({l["store_id"] for l in ls})
    buy = [l for l in ls if l["status"] in BUYABLE]
    sections = {}
    for l in ls:
        sections.setdefault(l.get("canonical") or "", []).append(l)
    order = [c["id"] for c in stores["canonical"] if c["id"] in sections] + ([""] if "" in sections else [])
    if g.get("dotgrid"):  # one block per shop, in stores.json order (Archer and Olive first)
        rank = {s["id"]: i for i, s in enumerate(stores["stores"])}
        order.sort(key=lambda cid: min(rank[l["store_id"]] for l in sections[cid]))
    parts = []
    seen_shop = set()
    for cid in order:
        sl = sections[cid]
        name = canon.get(cid) or ("Other designs and editions" if len(order) > 1 else "Listings")
        m = oe.get(cid) if cid else None
        amz_btn = (f'<p><a class="btn btn-amz" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a> '
                   f'<span class="muted small">{E(m["note"])}.</span></p>') if m else ""
        az_url, az_label = amazon_for(cid, sl[0]["url"])
        az_sub = "" if m or not az_url or cid in OTHER_BRAND else f' · <a class="az" href="{E(az_url)}" target="_blank">{E(az_label)}</a>'
        tracker = (f' · <a href="?product={E(cid)}#tracker">Filter below</a>' if g.get("dotgrid") else
                   f' · <a href="index.html?product={E(cid)}#tracker">Filter in the tracker</a>') if cid else ""
        sid = sl[0]["store_id"]
        hx = "h3" if g.get("dotgrid") else "h2"  # dot grid page: shop is the h2, its products are h3
        if g.get("dotgrid") and sid not in seen_shop:
            seen_shop.add(sid)
            st = next(x for x in stores["stores"] if x["id"] == sid)
            sls = [l for l in ls if l["store_id"] == sid]
            feat = ' <span class="badge featured">Featured</span>' if not parts else ""
            parts.append(f"""<h2 class="shop-head" id="shop-{E(sid)}"><span><a href="{E(st['url'])}" rel="noopener" target="_blank">{E(st['name'])}</a></span>{feat}
  <span class="muted small">{E(count_line(sls).capitalize())}</span></h2>""")
        parts.append(f"""<section class="card group-sec" id="{E(cid or 'other')}">
  <div class="section-head"><{hx}>{E(name)}</{hx}><p class="muted small">{E(count_line(sl, g.get('unit', 'listings')).capitalize())}</p></div>
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th><th class="hide-sm">Checked</th></tr></thead>
    <tbody>{status_rows(sl, oe)}</tbody>
  </table></div>
  <p class="muted small">{g.get('open_hint', "Open a shop's name to go straight to its listing")}{az_sub}{tracker}</p>
</section>""")
    unk = [l for l in ls if l["status"] == "unknown"]
    if len(unk) == len(ls):
        right_now = f"we couldn't check any of these {len(ls)} listings this run, so we're not showing a status."
    else:
        right_now = (f"{len(buy)} of {len(ls) - len(unk) if unk else len(ls)} {'checked ' if unk else ''}listings are in stock or on preorder "
                     f"at {len({l['store_id'] for l in buy})} of {shops} shops."
                     + (f" {len(unk)} couldn't be checked this run." if unk else ""))
    lead_n = 2 if g.get("dotgrid") else 1  # dot grid: first shop heading + its first card
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and c["to"] in BUYABLE and c["from"] in NOT_BUYABLE],
                key=lambda c: c["at"], reverse=True)[:10]
    if rs:
        feed = "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in rs)
        restock_html = f'<ol class="feed">{feed}</ol>'
    else:
        start = tracking_start(ls)
        restock_html = f'''<div class="empty"><p><strong>No restocks spotted yet.</strong> Tracking started <time datetime="{E(start)}">{E(fmt_et(start))}</time>.
  A restock shows up here the moment a sold-out listing flips back to in stock or preorder between two checks.</p></div>'''
    others = "".join(f'<li><a href="{x["slug"]}/">{E(x["short"])}</a></li>' for x in GROUPS if x is not g and bool(x.get("dotgrid")) == bool(g.get("dotgrid")))
    if g.get("dotgrid"):
        others += '<li><a href="#tracker">Every dot grid listing we track</a></li>'
        shop_nav = "".join(f'<a class="chip" href="#shop-{E(x["id"])}">{E(x["name"])}</a>' for x in DOTGRID_SHOPS if any(l["store_id"] == x["id"] for l in ls))
        shop_nav = f'<nav class="chips" aria-label="Shops on this page"><span class="muted small">Jump to a shop:</span> {shop_nav}</nav>'
        dg_tracker = tracker_block(ls, tracker_rows(ls, oe), "Tsuki, B5, Charcoal…") + stock_data(tracker_rows(ls, oe))
    else:
        others += '<li><a href="index.html#tracker">Every listing we track</a></li>'
        shop_nav = dg_tracker = ""
    body = f"""
<div class="product-page">
<nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a> <span aria-hidden="true">›</span> <span aria-current="page">{E(g['short'])}</span></nav>
<section class="hero">
  <p class="eyebrow">{E(g.get('eyebrow', 'Hobonichi Techo 2027'))} · {shops} {'shop' if shops == 1 else 'shops'} checked</p>
  <h1>{E(g['h1'])}</h1>
  <p class="lede">{E(g['intro'])}</p>
  <p><strong>Right now:</strong> {right_now}
  <span class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time>.</span></p>
</section>
<div class="layout">
  <div class="main-col">
    <div class="m-lead">{shop_nav}{''.join(parts[:lead_n])}</div>
    {''.join(parts[lead_n:])}
    {dg_tracker}
    <section class="card"><h2>Recent restocks</h2>{restock_html}</section>
    <section class="card"><h2>Good to know</h2>
      <ul>
        <li>Statuses are exactly what each shop's public product data said at the time shown. Always confirm on the shop's page before you buy.</li>
        <li>"Not yet on sale" means the shop has a preview page up but isn't taking orders yet. "Couldn't check" means our check failed, so we don't know.</li>
        <li>We don't show prices, because they change and differ by shop. Check the shop's page.</li>
        <li>{g.get('guide', 'For launch dates and how restocks usually go, see the <a href="hobonichi-2027.html">Hobonichi 2027 launch &amp; restock calendar</a>.')}</li>
      </ul>
    </section>
  </div>
  <aside class="side-col">
    {signup_block(compact=True)}
    {sponsor_block()}
    {editor_block("dotgrid" if g.get("dotgrid") else "home")}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {"" if g.get("dotgrid") else guides_block()}
  </aside>
</div>
</div>"""
    fname = g["slug"] + "/"
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": g["short"], "item": url_for(fname)}]}
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": g["h1"] + ": listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: (l.get("canonical") or "~", l["store"])))]}
    return fname, page(fname, f'{g["h1"]}: live stock at {shops} {"shop" if shops == 1 else "shops"} · Stationery Drop Watch', g["desc"].format(shops=shops), body, ld=(crumbs, items),
                       og_image=g.get("og_image", OG_IMAGE), og_alt=g.get("og_alt", OG_ALT))

def group_lastmod(g):
    ls = group_listings(g)
    return latest(*[l.get("status_since") for l in ls], *[l.get("first_seen") for l in ls], CONTENT_LASTMOD)

FAQ = [
    ("How often do you check the shops?",
     "About once an hour. A scheduled job reads each shop's public product data, then rebuilds this site with what it found."),
    ("Which shops do you check?",
     "{n} shops in two separate sections. Hobonichi: the official Hobonichi Online Store and independent stationery shops. Dot grid journaling: {dg}, each checked on its own store. Each listing in the tracker links to the shop's own page. JetPens and Nanami Paper are listed as links only, because their sites block automated checks."),
    ("What do you track?",
     "Hobonichi Techo 2027 planners: the Original A6 and Cousin A5 books, Weeks and Weeks Mega, and a few A6 covers. On a separate dot grid journaling page, we track a focused set of flagship dot grid notebooks from {dg}, size by size and color by color. We don't track pens or other paper."),
    ("What does \"Couldn't check\" mean?",
     "Our check of that listing failed, for example because the shop's site didn't respond. We show that instead of guessing whether it's in stock."),
    ("What does \"Not yet on sale\" mean?",
     "The shop has a preview page up for the product but isn't taking orders yet. That's different from sold out."),
    ("Do you sell planners?",
     "No. We link you to the shops. Amazon links on the site are affiliate links, and we say so on every page; links to the shops themselves are plain links."),
    ("How do restock alerts work?",
     "Sign up with your email and you'll get one short email when a sold-out item comes back somewhere we track. It's free and you can unsubscribe anytime."),
]

def faq_block():
    n = len({p["store_id"] for p in stock["products"]})
    qa = [(q, a.format(n=n, dg=dotgrid_names())) for q, a in FAQ]
    html_ = "".join(f"<details class=\"faq-item\"><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in qa)
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
    return f'<section class="card faq" id="faq"><h2>Good to know</h2>{html_}</section>', ld

def product_links_block():
    items = []
    for g in GROUPS:
        if g.get("dotgrid"):
            continue
        ls = group_listings(g)
        items.append(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a> <span class="muted small">· {E(count_line(ls))}</span></li>')
    guides = "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in GUIDES)
    return (f'<section class="card" id="by-product"><h2>Restock pages by product</h2><ul class="link-list">{"".join(items)}</ul>'
            f'<p class="eyebrow">Guides</p><ul class="link-list">{guides}</ul></section>')

STATIC_LASTMOD = {"hobonichi-2027.html": "2026-10-27", "about.html": "2026-10-27"}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes], CONTENT_LASTMOD)
    urls = [(url_for("index.html"), home_mod)]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    hobo_mod = latest(*[p.get("status_since") for p in hobo_products()], GUIDES_LASTMOD)
    urls += [(url_for(WTB_SLUG + "/"), hobo_mod), (url_for(VS_SLUG + "/"), GUIDES_LASTMOD)]
    def w3c(iso):
        return iso if len(iso) == 10 else dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    body = "".join(f"  <url><loc>{E(u)}</loc><lastmod>{w3c(m)}</lastmod></url>\n" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'

def redirect_page(target):
    u = BASE + target
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Moved: {E(u)}</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{E(u)}">
<meta http-equiv="refresh" content="0; url={E(u)}">
</head><body><p>This page moved to <a href="{E(u)}">{E(u)}</a>.</p></body></html>
"""

ROBOTS = f"""User-agent: *
Allow: /

Sitemap: {BASE}sitemap.xml
"""

def build_404():
    """GitHub Pages serves this for any unknown path, so every link is root-relative (see _page)."""
    hobo = "".join(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a></li>' for g in GROUPS if not g.get("dotgrid"))
    body = f"""
<section class="hero notfound">
  <p class="eyebrow">404 · page not found</p>
  <h1>This page sold out. Or it never existed.</h1>
  <p class="lede">The link may be old or mistyped. Every tracker is still here and checked hourly.</p>
  <p><a class="btn" href="index.html">Go to the Hobonichi tracker</a> <a class="btn-ghost" href="{DOTGRID_SLUG}/">Dot grid journals</a></p>
</section>
<div class="layout">
  <div class="main-col">
    <section class="card"><h2>Restock pages</h2>
      <p class="eyebrow">Hobonichi Techo 2027</p><ul class="link-list"><li><a href="index.html">All listings</a></li>{hobo}<li><a href="hobonichi-2027.html">2027 calendar</a></li></ul>
      <p class="eyebrow">Dot grid journaling</p><ul class="link-list"><li><a href="{DOTGRID_SLUG}/">Dot grid journals</a> <span class="muted small">· {E(dotgrid_names())}</span></li></ul>
    </section>
  </div>
  <aside class="side-col">{signup_block(compact=True)}</aside>
</div>"""
    return page("404.html", "Page not found · Stationery Drop Watch",
                "This page doesn't exist. Find the Hobonichi Techo 2027 and dot grid journal restock trackers here.", body, noindex=True)

# --- SEO guides (Hobonichi section) -------------------------------------------------------------
# Two editorial pages. Every stock status on them comes from data/stock.json (rebuilt hourly by the
# workflow); product facts come only from the sources listed on each page. No prices: the checker
# doesn't record them.
WTB_SLUG = "where-to-buy-hobonichi-2027"
VS_SLUG = "hobonichi-techo-vs-cousin-vs-weeks"
GUIDES = [(WTB_SLUG + "/", "Where to buy the Techo 2027"), (VS_SLUG + "/", "Techo vs Cousin vs Weeks")]
GUIDES_LASTMOD = "2026-10-29"  # last copy change on the guide pages (sitemap lastmod floor)
H_SRC = {  # official Hobonichi pages used for product facts
    "orig": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/ob27_jan_en/", "English Original Book A6 (2027), specifications"),
    "cousin": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/cb27_jan_en/", "English Cousin Book A5 (2027), specifications"),
    "weeks": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorsmblue/", "Weeks, Colors: Midnight Blue (2027), specifications"),
    "mega": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_m_tiecandy/", "Weeks Mega, Bow & Tie: Candy Dream (2027), specifications"),
    "g_orig": ("https://www.1101.com/store/techo/en/2027/all_about/original/", "Techo Type Guide: Original"),
    "g_cousin": ("https://www.1101.com/store/techo/en/2027/all_about/cousin/", "Techo Type Guide: Cousin"),
    "g_weeks": ("https://www.1101.com/store/techo/en/2027/all_about/weeks/", "Techo Type Guide: Weeks"),
    "shop": ("https://www.1101.com/store/techo/en/2027/pc/shopping_guide/", "Hobonichi Techo 2027 shopping guide"),
}

def guides_block():
    return ('<section class="card"><p class="eyebrow">Guides</p><ul class="link-list">'
            + "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in GUIDES) + "</ul></section>")

def _group(slug):
    return next(g for g in GROUPS if g["slug"] == slug)

def _buy_shops(ls):
    return sorted({l["store"] for l in ls if l["status"] in BUYABLE})

def _names(xs):
    xs = list(xs)
    return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else "".join(xs)

def _exact_amazon(ls):
    """Exact, verified Amazon listings for these tracked listings (never the brand-store fallback)."""
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    out = {}
    for l in ls:
        m = amz["products"].get(l.get("canonical") or "")
        name = canon.get(l.get("canonical") or "")
        if not m:
            m = amz.get("listings", {}).get(l["url"])
            name = m and m["amazon_title"]
        if m and m["asin"] not in out:
            out[m["asin"]] = name
    return out

def _shop_table(ls):
    rank = {s["id"]: i for i, s in enumerate(stores["stores"])}
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    by = {}
    for l in ls:
        by.setdefault(l["store_id"], []).append(l)
    rows = []
    for sid in sorted(by, key=lambda s: (min(order[l["status"]] for l in by[s]), rank.get(s, 99))):
        items = "".join(
            f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(canon.get(l.get("canonical") or "") or l.get("title") or l["label"])}</a> '
            f'<span class="badge {E(l["status"])}">{E(STATUS[l["status"]])}</span></li>'
            for l in sorted(by[sid], key=lambda l: (order[l["status"]], l["label"])))
        rows.append(f'<tr><td>{E(by[sid][0]["store"])}</td><td><ul class="wtb-items">{items}</ul></td></tr>')
    return f'''<div class="table-wrap"><table class="stock"><thead><tr><th>Shop</th><th>What we track there · status at last check</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>'''

def build_where_to_buy():
    fname = WTB_SLUG + "/"
    hobo = hobo_products()
    groups = [g for g in GROUPS if not g.get("dotgrid")]
    last = f'<time datetime="{E(stock["run_finished"])}">{E(fmt_et(stock["run_finished"]))}</time>'
    quick, secs = [], []
    for g in groups:
        ls = group_listings(g)
        if not ls:
            continue
        shops = len({l["store_id"] for l in ls})
        buy = _buy_shops(ls)
        quick.append(f'<li><a href="#{E(g["slug"])}">{E(g["short"])}</a>: in stock or on preorder at '
                     f'<strong>{len(buy)} of {shops}</strong> {"shop" if shops == 1 else "shops"} we track'
                     f'{" (" + E(_names(buy)) + ")" if 0 < len(buy) <= 4 else ""}.</li>')
        az = _exact_amazon(ls)
        az_html = ("<p class=\"small\">Also on Amazon (exact listings, affiliate links): " + " · ".join(
            f'<a class="az" href="https://www.amazon.com/dp/{E(a)}" target="_blank">{E(n)}</a>' for a, n in az.items()) + "</p>") if az else ""
        secs.append(f'''<section class="card" id="{E(g["slug"])}">
  <div class="section-head"><h2>{E(g["product"])}</h2><p class="muted small">{E(count_line(ls).capitalize())}</p></div>
  {_shop_table(ls)}
  {az_html}
  <p class="small"><a href="{g["slug"]}/">Full {E(g["short"])} restock page</a> <span class="muted">· every listing, when it last changed, and recent restocks</span></p>
</section>''')
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a> <span class="muted">· {E(n["reason"] or "")}</span></li>' for n in stock["not_checked"])
    # Live, data-driven tip: products sold out at one shop we track while another shop has them.
    split = {}
    for l in hobo:
        if l.get("canonical"):
            split.setdefault(l["canonical"], set()).add(l["status"])
    n_split = sum(1 for s in split.values() if "sold_out" in s and s & set(BUYABLE))
    tip_split = (f" Right now, {n_split} of the products we track are sold out at one shop but still available at another." if n_split else "")
    n_buy_shops = len(_buy_shops(hobo))
    n_shops = len({l["store_id"] for l in hobo})
    faq = [
        ("Where can I buy the Hobonichi Techo 2027?",
         f"At the official Hobonichi Online Store and at independent stationery shops. At our last check ({fmt_et(stock['run_finished'])}), "
         f"{n_buy_shops} of the {n_shops} shops we track had at least one 2027 Hobonichi item in stock or on preorder. This page lists them by book and edition."),
        ("Is the Hobonichi Techo 2027 sold out?",
         "It depends on the book, the cover design and the shop. A listing that's sold out at one shop is often still available at another, so check the tables on this page or the restock pages for each book."),
        ("Does Hobonichi send restock emails?",
         "Yes, on its own store: you can sign up for a restock notification email when a product is sold out. Hobonichi says the service covers the Hobonichi Techo and the Drawer Pouch only, not accessories, and that the email doesn't guarantee you'll be able to buy one."),
        ("Will sold-out 2027 books come back?",
         "Often, but not always. The Paper Mouse says almost all items have been restocked at least once after launch in past years, and that it doesn't usually restock dated planners after December."),
        ("How do I get told when something restocks?",
         "Sign up for Stationery Drop Watch alerts. We check the shops about once an hour and send one short email when a sold-out item comes back somewhere we track."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    body = f"""
<div class="product-page">
<nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a> <span aria-hidden="true">›</span> <span aria-current="page">Where to buy</span></nav>
<section class="hero">
  <p class="eyebrow">Guide · Hobonichi Techo 2027 · {n_shops} shops checked hourly</p>
  <h1>Where to buy the Hobonichi Techo 2027</h1>
  <p class="lede">Which shops have the 2027 Original A6, Cousin A5, Weeks, Weeks Mega and A6 covers right now, edition by edition. Every status below is what the shop's own product data said at our last check, {last}.</p>
</section>
<div class="layout">
  <div class="main-col">
    <div class="m-lead">
    <section class="card" id="quick">
      <h2>Quick answer</h2>
      <ul>{"".join(quick)}</ul>
      <p class="muted small">"Not yet on sale" means a preview page is up but the shop isn't taking orders. "Couldn't check" means our check failed, so we don't know. Always confirm on the shop's page before you buy. We don't show prices; check the shop.</p>
    </section>
    </div>
    {signup_block()}
    {"".join(secs)}
    <section class="card"><h2>Shops we list but can't check</h2>
      <p class="muted small">Their sites block automated checks, so we link to them without a status.</p>
      <ul>{not_checked}</ul></section>
    <section class="card" id="tips"><h2>Tips for catching a restock</h2>
      <ul>
        <li><strong>Check more than one shop.</strong> When one store sells out, another often still has it.{tip_split} The <a href="index.html#tracker">full tracker</a> puts every shop side by side.</li>
        <li><strong>Watch for preorders.</strong> Restocks don't always show up as "in stock". At the October 1 wave, some shops took preorders for earlier sell-outs. We count preorders as available. <a href="hobonichi-2027.html">See the 2027 calendar</a>.</li>
        <li><strong>Don't mistake "not yet on sale" for sold out.</strong> Shops put up preview pages before items go on sale.</li>
        <li><strong>Sign up at the official store too.</strong> Hobonichi's restock notification emails cover the Techo books and the Drawer Pouch, not accessories, and don't guarantee you'll get one <a href="#src-shop">[Hobonichi]</a>. Many independent shops offer their own restock sign-ups on product pages <a href="#src-pm">[Paper Mouse]</a>.</li>
        <li><strong>Don't wait past December for a dated book.</strong> The Paper Mouse says it doesn't usually restock dated planners after December <a href="#src-pm">[Paper Mouse]</a>. Spring (April-start) books launch in February; see the <a href="hobonichi-2027.html">calendar</a>.</li>
        <li><strong>Get our alerts.</strong> We check about once an hour and email you when a sold-out item comes back. <a href="#alerts">Sign up above</a>.</li>
      </ul>
    </section>
    <section class="card"><h2>Which one should you get?</h2>
      <p>Not sure between the A6 Original, the A5 Cousin and the slim Weeks? Read <a href="{VS_SLUG}/">Hobonichi Techo vs Cousin vs Weeks</a>: sizes, layouts and who each one suits, from Hobonichi's own specs.</p>
    </section>
    <section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>
    <section class="card"><h2>Sources</h2><ol class="sources">
      <li id="src-shop"><a href="{H_SRC['shop'][0]}" rel="noopener" target="_blank">{E(H_SRC['shop'][1])}</a>, Hobonichi (official). Restock notification emails.</li>
      <li id="src-pm"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Restock history, product-page restock sign-ups, no restocks of dated planners after December.</li>
      <li>Stock statuses: each shop's public product data, read by our checker; see <a href="about.html">how it works</a>.</li>
    </ol></section>
  </div>
  <aside class="side-col">
    {sponsor_block()}
    {guides_block()}
    <section class="card"><p class="eyebrow">Restock pages</p><ul class="link-list">{"".join(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a></li>' for g in groups)}<li><a href="index.html#tracker">Every listing we track</a></li><li><a href="hobonichi-2027.html">2027 calendar</a></li></ul></section>
  </aside>
</div>
</div>"""
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "Where to buy the Hobonichi Techo 2027", "item": url_for(fname)}]}
    art = {"@context": "https://schema.org", "@type": "Article", "headline": "Where to buy the Hobonichi Techo 2027",
           "dateModified": stock["run_finished"], "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, "Where to buy the Hobonichi Techo 2027: live stock by shop · Stationery Drop Watch",
                       f"Where to buy the Hobonichi Techo 2027 Original A6, Cousin A5, Weeks and Weeks Mega: which of {n_shops} shops have each one in stock, checked hourly, plus restock tips.",
                       body, ld=(crumbs, art, faq_ld))

def build_vs():
    fname = VS_SLUG + "/"
    def s(k, label=None):
        return f'<a href="#src-{k}">[{E(label or "Hobonichi")}]</a>'
    def avail(slug):
        ls = group_listings(_group(slug))
        b = _buy_shops(ls)
        return f'{len(b)} of {len({l["store_id"] for l in ls})} shops we track · <a href="{slug}/">live stock</a>'
    rows = [
        ("Size", "A6: 148 × 105 × 15 mm (5.8 × 4.1 × 0.6 in)", "A5: 210 × 148 × 18 mm (8.3 × 5.8 × 0.7 in)", "Tall and slim: 188 × 94 × 10 mm (7.4 × 3.7 × 0.4 in)"),
        ("Weight", "About 195 g", "About 445 g", "About 134 g (Colors cover; varies by cover)"),
        ("Main layout", "One page per day", "One page per day, plus vertical weekly pages", "Weekly: the week on the left page, grid memo page on the right"),
        ("Daily pages", "377 (Jan 1 – Dec 31, 2027)", "377 (Jan 1 – Dec 31, 2027)", "None"),
        ("Weekly pages", "Not included", "106 (vertical timeline)", "114 (Nov 30, 2026 – Jan 2, 2028)"),
        ("Monthly calendar", "Dec 2026 – Mar 2028 (32 pages)", "Dec 2026 – Mar 2028 (32 pages)", "Dec 2026 – Mar 2028 (32 pages)"),
        ("Memo pages", "17", "6", "75 (Weeks Mega: 219)"),
        ("Total pages", "464", "544", "240 (Weeks Mega: 384)"),
        ("Grid", "3.7 mm", "3.7 mm", "3.55 mm"),
        ("Paper and binding", "Tomoe River paper, thread-stitched, opens flat", "Tomoe River paper, thread-stitched, opens flat", "Tomoe River paper, thread-stitched"),
        ("Cover", "Book is meant to go in a separate A6 cover", "Book is meant to go in a separate A5 (Cousin) cover", "Comes as a light hardcover book; Weeks covers are optional"),
        ("Editions", "English (Monday start); Japanese (Monday or Sunday start); Avec two-book set", "English and Japanese", "English and Japanese; Weeks Mega with extra memo pages"),
    ]
    rows_html = "".join(f"<tr><th scope=\"row\">{E(r[0])}</th><td>{E(r[1])}</td><td>{E(r[2])}</td><td>{E(r[3])}</td></tr>" for r in rows)
    rows_html += f'<tr><th scope="row">In stock now</th><td>{avail("hobonichi-techo-2027-original-a6")}</td><td>{avail("hobonichi-techo-2027-cousin-a5")}</td><td>{avail("hobonichi-weeks-2027")}<br><span class="muted small">Weeks Mega: {avail("hobonichi-weeks-mega-2027")}</span></td></tr>'
    faq = [
        ("What's the difference between the Hobonichi Techo Original and the Cousin?",
         "Size and weekly pages. Both have one page per day for 2027. The Original is A6 (148 × 105 mm, about 195 g) and has no weekly pages. The Cousin is A5 (210 × 148 mm, about 445 g) and adds 106 pages of vertical weekly spreads, according to Hobonichi's specifications."),
        ("Is the Hobonichi Weeks a daily planner?",
         "No. Weeks has a weekly layout: each spread shows the week on the left page and a grid memo page on the right. It has no daily pages, plus 75 memo pages at the back in the English edition (219 in Weeks Mega)."),
        ("Which Hobonichi is the most portable?",
         "Weeks. Hobonichi describes it as a slim, long wallet-sized planner: 188 × 94 × 10 mm and about 134 g for the Colors version."),
        ("Do I need a cover?",
         "For the Original and the Cousin, Hobonichi says the book is designed to be used with a cover, sold separately in matching sizes. Weeks comes as a light hardcover book, and Weeks covers are optional."),
        ("What paper do they use?",
         "All three use Tomoe River paper, which Hobonichi describes as thin, light and durable, holding ink well. Hobonichi notes some inks may bleed through or dry slowly, and suggests testing pens first."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    src_items = "".join(f'<li id="src-{k}"><a href="{u}" rel="noopener" target="_blank">{E(t)}</a>, Hobonichi (official).</li>' for k, (u, t) in H_SRC.items() if k != "shop")
    body = f"""
<article class="prose vs-page">
<nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Home</a> <span aria-hidden="true">›</span> <span aria-current="page">Techo vs Cousin vs Weeks</span></nav>
<p class="eyebrow">Guide · Hobonichi Techo 2027 · updated Oct 29, 2026</p>
<h1>Hobonichi Techo vs Cousin vs Weeks: which 2027 planner fits you?</h1>
<p class="lede">The three most popular Hobonichi books differ in size, layout and how much you carry. Here's an honest side-by-side from Hobonichi's own 2027 specifications, with live stock for each.</p>

<h2>The short version</h2>
<ul>
  <li><strong>Original (A6)</strong>: one page per day in a paperback-size book. The classic. {s("g_orig")}</li>
  <li><strong>Cousin (A5)</strong>: one page per day with twice the page size, plus vertical weekly pages. Hobonichi says many people use it as a desk planner. {s("g_cousin")}</li>
  <li><strong>Weeks</strong>: a slim, wallet-size weekly planner with a memo page beside every week and extra memo pages at the back. Lightest of the three. {s("g_weeks")}</li>
</ul>

<h2>Side by side</h2>
<p class="muted small">2027 English, January-start books. Specs from Hobonichi's product pages {s("orig", "Original")} {s("cousin", "Cousin")} {s("weeks", "Weeks")} {s("mega", "Weeks Mega")}; Hobonichi says specifications may vary slightly.</p>
<div class="table-wrap"><table class="stock compare">
<thead><tr><th></th><th>Original (A6)</th><th>Cousin (A5)</th><th>Weeks</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p class="muted small">Stock counts are what each shop's product data said at our last check, <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time>.</p>

<h2>Who each one suits</h2>
<h3>Original (A6): a page a day you can carry</h3>
<p>Pick the Original if you want daily room to write, plan, sketch or paste in tickets, but still want something you can carry every day. Each day gets a full page with a to-do list and a 24-hour timetable {s("g_orig")}. The trade-off: there are no weekly pages, so week-at-a-glance planning happens on the monthly calendars. You'll also want a cover, since the book is designed to go in one.</p>
<p><a href="hobonichi-techo-2027-original-a6/">Live Original A6 stock</a> · <a href="hobonichi-techo-2027-covers/">A6 covers</a></p>
<h3>Cousin (A5): the most room</h3>
<p>Pick the Cousin if a daily page in A6 feels cramped. Hobonichi made it for people who wanted more space to write and paste, or who write in larger letters, and suggests it for work notes, a parenting diary, a shared journal, or a desk planner {s("g_cousin")} {s("cousin", "Cousin")}. It's the only one of the three with both daily pages and vertical weekly pages. The trade-off is weight: at about 445 g it's more than twice the Original, so it's less of an everyday carry.</p>
<p><a href="hobonichi-techo-2027-cousin-a5/">Live Cousin A5 stock</a></p>
<h3>Weeks: light and weekly</h3>
<p>Pick Weeks if you plan by the week and mostly want your schedule and short notes with you. It's slim and light, and each weekly spread pairs the week with a grid memo page {s("g_weeks")}. Weeks books come as a light hardcover in many designs, so you don't need a separate cover {s("weeks", "Weeks")}. The trade-off: there's no daily page, so it isn't for long daily entries. If you want more blank pages, Weeks Mega has about three times the memo pages (219 in English) at the same height and width {s("mega", "Weeks Mega")}.</p>
<p><a href="hobonichi-weeks-2027/">Live Weeks stock</a> · <a href="hobonichi-weeks-mega-2027/">Weeks Mega</a></p>

<h2>Where to buy</h2>
<p>Stock changes by the hour, and one shop is often sold out while another has it. See <a href="{WTB_SLUG}/">where to buy the Hobonichi Techo 2027</a> for every shop we track, edition by edition, or sign up below and we'll email you when a sold-out one comes back.</p>
{signup_block()}

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{src_items}</ol>
<p class="muted small">Hobonichi makes other types too, such as the A5 and A6 HON. This guide covers only the three above.</p>
</article>"""
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "Hobonichi Techo vs Cousin vs Weeks", "item": url_for(fname)}]}
    art = {"@context": "https://schema.org", "@type": "Article", "headline": "Hobonichi Techo vs Cousin vs Weeks: which 2027 planner fits you?",
           "dateModified": GUIDES_LASTMOD, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, "Hobonichi Techo vs Cousin vs Weeks (2027): sizes, layouts, who each suits · Stationery Drop Watch",
                       "Hobonichi Techo Original A6 vs Cousin A5 vs Weeks for 2027: size, weight, daily vs weekly layout, pages and paper from Hobonichi's specs, plus live stock.",
                       body, ld=(crumbs, art, faq_ld))


def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/stock.json", SITE / "data/stock.json")
    shutil.copy(ROOT / "data/changes.json", SITE / "data/changes.json")
    (SITE / "index.html").write_text(build_index())
    (SITE / "hobonichi-2027.html").write_text(build_hobonichi())
    (SITE / "about.html").write_text(build_about())
    (SITE / "404.html").write_text(build_404())
    oe = amazon_main(stock["products"])
    for g in GROUPS:
        fname, doc = build_group(g, oe)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for build in (build_where_to_buy, build_vs):
        fname, doc = build()
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for old, new in REDIRECTS.items():
        (SITE / old).mkdir(parents=True, exist_ok=True)
        (SITE / old / "index.html").write_text(redirect_page(new + "/"))
    (SITE / "sitemap.xml").write_text(build_sitemap())
    (SITE / "robots.txt").write_text(ROBOTS)
    (SITE / "CNAME").write_text(CNAME + "\n")
    print("built", sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*.html")), "+ sitemap.xml, robots.txt, CNAME")

if __name__ == "__main__":
    main()
