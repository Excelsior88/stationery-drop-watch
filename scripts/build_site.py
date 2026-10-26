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

def amazon_for(canonical, listing_url=""):
    """(tagged url, label) for a tracked listing: exact verified ASIN, else the Hobonichi brand link."""
    m = amz["products"].get(canonical or "") or amz.get("listings", {}).get(listing_url)
    if m:
        return amazon_link(f"https://www.amazon.com/dp/{m['asin']}"), "Also on Amazon"
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
NAV = [("index.html", "Restock tracker"), ("hobonichi-2027.html", "Hobonichi 2027 calendar"), ("about.html", "About")]

# Public URL of the GitHub Pages site. Used for canonical/OG URLs, JSON-LD and sitemap.xml.
BASE = "https://excelsior88.github.io/stationery-drop-watch/"
OG_IMAGE = BASE + "assets/brand/og-image.png"  # 1200x630, made by scripts/brand/make_og.py
X_HANDLE = "@stationerydrop"
LOCAL_LINK = re.compile(r'\b(href|src|srcset)="(?!https?:|mailto:|#|/|\.\./|data:)([^"]*)"')

def page(fname, title, desc, body, ld=(), og_type="website"):
    return tag_amazon_links(_page(fname, title, desc, body, ld, og_type))

def url_for(fname):
    """Absolute public URL: index.html -> BASE, 'slug/' -> BASE + 'slug/'."""
    return BASE if fname == "index.html" else BASE + fname

def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"

def _page(fname, title, desc, body, ld=(), og_type="website"):
    url = url_for(fname)
    nav = "".join(f'<a href="{h}"{" aria-current=page" if h == fname else ""}>{E(t)}</a>' for h, t in NAV)
    ld_html = "".join(jsonld(x) for x in ld)
    doc = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="Stationery Drop Watch">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}"><meta property="og:locale" content="en_US">
<meta property="og:image" content="{OG_IMAGE}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Stationery Drop Watch logo: Hobonichi Techo 2027 restock tracker, books, Weeks and covers checked hourly across 13 shops">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="{X_HANDLE}">
<meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{OG_IMAGE}">
<link rel="stylesheet" href="assets/style.css">
<link rel="icon" href="assets/brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="assets/brand/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="assets/brand/apple-touch-icon.png" sizes="180x180">
<meta name="theme-color" content="#fbf6ec">
<meta name="google-site-verification" content="ehGQbmQs5JxWElUIdG8edUxqUYenrSKHsw-bf0v0YzU" />
{ld_html}
</head><body>
<header class="masthead"><div class="wrap">
  <a class="brand" href="index.html" aria-label="Stationery Drop Watch home"><picture><source media="(max-width:340px)" srcset="assets/brand/icon.svg"><img class="brand-logo" src="assets/brand/logo.svg" alt="Stationery Drop Watch" width="248" height="44"></picture></a>
  <nav>{nav}</nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p><strong>Stationery Drop Watch</strong> checks independent and official stores for limited planner restocks so you don't have to refresh ten tabs.</p>
  <p class="foot-links">Restock pages: {" · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS)}</p>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it. Some links may become affiliate links; we'll label them when they do.</p>
  <p class="disclosure">{E(AMAZON_DISCLOSURE)}</p>
  <!-- TODO(affiliate): replace these with tracked links once each program approves the site -->
  <p class="partners">Notebooks we like: <a href="https://www.leuchtturm1917.com/" data-todo="affiliate-leuchtturm1917" rel="nofollow">Leuchtturm1917</a> · <a href="https://baronfig.com/" data-todo="affiliate-baronfig" rel="nofollow">Baron Fig</a> · <a href="https://stationerypal.com/" data-todo="affiliate-stationerypal" rel="nofollow">Stationery Pal</a> <span class="todo-chip" title="Affiliate links not set up yet">TODO: affiliate</span></p>
</div></footer>
<script src="assets/app.js" defer></script>
</body></html>"""
    depth = fname.count("/")
    if depth:  # page lives in a sub-folder (e.g. hobonichi-weeks-2027/): make site-relative links work from there
        doc = LOCAL_LINK.sub(lambda m: f'{m.group(1)}="{"../" * depth}{m.group(2)}"', doc)
    return doc

NEWSLETTER = "dropwatch"  # Buttondown username (https://buttondown.com/dropwatch)

def signup_block(compact=False):
    # Buttondown's standard HTML embed form (docs.buttondown.com/building-your-subscriber-base):
    # a plain POST to embed-subscribe; don't submit via fetch, Buttondown may need to show a CAPTCHA.
    return f"""<section class="card signup{' compact' if compact else ''}" id="alerts">
  <h2>Get restock alerts</h2>
  <p>One short email when a sold-out Hobonichi item comes back somewhere we track. No spam, unsubscribe anytime.</p>
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

def editor_block():
    items = []
    for b in picks["books"]:
        if b.get("hidden"):
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
        items.append(f"""<article class="book" data-book-id="{E(b['id'])}">
  <a class="book-cover" href="{E(own_amazon_link(b['url']))}" data-own-product rel="noopener" target="_blank">
    <img src="{E(b['cover'])}" alt="{E(b['cover_alt'])}" width="200" height="300" loading="lazy"></a>
  <div class="book-body">
    <p class="eyebrow">{E(b.get('kicker',''))}</p>
    <h3>{E(b['pitch'])}</h3>
    <p class="book-title">{E(b['title'])} <span class="muted">· {E(b.get('format',''))}</span></p>
    <p>{E(b['blurb'])}</p>
    <ul class="book-details">{details}</ul>
    <a class="btn" href="{E(own_amazon_link(b['url']))}" data-own-product rel="noopener" target="_blank">See it on Amazon</a>
  </div>
</article>""")
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
        groups.setdefault(product_key(p), []).append(p)
    out = {}
    for k, ls in groups.items():
        sts = {l["status"] for l in ls}
        if not sts <= set(NOT_BUYABLE):
            continue
        hit = next((amz["products"].get(l.get("canonical") or "") or amz.get("listings", {}).get(l["url"]) for l in ls
                    if amz["products"].get(l.get("canonical") or "") or amz.get("listings", {}).get(l["url"])), None)
        if hit:
            url, label, exact = amazon_link(f"https://www.amazon.com/dp/{hit['asin']}"), "Buy on Amazon", True
        else:
            url, label, exact = amazon_link(amz["brands"]["hobonichi"]["url"]), "Check Hobonichi on Amazon", False
        n = len({l["store_id"] for l in ls})
        if sts == {"sold_out"}:
            note = "Sold out at every shop we track" if n > 1 else "Sold out at the only shop we track"
        elif sts == {"coming_soon"}:
            note = "Not on sale yet at any shop we track" if n > 1 else "Not on sale yet at the only shop we track"
        else:
            note = "Sold out or not yet on sale at every shop we track"
        out[k] = dict(url=url, label=label, exact=exact, note=f"{note} ({n} shops)" if n > 1 else note, listings=ls)
    return out

def build_index():
    prods = stock["products"]
    s = stock["summary"]
    checked = sum(v for k, v in s.items() if k != "unknown")
    restocks = [c for c in changes if c["to"] in ("in_stock", "preorder") and c["from"] in ("sold_out", "coming_soon")]
    restocks.sort(key=lambda c: c["at"], reverse=True)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)
    recent = [c for c in restocks if dt.datetime.fromisoformat(c["at"]) >= cutoff][:12]
    if recent:
        feed = "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in recent)
        feed_html = f'<ol class="feed">{feed}</ol>'
    else:
        feed_html = f"""<div class="empty"><p><strong>No restocks spotted yet.</strong> Tracking started {E(fmt_et(stock['run_started']))}.
  A restock shows up here the moment a sold-out item flips back to in stock or preorder between two checks.</p>
  <p class="muted">Right now: {s['sold_out']} tracked listings are sold out and {s['coming_soon']} aren't on sale yet. Those are the ones we're watching.</p></div>"""

    # table data (embedded so the page works without fetch)
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    out_everywhere = amazon_main(prods)
    rows = [dict(g=product_key(p), p=p["label"], c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], st=p["status"],
                 u=p["url"], at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 va=p.get("available_variants"), tv=p.get("total_variants"),
                 az=amazon_for(p.get("canonical"), p["url"])[0], azl=amazon_for(p.get("canonical"), p["url"])[1]) for p in prods]
    for r in rows:  # product unavailable at every tracked shop: Amazon becomes the main action
        m = out_everywhere.get(r["g"])
        if m:
            r.update(az=m["url"], azl=m["label"], azm=1)
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
    store_opts = "".join(f'<option value="{E(x["id"])}">{E(x["name"])}</option>' for x in stores["stores"] if x["platform"] in ("shopify", "hobonichi"))
    prod_opts = "".join(f'<option value="{E(k)}">{E(v)}</option>' for k, v in canon.items() if any(p.get("canonical") == k for p in prods))
    type_opts = "".join(f'<option value="{E(t)}">{E(t)}</option>' for t in sorted({p["type"] for p in prods}))
    status_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items() if any(p["status"] == k for p in prods))
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a>: <span class="muted">{E(n["reason"] or "")}</span></li>' for n in stock["not_checked"])

    faq_html, faq_ld = faq_block()
    noscript_rows = "".join(f'<tr><td>{E(r["p"])}</td><td>{E(r["s"])}</td><td><span class="badge {r["st"]}">{STATUS[r["st"]]}</span></td></tr>' for r in rows)
    body = f"""
<section class="hero">
  <p class="eyebrow">Hobonichi Techo 2027 · {len({p['store_id'] for p in prods})} stores checked</p>
  <h1>Know the moment your planner is back.</h1>
  <p class="lede">We check the official Hobonichi store and independent shops for sold-out planners and covers, and tell you when they come back.</p>
  <div class="stats">
    <div><b>{s['in_stock']}</b><span>in stock</span></div>
    <div><b>{s['preorder']}</b><span>preorder</span></div>
    <div><b>{s['sold_out']}</b><span>sold out</span></div>
    <div><b>{s['coming_soon']}</b><span>not yet on sale</span></div>
  </div>
  <p class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time> · {checked} of {len(prods)} listings checked successfully.</p>
</section>

<div class="layout">
  <div class="main-col">
    <section class="card" id="restocked">
      <h2>Restocked recently</h2>
      {feed_html}
    </section>

    {oe_html}

    {product_links_block()}

    <section class="card" id="tracker">
      <div class="section-head"><h2>Every listing we track</h2><p class="muted small" id="count"></p></div>
      <form class="filters" onsubmit="return false">
        <label>Product<select id="f-product"><option value="">All products</option>{prod_opts}<option value="__other">Other 2027 items</option></select></label>
        <label>Type<select id="f-type"><option value="">All types</option>{type_opts}</select></label>
        <label>Store<select id="f-store"><option value="">All stores</option>{store_opts}</select></label>
        <label>Status<select id="f-status"><option value="">Any status</option>{status_opts}</select></label>
        <label class="grow">Search<input id="f-q" type="search" placeholder="Moomin, Cousin, Midnight Blue…"></label>
      </form>
      <div class="table-wrap"><table class="stock">
        <thead><tr><th>Product</th><th>Store</th><th>Status</th><th class="hide-sm">Checked</th></tr></thead>
        <tbody id="rows"><noscript>{noscript_rows}</noscript></tbody>
      </table></div>
      <button type="button" id="more" class="btn-ghost more" hidden>Show all</button>
      <p class="muted small">"Not yet on sale" means the store has a preview page up but isn't taking orders yet.</p>
      <details class="muted small"><summary>Stores we list but don't check automatically</summary><ul>{not_checked}</ul></details>
    </section>

    {faq_html}
  </div>
  <aside class="side-col">
    {signup_block(compact=True)}
    {sponsor_block()}
    {editor_block()}
    <section class="card soon">
      <p class="eyebrow">Coming to the tracker</p>
      <ul><li>Traveler's Company limited editions <span class="muted small">· {brand_amazon("travelers")}</span></li><li>MIDORI MD seasonal releases <span class="muted small">· {brand_amazon("midori")}</span></li><li>Leuchtturm1917 special editions <span class="muted small">· {brand_amazon("leuchtturm1917")}</span></li></ul>
    </section>
  </aside>
</div>
<script id="stock-data" type="application/json">{json.dumps(rows, ensure_ascii=False).replace('</', '<\\/')}</script>
"""
    n_shops = len({p['store_id'] for p in prods})
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Stationery Drop Watch", "url": BASE,
               "description": "Hourly restock checks for Hobonichi Techo 2027 planners and covers across the official store and independent shops.",
               "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE,
                             "logo": BASE + "assets/brand/icon-512.png", "email": "stationerydropwatch@gmail.com",
                             "sameAs": ["https://x.com/stationerydrop"]}}
    return page("index.html", "Hobonichi Techo 2027 restock tracker: books, Weeks & covers · Stationery Drop Watch",
                f"Is your Hobonichi Techo 2027 back in stock? Live status for Original A6, Cousin A5, Weeks and covers at {n_shops} shops, checked about every hour. Real status, never guessed.",
                body, ld=(site_ld, faq_ld))

def build_hobonichi():
    body = """
<article class="prose">
<p class="eyebrow">Guide · updated Oct 25, 2026</p>
<h1>Hobonichi Techo 2027: launch &amp; restock calendar</h1>
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
        {"@type": "ListItem", "position": 1, "name": "Restock tracker", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "Hobonichi Techo 2027 launch & restock calendar", "item": url_for("hobonichi-2027.html")}]}
    return page("hobonichi-2027.html", "Hobonichi Techo 2027 launch & restock calendar · Stationery Drop Watch",
                "When Hobonichi Techo 2027 planners launch, sell out and restock: launch times, the October wave, and when restocks usually land, with sources.", body, ld=(crumbs,))

def build_about():
    n_checked = len([s for s in stores["stores"] if s["platform"] in ("shopify", "hobonichi")])
    body = f"""
<article class="prose">
<h1>About Stationery Drop Watch</h1>
<p class="lede">Limited planners sell out fast, and every shop only posts its own restocks. This site checks them all in one place.</p>
<h2>How it works</h2>
<p>A small script visits the public product pages of {n_checked} stores on a schedule, at a polite pace and following each store's robots.txt. It reads whether each listing can be bought right now. When a sold-out listing becomes available again, it shows up in <a href="index.html#restocked">Restocked recently</a> and goes out to the alert list.</p>
<p>We only show what the stores report. If a check fails, we say so instead of guessing.</p>
<h2 id="sponsor">Featured shop slot</h2>
<p>Independent stationery shops can book the featured spot on the tracker to promote a restock or launch. It's clearly labeled as sponsored. Shops: want a featured restock slot? Email <a href="mailto:stationerydropwatch@gmail.com?subject=Featured%20restock%20slot">stationerydropwatch@gmail.com</a> for rates and dates.</p>
<h2>Affiliate links</h2>
<p>Some links to notebook brands may become affiliate links. If you buy through one, the site may earn a small commission at no extra cost to you. Store listings in the tracker are plain links.</p>
<h2>Contact</h2>
<p>Questions, corrections, or a shop we should track? Email <a href="mailto:stationerydropwatch@gmail.com">stationerydropwatch@gmail.com</a>.</p>
</article>"""
    return page("about.html", "About · Stationery Drop Watch", "How Stationery Drop Watch checks shops about every hour for Hobonichi Techo 2027 restocks, and why it never guesses stock.", body)

# --- Product restock pages (one indexable page per tracked product group) ---------------------
# Every status on these pages comes from data/stock.json exactly as the checker wrote it.
def _is_a6_book(p):
    return p["type"] == "Book" and (p.get("canonical") in ("original-a6-en", "original-a6-jp")
                                     or (not p.get("canonical") and "a6" in p["label"].lower()))

GROUPS = [
    dict(slug="hobonichi-techo-2027-original-a6", short="Original A6 books",
         match=_is_a6_book,
         title="Hobonichi Techo 2027 Original A6 in stock? Live restock tracker",
         h1="Hobonichi Techo 2027 Original (A6) stock",
         desc="Is the Hobonichi Techo 2027 Original A6 book in stock? Live status for the English and Japanese A6 books at {shops} shops, checked about every hour.",
         intro="The Original is Hobonichi's A6 one-page-a-day book, sold in an English and a Japanese edition. "
               "Below is what each shop we track reported at its last check: in stock, on preorder, sold out, or not on sale yet. "
               "If a check failed we say \"Couldn't check\" rather than guess."),
    dict(slug="hobonichi-techo-2027-cousin-a5", short="Cousin A5 books",
         match=lambda p: p.get("canonical") == "cousin-a5-en",
         title="Hobonichi Techo 2027 Cousin A5 restock & stock tracker",
         h1="Hobonichi Techo 2027 Cousin (A5) stock",
         desc="Live stock status for the Hobonichi Techo 2027 Cousin A5 book (English) at {shops} shops. See who has it in stock or on preorder and when sold-out listings come back.",
         intro="The Cousin is the A5 version of the Techo, with a page a day and more room to write. "
               "Here's what each shop we track reported for the English Cousin at its last check."),
    dict(slug="hobonichi-weeks-2027", short="Weeks",
         match=lambda p: p["type"] == "Weeks",
         title="Hobonichi Weeks 2027 restock tracker: which shops have it in stock",
         h1="Hobonichi Weeks 2027 restock tracker",
         desc="Hobonichi Techo Weeks 2027 stock across {shops} shops, checked about every hour: Midnight Blue, Canaria Yellow, Moomin, White Cat Wallpaper and more. Real status only.",
         intro="Weeks is Hobonichi's slim, wallet-size weekly planner, and the popular covers sell out fast. "
               "These are the 2027 Weeks listings we track, grouped by design, with the status each shop reported at its last check."),
    dict(slug="hobonichi-weeks-mega-2027", short="Weeks Mega",
         match=lambda p: p["type"] == "Weeks Mega",
         title="Hobonichi Weeks Mega 2027 in stock? Live restock tracker",
         h1="Hobonichi Weeks Mega 2027 stock",
         desc="Live stock status for Hobonichi Techo Weeks Mega 2027 (Midnight Blue, Bow & Tie: Candy Dream and more) at {shops} shops, checked about every hour.",
         intro="Weeks Mega is the Weeks planner with extra blank pages at the back. "
               "Here's what each shop we track reported for the 2027 Weeks Mega listings at its last check."),
    dict(slug="hobonichi-techo-2027-covers", short="A6 covers",
         match=lambda p: p["type"] == "Cover",
         title="Hobonichi Techo 2027 cover restock tracker (A6 covers)",
         h1="Hobonichi Techo 2027 cover restocks",
         desc="Restock tracker for Hobonichi Techo 2027 A6 covers like Moomin: My Yard and Yumi Kitagishi: White Cat House. Live status from {shops} shops, checked about every hour.",
         intro="Popular Hobonichi covers can sell out within minutes of a drop. "
               "We track a handful of 2027 A6 covers; here's what each shop reported at its last check."),
]

def latest(*isos):
    return max(i for i in isos if i)

def group_listings(g):
    return [p for p in stock["products"] if g["match"](p)]

def status_rows(ls, oe):
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    rows = []
    for l in sorted(ls, key=lambda l: (order.get(l["status"], 9), l["store"])):
        since = l.get("status_since")
        since_html = f'<span class="sub">since {E(fmt_et(since).rsplit(",", 1)[0])}</span>' if since and l["status"] != "unknown" else ""
        rows.append(f"""<tr><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a><span class="sub">{E(l.get('title') or l['label'])}</span></td>
  <td><span class="badge {E(l['status'])}">{E(STATUS[l['status']])}</span>{since_html}</td>
  <td class="hide-sm"><time datetime="{E(l['checked_at'])}">{E(fmt_et(l['checked_at']))}</time></td></tr>""")
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
    parts = []
    for cid in order:
        sl = sections[cid]
        name = canon.get(cid) or ("Other designs and editions" if len(order) > 1 else "Listings")
        n_buy = sum(l["status"] in BUYABLE for l in sl)
        m = oe.get(cid) if cid else None
        amz_btn = (f'<p><a class="btn btn-amz" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a> '
                   f'<span class="muted small">{E(m["note"])}.</span></p>') if m else ""
        az_url, az_label = amazon_for(cid, sl[0]["url"])
        az_sub = "" if m else f' · <a class="az" href="{E(az_url)}" target="_blank">{E(az_label)}</a>'
        tracker = f' · <a href="index.html?product={E(cid)}#tracker">Filter in the tracker</a>' if cid else ""
        parts.append(f"""<section class="card group-sec" id="{E(cid or 'other')}">
  <div class="section-head"><h2>{E(name)}</h2><p class="muted small">{n_buy} of {len(sl)} listings in stock or on preorder</p></div>
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th><th class="hide-sm">Checked</th></tr></thead>
    <tbody>{status_rows(sl, oe)}</tbody>
  </table></div>
  <p class="muted small">Open a shop's name to go straight to its listing{az_sub}{tracker}</p>
</section>""")
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and c["to"] in BUYABLE and c["from"] in NOT_BUYABLE],
                key=lambda c: c["at"], reverse=True)[:10]
    if rs:
        feed = "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in rs)
        restock_html = f'<ol class="feed">{feed}</ol>'
    else:
        restock_html = '<p class="muted">No restocks spotted for these listings since tracking started. When a sold-out listing flips back to in stock or preorder between two checks, it shows up here.</p>'
    others = "".join(f'<li><a href="{x["slug"]}/">{E(x["h1"])}</a></li>' for x in GROUPS if x is not g)
    body = f"""
<div class="product-page">
<nav class="crumbs" aria-label="Breadcrumb"><a href="index.html">Restock tracker</a> <span aria-hidden="true">›</span> <span aria-current="page">{E(g['short'])}</span></nav>
<section class="hero">
  <p class="eyebrow">Hobonichi Techo 2027 · {shops} shops checked</p>
  <h1>{E(g['h1'])}</h1>
  <p class="lede">{E(g['intro'])}</p>
  <p><strong>Right now:</strong> {len(buy)} of {len(ls)} listings are in stock or on preorder at {len({l['store_id'] for l in buy})} of {shops} shops.
  <span class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time>.</span></p>
</section>
<div class="layout">
  <div class="main-col">
    {''.join(parts)}
    <section class="card"><h2>Restocks spotted</h2>{restock_html}</section>
    <section class="card"><h2>Good to know</h2>
      <ul>
        <li>Statuses are exactly what each shop's public product data said at the time shown. Always confirm on the shop's page before you buy.</li>
        <li>"Not yet on sale" means the shop has a preview page up but isn't taking orders yet. "Couldn't check" means our check failed, so we don't know.</li>
        <li>We don't show prices, because they change and differ by shop. Check the shop's page.</li>
        <li>For launch dates and how restocks usually go, see the <a href="hobonichi-2027.html">Hobonichi 2027 launch &amp; restock calendar</a>.</li>
      </ul>
    </section>
  </div>
  <aside class="side-col">
    {signup_block(compact=True)}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}<li><a href="index.html#tracker">Every listing we track</a></li></ul></section>
  </aside>
</div>
</div>"""
    fname = g["slug"] + "/"
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Restock tracker", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": g["h1"], "item": url_for(fname)}]}
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": g["h1"] + ": shops we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: (l.get("canonical") or "~", l["store"])))]}
    return fname, page(fname, g["title"] + " · Stationery Drop Watch", g["desc"].format(shops=shops), body, ld=(crumbs, items))

def group_lastmod(g):
    ls = group_listings(g)
    return latest(*[l.get("status_since") for l in ls], *[l.get("first_seen") for l in ls])

FAQ = [
    ("How often do you check the shops?",
     "About once an hour. A scheduled job reads each shop's public product data, then rebuilds this site with what it found."),
    ("Which shops do you check?",
     "{n} shops, including the official Hobonichi Online Store and independent stationery shops. Each listing in the tracker links to the shop's own page. JetPens and Nanami Paper are listed as links only, because their sites block automated checks."),
    ("What do you track?",
     "Hobonichi Techo 2027 planners: the Original A6 and Cousin A5 books, Weeks and Weeks Mega, and a few A6 covers. We don't track other brands yet."),
    ("What does \"Couldn't check\" mean?",
     "Our check of that listing failed, for example because the shop's site didn't respond. We show that instead of guessing whether it's in stock."),
    ("What does \"Not yet on sale\" mean?",
     "The shop has a preview page up for the product but isn't taking orders yet. That's different from sold out."),
    ("Do you sell planners?",
     "No. We link you to the shops. Some Amazon links on the site are affiliate links, and we say so on every page."),
    ("How do restock alerts work?",
     "Sign up with your email and you'll get one short email when a sold-out Hobonichi item comes back somewhere we track. It's free and you can unsubscribe anytime."),
]

def faq_block():
    n = len({p["store_id"] for p in stock["products"]})
    qa = [(q, a.format(n=n)) for q, a in FAQ]
    html_ = "".join(f"<details class=\"faq-item\"><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in qa)
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
    return f'<section class="card faq" id="faq"><h2>Questions</h2>{html_}</section>', ld

def product_links_block():
    items = []
    for g in GROUPS:
        ls = group_listings(g)
        n = sum(l["status"] in BUYABLE for l in ls)
        items.append(f'<li><a href="{g["slug"]}/">{E(g["h1"])}</a> <span class="muted small">· {n} of {len(ls)} listings available</span></li>')
    return f'<section class="card" id="by-product"><h2>Restock pages by product</h2><ul class="link-list">{"".join(items)}</ul></section>'

STATIC_LASTMOD = {"hobonichi-2027.html": "2026-10-26", "about.html": "2026-10-26"}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes])
    urls = [(url_for("index.html"), home_mod)]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    def w3c(iso):
        return iso if len(iso) == 10 else dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    body = "".join(f"  <url><loc>{E(u)}</loc><lastmod>{w3c(m)}</lastmod></url>\n" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'

ROBOTS = f"""User-agent: *
Allow: /

Sitemap: {BASE}sitemap.xml
"""

def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/stock.json", SITE / "data/stock.json")
    shutil.copy(ROOT / "data/changes.json", SITE / "data/changes.json")
    (SITE / "index.html").write_text(build_index())
    (SITE / "hobonichi-2027.html").write_text(build_hobonichi())
    (SITE / "about.html").write_text(build_about())
    oe = amazon_main(stock["products"])
    for g in GROUPS:
        fname, doc = build_group(g, oe)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    (SITE / "sitemap.xml").write_text(build_sitemap())
    (SITE / "robots.txt").write_text(ROBOTS)
    print("built", sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*.html")), "+ sitemap.xml, robots.txt")

if __name__ == "__main__":
    main()
