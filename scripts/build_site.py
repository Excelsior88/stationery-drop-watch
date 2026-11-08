#!/usr/bin/env python3
"""Build the static site in site/ from stores.json, data/*.json and content/*.json.
Never invents data: every status shown comes from data/stock.json written by checker.py.
A recent-restock row keeps the historical event time, and its status is the latest check."""
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
    # Slugs stay on the published URLs. Visible names describe what the page tracks.
    # /archer-and-olive-dot-grid-journal/ covers all four dot-grid makers, not Archer and Olive alone.
    # /travelers-company-limited-edition/ covers Regular size colors and limited editions. Renaming either
    # URL needs a planned redirect, not a silent slug change.
    "dotgrid": dict(slug="archer-and-olive-dot-grid-journal", nav="Dot grid journals", name="dot grid journals",
                    foot="Dot grid journaling", link="Dot grid journals", count="dot grid journals",
                    one="dot grid journal", amazon=None),
    "travelers": dict(slug="travelers-company-limited-edition", nav="Traveler's Company",
                      name="Traveler's Notebook regular colors and limited editions",
                      foot="Traveler's Company", link="Regular colors and limited editions", count="Traveler's Company",
                      one="Traveler's Notebook regular-color and limited-edition", amazon="travelers"),
    "midori": dict(slug="midori-md-limited-edition", nav="MIDORI MD", name="MIDORI MD seasonal releases",
                   foot="MIDORI MD", link="Seasonal releases", count="MIDORI MD",
                   one="MIDORI MD seasonal release", amazon="midori"),
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

# Shop's home country, from its own site or domain (stores.json "country", first word). Never a shipping claim.
_REGION_FIX = {"travelerscompanyusa": "US", "tokyopenshop": "US", "mdproductusa": "US"}  # US company sites (Tokyo Pen Shop: Fairfield, Iowa)
REGION = {x["id"]: _REGION_FIX.get(x["id"]) or (x.get("country") or "").split()[0] for x in stores["stores"]}
REGION_NAME = {"US": "United States", "CA": "Canada", "SG": "Singapore", "UK": "United Kingdom", "JP": "Japan"}
assert all(REGION[x["id"]] in REGION_NAME for x in stores["stores"]), "every shop needs a country tag"

# A shop whose name ends with its country (e.g. "Leuchtturm1917 US") shows the plain name plus the
# country tag, like every other shop, so the country never appears twice.
_STRIP = {}
for _x in stores["stores"]:
    _sfx = " " + REGION[_x["id"]]
    if _x["name"].rstrip().upper().endswith(_sfx):
        _STRIP[_x["name"]] = _x["name"].rstrip()[:-len(_sfx)]
        _x["name"] = _STRIP[_x["name"]]
for _r in stock["products"] + changes + stock.get("not_checked", []):
    for _k in ("store", "name"):
        if _r.get(_k) in _STRIP:
            _r[_k] = _STRIP[_r[_k]]

def region_legend(store_ids):
    """One-line key for the country tags in the stock tables below or above it: where each shop is based."""
    cs = sorted({REGION.get(i) for i in store_ids if REGION.get(i)}, key=list(REGION_NAME).index)
    if not cs:
        return ""
    return ('<p class="muted small region-legend">Country tags show where each shop is based, not where it ships: '
            + ", ".join(f'<span class="region">{c}</span> {REGION_NAME[c]}' for c in cs) + ".</p>")

def nshops(n, w="shop"):
    return f"{n} {w}" if n == 1 else f"{n} {w}s"

def region_tag(store_id):
    r = REGION.get(store_id, "")
    return f' <span class="region" title="Shop based in {REGION_NAME[r]}">{r}</span>' if r else ""

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
    """No-JS label for one instant: "Nov 3, 11:47 AM ET" (the year is added only when it isn't this year).
    "ET" is America/New_York. It is not the visitor's zone. local-time.js rewrites time.time-instant when it can."""
    t = dt.datetime.fromisoformat(iso).astimezone(ET)
    yr = f", {t.year}" if t.year != dt.datetime.now(ET).year else ""
    return t.strftime("%b %-d") + yr + t.strftime(", %-I:%M %p ET")

def time_tag(iso):
    """An instant. datetime stays the stored ISO timestamp. The text is Eastern Time until local-time.js runs."""
    return f'<time class="time-instant" datetime="{E(iso)}">{E(fmt_et(iso))}</time>'

def checked_line(ls):
    """Every "checked" stamp on the site is the run's one check time (stock["run_finished"])."""
    return f'checked {time_tag(stock["run_finished"])}' if ls else ""

GUIDE_DATES = ROOT / "data/guide_dates.json"

def guide_updated(fn):
    """A guide's "updated" date: the day its template (the build function's source) last changed.
    Stored as {name: {hash, date}} in data/guide_dates.json; stock rebuilds don't move it."""
    import hashlib, inspect, json as _j
    db = _j.loads(GUIDE_DATES.read_text()) if GUIDE_DATES.exists() else {}
    h = hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()[:16]
    e = db.get(fn.__name__)
    if not e or e["hash"] != h:
        e = db[fn.__name__] = {"hash": h, "date": dt.datetime.now(ET).date().isoformat()}
        GUIDE_DATES.write_text(_j.dumps(db, indent=1, sort_keys=True) + "\n")
    d = dt.date.fromisoformat(e["date"])
    return f"updated {d.strftime('%b')} {d.day}, {d.year}"

STATUS = {"in_stock": "In stock", "preorder": "Preorder", "coming_soon": "Not yet on sale",
          "sold_out": "Sold out", "unknown": "Couldn't check"}
DOTGRID_SLUG = SECTIONS["dotgrid"]["slug"]
TN_GUIDE_SLUG = "travelers-notebook-regular-vs-passport-vs-card-size"
# Old slugs that now redirect (meta refresh + canonical) to their new page. Never listed in the sitemap.
REDIRECTS = {"archer-and-olive-bullet-journal": DOTGRID_SLUG + "/",
             "travelers-notebook-regular-size": SECTIONS["travelers"]["slug"] + "/#tracker"}  # Regular colors merged into the Traveler's Company page
# Home is a hub; the Hobonichi tracker (the old homepage content) lives on its own page.
HOBO_TRACKER = "hobonichi-restock-tracker/"
# Header: one link per restock tracker, then the rest of the site. Wraps on narrow screens; nothing is hidden.
# NAV is not part of the tracker count. The calendar, guides, and shop are resources, not extra trackers.
NAV_TRACKERS = [(HOBO_TRACKER, "Hobonichi tracker")] + [(SECTIONS[k]["slug"] + "/", SECTIONS[k]["nav"]) for k in LIVE]
NAV = [("hobonichi-2027.html", "2027 calendar"), ("guides/", "Guides"), ("shop/", "Planners and journals"),
       ("follow/", "Follow us"), ("about.html", "About")]

def tracker_count_label():
    """Eyebrow count of restock trackers only (Hobonichi plus each section that has listings)."""
    n = len(NAV_TRACKERS)
    return f"{n} restock tracker" if n == 1 else f"{n} restock trackers"
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
# The card artwork is "Hobonichi Techo 2027 restock tracker / Books, Weeks & covers · checked about every 30 minutes".
# It prints no shop count. This same file is the default image on the hub (all trackers), Hobonichi pages
# (Hobonichi shops only), and guides, so a single number in the alt cannot be true on every page.
# Hobonichi shop totals stay in Hobonichi copy, derived from N_SEC["hobonichi"]. The all-tracker total is N_STORES.
OG_ALT = ("Stationery Drop Watch: Hobonichi Techo 2027 restock tracker. "
          f"Books, Weeks and covers, checked {CHECK_FREQ}")
OG_DOTGRID = BASE + "assets/brand/og-dotgrid.png"  # same script; used on the dot grid journaling page
OG_DOTGRID_ALT = "Stationery Drop Watch: dot grid journal restock tracker for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, checked " + CHECK_FREQ
OG_TRAVELERS = BASE + "assets/brand/og-travelers.png"
# Matches the card: regular size colors, 2027 diary accessories, limited editions. No shop count on the artwork.
OG_TRAVELERS_ALT = ("Stationery Drop Watch: Traveler's Notebook restock tracker. "
                    "Regular size colors, 2027 diary accessories and limited editions, at official and independent shops, checked " + CHECK_FREQ)
OG_MIDORI = BASE + "assets/brand/og-midori.png"
# The approved 8 Nov 2026 card. It says these words and does not mention the check cadence.
OG_MIDORI_ALT = ("Stationery Drop Watch: MIDORI restock tracker. "
                 "Diaries, diary stickers and paper. stationerydropwatch.com")
MIDORI_OG_SHA = "1aa303925736d8469c7aae3c8e84c745e057451f82e2d95765deed23862cccde"

def _require_midori_card():
    import hashlib
    digest = hashlib.sha256((ROOT / "site/assets/brand/og-midori.png").read_bytes()).hexdigest()
    if digest != MIDORI_OG_SHA:
        raise SystemExit("og-midori.png is not the approved 8 Nov 2026 artwork")

_require_midori_card()
CONTENT_LASTMOD = "2026-11-08"  # last copy/structure change on the home and restock pages (sitemap lastmod floor)
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
    guide_page = fname in ("where-to-buy-hobonichi-2027/", "hobonichi-techo-vs-cousin-vs-weeks/", "best-dot-grid-journals/", TN_GUIDE_SLUG + "/")  # guides sit under Guides (the calendar keeps its own nav item)
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
{"".join(f'  <p class="foot-links">{E(SECTIONS[k]["foot"])}: <a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["link"])}</a> <span class="muted">({E(shop_names(k))})</span></p>' + chr(10) for k in LIVE)}  <p class="foot-links">Site: <a href="about.html">About</a> · <a href="about.html#sponsor">Featured shop slot</a> · <a href="privacy.html">Privacy</a> · <a href="mailto:stationerydropwatch@gmail.com">Contact</a></p>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it.</p>
  <p class="disclosure">{E(AFFILIATE_NOTE)}</p>
</div></footer>
<script src="assets/local-time.js?v={ASSET_V['local-time.js']}" defer></script>
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
    if kind == "shop" and shop_inserts_public():
        label = "Hear about new planners, journals, and inserts"
        note = "An occasional email when we release a new planner, journal, or printable insert, plus our restock alerts. No spam, unsubscribe anytime."
    return f"""<section class="signup-strip" id="alerts" aria-label="{E(label)}">
  <form class="signup-form embeddable-buttondown-form" action="{SIGNUP_ACTION}" method="post">
    <label class="strip-label" for="email-top">{E(label)}</label>
    <input id="email-top" type="email" name="email" placeholder="you@example.com" required autocomplete="email">
    <input type="hidden" value="1" name="embed">
    <button type="submit">Notify me</button>
  </form>
  <p class="strip-note">{E(note)} Sent via <a href="https://buttondown.com/{NEWSLETTER}" target="_blank" rel="noopener">Buttondown</a>. <a href="privacy.html">Privacy</a></p>
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
        out[k] = dict(url=url, label=label, exact=exact, note=oe_note(ls), listings=ls)
    return out

def oe_note(ls):
    n = len({l["store_id"] for l in ls})
    sts = {l["status"] for l in ls}
    if sts == {"sold_out"}:
        note = "Sold out at every shop we track" if n > 1 else "Sold out at the only shop we track"
    elif sts == {"coming_soon"}:
        note = "Not on sale yet at any shop we track" if n > 1 else "Not on sale yet at the only shop we track"
    else:
        note = "Sold out or not yet on sale at every shop we track"
    return f"{note} ({n} shops)" if n > 1 else note

def page_amz(ls, oe):
    """Top Amazon button for a set of listings shown together. Only offered when every one of
    those listings is sold out / not yet on sale; the note is worded over all of them."""
    if not ls or any(l["status"] not in NOT_BUYABLE for l in ls):
        return None
    keys = list(dict.fromkeys(oe_key(l) for l in ls))
    if exact_only(ls[0].get("canonical")) and len(keys) > 1:  # several exact sizes: no single Amazon match
        return None
    m = next((oe[k] for k in keys if k in oe), None)
    if not m:
        return None
    m = dict(m, note=oe_note(ls))
    check_amz_note(ls, m["note"])
    return m

def check_amz_note(ls, note):
    if any(l["status"] not in NOT_BUYABLE for l in ls):
        raise SystemExit(f"top Amazon note '{note}' contradicts a listing that is buyable or unchecked: {ls[0]['url']}")

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
        + "".join(f'<tr class="child"><td><a href="{E(r["u"])}" target="_blank" rel="noopener">{E(r["s"])}</a>{region_tag(r["sid"])}<span class="sub variant">{E(r["p"])}</span></td><td><span class="badge {r["st"]}">{STATUS[r["st"]]}</span></td></tr>' for r in ls)
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
      {region_legend(p["store_id"] for p in prods)}
      {extra}
    </section>"""

def tracker_rows(prods, out_everywhere):
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    rows = [dict(g=product_key(p), p=p["label"], gn=canon.get(p.get("canonical") or "", p["label"]), c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], rg=REGION.get(p["store_id"], ""), st=p["status"],
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

# Recent restocks are a history of flips. The status pill is the latest check, not the flip.
RESTOCK_NOW_NOTE = ("The time is when it came back. "
                    '<span class="time-zone-note">Times are labeled Eastern Time.</span> '
                    "The status is the latest check.")

def availability_now(url):
    """Latest known availability for one listing URL.

    Uses the current stock check only. The restock event's `to` value is the status at that
    moment, not availability now. A missing, conflicting, or unrecognized check is not in stock.
    """
    hits = [p for p in stock["products"] if p.get("url") == url]
    statuses = {p.get("status") for p in hits}
    if len(statuses) == 1:
        st = next(iter(statuses))
        if st in STATUS:
            return st, STATUS[st]
    return "unknown", "No current check"

def restock_groups(events):
    """One group per listing URL, newest event first. A different shop, variant, or edition has a different URL."""
    groups, order = {}, []
    for c in events:
        key = c.get("url") or ""
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)
    return [groups[k] for k in order]

def restock_feed_item(c, extra=""):
    """One listing: current availability, the newest restock, and any earlier ones in this list collapsed."""
    events = c if isinstance(c, list) else [c]
    newest = events[0]
    st, label = availability_now(newest["url"])
    ex = extra(newest) if callable(extra) else extra
    earlier = events[1:]
    history = ""
    if earlier:
        n = len(earlier)
        word = "restock" if n == 1 else "restocks"
        rows = "".join(f'<div class="feed-earlier">restocked {time_tag(old["at"])}</div>' for old in earlier)
        history = f'<details class="feed-history"><summary>Earlier {word} ({n})</summary>{rows}</details>'
    return f"""<li class="feed-item" data-now="{E(st)}"><span class="feed-now">now <span class="badge {E(st)}">{E(label)}</span></span>
  <a href="{E(newest['url'])}" rel="noopener" target="_blank">{E(newest['label'])}</a> <span class="muted">at {E(newest['store'])}</span>
  {ex}<span class="feed-when">restocked {time_tag(newest['at'])}</span>{history}</li>"""

def restock_feed(events, extra="", feed_id="restocks", limit=None):
    """Grouped restocks. `limit` is how many listings to show, not how many flips. In stock now is CSS-only."""
    groups = restock_groups(events)
    if limit is not None:
        groups = groups[:limit]
    fid = E(feed_id)
    items = "".join(restock_feed_item(g, extra) for g in groups)
    return f"""<div class="restocks" id="{fid}">
  <div class="feed-controls" role="radiogroup" aria-label="Which restocks to show">
    <label><input type="radio" name="{fid}-view" class="restock-all" checked> All</label>
    <label><input type="radio" name="{fid}-view" class="restock-in"> In stock now</label>
  </div>
  <ol class="feed">{items}</ol>
  <p class="feed-empty muted small">None of these are in stock now.</p>
</div>"""

def build_hobo_tracker():
    """The full Hobonichi tracker (the old homepage), now at HOBO_TRACKER. Copy, FAQ and FAQ schema unchanged."""
    prods = hobo_products()  # Hobonichi section only; dot grid shops live on their own page
    s = {k: sum(p["status"] == k for p in prods) for k in STATUS}
    checked = sum(v for k, v in s.items() if k != "unknown")
    urls = {p["url"] for p in prods}
    restocks = [c for c in changes if c["url"] in urls and c["to"] in ("in_stock", "preorder") and c["from"] in ("sold_out", "coming_soon")]
    restocks.sort(key=lambda c: c["at"], reverse=True)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=14)
    recent = [c for c in restocks if dt.datetime.fromisoformat(c["at"]) >= cutoff]
    if recent:
        feed_html = f'<p class="muted small">{RESTOCK_NOW_NOTE}</p>' + restock_feed(recent, feed_id="hobo-restocks", limit=12)
    else:
        start = tracking_start(prods)
        lead = "No restocks spotted yet." if not restocks else "No restocks in the last 14 days."
        feed_html = f"""<div class="empty"><p><strong>{lead}</strong> Tracking started {time_tag(start)}.
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
        shops = "".join(f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["store"])}</a>{region_tag(l["store_id"])} <span class="badge {E(l["status"])}">{E(STATUS[l["status"]])}</span></li>' for l in m["listings"])
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
  <p class="shop-cta"><a class="btn-ghost" href="shop/">{SHOP_NAME} →</a> <span class="muted small">{shop_cta_line()}</span></p>
  <p class="small section-switch">Also tracked: {" · ".join(f'<a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a>' for k in LIVE)}</p>
  {signup()}
  <div class="stats{' five' if s['unknown'] else ''}">
    <div><b>{s['in_stock']}</b><span>in stock</span></div>
    <div><b>{s['preorder']}</b><span>preorder</span></div>
    <div><b>{s['sold_out']}</b><span>sold out</span></div>
    <div><b>{s['coming_soon']}</b><span>not yet on sale</span></div>
    {f'<div class="unk"><b>{s["unknown"]}</b><span>couldn' + "'" + 't check this run</span></div>' if s['unknown'] else ''}
  </div>
  <p class="muted small">Last check: {time_tag(stock['run_finished'])} · {checked} of {len(prods)} listings checked successfully.</p>
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
    # Live listings are the five Regular colors, the ROAD TRIP exclusive, anniversary sets, and 2027 diary
    # accessories. Refills and Passport size are not listings on this tracker (the size guide says so).
    "travelers": ("Traveler's Company", "Regular size colors, plus limited editions: 2027 diary accessories, anniversary sets and shop exclusives."),
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
    recent = [c for c in restocks if dt.datetime.fromisoformat(c["at"]) >= cutoff]
    short = {"hobonichi": "Hobonichi", **{k: SECTIONS[k]["nav"] for k in LIVE}}
    def hub_tag(c):
        sec = sec_of_url[c["url"]]
        return f'<a class="hub-tag" href="{href[sec]}">{E(short[sec])}</a>\n  '
    if recent:
        feed_html = restock_feed(recent, hub_tag, feed_id="hub-restocks", limit=12)
    else:
        start = tracking_start(prods)
        lead = "No restocks spotted yet." if not restocks else "No restocks in the last 14 days."
        feed_html = f"""<div class="empty"><p><strong>{lead}</strong> Tracking started {time_tag(start)}.
  A restock shows up here the moment a sold-out item flips back to in stock or preorder between two checks.</p>
  <p class="muted">Right now: {s['sold_out']} tracked listings are sold out and {s['coming_soon']} aren't on sale yet.</p></div>"""
    guides = "".join(f'<li><a href="{h}">{E(t)}</a>{f"<p class=\"muted small\">{E(GUIDE_BLURBS[h])}</p>" if h in GUIDE_BLURBS else ""}</li>' for h, t in GUIDES)
    books = {b["id"]: b for b in picks["books"]}
    own = []
    for a in SHOP_ORDER:
        b = books[a]
        if not b.get("cover"):
            continue
        own.append((b["cover"], b["cover_alt"], SHOP_LABELS[a], b["format"], "",
                    b.get("cover_w", 200), b.get("cover_h", 300)))
    own += [(e["img"], e["alt"], e["title"], e.get("hub_sub", "Printable PDF"), e.get("img_class", ""), e.get("img_w", 200), e.get("img_h", 300))
            for e in etsy_listings()]
    row_cls = "hub-own-row" + {8: " cols-8", 9: " cols-9"}.get(len(own), "")
    own_html = "".join(
        f'<li><a href="shop/"><img{f" class=\"{E(cls)}\"" if cls else ""} src="{E(img)}" alt="{E(alt)}" loading="lazy" decoding="async" width="{w}" height="{h}"><span class="hub-own-t">{E(t)}</span><span class="muted small">{E(sub)}</span></a></li>'
        for img, alt, t, sub, cls, w, h in own)
    faq_html, _ = faq_block(only=HUB_FAQ, sid="good-to-know")
    unk = f' <span class="unk-note">{s["unknown"]} couldn\'t be checked this run.</span>' if s["unknown"] else ""
    body = f"""
<section class="hero">
  {eyebrow(tracker_count_label(), f"{N_STORES} shops", f"checked {CHECK_FREQ}")}
  <h1>Know the moment your planner or journal is back.</h1>
  <p class="lede">We check official stores and independent shops for sold-out Hobonichi planners, dot grid journals, Traveler's Company notebooks and MIDORI MD releases, and tell you when they come back.</p>
  <p class="small section-switch">Also on the site, separate from the trackers: <a href="hobonichi-2027.html">2027 calendar</a> · <a href="guides/">Guides</a> · <a href="shop/">Planners and journals</a>.</p>
  {signup()}
  <p class="muted small hub-status">Last check: {time_tag(stock['run_finished'])} · {checked} of {len(prods)} listings checked successfully.{unk}</p>
</section>

<section class="hub-trackers" id="trackers" aria-labelledby="trackers-h">
  <h2 id="trackers-h">Pick a tracker</h2>
  <ul class="hub-grid">{"".join(cards)}</ul>
</section>

<div class="hub-cols">
  <section class="card" id="restocked">
    <h2>Recent restocks</h2>
    <p class="muted small">Every tracker, newest first. Last 14 days.{' ' + RESTOCK_NOW_NOTE if recent else ''}</p>
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
  <p class="muted small">{E(shop_hub_line())}</p>
  <ul class="{row_cls}">{own_html}</ul>
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
""" + crumbs(("guides/", "Guides"), ("hobonichi-2027.html", "2027 calendar")) + eyebrow("Guide", "Hobonichi Techo 2027", guide_updated(build_hobonichi)) + """
<h1>Hobonichi Techo 2027 launch &amp; restock calendar</h1>
<p class="lede">Hobonichi sells its planners in two big drops a year, and popular covers can sell out within minutes. Here's how the 2027 season has gone so far and when stock usually comes back.</p>
""" + signup() + """

<h2 class="sr">2027 timeline</h2>
<ol class="timeline">
  <li><time>Aug 25, 2026</time><div><h3 class="tl">Previews go up</h3><p>Shops post the 2027 lineup as "out of stock" or "coming soon" pages. They aren't sold out; they're just not on sale yet. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Aug 31, 2026 · 10 PM ET</time><div><h3 class="tl">Worldwide launch (January-start planners)</h3><p>Everything goes live at the same moment worldwide: 11 AM on September 1 in Japan, 10 PM ET / 9 PM CT the night before in the US. Atlas Stationers warned that popular styles and collaborations "often sell out within minutes." <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-atlas">[Atlas]</a></p></div></li>
  <li><time>Sep 30 – Oct 1, 2026</time><div><h3 class="tl">Second fall wave</h3><p>Hobonichi notes that some products begin sales on October 1. At US shops that meant the ONE PIECE magazine collection and the Weeksdays 2027 desk calendar, plus a large restock of earlier sell-outs (as preorders at some shops). <a href="#s-1101">[Hobonichi]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Early–mid Oct 2026</time><div><h3 class="tl">First restocks land at indie shops</h3><p>Atlas expected its first restock in early October. Paper Mouse's shipment arrived October 15 and preorders began shipping. <a href="#s-atlas">[Atlas]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>February 2027</time><div><h3 class="tl">Spring launch (April-start planners)</h3><p>The second yearly release, timed to Japan's April academic and fiscal year. Expect another rush on new covers. <a href="#s-papermouse">[Paper Mouse]</a> <a href="#s-1101">[Hobonichi]</a></p></div></li>
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
""" + design_links_block() + related_block("hobonichi-2027.html") + """
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

def build_privacy():
    fname = "privacy.html"
    body = f"""
<article class="prose">
{crumbs((fname, "Privacy"))}
{eyebrow("Privacy", "updated Nov 4, 2026")}
<h1>Privacy</h1>
<p class="lede">What this site collects, who handles it, and how to reach us. In short: your email address if you sign up for alerts, and cookie-free page view counts.</p>
<h2>Email alerts (Buttondown)</h2>
<p>If you sign up for restock alerts, your email address goes to <a href="https://buttondown.com/{NEWSLETTER}" target="_blank" rel="noopener">Buttondown</a>, the service that stores the list and sends the emails. We use it only to send the alerts and occasional updates you signed up for. Every email has an unsubscribe link, and you can also email us to be removed. Buttondown's own privacy policy is at <a href="https://buttondown.com/legal/privacy" target="_blank" rel="noopener">buttondown.com/legal/privacy</a>.</p>
<h2>Page view counts (Cloudflare Web Analytics)</h2>
<p>The site is hosted on Cloudflare Pages and uses Cloudflare Web Analytics to count visits. It doesn't use cookies or local storage and doesn't follow you across other sites. Cloudflare also handles standard request data, such as your IP address, to deliver and protect the site. See <a href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener">Cloudflare's privacy policy</a>.</p>
<p>This site doesn't set its own cookies and doesn't run ad trackers.</p>
<h2>Amazon and affiliate links</h2>
<p>{E(AFFILIATE_NOTE)} When you open an Amazon link, Amazon may set its own cookies to credit the referral; that happens on Amazon's side under <a href="https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ" target="_blank" rel="noopener">Amazon's privacy notice</a>. Links to the shops we track are plain links, and what you do on their sites is covered by their own policies.</p>
<h2>Contact</h2>
<p>Questions, or want your email address removed? Email <a href="mailto:stationerydropwatch@gmail.com">stationerydropwatch@gmail.com</a>.</p>
</article>"""
    return page(fname, "Privacy", "How Stationery Drop Watch handles email signups (Buttondown), cookie-free Cloudflare Web Analytics and Amazon affiliate links.", body, ld=(crumbs_ld((fname, "Privacy")),))

def build_about():
    n_checked = N_STORES  # same count as the FAQ and footer: shops the checker actually checks
    body = f"""
<article class="prose">
{crumbs(("about.html", "About"))}
{eyebrow("About", "how we check stock")}
<h1>About Stationery Drop Watch</h1>
<p class="lede">Limited planners sell out fast, and every shop only posts its own restocks. This site checks them all in one place.</p>
{signup()}
<section class="couple" aria-labelledby="couple-h">
<h2 id="couple-h">The couple behind Drop Watch <span class="tag-soon">Coming soon</span></h2>
<p>Drop Watch is run by a couple. He built the tracker after seeing how frustrating it was for his partner to keep up with planner restocks, and now they run it together. Our story and a look at the planners we use are coming soon.</p>
</section>
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
         # Published URL stays /archer-and-olive-dot-grid-journal/ so existing links keep working.
         # The title, heading, nav, and breadcrumb name every maker we check, with Archer and Olive featured first.
         title=f"Dot grid journal restock tracker: {dotgrid_names()}",
         desc=f"Are {dotgrid_names()} dot grid journals in stock? Live size-by-size status from each maker's own store, checked {CHECK_FREQ}, with Archer and Olive featured first.",
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Popular dot grid journals and limited editions sell out, and every brand only posts its own restocks. "
               f"We track a focused set of flagship dot grid notebooks from {dotgrid_names()}, each on that maker's own store, size by size and color by color, plus Archer and Olive's dot grid refills. "
               "Archer and Olive is featured first. This page covers those dot grid notebooks and refills, not pens or other paper, and Hobonichi and our other sections have their own pages."),
    dict(slug=SECTIONS["travelers"]["slug"], short="Traveler's Company", product="Traveler's Notebook", section="travelers",
         h1="Traveler's Notebook restock tracker: regular colors and limited editions",
         match=lambda p: section_of(p) == "travelers", eyebrow="Traveler's Company", search_hint="Sticker set, Olive, 20th…",
         guide="Traveler's Company makes its limited editions in small runs, and each shop gets its own allocation, so one shop can sell out while another still has stock. "
               "We also track the five standard Regular size notebooks: Black (No. 13714006), Brown (No. 13715006), Blue (No. 15239006), Camel (No. 15193006) and Olive (No. 15342006). "
               "Traveler's Company warns that counterfeits are sold in the US, so we only list the official US shop and authorized retailers. For refills, check the shops directly. "
               f'Choosing Regular, Passport, or the Card Size anniversary set: <a href="{TN_GUIDE_SLUG}/">Regular vs Passport vs Card Size</a>.',
         # Published URL stays /travelers-company-limited-edition/. The heading names Regular colors and limited editions.
         title="Traveler's Notebook restock tracker: regular colors and limited editions",
         desc="Are the Traveler's Notebook Regular size colors (Black, Brown, Blue, Camel, Olive), 2027 diary accessories and 20th anniversary sets in stock? Live status at {shops} official and independent shops, checked " + CHECK_FREQ + ".",
         og_image=OG_TRAVELERS,
         og_alt=OG_TRAVELERS_ALT,
         intro="We track the five Regular size Traveler's Notebook colors (Black, Brown, Blue, Camel and Olive) plus Traveler's Company limited editions: the yearly diary accessories, anniversary sets and shop exclusives. "
               "We check the official Traveler's Company USA shop and independent shops, item by item. "
               "Hobonichi and our other sections have their own pages."),
    dict(slug=SECTIONS["midori"]["slug"], short="MIDORI MD", product="MIDORI MD seasonal release", section="midori",
         match=lambda p: section_of(p) == "midori", eyebrow="MIDORI MD", search_hint="Diary 2027, 1 Day 1 Page, Stickers…",
         guide="MIDORI makes the dated MD diaries and diary stickers once a year, so when a shop's allocation is gone it is usually gone until the next year's edition. "
               "The plain MD notebooks stay in the catalog all year, so we don't track them here.",
         title=f"MIDORI MD seasonal release restock tracker",
         desc="Are the MIDORI MD Notebook Diary 2027, the 1 Day 1 Page diary and the 2027 diary stickers in stock? Live status at {shops} official and independent shops, checked " + CHECK_FREQ + ".",
         og_image=OG_MIDORI,
         og_alt=OG_MIDORI_ALT,
         intro="MIDORI's MD line is sold as MD PRODUCT in 2026. The dated 2027 diaries, diary stickers and online store limited editions come once a year, in set quantities. "
               "We check the official MD PRODUCT USA store and independent shops, size by size. "
               "This covers MIDORI MD seasonal releases only; Hobonichi and our other sections have their own pages."),
]
for _g in GROUPS:  # one name per page: H1 is "<product> restock tracker" unless the group sets a wider h1
    _g.setdefault("h1", _g["product"] + " restock tracker")
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
        since_html = f'<span class="sub">since {time_tag(since)}</span>' if since and l["status"] != "unknown" else ""
        rows.append(f"""<tr><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a>{region_tag(l['store_id'])}<span class="sub">{E(l.get('title') or l['label'])}</span></td>
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
        m = page_amz(sl, oe) if cid else None
        amz_btn = (f'<p><a class="btn btn-amz" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a> '
                   f'<span class="muted small">{E(m["note"])}.</span></p>') if m else ""
        az_url, az_label = amazon_for(cid, sl[0]["url"])
        az_sub = "" if m or not az_url or exact_only(cid) else f' · <a class="az" href="{E(az_url)}" target="_blank">{E(az_label)}</a>'
        tracker = ("" if ext else
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
            parts.append(f"""<h2 class="shop-head" id="shop-{E(sid)}"><span><a href="{E(st['url'])}" rel="noopener" target="_blank">{E(st['name'])}</a>{region_tag(sid)}</span>{feat}
  <span class="muted small">{E(count_line(sls).capitalize())}</span></h2>""")
        parts.append(f"""<section class="card group-sec" id="{E(cid or 'other')}">
  <div class="section-head"><{hx}>{E(name)}</{hx}><p class="muted small">{E(count_line(sl, g.get('unit', 'listings')).capitalize())} · {checked_line(sl)}</p></div>
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(sl, oe)}</tbody>
  </table></div>
  <p class="muted small">{g.get('open_hint', "Open a shop's name to go straight to its listing")}{az_sub}{tracker}{dp_link}</p>
  {"" if any("region-legend" in x for x in parts) else region_legend(l["store_id"] for l in ls)}
</section>""")
    unk = [l for l in ls if l["status"] == "unknown"]
    if len(unk) == len(ls):
        right_now = ("we couldn't reach the shop for this listing at the last check, so its status is unknown." if len(ls) == 1 else f"we couldn't check any of these {len(ls)} listings at the last check, so their status is unknown.")
    else:
        right_now = (f"{len(buy)} of {len(ls) - len(unk) if unk else len(ls)} {'checked ' if unk else ''}listings are in stock or on preorder "
                     f"at {len({l['store_id'] for l in buy})} of {nshops(len({l['store_id'] for l in ls if l['status'] != 'unknown'})) + ' we could check' if unk else nshops(shops)}."
                     + (f" {len(unk)} couldn't be checked this run." if unk else ""))
    lead_n = 2 if per_shop else 1  # shop-by-shop pages: first shop heading + its first card
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and c["to"] in BUYABLE and c["from"] in NOT_BUYABLE],
                key=lambda c: c["at"], reverse=True)[:10]
    if rs:
        restock_html = f'<p class="muted small">{RESTOCK_NOW_NOTE}</p>' + restock_feed(rs, feed_id=g["slug"] + "-restocks")
    else:
        start = tracking_start(ls)
        restock_html = f'''<div class="empty"><p><strong>No restocks spotted yet.</strong> Tracking started {time_tag(start)}.
  A restock shows up here the moment a sold-out listing flips back to in stock or preorder between two checks.</p></div>'''
    others = "".join(f'<li><a href="{x["slug"]}/">{E(x["short"])}</a></li>' for x in GROUPS if x is not g and (g_sec(x) != "hobonichi") == ext)
    if ext:
        others += f'<li><a href="#tracker">Every {E(SECTIONS[g_sec(g)]["one"])} listing we track (this page)</a></li>'
        if per_shop:
            shop_ids = sorted({l["store_id"] for l in ls}, key=lambda sid: rank[sid])
            shop_nav = "".join(f'<a class="chip" href="#shop-{E(sid)}">{E(next(x["name"] for x in stores["stores"] if x["id"] == sid))}</a>' for sid in shop_ids)
            shop_nav = f'<nav class="chips" aria-label="Shops on this page"><span class="muted small">Jump to a shop:</span> {shop_nav}</nav>'
        else:  # products span several shops: jump by product instead
            shop_nav = "".join(f'<a class="chip" href="#{E(cid)}">{E(canon[cid].removeprefix("Traveler\'s notebook "))}</a>' for cid in order if cid)
            shop_nav = f'<nav class="chips" aria-label="Products on this page"><span class="muted small">Jump to:</span> {shop_nav}</nav>'
        dg_tracker = ""  # per-product tables are the one view; the old grouped table repeated every listing
    else:
        others += f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>'
        shop_nav = dg_tracker = ""
    card_filter = (f'<form class="filters card-filter" role="search" onsubmit="return false"><label class="grow">Search this page'
                   f'<input id="card-q" type="search" placeholder="{E(g["search_hint"])}"></label></form>') if ext else ""
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
  <span class="muted small">Last check: {time_tag(stock['run_finished'])}.</span></p>
  {signup()}
</section>
<div class="layout">
  <div class="main-col">
    <div id="tracker"{' class="card-filtered"' if ext else ''}>
    <div class="m-lead">{design_nav}{shop_nav}{card_filter}{''.join(parts[:lead_n])}</div>
    {''.join(parts[lead_n:])}
    <p class="muted small card-empty" hidden>Nothing on this page matches that search.</p>
    </div>
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
    # --- Round 3: one page per tracked planner or journal design. Facts come from the shops' own listing titles in data/stock.json.
    dict(parent="hobonichi-techo-2027-original-a6", slug="one-piece-edition", name="One Piece Edition", full="Hobonichi Techo 2027 One Piece Edition",
         match=lambda p: p["type"] == "Book" and "one piece edition" in p["label"].lower()),
    dict(parent="hobonichi-weeks-2027", slug="pink-sapphire", name="Pink Sapphire", full="Hobonichi Weeks 2027 Pink Sapphire",
         match=lambda p: p["type"] == "Weeks" and "pink sapphire" in p["label"].lower()),
    dict(parent="hobonichi-weeks-2027", slug="paper-series-jade", name="Paper Series: Jade", full="Hobonichi Weeks 2027 Paper Series Jade",
         match=lambda p: p["type"] == "Weeks" and "paper series" in p["label"].lower() and "jade" in p["label"].lower()),
    dict(parent="hobonichi-weeks-2027", slug="shirt-fabric-graph-plaid", name="Shirt Fabric: Graph Plaid", full="Hobonichi Weeks 2027 Shirt Fabric Graph Plaid",
         match=lambda p: p["type"] == "Weeks" and "shirt fabric" in p["label"].lower() and "graph plaid" in p["label"].lower()),
    dict(parent="hobonichi-techo-2027-covers", slug="moomin-my-yard", name="Moomin: My Yard", full="Hobonichi Techo 2027 A6 cover Moomin: My Yard",
         match=lambda p: p.get("canonical") == "cover-a6-moomin"),
    dict(parent="hobonichi-techo-2027-covers", slug="white-cat-house", name="Yumi Kitagishi: White Cat House", full="Hobonichi Techo 2027 A6 cover White Cat House",
         match=lambda p: p.get("canonical") == "cover-a6-white-cat-house"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-storybook-navy", name="Archer and Olive Storybook in Navy", full="Archer and Olive Storybook in Navy dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-storybook-navy"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-songbird-blue", name="Archer and Olive Songbird in Blue", full="Archer and Olive Songbird in Blue dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-songbird-blue"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-majestic-skies", name="Archer and Olive Majestic Skies", full="Archer and Olive Majestic Skies dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-majestic-skies"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-apothecary-shelf", name="Archer and Olive Apothecary Shelf", full="Archer and Olive Apothecary Shelf dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-apothecary-shelf"),
    dict(parent=DOTGRID_SLUG, slug="leuchtturm1917-hardcover-a5-dotted", name="Leuchtturm1917 Hardcover Medium (A5) dotted", full="Leuchtturm1917 Hardcover Medium (A5) dotted notebook",
         match=lambda p: p.get("canonical") == "lt-hardcover-a5"),
    dict(parent=DOTGRID_SLUG, slug="leuchtturm1917-120g-a5-dotted", name="Leuchtturm1917 Medium (A5) 120G dotted", full="Leuchtturm1917 Medium (A5) 120G dotted notebook",
         match=lambda p: p.get("canonical") == "lt-120g-a5"),
    dict(parent=DOTGRID_SLUG, slug="leuchtturm1917-edition-2", name="Leuchtturm1917 Bullet Journal Edition 2", full="Leuchtturm1917 Bullet Journal Edition 2 dot grid notebook",
         match=lambda p: p.get("canonical") == "lt-bullet-journal-ed2"),
    dict(parent=DOTGRID_SLUG, slug="scribbles-that-matter-pro", name="Scribbles That Matter Dotted Journal Pro", full="Scribbles That Matter Dotted Journal Pro",
         match=lambda p: p.get("canonical") == "stm-pro"),
    dict(parent=DOTGRID_SLUG, slug="scribbles-that-matter-iconic", name="Scribbles That Matter Dotted Journal Iconic", full="Scribbles That Matter Dotted Journal Iconic",
         match=lambda p: p.get("canonical") == "stm-iconic"),
    dict(parent=DOTGRID_SLUG, slug="scribbles-that-matter-starry-night", name="Scribbles That Matter Starry Night", full="Scribbles That Matter Starry Night dotted journal",
         match=lambda p: p.get("canonical") == "stm-starry-night"),
    dict(parent=DOTGRID_SLUG, slug="notebook-therapy-tsuki-160gsm", name="Notebook Therapy Tsuki 160GSM", full="Notebook Therapy Tsuki 160GSM dot grid journal",
         match=lambda p: p.get("canonical") == "nt-tsuki-160"),
    dict(parent=DOTGRID_SLUG, slug="notebook-therapy-tsuki-dark-academia", name="Notebook Therapy Tsuki Dark Academia", full="Notebook Therapy Tsuki Dark Academia dot grid journal",
         match=lambda p: p.get("canonical") == "nt-tsuki-dark-academia"),
    dict(parent=DOTGRID_SLUG, slug="notebook-therapy-tsuki-violet-nocturne", name="Notebook Therapy Tsuki Violet Nocturne", full="Notebook Therapy Tsuki Violet Nocturne dot grid journal",
         match=lambda p: p.get("canonical") == "nt-tsuki-violet-nocturne"),
    dict(parent=DOTGRID_SLUG, slug="notebook-therapy-tsuki-ravens-secret", name="Notebook Therapy Tsuki Raven's Secret", full="Notebook Therapy Tsuki Raven's Secret dot grid journal",
         match=lambda p: p.get("canonical") == "nt-tsuki-ravens-secret"),
    dict(parent=TN_SLUG, slug="regular-black", name="Regular size Black", full="Traveler's notebook Regular size Black",
         match=lambda p: p.get("canonical") == "tn-regular-black"),
    dict(parent=TN_SLUG, slug="regular-blue", name="Regular size Blue", full="Traveler's notebook Regular size Blue",
         match=lambda p: p.get("canonical") == "tn-regular-blue"),
    dict(parent=TN_SLUG, slug="regular-brown", name="Regular size Brown", full="Traveler's notebook Regular size Brown",
         match=lambda p: p.get("canonical") == "tn-regular-brown"),
    dict(parent=TN_SLUG, slug="road-trip-brown", name="ROAD TRIP Brown", full="Traveler's notebook ROAD TRIP Brown (Regular size)",
         match=lambda p: p.get("canonical") == "tn-road-trip-brown"),
    dict(parent=TN_SLUG, slug="card-size-20th-anniversary-black", name="Card Size 20th Anniversary Set Black", full="Traveler's notebook Card Size 20th Anniversary Set Black",
         match=lambda p: p.get("canonical") == "tn-20th-card-black"),
    dict(parent=SECTIONS["midori"]["slug"], slug="md-diary-2027-a5", name="MD Notebook Diary 2027 A5", full="MIDORI MD Notebook Diary 2027 A5",
         match=lambda p: p.get("canonical") == "md-diary-2027-a5"),
    dict(parent=SECTIONS["midori"]["slug"], slug="md-diary-1-day-1-page-2027-a5", name="MD Notebook Diary 1 Day 1 Page 2027 A5", full="MIDORI MD Notebook Diary 1 Day 1 Page 2027 A5",
         match=lambda p: p.get("canonical") == "md-diary-1day-2027-a5"),
]
DESIGNS_LASTMOD = "2026-11-04"

DESIGN_ABOUT = {'one-piece-edition': 'The One Piece Edition is a Japanese-language Hobonichi Techo 2027 Original book in A6 size, with a page for every day, a January start and Monday-start weeks.', 'hobonichi-weeks-2027/midnight-blue': 'Midnight Blue is a Colors design for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-mega-2027/midnight-blue': 'Midnight Blue is a Colors design for the Hobonichi Weeks Mega 2027 weekly planner.', 'hobonichi-weeks-2027/canaria-yellow': 'Canaria Yellow is a Colors design for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/white-cat-wallpaper': 'White Cat Wallpaper is a Yumi Kitagishi artist collaboration for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/moomin-at-the-table': 'Moomin: At the Table is a Moomin collaboration for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-mega-2027/candy-dream': 'Bow & Tie: Candy Dream is a design for the Hobonichi Weeks Mega 2027 weekly planner.', 'hobonichi-weeks-2027/sea-glass': 'Sea Glass is a Colors design for the Hobonichi Weeks weekly planner.', 'hobonichi-weeks-2027/v-and-a': 'The V&A series is a set of Hobonichi Weeks 2027 designs; we track Welcome to the V&A and Leicester.', 'hobonichi-weeks-2027/pink-sapphire': 'Pink Sapphire is a Colors design for the Hobonichi Weeks weekly planner.', 'hobonichi-weeks-2027/paper-series-jade': 'Jade is part of the Paper Series for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/shirt-fabric-graph-plaid': 'Graph Plaid is a Shirt Fabric design for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-techo-2027-covers/moomin-my-yard': 'Moomin: My Yard (Pale Mint) is a Hobonichi cover for the A6 Original book.', 'hobonichi-techo-2027-covers/white-cat-house': 'White Cat House is a Yumi Kitagishi artist collaboration cover for the Hobonichi A6 Original book.', 'archer-and-olive-storybook-navy': 'Storybook in Navy is an Archer and Olive dot grid notebook with white paper, in A5 (192 pages) and B5 (160 pages).', 'archer-and-olive-songbird-blue': 'Songbird in Blue is an Archer and Olive dot grid notebook in A5 (192 pages) and B5 (160 pages), and each size sells out on its own.', 'archer-and-olive-majestic-skies': 'Majestic Skies is an Archer and Olive dot grid notebook in A5 with 192 pages.', 'archer-and-olive-apothecary-shelf': "Apothecary Shelf is Archer and Olive's Halloween 2026 dot grid notebook, a B5 with 160 pages of white dot grid paper.", 'leuchtturm1917-hardcover-a5-dotted': 'The Leuchtturm1917 Hardcover Medium (A5) with dotted pages comes in several colors, and each one goes out of stock on its own.', 'leuchtturm1917-120g-a5-dotted': 'The Leuchtturm1917 120G edition is the Medium (A5) hardcover with heavier 120 g paper and 203 numbered pages.', 'leuchtturm1917-edition-2': "Bullet Journal Edition 2, as Leuchtturm1917 names it, is the brand's official dot grid journal, tracked here in every color its US shop lists.", 'scribbles-that-matter-pro': 'The Scribbles That Matter Dotted Journal Pro is a 160gsm dot grid journal in A5 and B5 and several colors.', 'scribbles-that-matter-iconic': 'The Scribbles That Matter Dotted Journal Iconic is an A5 dot grid journal with 160gsm paper, here in Bottle Green.', 'scribbles-that-matter-starry-night': 'Starry Night is a Scribbles That Matter A5 dotted journal with black paper.', 'notebook-therapy-tsuki-160gsm': "The Tsuki 160GSM is Notebook Therapy's dot grid journal with heavy 160gsm paper, and each cover color sells out on its own.", 'notebook-therapy-tsuki-dark-academia': 'Dark Academia is a limited edition Tsuki dot grid journal from Notebook Therapy, an A5 with 176 pages.', 'notebook-therapy-tsuki-violet-nocturne': 'Violet Nocturne is a limited edition A5 Tsuki dot grid journal from Notebook Therapy, with white paper.', 'notebook-therapy-tsuki-ravens-secret': "Raven's Secret is a limited edition Tsuki dot grid journal from Notebook Therapy, an A5 with 176 pages.", 'regular-black': "The Traveler's notebook Regular size in Black is a leather notebook cover from Traveler's Company.", 'regular-blue': "The Traveler's notebook Regular size in Blue is a leather notebook cover from Traveler's Company.", 'regular-brown': "The Traveler's notebook Regular size in Brown is a leather notebook cover from Traveler's Company.", 'regular-camel': "The Traveler's notebook Regular size in Camel is a leather notebook cover from Traveler's Company.", 'regular-olive': "The Traveler's notebook Regular size in Olive is a leather notebook cover from Traveler's Company.", 'road-trip-brown': "ROAD TRIP Brown is a Regular size Traveler's notebook that Traveler's Company USA sells as a US exclusive.", 'card-size-20th-anniversary-black': "The Card Size 20th Anniversary Set in Black is a limited Traveler's Company set for the notebook's 20th anniversary.", 'md-diary-2027-a5': 'The MIDORI MD Notebook Diary 2027 in A5 is a dated monthly planner on MD Paper.', 'md-diary-1-day-1-page-2027-a5': 'The MIDORI MD Notebook Diary 1 Day 1 Page 2027 in A5 gives every day of 2027 its own page.'}

def design_about(d):
    return DESIGN_ABOUT.get(d["parent"] + "/" + d["slug"]) or DESIGN_ABOUT[d["slug"]]

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
    pids = {id(x) for x in group_listings(parent)}
    if not all(id(l) in pids for l in ls):  # a design page must count only listings its parent tracker shows
        raise SystemExit(f"design page {design_fname(d)} has listings its parent tracker doesn't show")
    fname = design_fname(d)
    shops = len({l["store_id"] for l in ls})
    buy = [l for l in ls if l["status"] in BUYABLE]
    unk = [l for l in ls if l["status"] == "unknown"]
    run = stock["run_finished"]
    sec = g_sec(parent)
    ey = parent.get("eyebrow", "Hobonichi Techo 2027")
    h1 = f'{d["full"]} restock tracker'
    m = page_amz(ls, oe)
    amz_btn = (f'<p><a class="btn btn-amz" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a> '
               f'<span class="muted small">{E(m["note"])}.</span></p>') if m else ""
    if not ls:
        right_now = "none of the shops we check list this design right now. We'll show it here again if a shop adds it."
    elif len(unk) == len(ls):
        right_now = ("we couldn't reach the shop for this listing at the last check, so its status is unknown." if len(ls) == 1 else f"we couldn't check any of these {len(ls)} listings at the last check, so their status is unknown.")
    else:
        right_now = (f"{len(buy)} of {len(ls) - len(unk) if unk else len(ls)} {'checked ' if unk else ''}listings are in stock or on preorder "
                     f"at {len({l['store_id'] for l in buy})} of {nshops(len({l['store_id'] for l in ls if l['status'] != 'unknown'})) + ' we could check' if unk else nshops(shops)}."
                     + (f" {len(unk)} couldn't be checked this run." if unk else ""))
    table = (f"""<section class="card group-sec" id="stock">
  <div class="section-head"><h2>Stock by shop</h2><p class="muted small">{E(count_line(ls).capitalize())} · {checked_line(ls)}</p></div>
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(ls, oe)}</tbody>
  </table></div>
  <p class="muted small">Open a shop's name to go straight to its listing.</p>
  {region_legend(l["store_id"] for l in ls)}
</section>""" if ls else f'<section class="card group-sec" id="stock"><h2>Stock by shop</h2><div class="empty"><p>No shop we check lists this design right now. See the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a> for everything we track.</p></div></section>')
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and c["to"] in BUYABLE and c["from"] in NOT_BUYABLE],
                key=lambda c: c["at"], reverse=True)[:10]
    if rs:
        restock_html = f'<p class="muted small">{RESTOCK_NOW_NOTE}</p>' + restock_feed(rs, feed_id=d["parent"] + "-" + d["slug"] + "-restocks")
    else:
        start = tracking_start(ls) if ls else stock["run_started"]
        restock_html = f'''<div class="empty"><p><strong>No restocks spotted yet.</strong> Tracking started {time_tag(start)}.
  A restock shows up here the moment a sold-out listing flips back to in stock or preorder between two checks.</p></div>'''
    # short FAQ, answered from this run's data
    names = lambda xs: ", ".join(sorted({l["store"] for l in xs})) or "none"
    when = fmt_et(run)
    if not ls:
        a1 = f"At the last check ({when}) none of the shops we track listed it."
    elif len(unk) == len(ls):
        a1 = (f"We don't know. At the last check ({when}) we couldn't reach "
              f"{'the shop' if shops == 1 else f'any of the {shops} shops'} that list{'s' if shops == 1 else ''} it, so its status is unknown. Open the shop's page in the table above to see it there.")
    else:
        chk = len({l["store_id"] for l in ls if l["status"] != "unknown"})
        of = f"{nshops(chk)} we could check" if unk else nshops(shops)
        if not buy:
            a1 = (f"Not at the shops we track. At the last check ({when}) none of the {of} had it in stock or on preorder." if chk > 1 else
                  f"Not at the shops we track. At the last check ({when}) the {'one shop we could check' if unk else 'one shop we track'} didn't have it in stock or on preorder.") + (f" {m['note']}, so we link to Amazon, which may still have it." if m else "")
        else:
            a1 = f"Yes, at {len({l['store_id'] for l in buy})} of {of} at the last check ({when}): {names(buy)}. Stock can change within minutes, so confirm on the shop's page."
        if unk:
            a1 += f" We couldn't check {names(unk)} this run, so we don't know their status."
    a2 = (f"We track it at {shops} {'shop' if shops == 1 else 'shops'}: {names(ls)}. Each name in the table above opens that shop's own listing."
          if ls else "No shop we check lists it right now.")
    vers = sorted({(l.get("title") or l["label"]) for l in ls})
    a_v = (f"We track {len(ls)} {'listing' if len(ls) == 1 else 'listings'}. In each shop's own words: " + "; ".join(vers) + "." if ls else "None right now.")
    qa = [(f'Is {d["full"]} in stock?', a1),
          (f'Which sizes and versions of {d["full"]} do you track?', a_v),
          (f'Where can I buy {d["full"]}?', a2),
          ("How often do you check?",
           f"Every shop is checked {CHECK_FREQ}. Each status is exactly what the shop's public product data said at that time. \"Not yet on sale\" means the shop has a preview page up but isn't taking orders yet, and \"Couldn't check\" means our check failed, so we don't guess."),
          ("Can I get an alert when it's back?",
           "Yes. Sign up above for restock emails: we send one short email when a sold-out item comes back at any shop we track.")]
    when_html = time_tag(run)
    faq_html = '<section class="card faq" id="faq"><h2>Questions</h2>' + "".join(
        f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a).replace(E(when), when_html, 1)}</p></details>' for q, a in qa) + "</section>"
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
    sources = "".join(f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["store"])}: {E(l.get("title") or l["label"])}</a></li>' for l in sorted(ls, key=lambda l: l["store"]))
    sources_html = f"""<section class="card" id="sources"><h2>Sources</h2>
  <p class="muted small">Statuses come from each shop's own public product page, read by our checker at the time shown. The raw data for every check is public: <a href="data/stock.json">stock.json</a>.</p>
  <ul class="link-list">{sources}</ul></section>""" if ls else ""
    sibs = "".join(f'<li><a href="{design_fname(x)}">{E(x["name"])}</a></li>' for x in designs_of(d["parent"]) if x is not d)
    others = (f'<li><a href="{parent["slug"]}/">All {E(parent["short"])} designs</a></li>' + sibs
              + (f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>' if sec == "hobonichi" else f'<li><a href="{parent["slug"]}/#tracker">Every listing on the {E(parent["short"])} page</a></li>'))
    intro = (f'{E(design_about(d))} This page shows its stock at every shop we track, checked {CHECK_FREQ}. '
             f'For every design, see the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a>.')
    body = f"""
<div class="product-page">
{crumbs((parent["slug"] + "/", parent["short"]), (fname, d["name"]))}
<section class="hero">
  {eyebrow(ey, f"{shops} {'shop' if shops == 1 else 'shops'} checked {CHECK_FREQ}")}
  <h1>{E(h1)}</h1>
  <p class="lede">{intro}</p>
  <p><strong>Right now:</strong> {right_now}
  <span class="muted small">Last check: {time_tag(run)}.</span></p>
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
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {section_guides(sec)}
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
     "About every 30 minutes. A scheduled job reads each shop's public product data, then rebuilds this site with what it found. "
     "Restock times and last-check times are written as Eastern Time. A browser that can read them shows your local time zone instead and names that zone. "
     "If it cannot, the Eastern Time label stays. Guide dates and the 2027 calendar dates stay as written."),
    ("Which shops do you check?",
     "{n} shops across all trackers, in separate sections per brand family. Hobonichi: {nh} shops, the official Hobonichi Online Store and independent stationery shops. {secs}. Each listing in the tracker links to the shop's own page. JetPens and Nanami Paper are listed as links only, because their sites block automated checks."),
    ("What do you track?",
     "Hobonichi Techo 2027 planners: the Original A6 and Cousin A5 books, Weeks and Weeks Mega, and a few A6 covers. {tracks} We don't track pens."),
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
    "dotgrid": "On a separate dot grid journals page, we track a focused set of flagship dot grid notebooks from {dg}, size by size and color by color, plus Archer and Olive's dot grid refills.",
    "travelers": "On the Traveler's Company page, we track the five Regular size notebook colors plus limited editions: the 2027 diary accessories, anniversary sets and shop exclusives. We don't track Passport size or refills there.",
    "midori": "On the MIDORI MD page, we track seasonal and limited MD releases (MIDORI's MD line is now sold as MD PRODUCT).",
}

def faq_block(only=None, sid="faq"):
    """only: a subset of FAQ questions (the hub shows a short version, without FAQPage markup)."""
    n = len({p["store_id"] for p in stock["products"]})
    # {shop} is a link in the page and the plain URL in the FAQ structured data
    secs = ". ".join(f'{SECTIONS[k]["foot"]}: {N_SEC[k]} shops, {shop_names(k)}' + (", each checked on its own store" if k == "dotgrid" else "") for k in LIVE)
    secs += ". Some shops sell more than one brand, so they're counted once in the total"
    tracks = " ".join(FAQ_TRACKS[k] for k in LIVE)
    pairs = []
    for q, a in FAQ:
        if q == "Do you sell planners?" and shop_inserts_public():
            a = ("Yes, our own: we make planners, journals, and printable planner inserts, and sell them on our shop page ({shop}). "
                 "Printed books are on Amazon. Printable PDFs, including undated paper tip-ins, are on Etsy. "
                 "The stationery we track is sold by the shops themselves; we just link you to them. "
                 "Amazon links on the site are affiliate links, and we say so on every page; links to the shops we track are plain links.")
        if only is None or q in only:
            pairs.append((q, a))
    qa = [(q, a.format(n=n, nh=N_HOBO, secs=secs, tracks=tracks.format(dg=dotgrid_names()), shop=url_for("shop/")),
           E(a).format(n=n, nh=N_HOBO, secs=E(secs), tracks=E(tracks.format(dg=dotgrid_names())), shop=f'<a href="shop/">{E(SHOP_NAME.lower())}</a>')) for q, a in pairs]
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

STATIC_LASTMOD = {"hobonichi-2027.html": "2026-11-03", "about.html": "2026-11-03", "privacy.html": "2026-11-04"}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes], CONTENT_LASTMOD)
    urls = [(url_for("index.html"), home_mod), (url_for(HOBO_TRACKER), latest(*[p.get("status_since") for p in hobo_products()], *[c["at"] for c in changes], CONTENT_LASTMOD))]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(design_fname(d)), design_lastmod(d)) for d in DESIGNS]
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    hobo_mod = latest(*[p.get("status_since") for p in hobo_products()], GUIDES_LASTMOD)
    tn_mod = json.loads(GUIDE_DATES.read_text())["build_tn_sizes"]["date"]  # written when that guide is built, earlier in main()
    urls += [(url_for(WTB_SLUG + "/"), hobo_mod), (url_for(VS_SLUG + "/"), GUIDES_LASTMOD), (url_for(DG_GUIDE_SLUG + "/"), latest(*[p.get("status_since") for p in section_products("dotgrid")], DG_GUIDE_LASTMOD)), (url_for(TN_GUIDE_SLUG + "/"), tn_mod), (url_for("guides/"), latest(DG_GUIDE_LASTMOD, tn_mod)), (url_for("shop/"), shop_lastmod()), (url_for("follow/"), "2026-11-03")]
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
GUIDES = HOBO_GUIDES + [(DG_GUIDE_SLUG + "/", "Best dot grid journals compared"),
                        (TN_GUIDE_SLUG + "/", "Regular vs Passport vs Card Size")]  # footer, /guides/, 404, related block; Hobonichi pages use HOBO_GUIDES
GUIDES_LASTMOD = "2026-10-29"
DG_GUIDE_LASTMOD = "2026-11-04"  # last copy change on the dot grid guide
GUIDE_BLURBS = {WTB_SLUG + "/": "Which shops have each 2027 Original A6, Cousin A5, Weeks and Weeks Mega in stock right now, checked about every 30 minutes, plus tips for catching a restock.",
                VS_SLUG + "/": "Size, weight, daily vs weekly layout and pages for the three most popular Hobonichi books, from Hobonichi's own specs, and who each one suits.",
                "hobonichi-2027.html": "When the 2027 planners launched, the October wave, and when restocks usually land, with sources.",
                DG_GUIDE_SLUG + "/": "Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy: paper gsm, pages, size and features from each maker's own page, with live stock.",
                TN_GUIDE_SLUG + "/": "Leather cover and refill dimensions for Regular, Passport, and the limited Card Size 20th anniversary set, from TRAVELER'S COMPANY's own pages, plus which refills fit and which sizes we track."}  # last copy change on the guide pages (sitemap lastmod floor)
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

def design_links_block(sec="hobonichi", hx="h2"):
    """Design pages of one section (or every section with sec=None), for guides and the guides index."""
    def sec_of(d):
        return next(g_sec(g) for g in GROUPS if g["slug"] == d["parent"])
    items = "".join(f'<li><a href="{design_fname(d)}">{E(d["full"])}</a></li>' for d in DESIGNS if sec is None or sec_of(d) == sec)
    return f'<{hx}>Restock pages for single designs</{hx}><ul class="link-list">{items}</ul>' if items else ""

def design_index_block():
    """Every design page, grouped by family: the design-pages index on /guides/."""
    fam = [("hobonichi", "Hobonichi"), ("dotgrid", "Dot grid journals"), ("travelers", "Traveler's Company"), ("midori", "MIDORI MD")]
    out = []
    for k, t in fam:
        ds = [d for d in DESIGNS if next(g_sec(g) for g in GROUPS if g["slug"] == d["parent"]) == k]
        if ds:
            out.append(f'<h3>{E(t)}</h3><ul class="link-list">' + "".join(
                f'<li><a href="{design_fname(d)}">{E(d["full"])}</a> <span class="muted small">· {E(count_line(design_listings(d)))}</span></li>' for d in ds) + "</ul>")
    return f'<section class="card" id="design-pages"><h2>Restock pages for single designs</h2><p class="muted small">{len(DESIGNS)} pages, one per planner or journal design we track. Counts come from the same checks as the trackers.</p>{"".join(out)}</section>'


def guides_block():
    return ('<section class="card"><p class="eyebrow">Guides</p><ul class="link-list">'
            + "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in HOBO_GUIDES) + "</ul></section>")

def section_guides(sec):
    """Guide links on a design page. Hobonichi keeps its guides; dot grid and Traveler's link their own."""
    if sec == "hobonichi":
        return guides_block()
    link = {"dotgrid": (DG_GUIDE_SLUG + "/", "Best dot grid journals compared"),
            "travelers": (TN_GUIDE_SLUG + "/", "Regular vs Passport vs Card Size")}.get(sec)
    if not link:
        return ""
    h, t = link
    return f'<section class="card"><p class="eyebrow">Guide</p><ul class="link-list"><li><a href="{h}">{E(t)}</a></li></ul></section>'

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
        rows.append(f'<tr><td>{E(by[sid][0]["store"])}{region_tag(sid)}</td><td><ul class="wtb-items">{items}</ul></td></tr>')
    return f'''<div class="table-wrap"><table class="stock"><thead><tr><th>Shop</th><th>What we track there · status at last check</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>'''

def build_where_to_buy():
    fname = WTB_SLUG + "/"
    hobo = hobo_products()
    groups = [g for g in GROUPS if g_sec(g) == "hobonichi"]
    last = time_tag(stock["run_finished"])
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
  {"" if secs else region_legend(l["store_id"] for l in hobo)}
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
    checked_at = fmt_et(stock["run_finished"])
    faq_html = "".join(
        f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a).replace(E(checked_at), time_tag(stock["run_finished"]), 1)}</p></details>'
        for q, a in faq)
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
{design_links_block()}
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
        return f'{len(b)} of {nshops(len({l["store_id"] for l in ls}))} we track · <a href="{slug}/">live stock</a>'
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
{eyebrow("Guide", "Hobonichi Techo 2027", guide_updated(build_vs))}
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
<p class="muted small">Stock counts are what each shop's product data said at our last check, {time_tag(stock['run_finished'])}.</p>

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
{design_links_block()}
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
    def col_ls(store_id):  # same scope as the tracker: every dot grid listing at that shop
        return [p for p in dg if p["store_id"] == store_id]
    # Build check: the guide's counts must come from exactly the tracker's listings.
    dg_group = next(g for g in GROUPS if g["slug"] == DOTGRID_SLUG.rstrip("/"))
    trk = group_listings(dg_group)
    guide_ls = [p for _, sid, _ in DG_COLS for p in col_ls(sid)]
    if sorted(map(id, guide_ls)) != sorted(map(id, dg)) or count_line(guide_ls) != count_line(trk) or len(trk) != len(dg):
        raise SystemExit(f"dot grid guide counts differ from tracker: guide {count_line(guide_ls)!r}, tracker {count_line(trk)!r}")
    dg_total = count_line(guide_ls)
    def avail(store_id, canons):
        ls = col_ls(store_id)
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
    asof = time_tag(stock["run_finished"])
    body = f"""
<article class="prose guide vs-page">
{crumbs(("guides/", "Guides"), (fname, "Dot grid journals compared"))}
{eyebrow("Guide", "Dot grid journals", guide_updated(build_dotgrid_guide))}
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
<p class="muted small">Stock is what each maker's own shop said at our last check, {asof}. Each count covers every dot grid listing we track at that shop, the same listings as the <a href="{DOTGRID_SLUG}/">dot grid tracker</a>. Across all four: {E(dg_total)}.</p>
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
{design_links_block("dotgrid")}
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


# Manufacturer package specs, read from the product pages linked in the guide's Sources.
# Cover and refill are separate lines. The comparison uses those millimeters.
def build_tn_sizes():
    fname = TN_GUIDE_SLUG + "/"
    title = "Traveler's Notebook Regular vs Passport vs Card Size: Which Size Fits You?"
    desc = ("Regular, Passport, or the limited Card Size set: leather cover and refill dimensions from TRAVELER'S COMPANY, "
            "which refills fit which cover, and which sizes this site tracks.")
    updated = guide_updated(build_tn_sizes)
    iso = json.loads(GUIDE_DATES.read_text())[build_tn_sizes.__name__]["date"]
    ids = {c["id"] for c in stores["canonical"]}
    need = {"tn-regular-black", "tn-regular-brown", "tn-regular-blue", "tn-regular-camel", "tn-regular-olive",
            "tn-road-trip-brown", "tn-20th-card-black", "tn-2027-clear-folder-regular", "tn-2027-plastic-sheet-regular"}
    if not need <= ids or any("passport" in i for i in ids) or {i for i in ids if "card" in i} != {"tn-20th-card-black"}:
        raise SystemExit(f"Traveler's size guide tracking claims are out of date: {sorted(ids)}")
    for slug in ("regular-black", "regular-brown", "regular-blue", "regular-camel", "regular-olive",
                 "road-trip-brown", "card-size-20th-anniversary-black"):
        if not any(d["parent"] == TN_SLUG and d["slug"] == slug for d in DESIGNS):
            raise SystemExit(f"Traveler's size guide is missing a link target: {slug}")
        if any("passport" in (d["slug"] + d["full"]).lower() for d in DESIGNS):
            raise SystemExit("A Passport page exists; update the size guide before saying Passport is not tracked")

    def dlink(slug):
        d = next(x for x in DESIGNS if x["parent"] == TN_SLUG and x["slug"] == slug)
        return f'<a href="{design_fname(d)}">{E(d["name"])}</a>'

    src = [
        ("journey", "https://travelerscompanyusa.com/write-your-lifes-journey-starting-with-the-travelers-notebook/",
         "Write Your Life's Journey, starting with the TRAVELER'S notebook", "TRAVELER'S COMPANY USA, June 1, 2021. Two sizes, Regular and Passport, and how the maker describes carrying each."),
        ("reg", "https://www.travelers-company.com/products/trnote/starter-kit-regular/black",
         "Regular Size Black starter kit", "TRAVELER'S COMPANY. Leather cover H220 × W120 × D10 mm. Blank refill H210 × W110 × D4 mm, 64 pages, MD paper, saddle stitched. No. 13714006."),
        ("pass", "https://www.travelers-company.com/products/trnote/starter-kit-passport/black",
         "Passport Size Black starter kit", "TRAVELER'S COMPANY. Leather cover H134 × W98 × D10 mm. Blank refill H124 × W89 × D4 mm, 64 pages, MD paper, saddle stitched. No. 15026006."),
        ("usreg", "https://shop.travelerscompanyusa.com/products/travelers-notebook-black",
         "Black (Regular Size) starter kit", "TRAVELER'S COMPANY USA shop. The same Regular starter kit, No. 13714006."),
        ("uspass", "https://shop.travelerscompanyusa.com/products/travelers-notebook-passport-size-black",
         "Black (Passport Size) starter kit", "TRAVELER'S COMPANY USA shop. The same Passport starter kit, No. 15026006."),
        ("r001", "https://www.travelers-company.com/products/trnote/refill-regular/refill-r-001",
         "001 Lined Notebook, Regular Size", "TRAVELER'S COMPANY. Lined 6.5 mm, 64 pages, MD paper, H210 × W110 × D4 mm. No. 14245006."),
        ("p001", "https://www.travelers-company.com/products/trnote/refill-passport/refill-p-001n",
         "001 Lined Notebook, Passport Size (current MD specification)", "TRAVELER'S COMPANY. Lined 6.5 mm, 64 pages, MD paper, H124 × W89 × D4 mm. No. 14368006."),
        ("p001old", "https://www.travelers-company.com/products/trnote/refill-passport/refill-p-001",
         "001 Lined Notebook, Passport Size (old specification)", "TRAVELER'S COMPANY. Labeled old specification: DP paper, 80 pages, perforated, still H124 × W89 × D4 mm. The page says the current refill changed to MD paper and 64 pages in March 2016."),
        ("p003", "https://www.travelers-company.com/products/trnote/refill-passport/refill-p-003n",
         "003 Blank Notebook, Passport Size", "TRAVELER'S COMPANY. Blank, 64 pages, MD paper, H124 × W89 × D4 mm. No. 14370006."),
        ("ridx", "https://www.travelers-company.com/products/trnote/refill-regular",
         "Refills, Regular Size", "TRAVELER'S COMPANY. Refills made to set into a Regular cover, with that size's own item numbers."),
        ("pidx", "https://www.travelers-company.com/products/trnote/refill-passport",
         "Refills, Passport Size", "TRAVELER'S COMPANY. Refills made to set into a Passport cover. Lists repair kits 009 and 010, Pen Holder M (016), and brass clip 030 for both Regular and Passport."),
        ("cardnews", "https://travelerscompanyusa.com/travelers-notebook-card-size-20th-anniversary-set/",
         "TRAVELER'S notebook Card Size 20th Anniversary Set", "TRAVELER'S COMPANY USA, March 4, 2026. The set, the limited-quantity note, and Card Size refills after the set sales end."),
        ("cardb", "https://www.travelers-company.com/products/20th/20th-black",
         "Card Size 20th Anniversary Set Black", "TRAVELER'S COMPANY. Contents and package specs. Cover H110 × W75 × D10 mm. Refill H100 × W65 × D2 mm, 32 pages. No. 15411006."),
        ("cardbr", "https://www.travelers-company.com/products/20th/20th-brown",
         "Card Size 20th Anniversary Set Brown", "TRAVELER'S COMPANY. Same cover and refill measurements as the Black set. No. 15412006. Spare band orange; zipper case dark brown."),
    ]
    # Same millimeter lines confirmed on these Regular pages: Brown, Blue, Camel, Olive. Passport Blue matches the Passport Black lines.
    extra = {
        "reg": [("Brown", "https://www.travelers-company.com/products/trnote/starter-kit-regular/brown"),
                ("Blue", "https://www.travelers-company.com/products/trnote/starter-kit-regular/blue"),
                ("Camel", "https://www.travelers-company.com/products/trnote/starter-kit-regular/camel"),
                ("Olive", "https://www.travelers-company.com/products/trnote/starter-kit-regular/olive")],
        "pass": [("Blue, same measurements", "https://www.travelers-company.com/products/trnote/starter-kit-passport/blue")],
    }
    src_i = {k: i + 1 for i, (k, *_) in enumerate(src)}

    def cite(*keys):
        return " " + " ".join(f'<a href="#src-{k}">[{src_i[k]}]</a>' for k in keys)

    def row(label, cells):
        # cells: (html, source keys)
        tds = "".join(f"<td>{html}{cite(*keys)}</td>" for html, keys in cells)
        return f'<tr><th scope="row">{E(label)}</th>{tds}</tr>'

    rows = [
        row("Lineup", [
            ("One of the two standard sizes.", ("journey",)),
            ("The other standard size.", ("journey",)),
            ("A limited 20th-anniversary set. A new size for that anniversary, not a third standard size in the lineup.", ("cardnews", "journey")),
        ]),
        row("Leather cover", [
            ("H220 × W120 × D10 mm. Cowhide, made in Thailand. Height × width × depth.", ("reg",)),
            ("H134 × W98 × D10 mm. Cowhide, made in Thailand.", ("pass",)),
            ("H110 × W75 × D10 mm. The set page also says 110 mm tall and 75 mm wide without the fastener. A 20th-anniversary logo is engraved on the back.", ("cardb", "cardnews")),
        ]),
        row("Refill that comes with it", [
            ("H210 × W110 × D4 mm. Blank, 64 pages, MD paper, saddle stitched. The starter-kit page identifies this refill as 003.", ("reg",)),
            ("H124 × W89 × D4 mm. Blank, 64 pages, MD paper, saddle stitched. The current blank refill 003 is the same size.", ("pass", "p003")),
            ("H100 × W65 × D2 mm. Blank, 32 pages, MD paper, saddle stitched. The set holds five of these notebooks.", ("cardb",)),
        ]),
        row("Carry, in the maker's words", [
            ("Hold it in one hand. The 2021 article calls it about the height of an A5 notebook but slimmer, and says tickets, maps, and A4 paper folded in three fit. Two or three refills fit easily.", ("journey",)),
            ("Fits a palm or a back pocket, and a smaller bag. With a zipper case or file, the maker says it can be a wallet, a card case, or a passport cover. The refill is described as the same size as a passport.", ("journey", "pidx")),
            ("Fits the palm and a jeans pocket. With the pieces in the set, the maker says it can be a compact wallet, a business-card holder, a card case, or a mini pouch.", ("cardnews", "cardb")),
        ]),
        row("Notebook refills that fit", [
            ("The Regular refill catalog only. A Regular 001 lined refill is H210 × W110 × D4 mm.", ("ridx", "r001")),
            ("The Passport refill catalog only. A Passport 001 lined refill is H124 × W89 × D4 mm.", ("pidx", "p001")),
            ("Card Size refills. Regular and Passport refills are a different height and width. The maker says Card Size refills are planned at TRAVELER'S FACTORY and TRAVELER'S COMPANY USA after the set sales end.", ("cardb", "cardnews")),
        ]),
        row("Tracked on this site", [
            ("The five Regular colors, plus ROAD TRIP Brown. Open the color page for the shops we check.", ()),
            ("Passport is not tracked.", ()),
            ("The Black set only. The Brown set is not tracked.", ()),
        ]),
    ]
    reg_links = " · ".join(
        f'<a href="{u}" rel="noopener" target="_blank">{E(n)}</a>' for n, u in
        [("Black", src[1][1]), *extra["reg"]])
    pass_links = " · ".join(
        f'<a href="{u}" rel="noopener" target="_blank">{E(n)}</a>' for n, u in
        [("Black", src[2][1]), *extra["pass"]])
    src_items = []
    for k, u, t, note in src:
        more = ""
        if k == "reg":
            more = " Same cover and refill lines on " + reg_links + "."
        elif k == "pass":
            more = " Same cover and refill lines on " + pass_links + "."
        src_items.append(f'<li id="src-{k}"><a href="{u}" rel="noopener" target="_blank">{E(t)}</a>. {note}{more}</li>')
    faq = [
        ("What is the difference between Traveler's Notebook Regular and Passport?",
         "They are different sizes, cover and refill both. On the Regular starter kit the leather cover is H220 × W120 × D10 mm and the blank refill is H210 × W110 × D4 mm. "
         "On the Passport starter kit the leather cover is H134 × W98 × D10 mm and the blank refill is H124 × W89 × D4 mm. Both included refills are 64-page blank MD paper, saddle stitched. "
         "TRAVELER'S COMPANY USA describes Regular and Passport as the two sizes, and says you choose by what you want to do with the notebook."),
        ("Is Regular the same as A5, and Passport the same as A6?",
         "No. A5 paper is 148 × 210 mm. The Regular refill is 210 mm tall and 110 mm wide, so the height matches A5 and the width does not. It does not take A5 paper. "
         "A6 paper is 105 × 148 mm. The Passport refill is H124 × W89 mm, so it is not A6. The maker describes that refill as the same size as a passport you carry when traveling."),
        ("Do Regular, Passport, and Card Size refills fit each other's covers?",
         "No. Regular refills are made for a Regular cover (H210 × W110 mm for the notebook refills cited here). Passport refills are made for a Passport cover (H124 × W89 mm). "
         "Card Size refills are H100 × W65 mm. The item number is not enough: Regular 004 is a pocket sticker and Passport 004 is a zipper case; Regular 014 is kraft paper and Passport 014 is dot grid. "
         "The Passport refill index says four accessories fit both Regular and Passport: repair kits 009 and 010, Pen Holder M (016), and the brass clip (030). Connecting bands are separate items (Regular 021, Passport 011). "
         "The Card Size set includes its own connecting bands, H85 × W3 × D3 mm. That shared-accessory sentence does not mention Card Size."),
        ("Is Card Size a standard third Traveler's Notebook I can keep buying?",
         "No. TRAVELER'S COMPANY USA's size article names two sizes, Regular and Passport. Card Size was introduced for the 20th anniversary as a limited-quantity set in Black and Brown, on sale outside Japan from April 23, 2026. "
         "The maker says that after those set sales end, Card Size refills are planned for TRAVELER'S FACTORY and TRAVELER'S COMPANY USA. That note is about refills. It does not say the leather cover stays in the catalog."),
        ("What is in the Card Size 20th anniversary set, and do you track it?",
         "Cotton bag, a leather cover with one blank MD Paper White refill already in it, two more blank MD Paper White refills, two blank MD Paper Cream refills, a cotton zipper case, a kraft paper folder, two connecting rubber bands, and a spare rubber band. Five notebooks in total. "
         "Black is No. 15411006 and comes with a navy zipper case and a red spare band. Brown is No. 15412006 and comes with a dark brown zipper case and an orange spare band. "
         "We track the Black set. We do not track the Brown set, and we do not track Passport at all. Stock changes, so the listing pages are where to check the shops we follow."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    tracked = " · ".join(dlink(s) for s in ("regular-black", "regular-brown", "regular-blue", "regular-camel", "regular-olive", "road-trip-brown"))
    body = f"""
<article class="prose guide vs-page tn-size">
{crumbs(("guides/", "Guides"), (fname, "Regular vs Passport vs Card Size"))}
{eyebrow("Guide", "Traveler's Notebook", updated)}
<h1>{E(title)}</h1>
<p class="lede">Regular and Passport are the two standard sizes. Pick Regular for a larger page you can still hold, Passport for a pocket, or the Card Size set if you want the smaller 20th-anniversary notebook. Cover and refill are different sizes. The figures below are the manufacturer's package specs.</p>
{signup()}

<section class="card" id="quick">
  <h2>Quick recommendation</h2>
  <ul>
    <li><strong>Regular</strong> if you want the larger page. The refill is H210 × W110 mm, and the 2021 article says the notebook is for one hand, with room for tickets, maps, or A4 paper folded in three.{cite("journey", "reg")}</li>
    <li><strong>Passport</strong> if you want the cover that fits a palm or a back pocket (H134 × W98 × D10 mm) and a refill the maker compares to a passport (H124 × W89 mm).{cite("journey", "pass", "pidx")}</li>
    <li><strong>Card Size</strong> only if you want that anniversary pocket set. The cover is 110 mm tall and 75 mm wide without the fastener. It is a limited set, sold in Black and Brown, not a third everyday size.{cite("cardnews", "cardb")}</li>
  </ul>
  <p class="muted small">The maker's own line is that there is no required way to choose between Regular and Passport. It depends on what you want the notebook to do.{cite("journey")}</p>
</section>

<h2 id="compare">Side by side</h2>
<p class="muted small">Height × width × depth from the manufacturer's package specs. The leather cover and the paper refill are different sizes. Numbers in brackets point to the sources. On a small screen, scroll the table sideways. The row labels stay put.</p>
<div class="table-wrap">
<table class="stock compare">
<caption class="sr">Regular, Passport, and Card Size: cover, refill, carry, refills, and what this site tracks</caption>
<thead><tr><th></th><th>Regular</th><th>Passport</th><th>Card Size</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div>
<p class="muted small"><strong>Inches converted from those millimeters</strong> (25.4 mm = 1 in). This is arithmetic, not a published spec. Regular cover 8.66 × 4.72 × 0.39 in, refill 8.27 × 4.33 × 0.16 in. Passport cover 5.28 × 3.86 × 0.39 in, refill 4.88 × 3.50 × 0.16 in. Card Size cover 4.33 × 2.95 × 0.39 in, refill 3.94 × 2.56 × 0.08 in.</p>
<p><strong>Shop dimensions.</strong> The US shop prints different dimensions for these same starter kits.{cite("usreg", "uspass")} This guide uses the manufacturer's package specs. Check those for fit.</p>
<p>A5 paper is 148 × 210 mm. The Regular refill matches that height and is 38 mm narrower, so it does not take A5 sheets. The 2021 article calls Regular about the height of an A5 notebook but slimmer.{cite("journey", "reg")} A6 paper is 105 × 148 mm. Neither the Passport refill nor the Card Size refill is A6.</p>

<h2 id="carry">Carry and what each size is built to do</h2>
<h3>Regular: the larger page you can still hold</h3>
<p>Choose Regular when the writing page matters more than the smallest possible cover. The page is H210 × W110 mm, against H124 × W89 mm in Passport and H100 × W65 mm in the Card Size set. The 2021 article says you hold the Regular notebook in one hand, and that tickets, maps, and three-folded A4 paper fit. It also says two or three refills fit, and that adding more is up to you.{cite("journey")} The cover's own depth on the package line is D10 mm, and one refill is D4 mm. The maker does not publish a thickness for a cover stuffed with several refills, so a heavy stack is a different carry from the starter kit.</p>
<p>The same cover and refill measurements are printed on the Black, Brown, Blue, Camel, and Olive Regular starter kits. Color does not change the size.{cite("reg")}</p>
<h3>Passport: pocket, small bag, or a passport cover</h3>
<p>Choose Passport when the notebook has to live in a pocket or a small bag. The 2021 article says it fits a palm or the back pocket of your pants.{cite("journey")} The cover is H134 × W98 × D10 mm.{cite("pass")} The refill index says the paper is the same size as a passport, and that a zipper case or file lets this size work as a wallet, a card case, or a passport cover.{cite("pidx")} The writing page is H124 × W89 mm, 64 pages in the current blank and lined refills.{cite("pass", "p001", "p003")}</p>
<h3>Card Size: the anniversary notebook that goes in a jeans pocket</h3>
<p>Choose the Card Size set when you want something smaller than Passport and you are buying that specific anniversary kit. The maker describes it for a note you want down quickly, and says that once the zipper case, folder, and refills are in the cover it can be a compact wallet, a business-card holder, a card case, or a mini pouch.{cite("cardnews")} The cover is the one that "fits perfectly in the palm of your hand and slips easily into a jeans pocket."{cite("cardb")} Each notebook is 32 pages, half the page count of the Regular and Passport starter refills, on a smaller sheet.{cite("cardb", "reg", "pass")}</p>

<h2 id="refills">Refills and what fits which cover</h2>
<p>Each cover has its own refill list. Regular refills are "set in the regular sized TRAVELER'S notebook."{cite("ridx")} Passport refills are "set into your passport size TRAVELER'S notebook."{cite("pidx")} Card Size refills are the H100 × W65 mm notebooks in the anniversary set.{cite("cardb")} A refill from one list does not become the right size because the item number looks familiar.</p>
<ul>
  <li><strong>Regular notebooks</strong> use the Regular numbers. 001 lined is 6.5 mm ruling, 64 pages, MD paper, H210 × W110 × D4 mm (No. 14245006).{cite("r001")} The starter kit's blank 003 uses the same outer size.{cite("reg")} The Regular index also lists grid 002, dot grid 026, diaries 005, 017, 018, and 019, sketch 012, and a zipper case 008, among others. Full list on the Regular refill page.{cite("ridx")}</li>
  <li><strong>Passport notebooks</strong> use a different set of numbers for the same kinds of paper. Current 001 lined is also 6.5 mm and 64 pages of MD paper, but H124 × W89 × D4 mm (No. 14368006).{cite("p001")} Current blank 003 is that same size (No. 14370006).{cite("p003")} An older Passport 001 page is still online and labeled old specification: DP paper, 80 pages, perforated. The page says the refill changed to MD paper and 64 pages in March 2016. Use the current page for the paper you would buy now.{cite("p001old", "p001")}</li>
  <li><strong>Same number, different object.</strong> On the two indexes, Regular 004 is a pocket sticker and Passport 004 is a zipper case. Regular 014 is a kraft notebook and Passport 014 is dot grid. Match the size name on the package, then the number.{cite("ridx", "pidx")}</li>
  <li><strong>Shared by Regular and Passport only.</strong> The Passport index says these fit both: repair kit 009 (standard colors), repair kit 010 (spare colors), Pen Holder M (016), and brass clip 030. Zipper cases, folders, notebook refills, and connecting bands are not on that list. Regular's connecting band is 021. Passport's is 011.{cite("pidx", "ridx")}</li>
  <li><strong>Card Size accessories in the set</strong> are specified on their own: cotton zipper case H105 × W140 × D10 mm when open, kraft folder H100 × W130 × D1 mm when open, connecting bands H85 × W3 × D3 mm, two of them.{cite("cardb")} Nothing on the Regular or Passport "both sizes" line adds Card Size.</li>
</ul>

<h2 id="card-set">What the Card Size anniversary set includes</h2>
<p>TRAVELER'S COMPANY made Card Size for the notebook's 20th anniversary and put it on sale outside Japan on April 23, 2026. The sets are limited in quantity. Shops can sell out, and release dates differ by shop.{cite("cardnews", "cardb")} Black and Brown are the two editions. This is the anniversary set, not a standing third size next to Regular and Passport.{cite("journey", "cardnews")}</p>
<p>The maker's contents list:{cite("cardb", "cardbr")}</p>
<ol>
  <li>Cotton bag.</li>
  <li>Leather cover, Black or Brown, with one blank MD Paper White refill already set in it.</li>
  <li>Two more blank MD Paper White refills. The package line counts three white refills in total, including the one in the cover. Gray paper cover, letterpress logo.</li>
  <li>Two blank MD Paper Cream refills. Brown paper cover, gold foil logo.</li>
  <li>Cotton zipper case. Navy with the Black cover, dark brown with the Brown cover. A card pocket on the left, a zippered pocket on the right.</li>
  <li>Kraft paper folder, for folded banknotes, shop cards, and tickets.</li>
  <li>Two connecting rubber bands, for adding more than one refill.</li>
  <li>A spare rubber band. Red with Black, orange with Brown.</li>
</ol>
<p>After the set sales end, the maker says Card Size refills are planned for TRAVELER'S FACTORY and TRAVELER'S COMPANY USA.{cite("cardnews", "cardb")} That sentence is about refills. It does not promise that the leather cover, or the set, stays on sale.</p>

<h2 id="tracked">What this site tracks</h2>
<p>Live stock stays on the tracker. This guide does not say what is in stock today.</p>
<ul>
  <li><strong>Regular covers we track:</strong> {tracked}. ROAD TRIP Brown is a Regular size US exclusive. The five standard colors are the starter-kit size above. All of them sit on the <a href="{TN_SLUG}/">Traveler's Company tracker</a>.</li>
  <li><strong>Regular accessories we track:</strong> the <a href="{TN_SLUG}/#tn-2027-clear-folder-regular">2027 clear folder</a> and the <a href="{TN_SLUG}/#tn-2027-plastic-sheet-regular">2027 plastic sheet</a>, both labeled Regular size. We do not track Passport or Card Size accessories.</li>
  <li><strong>Card Size:</strong> {dlink("card-size-20th-anniversary-black")} only. The <a href="https://www.travelers-company.com/products/20th/20th-brown" rel="noopener" target="_blank">Brown set (No. 15412006)</a> is part of the anniversary pair, and we do not have a listing page for it.</li>
  <li><strong>Passport is not tracked.</strong> There is no Passport cover, refill, or accessory on the tracker. The <a href="https://www.travelers-company.com/products/trnote/starter-kit-passport/black" rel="noopener" target="_blank">Passport starter kit</a> and the <a href="https://www.travelers-company.com/products/trnote/refill-passport" rel="noopener" target="_blank">Passport refill list</a> are the manufacturer's pages. The <a href="https://shop.travelerscompanyusa.com/products/travelers-notebook-passport-size-black" rel="noopener" target="_blank">US shop</a> sells that same starter kit.</li>
</ul>
<p>The US shop warns that counterfeit notebooks using the TRAVELER'S COMPANY logo have been sold in the US, and says to buy from the official shop or an authorized reseller.{cite("usreg")}</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{"".join(src_items)}</ol>
<p class="muted small">TRAVELER'S COMPANY sells more refills than the examples named here. The index pages are the full lists. Prices are left off this guide because they change.</p>
{related_block(fname)}
</article>"""
    for banned in ("$", "most popular", "best seller", "bestseller", "search volume", "in stock now", "always available",
                    "5.7", "not interchangeable", "inches on the us shop"):
        if banned in body.lower():
            raise SystemExit(f"Traveler's size guide contains a banned claim: {banned}")
    for needed in ("H220", "H134", "H110", "H210", "H124", "H100", "Passport is not tracked", "We do not track the Brown set"):
        if needed not in body:
            raise SystemExit(f"Traveler's size guide is missing {needed}")
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title,
           "datePublished": iso, "dateModified": iso, "url": url_for(fname),
           "image": BASE + "assets/brand/og-travelers.png",
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE,
                         "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, title, desc, body,
                       ld=(crumbs_ld(("guides/", "Guides"), (fname, "Regular vs Passport vs Card Size")), art, faq_ld),
                       og_type="article", og_image=OG_TRAVELERS, og_alt=OG_TRAVELERS_ALT)


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
{design_index_block()}
</article>"""
    lst = {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": t, "url": url_for(h)} for i, (h, t) in enumerate(GUIDES)]}
    return fname, page(fname, "Guides: Hobonichi, dot grid journals, and Traveler's Notebook sizes · Stationery Drop Watch",
                       "Guides from Stationery Drop Watch: where to buy the Hobonichi Techo 2027, Techo vs Cousin vs Weeks, the 2027 launch calendar, dot grid journals compared, and Traveler's Notebook Regular vs Passport vs Card Size.",
                       body, ld=(crumbs_ld((fname, "Guides")), lst))

# Soft Days listing confirmed by the owner on 2026-11-06.
# Public permalink is the url below. The shopwide sale applies, so the card uses the
# same price line as the other Etsy printables: regular $6.99 plus "20% off launch sale
# Oct 31 to Nov 30". Do not print the intro amount (it would read as the lasting price),
# the sale code, an AI-disclosure line, or fee records.
# Fit: an earlier card said the inserts were tested in a Hobonichi Weeks Mega. The
# 2026-11-08 source for these files says the 85 x 175 mm trim was not physically tested.
# That test claim is removed. Do not add a Traveler's notebook fit claim.
# A gated item with url "" is omitted. DROPWATCH_SHOP_PREVIEW=1 can render that empty
# state into DROPWATCH_SITE_OUT only.
_ETSY_LISTING = re.compile(r"^https://www\.etsy\.com/listing/\d+(?:/[a-z0-9-]+)?$")
SHOP_ETSY = [
    dict(title="2027 Printable Planner, Blush", inside="womens", img="assets/shop/womens-2027-printable-planner.jpg",
         alt="2027 printable planner in blush, shown as printed pages", url="https://www.etsy.com/listing/4606759241",
         blurb="The same dated 2027 planner as a PDF you print at home. Sunday start, weekly and monthly pages, dot grid notes."),
    dict(title="2027 Printable Planner for Men", inside="mens", img="assets/shop/mens-2027-printable-planner.jpg",
         alt="2027 printable planner for men in charcoal, shown as printed pages", url="https://www.etsy.com/listing/4606781258",
         blurb="The men's 2027 planner as a PDF you print at home. Weekly and monthly pages, dot grid notes, workout log and budget pages."),
    dict(title="Level Up! My 2027 Kids Planner", inside="levelup-etsy",
         img="assets/shop/levelup-etsy-cover.webp", img_w=812, img_h=1050,
         alt="Front cover of the Level Up! 2027 printable planner", url="https://www.etsy.com/listing/4610143237",
         sub="Printable PDF for kids 7 to 11 · instant download from Etsy",
         hub_sub="Printable PDF",
         blurb="A printable 2027 kids planner that plays like a video game. 12 monthly Levels with Main Quests, Side Quests and Boss Battles, plus a habit tracker and XP bar.",
         details=["US Letter 8.5 x 11 in, no A4", "168 pages, Monday start, 53 weeks", "Reading Quest Log, Trophy Room, Coin Bank",
                  "Printable PDF. The paperback is a separate book on this page."]),
    dict(id="soft-days", kind="insert", gated=True, sale_confirmed=True, price="$6.99",
         title="Soft Days Narrow Planner Inserts",
         img="assets/shop/soft-days-narrow-inserts.png", img_class="sheet", img_w=2700, img_h=2025,
         url="https://www.etsy.com/listing/4611293526/soft-days-narrow-planner-inserts",
         alt=('Soft Days Narrow Planner Insert Set: four fanned printed tip-in sheets titled Month Dashboard, '
              'Habit Tracker, Weekly Plan, and Meal Planner, on a pale background. The sheet reads '
              '"16 undated tip-in templates · colour + grayscale · Letter & A4" and "Finished cut size 85 × 175 mm", '
              'and "Digital printable · not a physical planner · personal use".'),
         sub="Printable paper tip-ins · personal use · instant download from Etsy",
         sub_unpublished="Printable paper tip-ins · personal use",
         hub_sub="Printable inserts",
         blurb=("Sixteen undated templates you print, cut, and tip in yourself. Color and grayscale editions are the same "
                "16 designs, on US Letter and A4, not 64 different designs. Finished cut size is 85 × 175 mm (3.35 × 6.89 in). "
                "A digital download for personal use."),
         details=["Five PDFs: four 9-page editions (Letter and A4, color and grayscale) and a 2-page printing and tip-in guide",
                  "Two inserts per US Letter or A4 sheet, no bleed. Print at actual size (100%) and measure the 25 mm calibration square before printing the set",
                  "Monday-start weeks. Personal use only: don't share, resell, or redistribute the PDFs",
                  "Not a physical planner, bound refill, sticker sheet, or planner app",
                  "Finished cut size is 85 × 175 mm. Physical fit in a planner has not been tested. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Month Dashboard", "Habit Tracker (6 habits, 31 daily rows)", "Mood Tracker",
                    "Weekly Plan (Monday start, undated)", "Monthly Budget", "Reading Log", "Pen & Ink Swatches",
                    "Meal Planner (breakfast and lunch/dinner, Monday start)", "Wishlist & Gifts", "Annual Goals",
                    "Monthly Reset", "Order Tracker", "Stationery Inventory", "Brain Dump", "Dot Grid", "Lined Notes"],
         templates_label="16 templates",
         inside="soft-days"),
]

# FIX-06: prices on /shop. Amazon list prices were read from each product's own amazon.com page on
# 2026-11-04 (buy box and format swatch; no strikethrough or deal shown). A None here shows "See price on Amazon".
AMAZON_LIST_PRICES = {"B0HPBDNS7F": "$19.99", "B0HQ5TLDK3": "$14.99", "B0HQ5X3C7D": "$16.99",
                      "B0HP9PXSR1": "$14.99"}
SHOP_LABELS = {"B0HPBDNS7F": "2027 Planner, Blush", "B0HQ5TLDK3": "Habit & Mood Tracker Journal", "B0HQ5X3C7D": "Reading Journal",
               "B0HP9PXSR1": "2027 Planner for Men", "B0HQW8273V": "Level Up! My 2027 Planner"}
SHOP_ORDER = ("B0HPBDNS7F", "B0HQ5TLDK3", "B0HQ5X3C7D", "B0HP9PXSR1", "B0HQW8273V")
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
    "womens": [("04-weekly-spread-dec27-jan2", "Weekly spread, Dec 27 to Jan 2"), ("05-monthly-calendar-january", "Monthly calendar, January"),
               ("06-habit-tracker-january", "Habit tracker, January")],
    "mens": [("04-weekly-spread-dec27-jan2", "Weekly spread, Dec 27 to Jan 2"), ("05-monthly-calendar-january", "Monthly calendar, January"),
             ("06-habit-tracker-january", "Habit tracker, January")],
}

def _sample(src, alt, caption, w, h):
    """One collapsed-disclosure figure. The link opens this same file, with no second artwork."""
    return {"src": src, "alt": alt, "caption": caption, "w": w, "h": h}

# Covers are card thumbs, not members of these lists. Soft Days uses the three inserts only.
SHOP_SAMPLES = {
    "levelup-etsy": {"class": " samples", "items": [
        _sample("/assets/shop/inside/levelup-etsy-p009.webp",
                "Level Up Etsy digital: January 2027 Monday-start World Map calendar. Authentic final PDF interior, complete page.",
                "January 2027 calendar, page 9. Sample from the printable PDF.", 812, 1050),
        _sample("/assets/shop/inside/levelup-etsy-p012.webp",
                "Level Up Etsy digital: Week 2 dated Monday-start Week Plan. Authentic final PDF interior, complete page.",
                "Week 2 plan, January 4 to 10, page 12. Sample from the printable PDF.", 812, 1050),
        _sample("/assets/shop/inside/levelup-etsy-p013.webp",
                "Level Up Etsy digital: Week 2 Save Point with habit tracker, mood and XP. Authentic final PDF interior, complete page.",
                "Week 2 save point, page 13. Sample from the printable PDF.", 812, 1050),
    ]},
    "B0HQW8273V": {
        "class": " samples",
        "note": "Sample pages from the print-ready file, not photographs of a printed copy.",
        "items": [
        _sample("/assets/shop/inside/levelup-print-p009.webp",
                "Level Up local print master: January 2027 Monday-start World Map calendar. Authentic final PDF interior, complete page.",
                "January 2027 calendar, page 9.", 812, 1050),
        _sample("/assets/shop/inside/levelup-print-p012.webp",
                "Level Up local print master: Week 2 dated Monday-start Week Plan. Authentic final PDF interior, complete page.",
                "Week 2 plan, January 4 to 10, page 12.", 812, 1050),
        _sample("/assets/shop/inside/levelup-print-p013.webp",
                "Level Up local print master: Week 2 Save Point with habit tracker, mood and XP. Authentic final PDF interior, complete page.",
                "Week 2 save point, page 13.", 812, 1050),
    ]},
    "soft-days": {"class": " samples inserts", "items": [
        _sample("/assets/shop/inside/softdays-weekly-color.webp",
                "Soft Days soft colour: Weekly Plan, Monday start. Authentic final PDF interior extracted at full insert boundary.",
                "Weekly Plan, Monday start. Sample of a colour insert.", 511, 1051),
        _sample("/assets/shop/inside/softdays-habit-gray.webp",
                "Soft Days grayscale: Habit Tracker with six-habit key. Authentic final PDF interior extracted at full insert boundary.",
                "Habit Tracker. Sample of a grayscale insert.", 511, 1051),
        _sample("/assets/shop/inside/softdays-swatches-color.webp",
                "Soft Days soft colour: Pen & Ink Swatches. Authentic final PDF interior extracted at full insert boundary.",
                "Pen & Ink Swatches. One Soft Days insert, not a separate swatch product.", 511, 1051),
    ]},
}

import hashlib as _hl
ASSET_V = {n: _hl.md5((SITE / 'assets' / n).read_bytes()).hexdigest()[:8] for n in ('style.css', 'app.js', 'local-time.js')}

def shop_preview():
    return os.environ.get("DROPWATCH_SHOP_PREVIEW") == "1"

def etsy_listing_url(item):
    """A real public listing URL, or "" when the release gate is still closed."""
    url = (item.get("url") or "").strip()
    if not url:
        return ""
    if not _ETSY_LISTING.match(url):
        raise SystemExit(f"{item.get('title', 'Etsy item')}: listing URL must be https://www.etsy.com/listing/<id> with no placeholder")
    return url

def etsy_listings():
    """Listings this build may render. A gated item with no URL is omitted unless this is a preview build."""
    preview = shop_preview()
    out = []
    for item in SHOP_ETSY:
        url = etsy_listing_url(item)
        if url:
            out.append(item)
        elif item.get("gated"):
            if preview:
                out.append(item)
        else:
            raise SystemExit(f"{item['title']} is missing a public Etsy listing URL")
    return out

def shop_inserts_public():
    """True when this build shows a printable insert (live listing, or an explicit preview)."""
    return any(e.get("kind") == "insert" for e in etsy_listings())

def shop_hub_line():
    if shop_inserts_public():
        return "Planners, journals, and printable inserts we make: printed books on Amazon and printable PDFs on Etsy."
    return "2027 planners and journals we make: printed books on Amazon and printable PDFs on Etsy."

def shop_cta_line():
    if shop_inserts_public():
        return "Planners, journals, and printable inserts we make, printed on Amazon and as PDFs on Etsy"
    return "2027 planners and journals we make, printed on Amazon and printable on Etsy"

def shop_lastmod():
    # Shop facts changed 2026-11-08 (paperback listing, see-inside samples, fit wording).
    if any(e.get("kind") == "insert" and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-08"
    return "2026-11-03"

_BANNED_CLAIMS = ("$5.59", "us$5.59", "launch20", "ai-generated", "artificial intelligence",
                  "made with ai", "created with ai", "generated by ai", "weeks size",
                  "guaranteed to fit", "guaranteed compatibility")

def guard_release(fname, doc):
    """A public build must not claim Soft Days is listed, on sale, or AI-disclosed on the website."""
    low = doc.lower()
    for s in _BANNED_CLAIMS:
        if s in low:
            raise SystemExit(f"{fname}: copy contains {s!r}")
    shown = "Soft Days" in doc
    live = any(e.get("kind") == "insert" and etsy_listing_url(e) for e in SHOP_ETSY)
    preview = shop_preview()
    if shown and not preview and not live:
        raise SystemExit(f"{fname}: Soft Days is rendered but listing_url is empty")
    if fname.endswith("shop/index.html") and (preview or live) and not shown:
        raise SystemExit(f"{fname}: Soft Days card missing from this shop build")
    if not shown or not fname.endswith("shop/index.html"):
        return
    i = doc.find("Soft Days Narrow Planner Inserts")
    start = doc.rfind('<li class="shop-card"', 0, i)
    end = doc.find("</div></li>", i)
    card = doc[start:end + len("</div></li>")]
    text = html.unescape(card)
    for needed in ("Physical fit in a planner has not been tested.",
                   "Not a Hobonichi product", "not affiliated", "personal use", "85 × 175 mm",
                   "16 designs", "$6.99", "actual size (100%)", "25 mm"):
        if needed not in text:
            raise SystemExit(f"{fname}: Soft Days card is missing {needed!r}")
    for banned in ("tested in a hobonichi weeks mega", "traveler", "unverified", "perfect fit",
                   "full-page", "full page", "guaranteed to fit"):
        if banned in text.lower():
            raise SystemExit(f"{fname}: Soft Days card still has an unsupported fit claim {banned!r}")
    if card.count("<li>") < 16:  # detail bullets plus the 16 template names
        raise SystemExit(f"{fname}: Soft Days card is missing template names")
    if live:
        item = next(e for e in SHOP_ETSY if e.get("kind") == "insert")
        url = etsy_listing_url(item)
        if card.count(url) < 2 or "Etsy listing not published yet" in card or "not a live listing" in card:
            raise SystemExit(f"{fname}: published Soft Days card has the wrong listing state")
        if item.get("sale_confirmed", True) and (ETSY_PRICE[1] not in card or "Regular price" in card):
            raise SystemExit(f"{fname}: Soft Days must use the shared sale note, not a standalone intro price")
    else:
        if "etsy.com" in card or "not a live listing" not in card or "Etsy listing not published yet" not in card:
            raise SystemExit(f"{fname}: preview Soft Days card is not gated")

def build_shop():
    fname = "shop/"
    books = {b["id"]: b for b in json.loads((ROOT / "content/editor_picks.json").read_text())["books"]}
    labels = SHOP_LABELS
    for item in SHOP_ETSY:
        if not (ROOT / "site" / item["img"]).is_file():
            raise SystemExit(f"missing shop asset {item['img']}")
        if item.get("kind") == "insert" and len(item.get("templates") or []) != 16:
            raise SystemExit(f"{item['title']} must list 16 templates")
    def srcset(img):  # Etsy mockups ship 600w + 1200w copies; Amazon covers use their single file
        if img.startswith("assets/shop/") and img.endswith("-planner.jpg"):
            b = img[:-4]
            return f' srcset="/{E(b)}-600.jpg 600w, /{E(b)}-1200.jpg 1200w"'
        return ""
    def card(img, alt, title, sub, blurb, details, href, btn, own, price, inside=None, *,
             img_class="", dims=None, note="", templates=None, templates_label="Templates", card_id=""):
        dl = "".join(f"<li>{E(d)}</li>" for d in details)
        attr = ' data-own-product' if own else ''
        ins = ""
        if inside:
            if inside in SHOP_SAMPLES:
                sample = SHOP_SAMPLES[inside]
                figs = "".join(
                    f'<figure><a class="inside-zoom" href="{E(s["src"])}" target="_blank" rel="noopener">'
                    f'<img src="{E(s["src"])}" alt="{E(s["alt"])}" width="{s["w"]}" height="{s["h"]}" loading="lazy" decoding="async"></a>'
                    f'<figcaption>{E(s["caption"])} <a href="{E(s["src"])}" target="_blank" rel="noopener">Larger view</a></figcaption></figure>'
                    for s in sample["items"])
                grid = "inside-grid" + sample["class"]
                lead = f'<p class="muted small">{E(sample["note"])}</p>' if sample.get("note") else ""
            else:
                figs = "".join(f'<figure><img src="/assets/shop/inside/{inside}-{f}.jpg" alt="{E(title)}: {E(cap)}" loading="lazy" decoding="async"><figcaption>{E(cap)}</figcaption></figure>'
                               for f, cap in SHOP_INSIDE[inside])
                grid = "inside-grid" + (" spreads" if inside in AMAZON_LIST_PRICES else "")
                lead = ""
            ins = f'<details class="shop-inside"><summary>See inside</summary>{lead}<div class="{grid}">{figs}</div></details>'
        if templates:
            lis = "".join(f"<li>{E(t)}</li>" for t in templates)
            ins += f'<details class="shop-inside"><summary>{E(templates_label)}</summary><ul class="small">{lis}</ul></details>'
        if img_class:
            cls = "shop-img " + img_class
        elif own:
            cls = "shop-img"
        else:
            cls = "shop-img photo"
        dim = f' width="{int(dims[0])}" height="{int(dims[1])}"' if dims else ""
        image = f'<img src="{E(img)}"{srcset(img)}{dim} sizes="(max-width:600px) 240px, 150px" alt="{E(alt)}" loading="lazy" decoding="async">'
        if href:
            media = f'<a class="{cls}" href="{E(href)}"{attr} rel="noopener" target="_blank">{image}</a>'
            action = f'<a class="btn" href="{E(href)}"{attr} rel="noopener" target="_blank">{E(btn)}</a>'
        else:
            media = f'<div class="{cls}">{image}</div>'
            action = f'<p class="btn is-disabled" role="note">{E(btn)}</p>'
        note_html = f'<p class="release-gate">{E(note)}</p>' if note else ""
        idattr = f' id="{E(card_id)}"' if card_id else ""
        return f"""<li class="shop-card"{idattr}>
  {media}
  <div class="shop-body">{note_html}<h3>{E(title)}</h3><p class="muted small">{E(sub)}</p>{price}<p>{E(blurb)}</p><ul class="small">{dl}</ul>
  {ins}{action}</div></li>"""
    def amz_price(a):
        lp = AMAZON_LIST_PRICES.get(a)
        if not lp:
            return '<p class="shop-price"><span class="muted">See price on Amazon</span></p>'
        return f'<p class="shop-price"><strong>{E(lp)}</strong> <span class="muted small">List price, check current price on Amazon</span></p>'
    amz = "".join(card(books[a]["cover"], books[a]["cover_alt"], labels[a], books[a]["format"] + " · on Amazon",
                       books[a].get("blurb", ""), books[a].get("details", []), own_amazon_link(books[a]["url"]), "View on Amazon", True,
                       amz_price(a), a if a in SHOP_INSIDE or a in SHOP_SAMPLES else None,
                       dims=(books[a]["cover_w"], books[a]["cover_h"]) if books[a].get("cover_w") and books[a].get("cover_h") else None)
                  for a in SHOP_ORDER)
    def etsy_price_html(item):
        price = item.get("price", ETSY_PRICE[0])
        url = etsy_listing_url(item)
        if item.get("sale_confirmed", True) and url:
            note = item.get("sale_note", ETSY_PRICE[1])
            return f'<p class="shop-price"><strong>{E(price)}</strong> <span class="muted small">{E(note)}</span></p>'
        return f'<p class="shop-price"><strong>{E(price)}</strong> <span class="muted small">Regular price</span></p>'
    def etsy_card(item):
        url = etsy_listing_url(item)
        sub = item.get("sub", "Printable PDF · instant download from Etsy")
        note = ""
        btn = "View on Etsy"
        if not url:
            sub = item.get("sub_unpublished", sub)
            btn = "Etsy listing not published yet"
            note = ("Preview only, not a live listing. No public Etsy URL is set, so this card is left out of the public site. "
                    "The price shown is the approved regular price, US$6.99. Launch-sale eligibility is not confirmed.")
        return card(item["img"], item["alt"], item["title"], sub, item["blurb"],
                    item.get("details", ["US Letter 8.5 x 11 in", "172 pages"]), url, btn, False, etsy_price_html(item),
                    item.get("inside"), img_class=item.get("img_class", ""),
                    dims=(item["img_w"], item["img_h"]) if item.get("img_w") and item.get("img_h") else None,
                    note=note, templates=item.get("templates"), templates_label=item.get("templates_label", "Templates"),
                    card_id=item.get("id", ""))
    etsy = "".join(etsy_card(e) for e in etsy_listings())
    if shop_inserts_public():
        lede = "Planners, journals, and printable inserts we make. Get a printed copy on Amazon, or a printable PDF on Etsy."
        title = "Our planners and journals: printed books and printable inserts on Amazon and Etsy · Stationery Drop Watch"
        desc = ("Planners, journals, and printable inserts made by Stationery Drop Watch: printed 2027 planners, including a kids paperback, a habit and mood tracker, "
                "and a reading journal on Amazon, plus printable 2027 planner PDFs, including the kids planner, and undated narrow planner inserts on Etsy.")
        etsy_intro = '<p class="muted">Printable planner PDFs, and undated paper tip-ins you print and cut yourself.</p>'
    else:
        lede = "Planners and journals we make. Get a printed copy on Amazon or a printable PDF on Etsy."
        title = "Our planners and journals: 2027 planners and journals on Amazon and Etsy · Stationery Drop Watch"
        desc = "Planners and journals made by Stationery Drop Watch: printed 2027 planners, a habit and mood tracker, and a reading journal on Amazon, plus printable 2027 planner PDFs on Etsy, including a kids planner."
        etsy_intro = ""
    body = f"""
<article class="prose shop shop-wide">
{crumbs((fname, "Planners and journals"))}
{eyebrow("Shop", "made by Stationery Drop Watch")}
<h1>{SHOP_NAME}</h1>
<p class="lede">{E(lede)}</p>
{signup("shop")}
<h2>Printed planners and journals on Amazon</h2>
<ul class="shop-list">{amz}</ul>
<h2>Printable PDFs on Etsy</h2>
{etsy_intro}<ul class="shop-list">{etsy}</ul>
</article>"""
    return fname, page(fname, title, desc, body, ld=(crumbs_ld((fname, "Planners and journals")),))

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
  <div class="follow-text"><h2 class="h3">{E(n)}</h2><p class="muted small">{E(h)}</p><p class="small">{E(note)}</p></div>
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

_NONE_CLAIM = re.compile(r"none of the [^<.]*?(had it|in stock|on preorder)|didn't have it in stock|(?<![\w])0 of \d+ (checked )?listings are in stock", re.I)

def check_none_claim(fname, doc):
    """Build check: a page must not say no shop has an item when every listing it shows is 'Couldn't check'."""
    badges = re.findall(r'<span class="badge (\w+)">', doc)
    if badges and all(b == "unknown" for b in badges) and _NONE_CLAIM.search(doc):
        raise SystemExit(f"{fname}: says none in stock but every listing is Couldn't check")

_AMZ_NOTE = re.compile(r'class="btn btn-amz"[^>]*>[^<]*</a> <span class="muted small">(Sold out|Not on sale yet)[^<]*</span>')

def check_amz_doc(fname, doc):
    """Build check: a design page's top Amazon note must not claim sold out while a listing on it is buyable or unchecked.

    Only the stock table counts. A recent-restock row names the latest check too, but the
    Amazon note is about the listings in the table. A later sell-out still gets the sold-out
    note, and this check still fails if any current row is in stock, on preorder, or unchecked."""
    listings = "\n".join(m.group(1) for m in re.finditer(r'<table class="stock">(.*?)</table>', doc, re.S))
    if _AMZ_NOTE.search(doc) and re.search(r'<span class="badge (in_stock|preorder|unknown)">', listings):
        raise SystemExit(f"{fname}: top note claims sold out but a listing on the page is in stock, on preorder or unchecked")

def main():
    if shop_preview() and SITE.resolve() == (ROOT / "site").resolve():
        raise SystemExit("Refusing to write a shop preview into site/. Set DROPWATCH_SITE_OUT to another directory.")
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/stock.json", SITE / "data/stock.json")
    shutil.copy(ROOT / "data/changes.json", SITE / "data/changes.json")
    (SITE / "index.html").write_text(build_index())
    (SITE / HOBO_TRACKER).mkdir(parents=True, exist_ok=True)
    (SITE / HOBO_TRACKER / "index.html").write_text(build_hobo_tracker())
    (SITE / "hobonichi-2027.html").write_text(build_hobonichi())
    (SITE / "about.html").write_text(build_about())
    (SITE / "privacy.html").write_text(build_privacy())
    (SITE / "404.html").write_text(build_404())
    oe = amazon_main(stock["products"])
    for g in GROUPS:
        fname, doc = build_group(g, oe)
        check_none_claim(fname, doc)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for d in DESIGNS:
        fname, doc = build_design(d, oe)
        check_none_claim(fname, doc)
        check_amz_doc(fname, doc)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for build in (build_where_to_buy, build_vs, build_dotgrid_guide, build_tn_sizes, build_guides_index, build_shop, build_follow):
        fname, doc = build()
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for old, new in REDIRECTS.items():
        (SITE / old).mkdir(parents=True, exist_ok=True)
        (SITE / old / "index.html").write_text(redirect_page(new))
    (SITE / "sitemap.xml").write_text(build_sitemap())
    (SITE / "robots.txt").write_text(ROBOTS)
    (SITE / "CNAME").write_text(CNAME + "\n")
    for html_path in SITE.rglob("*.html"):
        guard_release(str(html_path.relative_to(SITE)), html_path.read_text())
    state = "preview" if shop_preview() else ("listed" if any(e.get("kind") == "insert" and etsy_listing_url(e) for e in SHOP_ETSY) else "gated")
    print("shop release gate:", state)
    print("built", sorted(str(p.relative_to(SITE)) for p in SITE.rglob("*.html")), "+ sitemap.xml, robots.txt, CNAME")

if __name__ == "__main__":
    main()
