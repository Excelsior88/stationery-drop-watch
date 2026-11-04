#!/usr/bin/env python3
"""Build the static site in site/ from stores.json, data/*.json and content/*.json.
Never invents data: every status shown comes from data/stock.json written by checker.py."""
import json, html, os, re, datetime as dt, shutil
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SITE = Path(os.environ["DROPWATCH_SITE_OUT"]) if os.environ.get("DROPWATCH_SITE_OUT") else ROOT / "site"  # draft builds write elsewhere
ET = ZoneInfo("America/New_York")
E = html.escape

# Amazon Associates tracking ID. Every amazon.com product link on the site is rewritten to
# https://www.amazon.com/dp/<ASIN>?tag=<AMAZON_TAG> with rel="sponsored noopener" (see tag_amazon_links).
AMAZON_TAG = "excelsior88-20"
AMAZON_DISCLOSURE = "As an Amazon Associate we earn from qualifying purchases."
# One affiliate statement, used in the footer and on About. Keep it true to how tag_amazon_links works.
AFFILIATE_NOTE = ("Amazon links on this site are affiliate links. " + AMAZON_DISCLOSURE +
                  " Links to the shops we track, and to our own planners and journals on Amazon, are plain links.")
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

# Canonical products from other brands (e.g. Archer and Olive). Dot grid items get no Amazon fallback link:
# we don't link a brand to a product it isn't. Sections with their own Amazon brand link (Traveler's, MIDORI) use that.
OTHER_BRAND = {c["id"] for c in stores["canonical"] if c.get("brand")}
CANON_SECTION = {c["id"]: c["section"] for c in stores["canonical"] if c.get("section")}
HOBO_SHOPS = {s["id"] for s in stores["stores"] if not s.get("brand") and not s.get("section")}
# The site keeps brand families apart, never mixed: Hobonichi (home tracker, calendar, Hobonichi product pages)
# plus one page per other section below. A listing's section is its own "section", its canonical's "section",
# or (older dot grid entries) a canonical with a "brand" or a store entry with a "brand".
DOTGRID_SHOPS = [s for s in stores["stores"] if s.get("brand")]
SECTIONS = {  # non-Hobonichi sections in nav/footer order; each has one page (the GROUPS entry with that section)
    "dotgrid": dict(slug="archer-and-olive-dot-grid-journal", nav="Dot grid journals", name="dot grid journals",
                    foot="Dot grid journaling", link="Dot grid journals", count="dot grid journals", amazon=None),
    "travelers": dict(slug="travelers-company-limited-edition", nav="Traveler's Company", name="Traveler's Company notebooks and limited editions",
                      foot="Traveler's Company", link="Notebooks and limited editions", count="Traveler's Company", amazon="travelers"),
    "midori": dict(slug="midori-md-limited-edition", nav="MIDORI MD", name="MIDORI MD seasonal releases",
                   foot="MIDORI MD", link="Seasonal releases", count="MIDORI MD", amazon="midori"),
}

def g_sec(g):
    return g.get("section", "hobonichi")

def section_of(p):
    s = p.get("section") or CANON_SECTION.get(p.get("canonical"))
    if s:
        return s
    return "dotgrid" if (p.get("canonical") in OTHER_BRAND or p["store_id"] not in HOBO_SHOPS) else "hobonichi"

def is_dotgrid(p):
    return section_of(p) == "dotgrid"

def section_products(sec):
    return [p for p in stock["products"] if section_of(p) == sec]

def hobo_products():
    return section_products("hobonichi")

N_STORES = len({p["store_id"] for p in stock["products"]})  # stores the checker actually checks
N_SEC = {k: len({p["store_id"] for p in section_products(k)}) for k in ("hobonichi", *SECTIONS)}  # shops per section, from data
LIVE = [k for k in SECTIONS if section_products(k)]  # sections that have tracked listings (and so a page)

def section_shops(sec):
    """Store entries with listings in a section, in stores.json order."""
    ids = {p["store_id"] for p in section_products(sec)}
    return [s for s in stores["stores"] if s["id"] in ids]

def names_and(n):
    return ", ".join(n[:-1]) + " and " + n[-1] if len(n) > 1 else "".join(n)

def dotgrid_names():
    return names_and([s["name"] for s in DOTGRID_SHOPS])

def shop_names(sec):
    return dotgrid_names() if sec == "dotgrid" else names_and([s["name"] for s in section_shops(sec)])

def sections_phrase():
    """'dot grid journals, Traveler's Company notebooks and limited editions and MIDORI MD seasonal releases' (live ones only)."""
    return names_and([SECTIONS[k]["name"] for k in LIVE])

def amazon_for(canonical, listing_url=""):
    """(tagged url, label) for a tracked listing: exact verified ASIN, else the brand link of its section
    (Hobonichi, Traveler's Company or MIDORI). ("", "") for dot grid products without an exact listing."""
    sec = CANON_SECTION.get(canonical or "")
    if canonical in OTHER_BRAND and not (sec and SECTIONS[sec]["amazon"]):  # dot grid: exact verified listing only
        m = amz.get("listings", {}).get(listing_url)
        return (amazon_link(f"https://www.amazon.com/dp/{m['asin']}"), "View on Amazon") if m else ("", "")
    m = amz["products"].get(canonical or "") or amz.get("listings", {}).get(listing_url)
    if m:
        return amazon_link(f"https://www.amazon.com/dp/{m['asin']}"), "View on Amazon"
    b = amz["brands"][SECTIONS[sec]["amazon"] if sec else "hobonichi"]
    return amazon_link(b["url"]), b["label"]

def brand_amazon(key):
    b = amz["brands"][key]
    return f'<a class="az" target="_blank" href="{E(b["url"])}">{E(b["label"])}</a>'

def fmt_et(iso):
    """The one time format on the site: "Nov 3, 11:47 AM ET" (the year is added only when it isn't this year)."""
    t = dt.datetime.fromisoformat(iso).astimezone(ET)
    yr = f", {t.year}" if t.year != dt.datetime.now(ET).year else ""
    return t.strftime("%b %-d") + yr + t.strftime(", %-I:%M %p ET")

def time_tag(iso):
    return f'<time datetime="{E(iso)}">{E(fmt_et(iso))}</time>'

def checked_line(ls):
    """One "checked" time per table: the latest check among its listings (all from the same run)."""
    return f'checked {time_tag(max(l["checked_at"] for l in ls))}' if ls else ""

STATUS = {"in_stock": "In stock", "preorder": "Preorder", "coming_soon": "Not yet on sale",
          "sold_out": "Sold out", "unknown": "Couldn't check"}
DOTGRID_SLUG = SECTIONS["dotgrid"]["slug"]
# Old slugs that now redirect (meta refresh + canonical) to their new page. Never listed in the sitemap.
REDIRECTS = {"archer-and-olive-bullet-journal": DOTGRID_SLUG + "/",
             "travelers-notebook-regular-size": SECTIONS["travelers"]["slug"] + "/#tracker"}  # Regular colors merged into the Traveler's Company page
# Home is a hub; the Hobonichi tracker (the old homepage content) lives on its own page.
HOBO_TRACKER = "hobonichi-restock-tracker/"
# Header: the four trackers as plain visible links, then the rest. Wraps on narrow screens; nothing is hidden.
NAV_TRACKERS = [(HOBO_TRACKER, "Hobonichi tracker")] + [(SECTIONS[k]["slug"] + "/", SECTIONS[k]["nav"]) for k in LIVE]
NAV = [("hobonichi-2027.html", "2027 calendar"), ("guides/", "Guides"), ("shop/", "Planners and journals"),
       ("follow/", "Follow us"), ("about.html", "About")]
SHOP_NAME = "Our planners and journals"  # h1 of /shop; nav and breadcrumb say "Planners and journals"
# The workflow cron is "17,47 * * * *": two runs an hour. Every page says it the same way.
CHECK_FREQ = "about every 30 minutes"
N_HOBO = N_SEC["hobonichi"]   # Hobonichi shops we check
N_DG = N_SEC["dotgrid"]        # dot grid shops we check
TITLE_SUFFIX = " · Stationery Drop Watch"

# Public URL of the site (GitHub Pages custom domain, see site/CNAME). Used for canonical/OG URLs, JSON-LD and sitemap.xml.
BASE = "https://stationerydropwatch.com/"
CNAME = "stationerydropwatch.com"
OG_IMAGE = BASE + "assets/brand/og-image.png"  # 1200x630, made by scripts/brand/make_og.py (Hobonichi side)
OG_ALT = f"Stationery Drop Watch: Hobonichi Techo 2027 restock tracker, books, Weeks and covers checked {CHECK_FREQ} across {N_HOBO} shops"
OG_DOTGRID = BASE + "assets/brand/og-dotgrid.png"  # same script; used on the dot grid journaling page
OG_DOTGRID_ALT = "Stationery Drop Watch: dot grid journal restock tracker for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, checked " + CHECK_FREQ
CONTENT_LASTMOD = "2026-11-03"  # last copy/structure change on the home and restock pages (sitemap lastmod floor)
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
    if not title.endswith(TITLE_SUFFIX):  # every page title ends with the site name
        title += TITLE_SUFFIX
    hobo_page = fname.startswith(("hobonichi-techo-", "hobonichi-weeks-"))  # Hobonichi product pages sit under the tracker
    guide_page = fname in ("where-to-buy-hobonichi-2027/", "hobonichi-techo-vs-cousin-vs-weeks/", "best-dot-grid-journals/")  # guides sit under Guides (the calendar keeps its own nav item)
    def cur(h):  # this page, or the page it sits under (product pages under the tracker, design pages under their section)
        return (h == fname or (hobo_page and h == HOBO_TRACKER) or (guide_page and h == "guides/")
                or (h in [x for x, _ in NAV_TRACKERS] and h.endswith("/") and fname.startswith(h)))
    trk = "".join(f'<a href="{h}"{" aria-current=page" if cur(h) else ""}>{E(t)}</a>' for h, t in NAV_TRACKERS)
    nav = (f'<span class="nav-trackers">{trk}</span><span class="nav-rest">'
           + "".join(f'<a href="{h}"{" aria-current=page" if cur(h) else ""}>{E(t)}</a>' for h, t in NAV) + '</span>')
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
<link rel="stylesheet" href="assets/style.css?v={ASSET_V['style.css']}">
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
  <nav class="site-nav" aria-label="Main">{nav}</nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p><strong>Stationery Drop Watch</strong> checks {N_STORES} official and independent shops ({", ".join([f"{N_HOBO} for Hobonichi"] + [f"{N_SEC[k]} for {SECTIONS[k]['count']}" for k in LIVE])}) {CHECK_FREQ} for limited planner and journal restocks, so you don't have to keep refreshing tabs.</p>
  <p class="foot-links">Hobonichi: <a href="{HOBO_TRACKER}">Hobonichi tracker</a> · {" · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS if g_sec(g) == "hobonichi")}</p>
  <p class="foot-links">Shop: <a href="shop/">{SHOP_NAME}</a> (printed on Amazon, printable PDFs on Etsy)</p>
  <p class="foot-links">Follow: {" · ".join(f'<a href="{E(u)}" rel="noopener" target="_blank">{E(n)}</a>' for n, h, u, note, ic in SOCIALS)} · <a href="follow/">All socials</a></p>
  <p class="foot-links">Guides: {" · ".join(f'<a href="{h}">{E(t)}</a>' for h, t in GUIDES)}</p>
{"".join(f'  <p class="foot-links">{E(SECTIONS[k]["foot"])}: <a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["link"])}</a> <span class="muted">({E(shop_names(k))})</span></p>' + chr(10) for k in LIVE)}  <p class="foot-links">Site: <a href="about.html">About</a> · <a href="about.html#sponsor">Featured shop slot</a> · <a href="mailto:stationerydropwatch@gmail.com">Contact</a></p>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it.</p>
  <p class="disclosure">{E(AFFILIATE_NOTE)}</p>
</div></footer>
<script src="assets/app.js?v={ASSET_V['app.js']}" defer></script>
</body></html>"""
    # The site is served at the domain root, so make every local link root-relative ("assets/x" -> "/assets/x").
    # "index.html" becomes "/" and "about.html" becomes "/about" so internal links match the canonical URLs.
    doc = LOCAL_LINK.sub(lambda m: f'{m.group(1)}="/{pretty(m.group(2))}"', doc)
    return doc

NEWSLETTER = "dropwatch"  # Buttondown username (https://buttondown.com/dropwatch)

# Page types: trackers (home + GROUPS) use hero + .layout with a sidebar; guides and info pages use article.prose.
# Every page has at most one signup box, signup(), placed right after the page intro.
SIGNUP_ACTION = f"https://buttondown.com/api/emails/embed-subscribe/{NEWSLETTER}"

SIGNUP_COPY = {
    "alerts": ("Get restock alerts by email",
               "One short email when a sold-out item comes back somewhere we track. No spam, unsubscribe anytime."),
    "shop": ("Hear about new planners and journals",
             "An occasional email when we release a new planner or journal, plus our restock alerts. No spam, unsubscribe anytime."),
}

def signup(kind="alerts"):
    """The site's one signup box (one per page, right under the page intro). Buttondown's standard HTML embed form
    (docs.buttondown.com/building-your-subscriber-base): a plain POST to embed-subscribe; don't submit via fetch,
    Buttondown may need to show a CAPTCHA. Always id="alerts", so "#alerts" links work on every page."""
    label, note = SIGNUP_COPY[kind]
    return f"""<section class="signup-strip" id="alerts" aria-label="{E(label)}">
  <form class="signup-form embeddable-buttondown-form" action="{SIGNUP_ACTION}" method="post">
    <label class="strip-label" for="email-top">{E(label)}</label>
    <input id="email-top" type="email" name="email" placeholder="you@example.com" required autocomplete="email">
    <input type="hidden" value="1" name="embed">
    <button type="submit">Notify me</button>
  </form>
  <p class="strip-note">{E(note)} Sent via <a href="https://buttondown.com/{NEWSLETTER}" target="_blank" rel="noopener">Buttondown</a>.</p>
</section>"""

def crumbs(*trail):
    """Breadcrumb for every non-home page: Home > ... > this page. trail = (href, label) pairs; the last one is this page."""
    parts = ['<a href="index.html">Home</a>'] + [f'<a href="{h}">{E(t)}</a>' for h, t in trail[:-1]] + [f'<span aria-current="page">{E(trail[-1][1])}</span>']
    return '<nav class="crumbs" aria-label="Breadcrumb">' + ' <span aria-hidden="true">›</span> '.join(parts) + '</nav>'

def crumbs_ld(*trail):
    items = [("index.html", "Home")] + list(trail)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": t, "item": url_for(h)} for i, (h, t) in enumerate(items)]}

def eyebrow(*parts):
    """One eyebrow format: "Section · detail · detail"."""
    return f'<p class="eyebrow">{E(" · ".join(parts))}</p>'



# Featured shop slot. Hidden until a shop books it: set SPONSOR to dict(name=..., line=..., url=...) to show it.
SPONSOR = None

def sponsor_block():
    if not SPONSOR:
        return ""
    return f"""<aside class="card sponsor" aria-label="Featured shop">
  <p class="eyebrow">Featured shop · sponsored</p>
  <p class="sponsor-title"><a href="{E(SPONSOR['url'])}" rel="sponsored noopener" target="_blank">{E(SPONSOR['name'])}</a></p>
  <p>{E(SPONSOR['line'])}</p>
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
    <p class="book-title">{E(b['title'].replace(" - ", " – "))} <span class="muted">· {E(b.get('format',''))}</span></p>
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
  <p class="muted small">Our own planners and journals. <a href="shop/">See them all</a>.</p>
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

def exact_only(canonical):
    """Dot grid products are tracked size by size and only ever get an exact verified Amazon listing."""
    return canonical in OTHER_BRAND and not SECTIONS.get(CANON_SECTION.get(canonical or ""), {}).get("amazon")

def oe_key(p):
    return p["url"] if exact_only(p.get("canonical")) else product_key(p)

def amazon_main(prods):
    """Products that no tracked shop can sell right now (every listing sold out / not yet on sale).
    Recomputed from data/stock.json on every build. A product with any listing we couldn't
    check ('unknown') is left out, since we can't honestly say it's unavailable everywhere."""
    groups = {}
    for p in prods:
        groups.setdefault(oe_key(p), []).append(p)
    out = {}
    for k, ls in groups.items():
        other = exact_only(ls[0].get("canonical"))
        brand = SECTIONS.get(CANON_SECTION.get(ls[0].get("canonical") or ""), {}).get("amazon") or "hobonichi"
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
            url, label, exact = amazon_link(amz["brands"][brand]["url"]), amz["brands"][brand]["label"], False
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
    ns_groups = {}
    for r in sorted(rows, key=lambda r: (r["gn"].lower(), r["s"].lower())):
        ns_groups.setdefault(r["g"], []).append(r)
    noscript_rows = "".join(
        f'<tr class="grp"><th colspan="2" scope="rowgroup">{E(ls[0]["gn"])} <span class="sub">{E(ls[0]["t"])}</span></th></tr>'
        + "".join(f'<tr class="child"><td><a href="{E(r["u"])}" target="_blank" rel="noopener">{E(r["s"])}</a></td><td><span class="badge {r["st"]}">{STATUS[r["st"]]}</span></td></tr>' for r in ls)
        for ls in ns_groups.values())
    return f"""<section class="card" id="tracker">
      <div class="section-head"><h2>Every listing we track</h2><p class="muted small"><span id="count"></span> · {checked_line(prods)}</p></div>
      <form class="filters" onsubmit="return false">
        <label>Product<select id="f-product"><option value="">All products</option>{prod_opts}{other_opt}</select></label>
        <label>Type<select id="f-type"><option value="">All types</option>{type_opts}</select></label>
        <label>Store<select id="f-store"><option value="">All stores</option>{store_opts}</select></label>
        <label>Status<select id="f-status"><option value="">Any status</option>{status_opts}</select></label>
        <label class="grow">Search<input id="f-q" type="search" placeholder="{E(search_hint)}"></label>
      </form>
      <div class="table-wrap"><table class="stock">
        <thead><tr><th>Product, then each shop</th><th>Status</th></tr></thead>
        <tbody id="rows"><noscript>{noscript_rows}</noscript></tbody>
      </table></div>
      <button type="button" id="more" class="btn-ghost more" hidden>Show all</button>
      <p class="muted small">"Not yet on sale" means the store has a preview page up but isn't taking orders yet.</p>
      {extra}
    </section>"""

def tracker_rows(prods, out_everywhere):
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    rows = [dict(g=product_key(p), p=p["label"], gn=canon.get(p.get("canonical") or "", p["label"]), c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], st=p["status"],
                 u=p["url"], at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 va=p.get("available_variants"), tv=p.get("total_variants"),
                 az=amazon_for(p.get("canonical"), p["url"])[0], azl=amazon_for(p.get("canonical"), p["url"])[1]) for p in prods]
    for r in rows:  # product unavailable at every tracked shop: Amazon becomes the main action
        m = out_everywhere.get(r["u"] if exact_only(r["c"]) else r["g"])
        if m:
            r.update(az=m["url"], azl=m["label"], azm=1)
    for r, p in zip(rows, prods):  # design page link (FIX-09), shown on the product's group header
        dp = design_page_for([p])
        if dp:
            r["dp"] = "/" + pretty(dp)
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

def soon_block():
    """Sections we plan to track but don't have listings for yet. Disappears once every one is live."""
    soon = [k for k in SECTIONS if k not in LIVE and SECTIONS[k]["amazon"]]
    if not soon:
        return ""
    items = "".join(f'<li>{E(SECTIONS[k]["name"])} <span class="muted small">· {brand_amazon(SECTIONS[k]["amazon"])}</span></li>' for k in soon)
    return f"""<section class="card soon">
      <p class="eyebrow">Coming to the tracker</p>
      <ul>{items}</ul>
    </section>"""

def build_hobo_tracker():
    """The full Hobonichi tracker (the old homepage), now at HOBO_TRACKER. Copy, FAQ and FAQ schema unchanged."""
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
    def oe_since(m):
        """Latest date a listing flipped to its current status, only if we actually saw the flip
        (status_since later than first_seen). Listings unavailable since we started tracking get no date."""
        seen = [l["status_since"] for l in m["listings"] if l.get("status_since") and l.get("status_since") != l.get("first_seen")]
        return max(seen) if seen else None
    def oe_row(m):
        l0 = m["listings"][0]
        name = canon.get(l0.get("canonical") or "", l0["label"])
        dp = design_page_for(m["listings"])
        name_html = f'<a href="{dp}">{E(name)}</a>' if dp else E(name)
        since = oe_since(m)
        since_html = f' <span class="oe-since">sold out since {time_tag(since)}</span>' if since else ""
        shops = "".join(f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["store"])}</a> <span class="badge {E(l["status"])}">{E(STATUS[l["status"]])}</span></li>' for l in m["listings"])
        n = len({l["store_id"] for l in m["listings"]})
        amz_label = "View on Amazon" if m["exact"] else "Search Amazon"
        return f"""<li class="oe-row"><div class="oe-name"><span class="oe-title">{name_html}</span>{since_html}
  <details class="oe-det"><summary>Shops we checked ({n})</summary><ul class="oe-shops">{shops}</ul></details></div>
  <a class="oe-amz" href="{E(m['url'])}" target="_blank" title="{E(m['label'])}">{amz_label}</a></li>"""
    oe_groups = {}
    for m in sorted(out_everywhere.values(), key=lambda m: not m["exact"]):
        oe_groups.setdefault(m["note"], []).append(m)
    oe_html = (f"""<section class="card" id="sold-out-everywhere">
      <div class="section-head"><h2>Sold out at every shop we track</h2></div>
      <p class="muted small">None of the shops we check can sell these right now. Amazon may still have them, so each row links there. A product leaves this list as soon as any shop we track has it in stock or on preorder.</p>
      {"".join(f'<h3 class="oe-group">{E(note)}</h3><ul class="oe-list compact">{"".join(oe_row(m) for m in ms)}</ul>' for note, ms in oe_groups.items())}
    </section>""" if out_everywhere else "")
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a>: <span class="muted">{E(n["reason"] or "")}</span></li>' for n in stock["not_checked"])

    side = sponsor_block() + soon_block()  # the "From the editor" card is gone from this page
    faq_html, faq_ld = faq_block()
    tracker_html = tracker_block(prods, rows, "Moomin, Cousin, Midnight Blue…", '<option value="__other">Other 2027 items</option>',
        f'<details class="muted small"><summary>Stores we list but don\'t check automatically</summary><ul>{not_checked}</ul></details>')
    body = f"""
{crumbs((HOBO_TRACKER, "Hobonichi tracker"))}
<section class="hero">
  {eyebrow("Hobonichi Techo 2027", f"{len({p['store_id'] for p in prods})} Hobonichi shops", f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}")}
  <h1>Know the moment your planner is back.</h1>
  <p class="lede">We check the official Hobonichi store and independent shops for sold-out Hobonichi planners and covers, and tell you when they come back.</p>
  <p class="shop-cta"><a class="btn-ghost" href="shop/">{SHOP_NAME} →</a> <span class="muted small">2027 planners and journals we make, printed on Amazon and printable on Etsy</span></p>
  <p class="small section-switch">Also tracked: {" · ".join(f'<a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a>' for k in LIVE)}</p>
  {signup()}
  <div class="stats{' five' if s['unknown'] else ''}">
    <div><b>{s['in_stock']}</b><span>in stock</span></div>
    <div><b>{s['preorder']}</b><span>preorder</span></div>
    <div><b>{s['sold_out']}</b><span>sold out</span></div>
    <div><b>{s['coming_soon']}</b><span>not yet on sale</span></div>
    {f'<div class="unk"><b>{s["unknown"]}</b><span>couldn' + "'" + 't check this run</span></div>' if s['unknown'] else ''}
  </div>
  <p class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time> · {checked} of {len(prods)} listings checked successfully.</p>
</section>

<div class="layout{'' if side.strip() else ' solo'}">
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
  {f'<aside class="side-col">{side}</aside>' if side.strip() else ''}
</div>
{stock_data(rows)}
"""
    n_shops = len({p['store_id'] for p in prods if p['store_id'] in HOBO_SHOPS})
    return page(HOBO_TRACKER, "Hobonichi Techo 2027 restock tracker · Stationery Drop Watch",
                f"Is your Hobonichi Techo 2027 back in stock? Live status for Original A6, Cousin A5, Weeks and covers at {n_shops} shops, checked {CHECK_FREQ}. Plus separate trackers for {sections_phrase()}.",
                body, ld=(faq_ld, crumbs_ld((HOBO_TRACKER, "Hobonichi tracker"))))

HUB_TRACKERS = {  # one line per tracker card on the hub homepage
    "hobonichi": ("Hobonichi Techo 2027", "Original A6, Cousin A5, Weeks, Weeks Mega and covers, at the official store and independent shops."),
    "dotgrid": ("Dot grid journals", ""),  # shop names filled in from stores.json
    "travelers": ("Traveler's Company", "Traveler's notebooks, refills and limited editions."),
    "midori": ("MIDORI MD", "MD Notebook diaries and MIDORI MD seasonal releases."),
}
HUB_FAQ = ("What do you track?", "How often do you check the shops?", 'What does "Couldn\'t check" mean?',
           'What does "Not yet on sale" mean?', "How do restock alerts work?")

def build_index():
    """Hub homepage: hero and signup, the four trackers, recent restocks from every tracker, guides, our own products, FAQ."""
    prods = stock["products"]
    s = {k: sum(p["status"] == k for p in prods) for k in STATUS}
    checked = sum(v for k, v in s.items() if k != "unknown")
    keys = ["hobonichi", *LIVE]
    href = {"hobonichi": HOBO_TRACKER, **{k: SECTIONS[k]["slug"] + "/" for k in LIVE}}
    cards = []
    for k in keys:
        ps = section_products(k)
        st = {x: sum(p["status"] == x for p in ps) for x in STATUS}
        name, line = HUB_TRACKERS[k]
        if k == "dotgrid":
            line = f"{dotgrid_names()}, each checked on its own store."
        extra = (f' · {st["preorder"]} on preorder' if st["preorder"] else "") + (f' · {st["unknown"]} couldn\'t be checked' if st["unknown"] else "")
        cards.append(f"""<li class="hub-card"><a href="{href[k]}">
  <h3>{E(name)}</h3><p>{E(line)}</p>
  <p class="hub-count"><b>{st["in_stock"]}</b> in stock now <span class="muted small">of {len(ps)} listings · {N_SEC[k]} shops{E(extra)}</span></p>
  <span class="hub-go">Open the tracker →</span></a></li>""")
    sec_of_url = {p["url"]: section_of(p) for p in prods}
    restocks = [c for c in changes if c["url"] in sec_of_url and c["to"] in ("in_stock", "preorder") and c["from"] in ("sold_out", "coming_soon")]
    restocks.sort(key=lambda c: c["at"], reverse=True)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)
    recent = [c for c in restocks if dt.datetime.fromisoformat(c["at"]) >= cutoff][:12]
    short = {"hobonichi": "Hobonichi", **{k: SECTIONS[k]["nav"] for k in LIVE}}
    if recent:
        feed = "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <a class="hub-tag" href="{href[sec_of_url[c['url']]]}">{E(short[sec_of_url[c['url']]])}</a>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in recent)
        feed_html = f'<ol class="feed">{feed}</ol>'
    else:
        start = tracking_start(prods)
        lead = "No restocks spotted yet." if not restocks else "No restocks in the last 14 days."
        feed_html = f"""<div class="empty"><p><strong>{lead}</strong> Tracking started <time datetime="{E(start)}">{E(fmt_et(start))}</time>.
  A restock shows up here the moment a sold-out item flips back to in stock or preorder between two checks.</p>
  <p class="muted">Right now: {s['sold_out']} tracked listings are sold out and {s['coming_soon']} aren't on sale yet.</p></div>"""
    guides = "".join(f'<li><a href="{h}">{E(t)}</a>{f"<p class=\"muted small\">{E(GUIDE_BLURBS[h])}</p>" if h in GUIDE_BLURBS else ""}</li>' for h, t in GUIDES)
    books = {b["id"]: b for b in picks["books"]}
    own = [(books[a]["cover"], books[a]["cover_alt"], SHOP_LABELS[a], books[a]["format"]) for a in SHOP_ORDER if a in books and books[a].get("cover")]
    own += [(e["img"], e["alt"], e["title"], "Printable PDF") for e in SHOP_ETSY]
    own_html = "".join(f'<li><a href="shop/"><img src="{E(img)}" alt="{E(alt)}" loading="lazy" decoding="async" width="200" height="300"><span class="hub-own-t">{E(t)}</span><span class="muted small">{E(sub)}</span></a></li>' for img, alt, t, sub in own)
    faq_html, _ = faq_block(only=HUB_FAQ, sid="good-to-know")
    unk = f' <span class="unk-note">{s["unknown"]} couldn\'t be checked this run.</span>' if s["unknown"] else ""
    body = f"""
<section class="hero">
  {eyebrow("4 restock trackers", f"{N_STORES} shops", f"checked {CHECK_FREQ}")}
  <h1>Know the moment your planner or journal is back.</h1>
  <p class="lede">We check official stores and independent shops for sold-out Hobonichi planners, dot grid journals, Traveler's Company notebooks and MIDORI MD releases, and tell you when they come back.</p>
  {signup()}
  <p class="muted small hub-status">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time> · {checked} of {len(prods)} listings checked successfully.{unk}</p>
</section>

<section class="hub-trackers" id="trackers" aria-labelledby="trackers-h">
  <h2 id="trackers-h">Pick a tracker</h2>
  <ul class="hub-grid">{"".join(cards)}</ul>
</section>

<div class="hub-cols">
  <section class="card" id="restocked">
    <h2>Recent restocks</h2>
    <p class="muted small">Every tracker, newest first. Last 14 days.</p>
    {feed_html}
  </section>
  <section class="card" id="guides">
    <h2>Guides</h2>
    <ul class="link-list hub-guides">{guides}</ul>
    <p class="small"><a href="guides/">All guides →</a></p>
  </section>
</div>

<section class="hub-own" id="our-planners" aria-labelledby="own-h">
  <div class="section-head"><h2 id="own-h">{SHOP_NAME}</h2><a class="btn-ghost" href="shop/">See them all →</a></div>
  <p class="muted small">2027 planners and journals we make: printed books on Amazon and printable PDFs on Etsy.</p>
  <ul class="hub-own-row">{own_html}</ul>
</section>

{faq_html}
"""
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Stationery Drop Watch", "url": BASE,
               "description": f"Restock checks {CHECK_FREQ} for Hobonichi Techo 2027 planners and covers across the official store and independent shops, and, in separate sections, {sections_phrase()}.",
               "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE,
                             "description": f"Independent restock tracker for Hobonichi Techo 2027 planners and covers, plus {sections_phrase()}. Statuses come straight from each shop's public product data.",
                             "logo": BASE + "assets/brand/icon-512.png", "email": "stationerydropwatch@gmail.com",
                             "sameAs": [s[2] for s in SOCIALS]}}
    return page("index.html", "Hobonichi, dot grid, Traveler's Company & MIDORI MD restock tracker · Stationery Drop Watch",
                f"Live restock checks {CHECK_FREQ} at {N_STORES} shops: Hobonichi Techo 2027 planners and covers, dot grid journals, Traveler's Company notebooks and MIDORI MD releases. See what's in stock now and get an email when a sold-out item is back.",
                body, ld=(site_ld,))

def build_hobonichi():
    body = """
<article class="prose guide">
""" + crumbs(("guides/", "Guides"), ("hobonichi-2027.html", "2027 calendar")) + eyebrow("Guide", "Hobonichi Techo 2027", "updated Oct 25, 2026") + """
<h1>Hobonichi Techo 2027 launch &amp; restock calendar</h1>
<p class="lede">Hobonichi sells its planners in two big drops a year, and popular covers can sell out within minutes. Here's how the 2027 season has gone so far and when stock usually comes back.</p>
""" + signup() + """

<ol class="timeline">
  <li><time>Aug 25, 2026</time><div><h3>Previews go up</h3><p>Shops post the 2027 lineup as "out of stock" or "coming soon" pages. They aren't sold out; they're just not on sale yet. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Aug 31, 2026 · 10 PM ET</time><div><h3>Worldwide launch (January-start planners)</h3><p>Everything goes live at the same moment worldwide: 11 AM on September 1 in Japan, 10 PM ET / 9 PM CT the night before in the US. Atlas Stationers warned that popular styles and collaborations "often sell out within minutes." <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-atlas">[Atlas]</a></p></div></li>
  <li><time>Sep 30 – Oct 1, 2026</time><div><h3>Second fall wave</h3><p>Hobonichi notes that some products begin sales on October 1. At US shops that meant the ONE PIECE magazine collection and the Weeksdays 2027 desk calendar, plus a large restock of earlier sell-outs (as preorders at some shops). <a href="#s-1101">[Hobonichi]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Early–mid Oct 2026</time><div><h3>First restocks land at indie shops</h3><p>Atlas expected its first restock in early October. Paper Mouse's shipment arrived October 15 and preorders began shipping. <a href="#s-atlas">[Atlas]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>February 2027</time><div><h3>Spring launch (April-start planners)</h3><p>The second yearly release, timed to Japan's April academic and fiscal year. Expect another rush on new covers. <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-1101">[Hobonichi]</a></p></div></li>
</ol>

<h2>Will it come back?</h2>
<p>Usually, but not always. Standard planner books and core colors tend to be restocked. Special collaborations may only be sold at launch <a href="#s-atlas">[Atlas]</a>. Paper Mouse says almost every item has been restocked at least once after launch in past years <a href="#s-papermouse">[Paper Mouse]</a>. Hobonichi's own restock emails are only for the Techo books and the Drawer Pouch, not accessories, and they don't promise you'll get one <a href="#s-1101">[Hobonichi]</a>.</p>

<h2>How to not miss it</h2>
<ul>
  <li>Check several shops. When one store sells out, another often still has stock. That's the whole point of the <a href=\"""" + HOBO_TRACKER + """#tracker">tracker</a>.</li>
  <li>Live stock by product: """ + " · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS) + """.</li>
  <li>Buying direct from Hobonichi is the only way to get store-exclusive extras, but it ships from Japan and tariffs may apply in the US <a href="#s-papermouse">[Paper Mouse]</a>.</li>
  <li>Which shops have it right now: <a href="where-to-buy-hobonichi-2027/">where to buy the Hobonichi Techo 2027</a>. Choosing a size: <a href="hobonichi-techo-vs-cousin-vs-weeks/">Techo vs Cousin vs Weeks</a>.</li>
  <li><a href="#alerts">Sign up for alerts</a> (above) and we'll email you when something flips back to in stock.</li>
</ul>

<h2>Sources</h2>
<ol class="sources">
  <li id="s-1101"><a href="https://www.1101.com/store/techo/en/2027/pc/shopping_guide/" rel="noopener" target="_blank">Hobonichi Techo 2027 shopping guide</a>, Hobonichi (official). Release dates, shipping, and restock notification rules.</li>
  <li id="s-papermouse"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Launch times, the Sept 30 preorder, the Oct 15 arrival, and restock history.</li>
  <li id="s-atlas"><a href="https://www.atlasstationers.com/blogs/news/hobonichi-faq-2027" rel="noopener" target="_blank">Hobonichi FAQ – 2027</a>, Atlas Stationers. Launch time, sell-out warning, and the early-October restock.</li>
</ol>
""" + related_block("hobonichi-2027.html") + """
</article>"""
    return page("hobonichi-2027.html", "Hobonichi Techo 2027 launch & restock calendar · Stationery Drop Watch",
                "When Hobonichi Techo 2027 planners launch, sell out and restock: launch times, the October wave, and when restocks usually land, with sources.",
                body, ld=(crumbs_ld(("guides/", "Guides"), ("hobonichi-2027.html", "2027 calendar")),))

def related_block(current):
    """Same closing card on every guide: the other guides, then the live restock pages."""
    others = "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in GUIDES if h != current)
    pages = " · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS)
    return f"""<section class="card related" aria-label="More guides and restock pages">
  <h2>More guides</h2>
  <ul>{others}</ul>
  <p class="small">Live stock: <a href="{HOBO_TRACKER}">Hobonichi tracker</a> · {pages}</p>
</section>"""

def build_about():
    n_checked = N_STORES  # same count as the FAQ and footer: shops the checker actually checks
    body = f"""
<article class="prose">
{crumbs(("about.html", "About"))}
{eyebrow("About", "how we check stock")}
<h1>About Stationery Drop Watch</h1>
<p class="lede">Limited planners sell out fast, and every shop only posts its own restocks. This site checks them all in one place.</p>
{signup()}
<h2>How it works</h2>
<p>A small script visits the public product pages of {n_checked} stores {CHECK_FREQ}, at a polite pace and following each store's robots.txt. It reads whether each listing can be bought right now. Each brand family has its own section, never mixed: the <a href="{HOBO_TRACKER}">Hobonichi tracker</a> (the official store and independent shops){"".join(f', <a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["name"])}</a> ({E(shop_names(k))})' for k in LIVE)}. When a sold-out listing becomes available again, it shows up in <a href="index.html#restocked">Recent restocks</a> and goes out to the alert list.</p>
<p>We only show what the stores report. If a check fails, we say so instead of guessing.</p>
<h2 id="sponsor">Featured shop slot</h2>
<p>Independent stationery shops can book the featured spot on the tracker to promote a restock or launch. It's clearly labeled as sponsored. Shops: want a featured restock slot? Email <a href="mailto:stationerydropwatch@gmail.com?subject=Featured%20restock%20slot">stationerydropwatch@gmail.com</a> for rates and dates.</p>
<h2>Affiliate links</h2>
<p>{E(AFFILIATE_NOTE)} Buying through an Amazon link costs you nothing extra, and it never changes what the tracker shows.</p>
<h2>Contact</h2>
<p>Questions, corrections, or a shop we should track? Email <a href="mailto:stationerydropwatch@gmail.com">stationerydropwatch@gmail.com</a>.</p>
</article>"""
    return page("about.html", "About Stationery Drop Watch: how we check stock", f"How Stationery Drop Watch checks shops {CHECK_FREQ} for Hobonichi Techo 2027, {sections_phrase()} restocks, and why it never guesses stock.", body, ld=(crumbs_ld(("about.html", "About")),))

# --- Product restock pages (one indexable page per tracked product group) ---------------------
# Every status on these pages comes from data/stock.json exactly as the checker wrote it.
def _is_a6_book(p):
    return p["type"] == "Book" and (p.get("canonical") in ("original-a6-en", "original-a6-jp")
                                     or (not p.get("canonical") and "a6" in p["label"].lower()))

GROUPS = [
    dict(slug="hobonichi-techo-2027-original-a6", short="Original A6", product="Hobonichi Techo 2027 Original (A6)",
         match=_is_a6_book,
         desc="Is the Hobonichi Techo 2027 Original A6 book in stock? Live status for the English and Japanese A6 books at {shops} shops, checked about every 30 minutes.",
         intro="The Original is Hobonichi's A6 one-page-a-day book, sold in an English and a Japanese edition. "
               "Below is what each shop we track reported at its last check: in stock, on preorder, sold out, or not on sale yet. "
               "If a check failed we say \"Couldn't check\" rather than guess."),
    dict(slug="hobonichi-techo-2027-cousin-a5", short="Cousin A5", product="Hobonichi Techo 2027 Cousin (A5)",
         match=lambda p: p.get("canonical") == "cousin-a5-en",
         desc="Is the Hobonichi Techo 2027 Cousin A5 book in stock? Live status for the English Cousin at {shops} shops, checked about every 30 minutes, with every restock we spot.",
         intro="The Cousin is the A5 version of the Techo, with a page a day and more room to write. "
               "Here's what each shop we track reported for the English Cousin at its last check."),
    dict(slug="hobonichi-weeks-2027", short="Weeks", product="Hobonichi Weeks 2027",
         match=lambda p: p["type"] == "Weeks",
         desc="Is Hobonichi Weeks 2027 in stock? Live status for Midnight Blue, Canaria Yellow, Moomin, White Cat Wallpaper and more at {shops} shops, checked about every 30 minutes.",
         intro="Weeks is Hobonichi's slim, wallet-size weekly planner, and the popular covers sell out fast. "
               "These are the 2027 Weeks listings we track, grouped by design, with the status each shop reported at its last check."),
    dict(slug="hobonichi-weeks-mega-2027", short="Weeks Mega", product="Hobonichi Weeks Mega 2027",
         match=lambda p: p["type"] == "Weeks Mega",
         desc="Is Hobonichi Weeks Mega 2027 in stock? Live status for Midnight Blue, Bow & Tie: Candy Dream and more at {shops} shops, checked about every 30 minutes.",
         intro="Weeks Mega is the Weeks planner with extra blank pages at the back. "
               "Here's what each shop we track reported for the 2027 Weeks Mega listings at its last check."),
    dict(slug="hobonichi-techo-2027-covers", short="A6 covers", product="Hobonichi Techo 2027 A6 cover",
         match=lambda p: p["type"] == "Cover",
         desc="Are Hobonichi Techo 2027 A6 covers like Moomin: My Yard and Yumi Kitagishi: White Cat House in stock? Live status at {shops} shops, checked about every 30 minutes.",
         intro="Popular Hobonichi covers can sell out within minutes of a drop. "
               "We track a handful of 2027 A6 covers; here's what each shop reported at its last check."),
    dict(slug=DOTGRID_SLUG, short="Dot grid journals", product="Dot grid journal", section="dotgrid", featured=True, per_shop=True,
         search_hint="Tsuki, B5, Charcoal…",
         match=is_dotgrid,
         eyebrow="Dot grid journaling", unit="listings",
         open_hint="Open a row to go straight to that exact size and color on the shop's site",
         guide="Dot grid journals come in several sizes, papers and colors, and each one sells out on its own. "
               "We check the exact variant named in each row, so \"In stock\" means that size and color, not just some version of the journal. "
               "To compare paper weight, pages and size across the four brands, see <a href=\"best-dot-grid-journals/\">best dot grid journals compared</a>.",
         # The URL slug says "archer-and-olive" (kept so links don't break); the page covers every dot grid shop we check,
         # with Archer and Olive featured first, so the title and description name them all.
         title=f"Dot grid journal restock tracker: {dotgrid_names()}",
         desc=f"Are {dotgrid_names()} dot grid journals in stock? Live size-by-size status from each maker's own store, checked {CHECK_FREQ}, with Archer and Olive featured first.",
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Popular dot grid journals and limited editions sell out, and every brand only posts its own restocks. "
               "We track a focused set of flagship dot grid notebooks straight from each maker's own store, size by size and color by color. "
               "Archer and Olive is featured first. This covers dot grid journals only; we don't track pens or other paper here, and Hobonichi and our other sections have their own pages."),
    dict(slug=SECTIONS["travelers"]["slug"], short="Traveler's Company", product="Traveler's Company notebook and limited edition", section="travelers",
         match=lambda p: section_of(p) == "travelers", eyebrow="Traveler's Company", search_hint="Sticker set, Olive, 20th…",
         guide="Traveler's Company makes its limited editions in small runs, and each shop gets its own allocation, so one shop can sell out while another still has stock. "
               "We also track the five standard Regular size notebooks: Black (No. 13714006), Brown (No. 13715006), Blue (No. 15239006), Camel (No. 15193006) and Olive (No. 15342006). "
               "Traveler's Company warns that counterfeits are sold in the US, so we only list the official US shop and authorized retailers. For refills, check the shops directly.",
         title=f"Traveler's Notebook restock tracker: regular colors and limited editions",
         desc="Are the Traveler's Notebook Regular size colors (Black, Brown, Blue, Camel, Olive), 2027 diary accessories and 20th anniversary sets in stock? Live status at {shops} official and independent shops, checked " + CHECK_FREQ + ".",
         og_image=BASE + "assets/brand/og-travelers.png",
         og_alt="Stationery Drop Watch: Traveler's Notebook and limited edition tracker, checked " + CHECK_FREQ,
         intro="We track the five Regular size Traveler's Notebook colors (Black, Brown, Blue, Camel and Olive) plus Traveler's Company limited editions: the yearly diary accessories, anniversary sets and shop exclusives. "
               "We check the official Traveler's Company USA shop and independent shops, item by item. "
               "Hobonichi and our other sections have their own pages."),
    dict(slug=SECTIONS["midori"]["slug"], short="MIDORI MD", product="MIDORI MD seasonal release", section="midori",
         match=lambda p: section_of(p) == "midori", eyebrow="MIDORI MD", search_hint="Diary 2027, 1 Day 1 Page, Stickers…",
         guide="MIDORI makes the dated MD diaries and diary stickers once a year, so when a shop's allocation is gone it is usually gone until the next year's edition. "
               "The plain MD notebooks stay in the catalog all year, so we don't track them here.",
         title=f"MIDORI MD seasonal release restock tracker",
         desc="Are the MIDORI MD Notebook Diary 2027, the 1 Day 1 Page diary and the 2027 diary stickers in stock? Live status at {shops} official and independent shops, checked " + CHECK_FREQ + ".",
         og_image=BASE + "assets/brand/og-midori.png",
         og_alt="Stationery Drop Watch: MIDORI MD seasonal release tracker, checked " + CHECK_FREQ,
         intro="MIDORI's MD line is sold as MD PRODUCT in 2026. The dated 2027 diaries, diary stickers and online store limited editions come once a year, in set quantities. "
               "We check the official MD PRODUCT USA store and independent shops, size by size. "
               "This covers MIDORI MD seasonal releases only; Hobonichi and our other sections have their own pages."),
]
for _g in GROUPS:  # one name per page: H1 is "<product> restock tracker"; the <title> adds the live shop count
    _g["h1"] = _g["product"] + " restock tracker"
for _g in GROUPS:  # Hobonichi pages never pick up listings from another section
    if g_sec(_g) == "hobonichi":
        _g["match"] = (lambda m: lambda p: section_of(p) == "hobonichi" and m(p))(_g["match"])
# A section's page exists only once it has listings; until then it sits in the "Coming to the tracker" box.
GROUPS = [g for g in GROUPS if g_sec(g) == "hobonichi" or g_sec(g) in LIVE]

def latest(*isos):
    return max(i for i in isos if i)

def group_listings(g):
    return [p for p in stock["products"] if g["match"](p)]

def row_amz(l, oe):
    """Per-size Amazon button for other brands' listings (their oe entries are keyed by listing URL)."""
    m = oe.get(l["url"]) if exact_only(l.get("canonical")) else None
    return f'<a class="btn btn-amz btn-sm" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a>' if m else ""

def status_rows(ls, oe):
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    rows = []
    for l in sorted(ls, key=lambda l: (order.get(l["status"], 9), l["store"])):
        since = l.get("status_since")
        since_html = f'<span class="sub">since {E(fmt_et(since).rsplit(",", 1)[0])}</span>' if since and l["status"] != "unknown" else ""
        rows.append(f"""<tr><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a><span class="sub">{E(l.get('title') or l['label'])}</span></td>
  <td><span class="badge {E(l['status'])}">{E(STATUS[l['status']])}</span>{since_html}{row_amz(l, oe)}</td></tr>""")
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
    ext = g_sec(g) != "hobonichi"  # non-Hobonichi sections carry their own tracker table on the page
    per_shop = g.get("per_shop")  # dot grid: every product sits in one maker's store, so the page goes shop by shop
    if per_shop:  # shops in stores.json order (Archer and Olive first)
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
        az_sub = "" if m or not az_url or exact_only(cid) else f' · <a class="az" href="{E(az_url)}" target="_blank">{E(az_label)}</a>'
        tracker = (f' · <a href="{g['slug']}/?product={E(cid)}#tracker">Filter below</a>' if ext else
                   f' · <a href="{HOBO_TRACKER}?product={E(cid)}#tracker">Filter in the tracker</a>') if cid else ""
        dp = design_page_for(sl)
        dp_link = f' · <a href="{dp}">{"Design page" if cid else "Design pages"}: {E(", ".join(d["name"] for d in DESIGNS if any(d["match"](l) for l in sl)))}</a>' if dp else ""
        if dp and not cid:  # "Other designs" card can hold several designed pages: link each
            dp_link = " · Design pages: " + ", ".join(f'<a href="{design_fname(d)}">{E(d["name"])}</a>' for d in DESIGNS if any(d["match"](l) for l in sl))
        sid = sl[0]["store_id"]
        hx = "h3" if per_shop else "h2"  # shop-by-shop pages: shop is the h2, its products are h3
        if per_shop and sid not in seen_shop:
            seen_shop.add(sid)
            st = next(x for x in stores["stores"] if x["id"] == sid)
            sls = [l for l in ls if l["store_id"] == sid]
            feat = ' <span class="badge featured">Featured</span>' if not parts and g.get("featured") else ""
            parts.append(f"""<h2 class="shop-head" id="shop-{E(sid)}"><span><a href="{E(st['url'])}" rel="noopener" target="_blank">{E(st['name'])}</a></span>{feat}
  <span class="muted small">{E(count_line(sls).capitalize())}</span></h2>""")
        parts.append(f"""<section class="card group-sec" id="{E(cid or 'other')}">
  <div class="section-head"><{hx}>{E(name)}</{hx}><p class="muted small">{E(count_line(sl, g.get('unit', 'listings')).capitalize())} · {checked_line(sl)}</p></div>
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(sl, oe)}</tbody>
  </table></div>
  <p class="muted small">{g.get('open_hint', "Open a shop's name to go straight to its listing")}{az_sub}{tracker}{dp_link}</p>
</section>""")
    unk = [l for l in ls if l["status"] == "unknown"]
    if len(unk) == len(ls):
        right_now = f"we couldn't check any of these {len(ls)} listings this run, so we're not showing a status."
    else:
        right_now = (f"{len(buy)} of {len(ls) - len(unk) if unk else len(ls)} {'checked ' if unk else ''}listings are in stock or on preorder "
                     f"at {len({l['store_id'] for l in buy})} of {shops} shops."
                     + (f" {len(unk)} couldn't be checked this run." if unk else ""))
    lead_n = 2 if per_shop else 1  # shop-by-shop pages: first shop heading + its first card
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
    others = "".join(f'<li><a href="{x["slug"]}/">{E(x["short"])}</a></li>' for x in GROUPS if x is not g and (g_sec(x) != "hobonichi") == ext)
    if ext:
        others += f'<li><a href="#tracker">Every {E(SECTIONS[g_sec(g)]["name"].removesuffix("s"))} listing we track</a></li>'
        if per_shop:
            shop_ids = sorted({l["store_id"] for l in ls}, key=lambda sid: rank[sid])
            shop_nav = "".join(f'<a class="chip" href="#shop-{E(sid)}">{E(next(x["name"] for x in stores["stores"] if x["id"] == sid))}</a>' for sid in shop_ids)
            shop_nav = f'<nav class="chips" aria-label="Shops on this page"><span class="muted small">Jump to a shop:</span> {shop_nav}</nav>'
        else:  # products span several shops: jump by product instead
            shop_nav = "".join(f'<a class="chip" href="#{E(cid)}">{E(canon[cid].removeprefix("Traveler\'s notebook "))}</a>' for cid in order if cid)
            shop_nav = f'<nav class="chips" aria-label="Products on this page"><span class="muted small">Jump to:</span> {shop_nav}</nav>'
        dg_tracker = tracker_block(ls, tracker_rows(ls, oe), g["search_hint"]) + stock_data(tracker_rows(ls, oe))
    else:
        others += f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>'
        shop_nav = dg_tracker = ""
    ds = designs_of(g["slug"])
    design_nav = ('<nav class="chips" aria-label="Design pages"><span class="muted small">Design pages:</span> '
                  + "".join(f'<a class="chip" href="{design_fname(d)}">{E(d["name"])}</a>' for d in ds) + '</nav>') if ds else ""
    body = f"""
<div class="product-page">
{crumbs((g["slug"] + "/", g["short"]))}
<section class="hero">
  {eyebrow(g.get('eyebrow', 'Hobonichi Techo 2027'), f"{shops} {'shop' if shops == 1 else 'shops'}", f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}") if ext and not g.get("parent") else eyebrow(g.get('eyebrow', 'Hobonichi Techo 2027'), f"{shops} {'shop' if shops == 1 else 'shops'} checked {CHECK_FREQ}")}
  <h1>{E(g['h1'])}</h1>
  <p class="lede">{E(g['intro'])}</p>
  <p><strong>Right now:</strong> {right_now}
  <span class="muted small">Last check: <time datetime="{E(stock['run_finished'])}">{E(fmt_et(stock['run_finished']))}</time>.</span></p>
  {signup()}
</section>
<div class="layout">
  <div class="main-col">
    <div class="m-lead">{design_nav}{shop_nav}{''.join(parts[:lead_n])}</div>
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
    {sponsor_block()}
    {editor_block("dotgrid" if ext else "home")}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {"" if ext else guides_block()}
  </aside>
</div>
</div>"""
    fname = g["slug"] + "/"
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": g["h1"] + ": listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: (l.get("canonical") or "~", l["store"])))]}
    title = g.get("title") or f'{g["h1"]}: live stock at {shops} {"shop" if shops == 1 else "shops"}'
    return fname, page(fname, title, g["desc"].format(shops=shops), body, ld=(crumbs_ld((fname, g["short"])), items),
                       og_image=g.get("og_image", OG_IMAGE), og_alt=g.get("og_alt", OG_ALT))

def group_lastmod(g):
    ls = group_listings(g)
    return latest(*[l.get("status_since") for l in ls], *[l.get("first_seen") for l in ls], CONTENT_LASTMOD)

# FIX-09: one indexable page per high-demand design, nested under its book-type restock page
# (e.g. /hobonichi-weeks-2027/midnight-blue/). Same template pieces and SEO pattern as the restock pages.
# Picked from data/stock.json on 2026-11-04; "why" records the reason each design got a page.
TN_SLUG = SECTIONS["travelers"]["slug"]
DESIGNS = [
    dict(parent="hobonichi-weeks-2027", slug="midnight-blue", name="Midnight Blue", full="Hobonichi Weeks 2027 Midnight Blue",
         match=lambda p: p.get("canonical") == "weeks-midnight-blue",
         why="Most widely stocked Weeks design: 8 shops, with a mix of in stock, sold out and not yet on sale."),
    dict(parent="hobonichi-weeks-mega-2027", slug="midnight-blue", name="Midnight Blue", full="Hobonichi Weeks Mega 2027 Midnight Blue",
         match=lambda p: p.get("canonical") == "weeks-mega-midnight-blue",
         why="8 shops and half of them sold out: the Weeks Mega design people chase most."),
    dict(parent="hobonichi-weeks-2027", slug="canaria-yellow", name="Canaria Yellow", full="Hobonichi Weeks 2027 Canaria Yellow",
         match=lambda p: p.get("canonical") == "weeks-canaria-yellow",
         why="7 shops, 2 already sold out."),
    dict(parent="hobonichi-weeks-2027", slug="white-cat-wallpaper", name="Yumi Kitagishi: White Cat Wallpaper", full="Hobonichi Weeks 2027 White Cat Wallpaper",
         match=lambda p: p.get("canonical") == "weeks-white-cat",
         why="7 shops, 1 sold out; artist collaboration designs sell out fast."),
    dict(parent="hobonichi-weeks-2027", slug="moomin-at-the-table", name="Moomin: At the Table", full="Hobonichi Weeks 2027 Moomin: At the Table",
         match=lambda p: p.get("canonical") == "weeks-moomin-table",
         why="6 shops; Moomin designs are among the most searched Hobonichi collaborations."),
    dict(parent="hobonichi-weeks-mega-2027", slug="candy-dream", name="Bow & Tie: Candy Dream", full="Hobonichi Weeks Mega 2027 Bow & Tie: Candy Dream",
         match=lambda p: p.get("canonical") == "weeks-mega-candy-dream",
         why="5 shops, including one not yet on sale."),
    dict(parent="hobonichi-weeks-2027", slug="sea-glass", name="Sea Glass", full="Hobonichi Weeks 2027 Sea Glass",
         match=lambda p: p["type"] == "Weeks" and "sea glass" in p["label"].lower(),
         why="Sold out at the only shop we track and named in the site review as a design people look for."),
    dict(parent="hobonichi-weeks-2027", slug="v-and-a", name="V&A series", full="Hobonichi Weeks 2027 V&A series",
         match=lambda p: p["type"] == "Weeks" and "v&a" in p["label"].lower(),
         why="Both V&A designs we track are sold out; named in the site review."),
    dict(parent=TN_SLUG, slug="regular-camel", name="Regular size Camel", full="Traveler's notebook Regular size Camel",
         match=lambda p: p.get("canonical") == "tn-regular-camel",
         why="Sold out at all 5 shops we track."),
    dict(parent=TN_SLUG, slug="regular-olive", name="Regular size Olive", full="Traveler's notebook Regular size Olive",
         match=lambda p: p.get("canonical") == "tn-regular-olive",
         why="Sold out at all 5 shops we track."),
]
DESIGNS_LASTMOD = "2026-11-04"

def design_fname(d):
    return f'{d["parent"]}/{d["slug"]}/'

def design_listings(d):
    return [p for p in stock["products"] if d["match"](p)]

def design_page_for(listings):
    """Local path ('parent/slug/') of the design page covering these listings, if one exists."""
    for d in DESIGNS:
        if any(d["match"](l) for l in listings):
            return design_fname(d)
    return None

def designs_of(parent_slug):
    return [d for d in DESIGNS if d["parent"] == parent_slug]

def build_design(d, oe):
    parent = next(g for g in GROUPS if g["slug"] == d["parent"])
    ls = design_listings(d)
    fname = design_fname(d)
    shops = len({l["store_id"] for l in ls})
    buy = [l for l in ls if l["status"] in BUYABLE]
    unk = [l for l in ls if l["status"] == "unknown"]
    run = stock["run_finished"]
    sec = g_sec(parent)
    ey = parent.get("eyebrow", "Hobonichi Techo 2027")
    h1 = f'{d["full"]} restock tracker'
    m = next((oe.get(k) for k in {oe_key(l) for l in ls} if oe.get(k)), None)
    amz_btn = (f'<p><a class="btn btn-amz" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a> '
               f'<span class="muted small">{E(m["note"])}.</span></p>') if m else ""
    if not ls:
        right_now = "none of the shops we check list this design right now. We'll show it here again if a shop adds it."
    elif len(unk) == len(ls):
        right_now = f"we couldn't check any of these {len(ls)} listings this run, so we're not showing a status."
    else:
        right_now = (f"{len(buy)} of {len(ls) - len(unk) if unk else len(ls)} {'checked ' if unk else ''}listings are in stock or on preorder "
                     f"at {len({l['store_id'] for l in buy})} of {shops} {'shop' if shops == 1 else 'shops'}."
                     + (f" {len(unk)} couldn't be checked this run." if unk else ""))
    table = (f"""<section class="card group-sec" id="stock">
  <div class="section-head"><h2>Stock by shop</h2><p class="muted small">{E(count_line(ls).capitalize())} · {checked_line(ls)}</p></div>
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(ls, oe)}</tbody>
  </table></div>
  <p class="muted small">Open a shop's name to go straight to its listing.</p>
</section>""" if ls else f'<section class="card group-sec" id="stock"><h2>Stock by shop</h2><div class="empty"><p>No shop we check lists this design right now. See the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a> for everything we track.</p></div></section>')
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and c["to"] in BUYABLE and c["from"] in NOT_BUYABLE],
                key=lambda c: c["at"], reverse=True)[:10]
    if rs:
        restock_html = '<ol class="feed">' + "".join(f"""<li class="feed-item"><span class="badge {E(c['to'])}">{E(STATUS[c['to']])}</span>
  <a href="{E(c['url'])}" rel="noopener" target="_blank">{E(c['label'])}</a> <span class="muted">at {E(c['store'])}</span>
  <time datetime="{E(c['at'])}">{E(fmt_et(c['at']))}</time></li>""" for c in rs) + "</ol>"
    else:
        start = tracking_start(ls) if ls else stock["run_started"]
        restock_html = f'''<div class="empty"><p><strong>No restocks spotted yet.</strong> Tracking started <time datetime="{E(start)}">{E(fmt_et(start))}</time>.
  A restock shows up here the moment a sold-out listing flips back to in stock or preorder between two checks.</p></div>'''
    # short FAQ, answered from this run's data
    names = lambda xs: ", ".join(sorted({l["store"] for l in xs})) or "none"
    when = fmt_et(run)
    if not ls:
        a1 = f"At the last check ({when}) none of the shops we track listed it."
    elif not buy:
        a1 = f"Not at the shops we track. At the last check ({when}) none of the {shops} shops had it in stock or on preorder." + (f" {m['note']}, so we link to Amazon, which may still have it." if m else "")
    else:
        a1 = f"Yes, at {len({l['store_id'] for l in buy})} of {shops} shops at the last check ({when}): {names(buy)}. Stock can change within minutes, so confirm on the shop's page."
    if unk:
        a1 += f" We couldn't check {names(unk)} this run, so we don't know their status."
    a2 = (f"We track it at {shops} {'shop' if shops == 1 else 'shops'}: {names(ls)}. Each name in the table above opens that shop's own listing."
          if ls else "No shop we check lists it right now.")
    qa = [(f'Is {d["full"]} in stock?', a1),
          (f'Where can I buy {d["full"]}?', a2),
          ("How often do you check?",
           f"Every shop is checked {CHECK_FREQ}. Each status is exactly what the shop's public product data said at that time. \"Not yet on sale\" means the shop has a preview page up but isn't taking orders yet, and \"Couldn't check\" means our check failed, so we don't guess."),
          ("Can I get an alert when it's back?",
           "Yes. Sign up above for restock emails: we send one short email when a sold-out item comes back at any shop we track.")]
    faq_html = '<section class="card faq" id="faq"><h2>Questions</h2>' + "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in qa) + "</section>"
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
    sources = "".join(f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["store"])}: {E(l.get("title") or l["label"])}</a></li>' for l in sorted(ls, key=lambda l: l["store"]))
    sources_html = f"""<section class="card" id="sources"><h2>Sources</h2>
  <p class="muted small">Statuses come from each shop's own public product page, read by our checker at the time shown. The raw data for every check is public: <a href="data/stock.json">stock.json</a>.</p>
  <ul class="link-list">{sources}</ul></section>""" if ls else ""
    sibs = "".join(f'<li><a href="{design_fname(x)}">{E(x["name"])}</a></li>' for x in designs_of(d["parent"]) if x is not d)
    others = (f'<li><a href="{parent["slug"]}/">All {E(parent["short"])} designs</a></li>' + sibs
              + (f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>' if sec == "hobonichi" else f'<li><a href="{parent["slug"]}/#tracker">Every listing on the {E(parent["short"])} page</a></li>'))
    intro = (f'{d["full"]}: the status each shop we track reported at its last check, in one place. '
             f'This page covers just this design; the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a> has every design we track.')
    body = f"""
<div class="product-page">
{crumbs((parent["slug"] + "/", parent["short"]), (fname, d["name"]))}
<section class="hero">
  {eyebrow(ey, f"{shops} {'shop' if shops == 1 else 'shops'} checked {CHECK_FREQ}")}
  <h1>{E(h1)}</h1>
  <p class="lede">{intro}</p>
  <p><strong>Right now:</strong> {right_now}
  <span class="muted small">Last check: <time datetime="{E(run)}">{E(fmt_et(run))}</time>.</span></p>
  {signup()}
</section>
<div class="layout">
  <div class="main-col">
    <div class="m-lead">{table}</div>
    <section class="card"><h2>Recent restocks</h2>{restock_html}</section>
    {faq_html}
    {sources_html}
  </div>
  <aside class="side-col">
    {sponsor_block()}
    {editor_block("dotgrid" if sec != "hobonichi" else "home")}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {guides_block() if sec == "hobonichi" else ""}
  </aside>
</div>
</div>"""
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": h1.replace(" restock tracker", "") + ": listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: l["store"]))]}
    title = f'{d["full"]}: live stock at {shops} {"shop" if shops == 1 else "shops"}'
    desc = (f'Is {d["full"]} in stock? Live status at {shops} {"shop" if shops == 1 else "shops"}, checked {CHECK_FREQ}, '
            f'with every restock we spot and a link to each shop\'s listing.')
    return fname, page(fname, title, desc, body, ld=(crumbs_ld((parent["slug"] + "/", parent["short"]), (fname, d["name"])), items, faq_ld),
                       og_image=parent.get("og_image", OG_IMAGE), og_alt=parent.get("og_alt", OG_ALT))

def design_lastmod(d):
    ls = design_listings(d)
    return latest(*[l.get("status_since") for l in ls], *[l.get("first_seen") for l in ls], DESIGNS_LASTMOD)

FAQ = [
    ("How often do you check the shops?",
     "About every 30 minutes. A scheduled job reads each shop's public product data, then rebuilds this site with what it found."),
    ("Which shops do you check?",
     "{n} shops across all trackers, in separate sections per brand family. Hobonichi: {nh} shops, the official Hobonichi Online Store and independent stationery shops. {secs}. Each listing in the tracker links to the shop's own page. JetPens and Nanami Paper are listed as links only, because their sites block automated checks."),
    ("What do you track?",
     "Hobonichi Techo 2027 planners: the Original A6 and Cousin A5 books, Weeks and Weeks Mega, and a few A6 covers. {tracks} We don't track pens or everyday refills."),
    ("What does \"Couldn't check\" mean?",
     "Our check of that listing failed, for example because the shop's site didn't respond. We show that instead of guessing whether it's in stock."),
    ("What does \"Not yet on sale\" mean?",
     "The shop has a preview page up for the product but isn't taking orders yet. That's different from sold out."),
    ("Do you sell planners?",
     "Yes, our own: we make planners and journals and sell them on our shop page ({shop}), printed on Amazon and as printable PDFs on Etsy. "
     "The stationery we track is sold by the shops themselves; we just link you to them. "
     "Amazon links on the site are affiliate links, and we say so on every page; links to the shops we track are plain links."),
    ("How do restock alerts work?",
     "Sign up with your email and you'll get one short email when a sold-out item comes back somewhere we track. It's free and you can unsubscribe anytime."),
]

FAQ_TRACKS = {  # one sentence per live section for "What do you track?"
    "dotgrid": "On a separate dot grid journals page, we track a focused set of flagship dot grid notebooks from {dg}, size by size and color by color.",
    "travelers": "On the Traveler's Company page, we track the five Regular size notebook colors plus limited editions: the 2027 diary accessories, anniversary sets and shop exclusives.",
    "midori": "On the MIDORI MD page, we track seasonal and limited MD releases (MIDORI's MD line is now sold as MD PRODUCT).",
}

def faq_block(only=None, sid="faq"):
    """only: a subset of FAQ questions (the hub shows a short version, without FAQPage markup)."""
    n = len({p["store_id"] for p in stock["products"]})
    # {shop} is a link in the page and the plain URL in the FAQ structured data
    secs = ". ".join(f'{SECTIONS[k]["foot"]}: {N_SEC[k]} shops, {shop_names(k)}' + (", each checked on its own store" if k == "dotgrid" else "") for k in LIVE)
    secs += ". Some shops sell more than one brand, so they're counted once in the total"
    tracks = " ".join(FAQ_TRACKS[k] for k in LIVE)
    qa = [(q, a.format(n=n, nh=N_HOBO, secs=secs, tracks=tracks.format(dg=dotgrid_names()), shop=url_for("shop/")),
           E(a).format(n=n, nh=N_HOBO, secs=E(secs), tracks=E(tracks.format(dg=dotgrid_names())), shop=f'<a href="shop/">{E(SHOP_NAME.lower())}</a>')) for q, a in FAQ if only is None or q in only]
    html_ = "".join(f"<details class=\"faq-item\"><summary>{E(q)}</summary><p>{h}</p></details>" for q, a, h in qa)
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, h in qa]}
    return f'<section class="card faq" id="{sid}"><h2>Good to know</h2>{html_}</section>', ld

def product_links_block():
    items = []
    for g in GROUPS:
        if g_sec(g) != "hobonichi":
            continue
        ls = group_listings(g)
        ds = designs_of(g["slug"])
        dl = (' <span class="muted small">· Designs: ' + ", ".join(f'<a href="{design_fname(d)}">{E(d["name"])}</a>' for d in ds) + '</span>') if ds else ""
        items.append(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a> <span class="muted small">· {E(count_line(ls))}</span>{dl}</li>')
    guides = "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in HOBO_GUIDES)
    return (f'<section class="card" id="by-product"><h2>Restock pages by product</h2><ul class="link-list">{"".join(items)}</ul>'
            f'<p class="eyebrow">Guides</p><ul class="link-list">{guides}</ul></section>')

STATIC_LASTMOD = {"hobonichi-2027.html": "2026-11-03", "about.html": "2026-11-03"}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes], CONTENT_LASTMOD)
    urls = [(url_for("index.html"), home_mod), (url_for(HOBO_TRACKER), latest(*[p.get("status_since") for p in hobo_products()], *[c["at"] for c in changes], CONTENT_LASTMOD))]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(design_fname(d)), design_lastmod(d)) for d in DESIGNS]
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    hobo_mod = latest(*[p.get("status_since") for p in hobo_products()], GUIDES_LASTMOD)
    urls += [(url_for(WTB_SLUG + "/"), hobo_mod), (url_for(VS_SLUG + "/"), GUIDES_LASTMOD), (url_for(DG_GUIDE_SLUG + "/"), latest(*[p.get("status_since") for p in section_products("dotgrid")], DG_GUIDE_LASTMOD)), (url_for("guides/"), DG_GUIDE_LASTMOD), (url_for("shop/"), "2026-11-03"), (url_for("follow/"), "2026-11-03")]
    def w3c(iso):
        return iso if len(iso) == 10 else dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    body = "".join(f"  <url><loc>{E(u)}</loc><lastmod>{w3c(m)}</lastmod></url>\n" for u, m in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}</urlset>\n'

def redirect_page(target):
    u = BASE + target
    c = u.split("#")[0]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Moved: {E(u)}</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{E(c)}">
<meta http-equiv="refresh" content="0; url={E(u)}">
</head><body><p>This page moved to <a href="{E(u)}">{E(u)}</a>.</p></body></html>
"""

ROBOTS = f"""User-agent: *
Allow: /

Sitemap: {BASE}sitemap.xml
"""

def build_404():
    """GitHub Pages serves this for any unknown path, so every link is root-relative (see _page)."""
    hobo = "".join(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a></li>' for g in GROUPS if g_sec(g) == "hobonichi")
    body = f"""
<article class="prose notfound">
{crumbs(("404.html", "Page not found"))}
{eyebrow("404", "page not found")}
<h1>This page sold out. Or it never existed.</h1>
<p class="lede">The link may be old or mistyped. Every tracker is still here and checked {CHECK_FREQ}.</p>
<p><a class="btn" href="{HOBO_TRACKER}">Go to the Hobonichi tracker</a> {" ".join(f'<a class="btn-ghost" href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a>' for k in LIVE)}</p>
<section class="card"><h2>Restock pages</h2>
  <p class="eyebrow">Hobonichi Techo 2027</p><ul class="link-list"><li><a href="{HOBO_TRACKER}">Hobonichi tracker</a></li>{hobo}</ul>
{"".join(f'  <p class="eyebrow">{E(SECTIONS[k]["foot"])}</p><ul class="link-list"><li><a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a> <span class="muted small">· {E(shop_names(k))}</span></li></ul>' + chr(10) for k in LIVE)}
  <p class="eyebrow">Guides</p><ul class="link-list">{"".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in GUIDES)}</ul>
</section>
</article>"""
    return page("404.html", "Page not found · Stationery Drop Watch",
                f"This page doesn't exist. Find the Hobonichi Techo 2027, {sections_phrase()} restock trackers here.", body, noindex=True)

# --- SEO guides (Hobonichi section) -------------------------------------------------------------
# Editorial pages. Every stock status on them comes from data/stock.json (rebuilt about every 30 minutes by the
# workflow); product facts come only from the sources listed on each page. No prices: the checker
# doesn't record them.
WTB_SLUG = "where-to-buy-hobonichi-2027"
VS_SLUG = "hobonichi-techo-vs-cousin-vs-weeks"
DG_GUIDE_SLUG = "best-dot-grid-journals"
HOBO_GUIDES = [(WTB_SLUG + "/", "Where to buy the Techo 2027"), (VS_SLUG + "/", "Techo vs Cousin vs Weeks"), ("hobonichi-2027.html", "2027 launch & restock calendar")]
GUIDES = HOBO_GUIDES + [(DG_GUIDE_SLUG + "/", "Best dot grid journals compared")]  # footer, /guides/, 404, related block; Hobonichi pages use HOBO_GUIDES
GUIDES_LASTMOD = "2026-10-29"
DG_GUIDE_LASTMOD = "2026-11-04"  # last copy change on the dot grid guide
GUIDE_BLURBS = {WTB_SLUG + "/": "Which shops have each 2027 Original A6, Cousin A5, Weeks and Weeks Mega in stock right now, checked about every 30 minutes, plus tips for catching a restock.",
                VS_SLUG + "/": "Size, weight, daily vs weekly layout and pages for the three most popular Hobonichi books, from Hobonichi's own specs, and who each one suits.",
                "hobonichi-2027.html": "When the 2027 planners launched, the October wave, and when restocks usually land, with sources.",
                DG_GUIDE_SLUG + "/": "Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy: paper gsm, pages, size and features from each maker's own page, with live stock."}  # last copy change on the guide pages (sitemap lastmod floor)
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
            + "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in HOBO_GUIDES) + "</ul></section>")

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
    groups = [g for g in GROUPS if g_sec(g) == "hobonichi"]
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
         "Often, but not always. The Paper Mouse says almost all items have been restocked at least once after launch in past years, but it can't guarantee restocks."),
        ("How do I get told when something restocks?",
         "Sign up for Stationery Drop Watch alerts. We check the shops about every 30 minutes and send one short email when a sold-out item comes back somewhere we track."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    body = f"""
<article class="prose guide">
{crumbs(("guides/", "Guides"), (fname, "Where to buy"))}
{eyebrow("Guide", "Hobonichi Techo 2027", f"live stock from {n_shops} shops")}
<h1>Where to buy the Hobonichi Techo 2027</h1>
<p class="lede">Which shops have the 2027 Original A6, Cousin A5, Weeks, Weeks Mega and A6 covers right now, edition by edition. Every status below is what the shop's own product data said at our last check, {last}.</p>
{signup()}
    <section class="card" id="quick">
      <h2>Quick answer</h2>
      <ul>{"".join(quick)}</ul>
      <p class="muted small">"Not yet on sale" means a preview page is up but the shop isn't taking orders. "Couldn't check" means our check failed, so we don't know. Always confirm on the shop's page before you buy. We don't show prices; check the shop.</p>
    </section>
    {"".join(secs)}
    <section class="card"><h2>Shops we list but can't check</h2>
      <p class="muted small">Their sites block automated checks, so we link to them without a status.</p>
      <ul>{not_checked}</ul></section>
    <section class="card" id="tips"><h2>Tips for catching a restock</h2>
      <ul>
        <li><strong>Check more than one shop.</strong> When one store sells out, another often still has it.{tip_split} The <a href="{HOBO_TRACKER}#tracker">full tracker</a> puts every shop side by side.</li>
        <li><strong>Watch for preorders.</strong> Restocks don't always show up as "in stock". At the October 1 wave, some shops took preorders for earlier sell-outs. We count preorders as available. <a href="hobonichi-2027.html">See the 2027 calendar</a>.</li>
        <li><strong>Don't mistake "not yet on sale" for sold out.</strong> Shops put up preview pages before items go on sale.</li>
        <li><strong>Sign up at the official store too.</strong> Hobonichi's restock notification emails cover the Techo books and the Drawer Pouch, not accessories, and don't guarantee you'll get one <a href="#src-shop">[Hobonichi]</a>. Many independent shops offer their own restock sign-ups on product pages <a href="#src-pm">[Paper Mouse]</a>.</li>
        <li><strong>Get our alerts.</strong> We check about every 30 minutes and email you when a sold-out item comes back. <a href="#alerts">Sign up above</a>.</li>
      </ul>
    </section>
<h2>Which one should you get?</h2>
<p>Not sure between the A6 Original, the A5 Cousin and the slim Weeks? Read <a href="{VS_SLUG}/">Hobonichi Techo vs Cousin vs Weeks</a>: sizes, layouts and who each one suits, from Hobonichi's own specs.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">
  <li id="src-shop"><a href="{H_SRC['shop'][0]}" rel="noopener" target="_blank">{E(H_SRC['shop'][1])}</a>, Hobonichi (official). Restock notification emails.</li>
  <li id="src-pm"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Restock history (restocks not guaranteed; almost all items restocked at least once after launch in past years), product-page restock sign-ups.</li>
  <li>Stock statuses: each shop's public product data, read by our checker; see <a href="about.html">how it works</a>.</li>
</ol>
{related_block(fname)}
</article>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": "Where to buy the Hobonichi Techo 2027",
           "dateModified": stock["run_finished"], "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, "Where to buy the Hobonichi Techo 2027: live stock by shop · Stationery Drop Watch",
                       f"Where to buy the Hobonichi Techo 2027 Original A6, Cousin A5, Weeks and Weeks Mega: which of {n_shops} shops have each one in stock, checked {CHECK_FREQ}, plus restock tips.",
                       body, ld=(crumbs_ld(("guides/", "Guides"), (fname, "Where to buy the Hobonichi Techo 2027")), art, faq_ld))

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
<article class="prose guide vs-page">
{crumbs(("guides/", "Guides"), (fname, "Techo vs Cousin vs Weeks"))}
{eyebrow("Guide", "Hobonichi Techo 2027", "updated Oct 29, 2026")}
<h1>Hobonichi Techo vs Cousin vs Weeks: which 2027 planner fits you?</h1>
<p class="lede">The three most popular Hobonichi books differ in size, layout and how much you carry. Here's an honest side-by-side from Hobonichi's own 2027 specifications, with live stock for each.</p>
{signup()}

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
<p>Stock changes fast, and one shop is often sold out while another has it. See <a href="{WTB_SLUG}/">where to buy the Hobonichi Techo 2027</a> for every shop we track, edition by edition, or <a href="#alerts">sign up above</a> and we'll email you when a sold-out one comes back.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{src_items}</ol>
<p class="muted small">Hobonichi makes other types too, such as the A5 and A6 HON. This guide covers only the three above.</p>
{related_block(fname)}
</article>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": "Hobonichi Techo vs Cousin vs Weeks: which 2027 planner fits you?",
           "dateModified": GUIDES_LASTMOD, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, "Hobonichi Techo vs Cousin vs Weeks (2027): sizes, layouts, who each suits · Stationery Drop Watch",
                       "Hobonichi Techo Original A6 vs Cousin A5 vs Weeks for 2027: size, weight, daily vs weekly layout, pages and paper from Hobonichi's specs, plus live stock.",
                       body, ld=(crumbs_ld(("guides/", "Guides"), (fname, "Hobonichi Techo vs Cousin vs Weeks")), art, faq_ld))


DG_SRC = {  # each maker's own product page, read Nov 4, 2026; every spec on the guide cites one of these
    "ao": ("https://www.archerandolive.com/products/songbird-in-blue", "Songbird in Blue notebook", "Archer and Olive"),
    "ao2": ("https://www.archerandolive.com/products/storybook-in-navy-books", "Storybook in Navy notebook", "Archer and Olive"),
    "lt": ("https://www.leuchtturm1917.us/products/hardcover-notebook", "Hardcover Notebook", "Leuchtturm1917"),
    "lt120": ("https://www.leuchtturm1917.us/products/120g-edition", "Notebook Medium (A5), 120G", "Leuchtturm1917"),
    "stm": ("https://scribblesthatmatter.com/products/dotted-journal-pro", "Dotted Journal Pro", "Scribbles That Matter"),
    "stm2": ("https://scribblesthatmatter.com/products/dotted-journal-iconic", "Dotted Journal Iconic", "Scribbles That Matter"),
    "nt": ("https://notebooktherapy.com/products/notebooktherapy-tsuki-bullet-journal", "Tsuki 160GSM dot grid journal", "Notebook Therapy"),
}
DG_COLS = [  # (column heading, store_id, canonicals whose live stock fills the column)
    ("Archer and Olive A5 dot grid", "archerolive", ("ao-storybook-navy", "ao-songbird-blue", "ao-majestic-skies", "ao-apothecary-shelf")),
    ("Leuchtturm1917 Hardcover Medium (A5) dotted", "leuchtturm-us", ("lt-hardcover-a5", "lt-120g-a5")),
    ("Scribbles That Matter Dotted Journal Pro", "scribbles", ("stm-pro", "stm-iconic")),
    ("Notebook Therapy Tsuki 160GSM", "notebooktherapy", ("nt-tsuki-160",)),
]

def build_dotgrid_guide():
    fname = DG_GUIDE_SLUG + "/"
    title = "Best dot grid journals compared: Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy"
    desc = ("Dot grid journals compared: paper weight (gsm), pages, size and features for Archer and Olive, Leuchtturm1917, "
            "Scribbles That Matter and Notebook Therapy, from each maker's page, plus live stock.")
    dg = section_products("dotgrid")
    def s(k):
        return f'<a href="#src-{k}">[{E(DG_SRC[k][2])}]</a>'
    def col_ls(canons):
        return [p for p in dg if p.get("canonical") in canons]
    def avail(store_id, canons):
        ls = col_ls(canons)
        if not ls:
            return f'<a href="{DOTGRID_SLUG}/#shop-{store_id}">Live stock</a>'
        buy = [re.sub(r"\s*Bullet Journal", "", l["label"]) for l in ls if l["status"] in BUYABLE]
        names = f'<br><span class="muted small">In stock: {E("; ".join(buy))}</span>' if buy else ""
        return f'<strong>{len(buy)} of {len(ls)}</strong> versions we track · <a href="{DOTGRID_SLUG}/#shop-{store_id}">live stock</a>{names}'
    na = "Not listed on the product page"
    rows = [  # (row, A&O, Leuchtturm1917, Scribbles That Matter, Notebook Therapy), each cell (text, source keys)
        ("Paper weight", ("160gsm (Storybook also comes in kraft dot grid, 150gsm)", "ao ao2"), ("80 g/m² (the 120G edition is 120 gsm)", "lt lt120"),
         ("160gsm or 120gsm, your choice", "stm"), ("160 GSM", "nt")),
        ("Pages", ("192 (A5)", "ao ao2"), ("251 numbered pages (120G edition: 203)", "lt lt120"), (na, "stm"), ("128, with gilded edges", "nt")),
        ("Size", ('A5: 5.75 × 8.25 in', "ao"), ("Medium (A5): 5.71 × 8.27 in", "lt"), ("A5 or B5 (dimensions not listed)", "stm"), ("135 × 195 mm", "nt")),
        ("Dot grid", ("Dot grid (spacing not listed)", "ao"), ("Dots 5 mm apart", "lt"), ("5 mm dot grid", "stm"), ("5 mm, light grey dots", "nt")),
        ("Paper color", ("White, kraft or ivory dot grid (Storybook)", "ao2"), ("Slightly chamois-colored", "lt"), ("Bright white", "stm"), ("Bright white", "nt")),
        ("Cover", ("Vegan leather (hard or soft not listed)", "ao"), ("Hardcover; softcover also sold", "lt"), ("Vegan leather hardcover", "stm"), ("Vegan leather (hard or soft not listed)", "nt")),
        ("Lays flat", ("Yes, lay-flat binding", "ao"), ("Yes, thread-bound, opens flat", "lt"), ("Yes, lay-flat binding", "stm"), ("Yes, 180° lay flat", "nt")),
        ("Page numbers and index", (na, "ao"), ("Numbered pages and a blank table of contents", "lt"), ("Numbered pages, index, key and pen test page", "stm"), (na, "nt")),
        ("Bookmarks", (na, "ao"), ("Two page markers", "lt"), ("Two ribbon bookmarks", "stm"), (na, "nt")),
        ("Extras", (na, "ao"), ("Gusseted pocket, elastic band, 8 perforated sheets, stickers", "lt"),
         ("Back pocket, elastic, pen loop; comes with a 0.7 mm fineliner, layout guide and box", "stm"), ("Back pocket with a sticker sheet, elastic band", "nt")),
        ("Other sizes", ("B5, 8x8 square, B6, TN, Pocket and Letter (Songbird)", "ao"), ("Pocket (A6), Composition (B5) and Master (A4+)", "lt"), ("B5", "stm"), ("None listed on this page", "nt")),
    ]
    def n(k):  # numbered citation, matching the Sources list order
        return f'<a href="#src-{k}">[{list(DG_SRC).index(k) + 1}]</a>'
    def cell(t, keys):
        return f'{E(t)} <span class="small">{"".join(n(k) for k in keys.split())}</span>'
    rows_html = "".join(f'<tr><th scope="row">{E(r[0])}</th>' + "".join(f"<td>{cell(*c)}</td>" for c in r[1:]) + "</tr>" for r in rows)
    rows_html += '<tr><th scope="row">In stock now</th>' + "".join(f"<td>{avail(sid, cs)}</td>" for _, sid, cs in DG_COLS) + "</tr>"
    az = _exact_amazon([p for p in dg if p.get("canonical") in ("lt-hardcover-a5", "lt-120g-a5", "stm-pro")])
    az_html = ('<p class="small">Also on Amazon (exact listings, affiliate links): ' + " · ".join(
        f'<a class="az" href="https://www.amazon.com/dp/{E(a)}" target="_blank">{E(n)}</a>' for a, n in az.items()) + "</p>") if az else ""
    faq = [
        ("What paper weight (gsm) is best for a dot grid journal?",
         "Heavier paper is thicker. Archer and Olive, Notebook Therapy's Tsuki and the 160gsm Scribbles That Matter journals use 160gsm paper. "
         "Scribbles That Matter also sells 120gsm, and Leuchtturm1917 sells a 120 gsm edition. Leuchtturm1917's standard hardcover uses 80 g/m² paper. "
         "If you use markers or brush pens, the thicker papers are the safer pick; if you mostly write, thinner paper gives you more pages per book."),
        ("Archer and Olive vs Leuchtturm1917: what's the difference?",
         "Paper and pages. Archer and Olive's A5 dot grid notebook has 160gsm paper and 192 pages. Leuchtturm1917's Hardcover Medium (A5) has 80 g/m² paper "
         "and 251 numbered pages, plus a blank table of contents and two page markers. Both are close to A5 in size."),
        ("Which of these dot grid journals has the most pages?",
         "Of the four, the Leuchtturm1917 Hardcover Medium (A5) has the most pages listed: 251. Archer and Olive's A5 has 192 and the Tsuki 160GSM has 128. "
         "Scribbles That Matter doesn't list a page count on its Dotted Journal Pro page."),
        ("Which ones come with page numbers and an index?",
         "Leuchtturm1917 (numbered pages and a blank table of contents) and Scribbles That Matter (numbered pages, an index, a key page and a pen test page). "
         "Archer and Olive's and Notebook Therapy's product pages don't mention numbered pages or an index."),
        ("How do I know when a sold-out dot grid journal is back?",
         f"Our dot grid tracker checks every journal above {CHECK_FREQ}. Sign up for the free email alerts and we'll tell you when a sold-out size or color comes back."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    src_items = "".join(f'<li id="src-{k}"><a href="{u}" rel="noopener" target="_blank">{E(t)}</a>, {E(b)} (official product page).</li>'
                        for k, (u, t, b) in DG_SRC.items())
    asof = f'<time datetime="{E(stock["run_finished"])}">{E(fmt_et(stock["run_finished"]))}</time>'
    body = f"""
<article class="prose guide vs-page">
{crumbs(("guides/", "Guides"), (fname, "Dot grid journals compared"))}
{eyebrow("Guide", "Dot grid journals", "updated Nov 4, 2026")}
<h1>Best dot grid journals compared: Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy</h1>
<p class="lede">Four popular dot grid journals, side by side: paper weight, pages, size and what comes in the book. Every spec is from the maker's own product page, and stock is live from our tracker.</p>
{signup()}

<h2>The short version</h2>
<ul>
  <li><strong>Archer and Olive</strong>: thick 160gsm paper in many sizes and designs. {s("ao")}</li>
  <li><strong>Leuchtturm1917</strong>: the most pages (251 in A5), with numbered pages, a table of contents and two page markers. Thinner 80 g/m² paper, or 120 gsm in the 120G edition. {s("lt")} {s("lt120")}</li>
  <li><strong>Scribbles That Matter</strong>: the most set up out of the box, with numbered pages, an index, a key and a pen test page, and a choice of 160gsm or 120gsm paper. {s("stm")}</li>
  <li><strong>Notebook Therapy Tsuki</strong>: 160 GSM paper in a slightly smaller book (135 × 195 mm) with 128 gilded-edge pages. {s("nt")}</li>
</ul>

<h2>Side by side</h2>
<p class="muted small">A5 dot grid versions (the Tsuki comes in one size), from each maker's US product page as of Nov 4, 2026. Numbers in brackets point to the sources below. Where a page doesn't list something, we say so instead of guessing. We don't show prices, because they change and differ by edition.</p>
<div class="table-wrap"><table class="stock compare">
<thead><tr><th></th>{"".join(f"<th>{E(h)}</th>" for h, _, _ in DG_COLS)}</tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p class="muted small">Stock is what each maker's own shop said at our last check, {asof}. Archer and Olive counts the A5 and B5 dot grid notebooks we track; Scribbles That Matter includes the Iconic.</p>
{az_html}

<h2>Who each one suits</h2>
<h3>Archer and Olive: for markers, paint and lots of size choices</h3>
<p>Pick Archer and Olive if you want thick paper and a specific size. Its notebooks use 160gsm paper, and the A5 has 192 pages {s("ao")}. Sizes run from Pocket to Letter, including B5, B6, square and a traveler's notebook size {s("ao")}. Some designs also offer kraft (150gsm) or ivory dot grid paper {s("ao2")}. The product page doesn't mention page numbers, an index or bookmarks, so plan to set those up yourself.</p>
<p><a href="{DOTGRID_SLUG}/#shop-archerolive">Live Archer and Olive stock</a></p>
<h3>Leuchtturm1917: for writing, and the most pages</h3>
<p>Pick the Leuchtturm1917 Hardcover Medium (A5) if you mostly write and want room. It has 251 numbered pages, a blank table of contents, two page markers, a gusseted pocket and 8 perforated sheets {s("lt")}. The paper is 80 g/m² and slightly chamois-colored, the thinnest here {s("lt")}. If you want thicker paper with the same setup, the 120G edition has 120 gsm paper and 203 numbered pages {s("lt120")}.</p>
<p><a href="{DOTGRID_SLUG}/#shop-leuchtturm-us">Live Leuchtturm1917 stock</a></p>
<h3>Scribbles That Matter: for starting right away</h3>
<p>Pick the Scribbles That Matter Dotted Journal Pro if you want the setup done. It comes with numbered pages, an index, a key page and a pen test page, two ribbon bookmarks, a pen loop and a 0.7 mm fineliner in the box {s("stm")}. You choose 160gsm or 120gsm paper, in A5 or B5 {s("stm")}. The Pro has a plain matte cover; the Iconic is the same idea with an embossed cover {s("stm2")}. The page doesn't list a page count.</p>
<p><a href="{DOTGRID_SLUG}/#shop-scribbles">Live Scribbles That Matter stock</a></p>
<h3>Notebook Therapy Tsuki: for a smaller book</h3>
<p>Pick the Tsuki 160GSM if you want thick 160 GSM paper in a book you'll finish sooner. It's 135 × 195 mm with 128 pages, gilded edges, a 5 mm light grey dot grid, a back pocket with a sticker sheet and an elastic band {s("nt")}. The product page doesn't mention page numbers, an index or bookmarks. Notebook Therapy also releases limited-edition Tsuki designs, which we track too.</p>
<p><a href="{DOTGRID_SLUG}/#shop-notebooktherapy">Live Notebook Therapy stock</a></p>

<h2>Where to buy</h2>
<p>All four sell direct, and sizes and colors sell out often. Our <a href="{DOTGRID_SLUG}/">dot grid journal tracker</a> checks each one at the maker's own shop {CHECK_FREQ}. <a href="#alerts">Sign up above</a> and we'll email you when a sold-out one comes back. More guides are on the <a href="guides/">guides page</a>.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{src_items}</ol>
<p class="muted small">Each maker sells other dot grid journals too. This guide covers the A5 versions above.</p>
{related_block(fname)}
</article>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title,
           "datePublished": DG_GUIDE_LASTMOD, "dateModified": DG_GUIDE_LASTMOD, "url": url_for(fname), "image": OG_DOTGRID,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, title + TITLE_SUFFIX, desc, body,
                       ld=(crumbs_ld(("guides/", "Guides"), (fname, "Dot grid journals compared")), art, faq_ld),
                       og_type="article", og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT)


def build_guides_index():
    fname = "guides/"
    items = "".join(f'<li><a href="{h}"><strong>{E(t)}</strong></a><br><span class="muted">{E(GUIDE_BLURBS[h])}</span></li>' for h, t in GUIDES)
    body = f"""
<article class="prose">
{crumbs((fname, "Guides"))}
{eyebrow("Guides", f"{len(GUIDES)} guides")}
<h1>Stationery buying guides</h1>
<p class="lede">Short, sourced guides to help you choose and find stationery that sells out. Live stock on the guides comes from the same checks as the tracker, {CHECK_FREQ}.</p>
{signup()}
<ul class="guide-list">{items}</ul>
</article>"""
    lst = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": t, "url": url_for(h)} for i, (h, t) in enumerate(GUIDES)]}
    return fname, page(fname, "Guides: best dot grid journals, where to buy and which Hobonichi to choose · Stationery Drop Watch",
                       "Stationery Drop Watch guides: the best dot grid journals compared, where to buy the Hobonichi Techo 2027 with live stock by shop, Hobonichi Techo vs Cousin vs Weeks, and the 2027 launch and restock calendar.",
                       body, ld=(crumbs_ld((fname, "Guides")), lst))

SHOP_ETSY = [
    dict(title="2027 Printable Planner, Blush", inside="womens", img="assets/shop/womens-2027-printable-planner.jpg",
         alt="2027 printable planner in blush, shown as printed pages", url="https://www.etsy.com/listing/4606759241",
         blurb="The same dated 2027 planner as a PDF you print at home. Sunday start, weekly and monthly pages, dot grid notes."),
    dict(title="2027 Printable Planner for Men", inside="mens", img="assets/shop/mens-2027-printable-planner.jpg",
         alt="2027 printable planner for men in charcoal, shown as printed pages", url="https://www.etsy.com/listing/4606781258",
         blurb="The men's 2027 planner as a PDF you print at home. Weekly and monthly pages, dot grid notes, workout log and budget pages."),
]

# FIX-06: prices on /shop. Amazon list prices were read from each product's own amazon.com page on
# 2026-11-04 (buy box and format swatch; no strikethrough or deal shown). A None here shows "See price on Amazon".
AMAZON_LIST_PRICES = {"B0HPBDNS7F": "$19.99", "B0HQ5TLDK3": "$14.99", "B0HQ5X3C7D": "$16.99",
                      "B0HP9PXSR1": "$14.99", "B0HP85QLMS": "$9.99"}
SHOP_LABELS = {"B0HPBDNS7F": "2027 Planner, Blush", "B0HQ5TLDK3": "Habit & Mood Tracker Journal", "B0HQ5X3C7D": "Reading Journal",
               "B0HP9PXSR1": "2027 Planner for Men", "B0HP85QLMS": "Kids' Goldfish Journal"}
SHOP_ORDER = ("B0HPBDNS7F", "B0HQ5TLDK3", "B0HQ5X3C7D", "B0HP9PXSR1", "B0HP85QLMS")
ETSY_PRICE = ("$6.99", "20% off launch sale Oct 31 to Nov 30")
# Interior previews, web-sized into assets/shop/inside/: our own Etsy listing images (etsy/printables/*/listing-images)
# and, for the Amazon books, interior spreads Kiln exported from the print files (keyed by ASIN). (file stem, caption)
SHOP_INSIDE = {
    "B0HPBDNS7F": [("monthly-calendar-goals-spread-p6-7", "January calendar and Goals & Priorities, pages 6-7"),
                   ("weekly-spread-p12-13", "Weekly spread, Jan 3 to 9, pages 12-13")],
    "B0HQ5TLDK3": [("habit-and-mood-tracker-spread-p6-7", "Habit tracker and mood tracker, pages 6-7"),
                   ("weekly-checkin-spread-p8-9", "Weekly check-in, pages 8-9")],
    "B0HQ5X3C7D": [("genre-tracker-books-read-log-spread-p12-13", "Genre tracker and books-read log, pages 12-13"),
                   ("book-review-spread-p24-25", "Book review pages, pages 24-25")],
    "B0HP9PXSR1": [("monthly-calendar-goals-spread-p6-7", "January calendar and Goals & Priorities, pages 6-7"),
                   ("weekly-spread-p12-13", "Weekly spread, Jan 3 to 9, pages 12-13")],
    "B0HP85QLMS": [("journal-page-spread-p2-3", "Journal pages, pages 2-3 (every page has this layout)")],
    "womens": [("04-weekly-spread-dec27-jan2", "Weekly spread, Dec 27 to Jan 2"), ("05-monthly-calendar-january", "Monthly calendar, January"),
               ("06-habit-tracker-january", "Habit tracker, January")],
    "mens": [("04-weekly-spread-dec27-jan2", "Weekly spread, Dec 27 to Jan 2"), ("05-monthly-calendar-january", "Monthly calendar, January"),
             ("06-habit-tracker-january", "Habit tracker, January")],
}

import hashlib as _hl
ASSET_V = {n: _hl.md5((SITE / 'assets' / n).read_bytes()).hexdigest()[:8] for n in ('style.css', 'app.js')}

def build_shop():
    fname = "shop/"
    books = {b["id"]: b for b in json.loads((ROOT / "content/editor_picks.json").read_text())["books"]}
    labels = SHOP_LABELS
    def srcset(img):  # Etsy mockups ship 600w + 1200w copies; Amazon covers use their single file
        if img.startswith("assets/shop/") and img.endswith("-planner.jpg"):
            b = img[:-4]
            return f' srcset="/{E(b)}-600.jpg 600w, /{E(b)}-1200.jpg 1200w"'
        return ""
    def card(img, alt, title, sub, blurb, details, href, btn, own, price, inside=None):
        dl = "".join(f"<li>{E(d)}</li>" for d in details)
        attr = ' data-own-product' if own else ''
        ins = ""
        if inside:
            figs = "".join(f'<figure><img src="/assets/shop/inside/{inside}-{f}.jpg" alt="{E(title)}: {E(cap)}" loading="lazy" decoding="async"><figcaption>{E(cap)}</figcaption></figure>'
                           for f, cap in SHOP_INSIDE[inside])
            spreads = ' spreads' if inside in AMAZON_LIST_PRICES else ''
            ins = f'<details class="shop-inside"><summary>See inside</summary><div class="inside-grid{spreads}">{figs}</div></details>'
        return f"""<li class="shop-card">
  <a class="shop-img{' photo' if not own else ''}" href="{E(href)}"{attr} rel="noopener" target="_blank"><img src="{E(img)}"{srcset(img)} sizes="(max-width:600px) 240px, 150px" alt="{E(alt)}" loading="lazy" decoding="async"></a>
  <div class="shop-body"><h3>{E(title)}</h3><p class="muted small">{E(sub)}</p>{price}<p>{E(blurb)}</p><ul class="small">{dl}</ul>
  {ins}<a class="btn" href="{E(href)}"{attr} rel="noopener" target="_blank">{E(btn)}</a></div></li>"""
    def amz_price(a):
        lp = AMAZON_LIST_PRICES.get(a)
        if not lp:
            return '<p class="shop-price"><span class="muted">See price on Amazon</span></p>'
        return f'<p class="shop-price"><strong>{E(lp)}</strong> <span class="muted small">List price, check current price on Amazon</span></p>'
    amz = "".join(card(books[a]["cover"], books[a]["cover_alt"], labels[a], books[a]["format"] + " · on Amazon",
                       books[a].get("blurb", ""), books[a].get("details", []), own_amazon_link(books[a]["url"]), "View on Amazon", True,
                       amz_price(a), a if a in SHOP_INSIDE else None)
                  for a in SHOP_ORDER)
    etsy_price = f'<p class="shop-price"><strong>{E(ETSY_PRICE[0])}</strong> <span class="muted small">{E(ETSY_PRICE[1])}</span></p>'
    etsy = "".join(card(e["img"], e["alt"], e["title"], "Printable PDF · instant download from Etsy", e["blurb"],
                        ["US Letter 8.5 x 11 in", "172 pages"], e["url"], "View on Etsy", False, etsy_price, e.get("inside"))
                   for e in SHOP_ETSY)
    body = f"""
<article class="prose shop shop-wide">
{crumbs((fname, "Planners and journals"))}
{eyebrow("Shop", "made by Stationery Drop Watch")}
<h1>{SHOP_NAME}</h1>
<p class="lede">Planners and journals we make. Get a printed copy on Amazon or a printable PDF on Etsy.</p>
{signup("shop")}
<h2>Printed planners and journals on Amazon</h2>
<ul class="shop-list">{amz}</ul>
<h2>Printable PDFs on Etsy</h2>
<ul class="shop-list">{etsy}</ul>
</article>"""
    return fname, page(fname, "Our planners and journals: 2027 planners and journals on Amazon and Etsy · Stationery Drop Watch",
                       "Planners and journals made by Stationery Drop Watch: printed 2027 planners, a habit and mood tracker, a reading journal and a kids' journal on Amazon, plus printable 2027 planner PDFs on Etsy.",
                       body, ld=(crumbs_ld((fname, "Planners and journals")),))

SOCIALS = [  # (platform, handle, url, note, icon letter)
    ("X", "@stationerydrop", "https://x.com/stationerydrop", "Restock alerts the moment we confirm them, plus planner news.", "X"),
    ("Instagram", "@stationerydropwatch", "https://www.instagram.com/stationerydropwatch/", "Planner photos and restock alerts.", "IG"),
    ("Threads", "@stationerydropwatch", "https://www.threads.com/@stationerydropwatch", "Restock alerts and planner chat.", "@"),
    ("Bluesky", "@stationerydropwatch.com", "https://bsky.app/profile/stationerydropwatch.com", "Restock alerts and planner news.", "B"),
    ("Pinterest", "@stationerydropwatch", "https://www.pinterest.com/stationerydropwatch/", "Planner pins and guides to save for later.", "P"),
    ("Facebook", "Stationery Drop Watch", "https://www.facebook.com/stationerydropwatch", "Restock alerts and planner news on our Page.", "f"),
    ("Reddit", "u/stationerydropwatch", "https://www.reddit.com/user/stationerydropwatch/", "Where we join planner conversations.", "r/"),
]

def build_follow():
    fname = "follow/"
    rows = "".join(f"""<li class="follow-card"><span class="follow-ico" aria-hidden="true">{E(ic)}</span>
  <div class="follow-text"><h3>{E(n)}</h3><p class="muted small">{E(h)}</p><p class="small">{E(note)}</p></div>
  <a class="btn" href="{E(u)}" rel="noopener" target="_blank">Follow on {E(n)}</a></li>""" for n, h, u, note, ic in SOCIALS)
    body = f"""
<article class="prose follow">
{crumbs((fname, "Follow us"))}
{eyebrow("Follow us", f"{len(SOCIALS)} apps")}
<h1>Follow us</h1>
<p class="lede">We post restock alerts and planner news. Pick the app you already use.</p>
{signup()}
<ul class="follow-list">{rows}</ul>
</article>"""
    return fname, page(fname, "Follow us · Stationery Drop Watch",
                       "Follow Stationery Drop Watch on X, Instagram, Threads, Bluesky, Pinterest, Facebook and Reddit for restock alerts and planner news.",
                       body, ld=(crumbs_ld((fname, "Follow us")),))

def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/stock.json", SITE / "data/stock.json")
    shutil.copy(ROOT / "data/changes.json", SITE / "data/changes.json")
    (SITE / "index.html").write_text(build_index())
    (SITE / HOBO_TRACKER).mkdir(parents=True, exist_ok=True)
    (SITE / HOBO_TRACKER / "index.html").write_text(build_hobo_tracker())
    (SITE / "hobonichi-2027.html").write_text(build_hobonichi())
    (SITE / "about.html").write_text(build_about())
    (SITE / "404.html").write_text(build_404())
    oe = amazon_main(stock["products"])
    for g in GROUPS:
        fname, doc = build_group(g, oe)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for d in DESIGNS:
        fname, doc = build_design(d, oe)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for build in (build_where_to_buy, build_vs, build_dotgrid_guide, build_guides_index, build_shop, build_follow):
        fname, doc = build()
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for old, new in REDIRECTS.items():
        (SITE / old).mkdir(parents=True, exist_ok=True)
        (SITE / old / "index.html").write_text(redirect_page(new))
    (SITE / "sitemap.xml").write_text(build_sitemap())
    (SITE / "robots.txt").write_text(ROBOTS)
    (SITE / "CNAME").write_text(CNAME + "\n")
    print("built", sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*.html")), "+ sitemap.xml, robots.txt, CNAME")

if __name__ == "__main__":
    main()
