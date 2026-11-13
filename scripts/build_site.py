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
        if "data-plain-amazon" in a:  # policy pages, not product links: no Associates tag, no rel=sponsored
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
             "travelers-notebook-regular-size": SECTIONS["travelers"]["slug"] + "/#tracker",  # Regular colors merged into the Traveler's Company page
             "faq": "#good-to-know"}  # /faq -> the homepage FAQ ("Good to know")
# Home is a hub; the Hobonichi tracker (the old homepage content) lives on its own page.
HOBO_TRACKER = "hobonichi-restock-tracker/"
# Header: one link per restock tracker, then the rest of the site. Wraps on narrow screens; nothing is hidden.
# NAV is not part of the tracker count. The calendar, guides, and shop are resources, not extra trackers.
NAV_TRACKERS = [(HOBO_TRACKER, "Hobonichi tracker")] + [(SECTIONS[k]["slug"] + "/", SECTIONS[k]["nav"]) for k in LIVE]
# Shop stays in the header, after the trackers, and is not one of them.
NAV = [("hobonichi-2027.html", "2027 calendar"), ("guides/", "Guides"),
       ("follow/", "Follow us"), ("about.html", "About")]

def tracker_count_label():
    """Eyebrow count of restock trackers only (Hobonichi plus each section that has listings)."""
    n = len(NAV_TRACKERS)
    return f"{n} restock tracker" if n == 1 else f"{n} restock trackers"
SHOP_NAME = "Our planners and journals"  # h1 of /shop; breadcrumb says "Planners and journals". The header link says Shop.
# The workflow cron is "17,47 * * * *": two runs an hour. Every page says it the same way.
CHECK_FREQ = "about every 30 minutes"
N_HOBO = N_SEC["hobonichi"]   # Hobonichi shops we check
N_DG = N_SEC["dotgrid"]        # dot grid shops we check
TITLE_SUFFIX = " · Stationery Drop Watch"
TITLE_LIMIT = 60  # search-result titles past this are cut off
DESC_LIMIT = 160  # meta descriptions past this are cut off
BRAND_SHORT = " · Drop Watch"

# Guide templates hash their own source for the visible "updated" date. Short titles for those
# pages are applied here, so the guide functions themselves stay byte-for-byte and the date does not move.
TITLE_OVERRIDES = {
    "Hobonichi Techo 2027 launch & restock calendar": "Hobonichi Techo 2027 calendar",
    "Hobonichi Techo vs Cousin vs Weeks (2027): sizes, layouts, who each suits": "Hobonichi Techo vs Cousin vs Weeks",
    "Best dot grid journals compared: Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy": "Best dot grid journals compared",
    "Traveler's Notebook Regular vs Passport vs Card Size: Which Size Fits You?": "Traveler's Regular vs Passport vs Card Size",
    "Hobonichi Techo January-start vs April-start: which one should you buy?": "Hobonichi Techo January-start vs April-start",
}
DESC_OVERRIDES = {
    "Dot grid journals compared: paper weight (gsm), pages, size and features for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, from each maker's page, plus live stock.":
    "Dot grid journals compared: paper, pages, size and features for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, plus live stock.",
    "Regular, Passport, or the limited Card Size set: leather cover and refill dimensions from TRAVELER'S COMPANY, which refills fit which cover, and which sizes this site tracks.":
    "Regular, Passport, or the limited Card Size set: cover and refill sizes from TRAVELER'S COMPANY, which refills fit, and which sizes this site tracks.",
    # Approved sentence is 170 characters. The meta tag keeps that opening through a finished sentence.
    "Hobonichi's April-start (Spring) techo comes in fewer versions than the January-start edition and goes on sale on February 1. Here's how the two differ and how to choose.":
    "Hobonichi's April-start (Spring) techo comes in fewer versions than the January-start edition and goes on sale on February 1. Here's how the two differ.",
}

def seo_title(base):
    """Document title of about 60 characters, key phrase first.

    The full ' · Stationery Drop Watch' suffix stays only when the whole title still fits.
    A shorter ' · Drop Watch' suffix is used when that fits and the long one does not.
    A title that already names the site is left alone, so the brand is not repeated."""
    text = " ".join(str(base).split())
    for suffix in (TITLE_SUFFIX, BRAND_SHORT):
        if text.endswith(suffix):
            text = text[: -len(suffix)].rstrip(" ·")
    text = TITLE_OVERRIDES.get(text, text)
    if "Stationery Drop Watch" in text or text.endswith("Drop Watch"):
        return text
    if len(text) + len(TITLE_SUFFIX) <= TITLE_LIMIT:
        return text + TITLE_SUFFIX
    if len(text) + len(BRAND_SHORT) <= TITLE_LIMIT:
        return text + BRAND_SHORT
    return text

def seo_desc(text):
    """Meta description of about 160 characters, cut on a word if a template runs long."""
    text = " ".join(str(text).split())
    text = DESC_OVERRIDES.get(text, text)
    if len(text) <= DESC_LIMIT:
        return text
    cut = text[: DESC_LIMIT - 1].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    if not cut.endswith("."):
        cut += "."
    return cut

# Public URL of the site (GitHub Pages custom domain, see site/CNAME). Used for canonical/OG URLs, JSON-LD and sitemap.xml.
BASE = "https://stationerydropwatch.com/"
CNAME = "stationerydropwatch.com"
OG_IMAGE = BASE + "assets/brand/og-image.png"  # 1200x630, made by scripts/brand/make_og.py (Hobonichi side)
# The default card file is still the Hobonichi artwork. It is also the image on the hub and
# the utility pages, so the alt names every tracker. It prints no shop count.
OG_ALT = ("Stationery Drop Watch: restock tracker for Hobonichi, dot grid journals, "
          f"Traveler's Company and MIDORI, checked {CHECK_FREQ}")
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
CONTENT_LASTMOD = "2026-11-12"  # floor for pages whose HTML changed in the Nov 12 refresh
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

PUBLIC_EMAIL = "admin@stationerydropwatch.com"

def plain_email():
    """Visible address, not a mailto link. The comments keep Cloudflare from obfuscating it."""
    return f"<!--email_off-->{E(PUBLIC_EMAIL)}<!--/email_off-->"

def jsonld(obj):
    payload = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    script = '<script type="application/ld+json">' + payload + "</script>"
    if PUBLIC_EMAIL in payload:  # keep the publisher address literal in the page source
        return "<!--email_off-->" + script + "<!--/email_off-->"
    return script

def _page(fname, title, desc, body, ld=(), og_type="website", og_image=OG_IMAGE, og_alt=OG_ALT, noindex=False):
    url = url_for(fname)
    title = seo_title(title)  # brand suffix only when the title still fits in a search result
    desc = seo_desc(desc)
    guide_page = fname in ("where-to-buy-hobonichi-2027/", "hobonichi-techo-vs-cousin-vs-weeks/", "hobonichi-january-start-vs-april-start/", "best-dot-grid-journals/", TN_GUIDE_SLUG + "/")  # guides sit under Guides (the calendar keeps its own nav item)
    # Hobonichi product pages sit under the tracker. The Techo vs Cousin vs Weeks guide
    # starts with hobonichi-techo-, but it is a guide, so only Guides is current.
    hobo_page = fname.startswith(("hobonichi-techo-", "hobonichi-weeks-")) and not guide_page
    def cur(h):  # this page, or the page it sits under (product pages under the tracker, design pages under their section)
        return (h == fname or (hobo_page and h == HOBO_TRACKER) or (guide_page and h == "guides/")
                or (h in [x for x, _ in NAV_TRACKERS] and h.endswith("/") and fname.startswith(h)))
    def nav_a(h, t, cls=""):
        attrs = f' class="{cls}"' if cls else ""
        if cur(h):
            attrs += " aria-current=page"
        return f'<a href="{h}"{attrs}>{E(t)}</a>'
    trk = "".join(nav_a(h, t) for h, t in NAV_TRACKERS)
    # Trackers lead. Shop is a separate link at the end of the rest of the nav, not a fifth tracker.
    rest = "".join(nav_a(h, t) for h, t in NAV) + nav_a("shop/", "Shop")
    nav_inner = f'<span class="nav-trackers">{trk}</span><span class="nav-rest">{rest}</span>'
    # Desktop shows the bar. Narrow screens use a Menu disclosure, which opens without JavaScript.
    nav = (f'<nav class="site-nav site-nav-bar" aria-label="Main">{nav_inner}</nav>'
           f'<details class="nav-menu"><summary>Menu</summary>'
           f'<nav class="site-nav site-nav-panel" aria-label="Main">{nav_inner}</nav></details>')
    foot_items = list(NAV_TRACKERS) + [
        ("guides/", "Guides"), ("hobonichi-2027.html", "2027 calendar"), ("shop/", "Shop"),
        ("about.html", "About"), ("/#good-to-know", "FAQ"), ("contact/", "Contact"), ("privacy.html", "Privacy")]
    foot_nav = "".join(f'<a href="{h}">{E(t)}</a>' for h, t in foot_items)
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
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="assets/brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="assets/brand/favicon-32.png" type="image/png" sizes="32x32">
<link rel="apple-touch-icon" href="assets/brand/apple-touch-icon.png" sizes="180x180">
<meta name="theme-color" content="#fbf6ec">
<meta name="google-site-verification" content="ehGQbmQs5JxWElUIdG8edUxqUYenrSKHsw-bf0v0YzU" />
<meta name="google-site-verification" content="TIX916oAoBcBQiw9fOlEYtdMJCR7GQYKtW67hfrmcA8" />
{ld_html}
</head><body>
<a class="skip" href="#content">Skip to content</a>
<header class="masthead"><div class="wrap">
  <a class="brand" href="index.html" aria-label="Stationery Drop Watch home"><picture><source media="(max-width:340px)" srcset="assets/brand/icon.svg"><img class="brand-logo" src="assets/brand/logo.svg" alt="" width="248" height="44"></picture></a>
  <nav class="site-nav" aria-label="Main">{nav}</nav>
</div></header>
<main id="content" class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p class="foot-brand"><strong>Stationery Drop Watch</strong> checks {N_STORES} shops {CHECK_FREQ}.</p>
  <nav class="foot-nav" aria-label="Footer">{foot_nav}</nav>
  <p class="foot-follow"><a href="follow/">Follow us</a></p>
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
               "The list covers every restock we track, so it could be multiple emails a day. Free, and you can unsubscribe anytime."),
    "shop": ("Hear about new planners and journals",
             "An occasional email when we release a new planner or journal, plus our restock alerts. No spam, unsubscribe anytime."),
}

# One Buttondown list: every subscriber gets every restock email. The label never names a single item.
# The note may say a subscriber can get multiple emails a day. It must not give a daily number.
# SPEED_LINE is backed by data/changes.json (Oct 26-Nov 11, 2026): of 19 restocks where we also saw the sell-out,
# 7 sold out within an hour and 14 within 6 hours. Re-check it before changing the wording.
SPEED_LINE = "Restocks often sell out within hours."
LIST_LINE = "The list covers every restock we track, so it could be multiple emails a day. Free, and you can unsubscribe anytime."
ONE_LIST_LABEL = "Get every restock alert by email"

def signup_for(subject=None, back=None):
    """Signup box for a product, design, or tracker page. subject and back stay so callers can name the page,
    but the label is always the one list. New pages inherit this wording."""
    return signup(label=ONE_LIST_LABEL, note=f"{SPEED_LINE} {LIST_LINE}")

def signup(kind="alerts", label=None, note=None):
    """The site's one signup box (one per page, right under the page intro). Buttondown's standard HTML embed form
    (docs.buttondown.com/building-your-subscriber-base): a plain POST to embed-subscribe; don't submit via fetch,
    Buttondown may need to show a CAPTCHA. Always id="alerts", so "#alerts" links work on every page.
    label/note override the default copy (see signup_for); the form itself never changes."""
    d_label, d_note = SIGNUP_COPY[kind]
    if kind == "shop" and shop_inserts_public():
        d_label = "Hear about new planners, journals, and inserts"
        d_note = "An occasional email when we release a new planner, journal, or printable insert, plus our restock alerts. No spam, unsubscribe anytime."
    label, note = label or d_label, note or d_note
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

def sold_everywhere_html(items, status="status", shop="store_id"):
    """The Traveler's sold-out sentence, inside a product group.

    Shown only when every listing in that group is sold out. A coming-soon or unchecked
    listing keeps the group quiet, the same way the Amazon note does."""
    if not items or {item[status] for item in items} != {"sold_out"}:
        return ""
    n = len({item[shop] for item in items})
    text = (f"Sold out at every shop we track ({n} shops)." if n > 1
            else "Sold out at the only shop we track.")
    return f'<p class="muted small">{text}</p>'

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

# Size and language come only from fields the checker already stores (type, label, title).
# A listing that does not name one is left blank. It is never guessed, and it is never counted as in stock.
_ISO_SIZE = re.compile(r"\b(A4|A5|A6|A7|B5|B6|B7)\b", re.I)
_SIZE_RANK = {name: i for i, name in enumerate(
    ["A6", "A5", "A4", "A7", "B6", "B5", "B7", "Weeks", "Weeks Mega", "Regular", "Card", "Large"])}

def listing_blob(p):
    return " ".join(x for x in (p.get("label"), p.get("title"), p.get("canonical")) if x)

def listing_size(p):
    """Named size only. Weeks and Weeks Mega are the type field. Paper sizes and Regular/Card/Large
    are read from the listing's own label or title."""
    t = p.get("type") or ""
    if t in ("Weeks", "Weeks Mega"):
        return t
    blob = listing_blob(p)
    m = _ISO_SIZE.search(blob)
    if m:
        return m.group(1).upper()
    low = blob.lower()
    if "card size" in low:
        return "Card"
    if re.search(r"\bregular(?:\s+size)?\b", low):
        return "Regular"
    if re.search(r"\blarge\b", low) or re.search(r"\bsize l\b", low):
        return "Large"
    return ""

def listing_language(p):
    """English or Japanese only when that listing's label or title says so.
    A title that names both is not treated as one language."""
    blob = " ".join(x for x in (p.get("label"), p.get("title")) if x)
    found = []
    for word in re.findall(r"\b(English|Japanese)\b", blob, re.I):
        name = "English" if word.lower() == "english" else "Japanese"
        if name not in found:
            found.append(name)
    return found[0] if len(found) == 1 else ""

def listing_family(p):
    """Hobonichi family from the same groups the restock pages already use."""
    for g in GROUPS:
        if g_sec(g) == "hobonichi" and g["match"](p):
            return g["short"], g["slug"]
    return "Other", "other"

def facet_values(items, fn):
    vals = []
    for it in items:
        v = fn(it)
        if v and v not in vals:
            vals.append(v)
    vals.sort(key=lambda v: (_SIZE_RANK.get(v, 50), v))
    return vals

def show_language_filter(items, fn):
    seen = {fn(it) for it in items}
    named = seen - {""}
    return bool(named) and ("" in seen or len(named) > 1)

def in_stock_tally(statuses):
    """In-stock count. unknown is not in stock, and it is not folded into the checked total."""
    n = len(statuses)
    unk = sum(s == "unknown" for s in statuses)
    inn = sum(s == "in_stock" for s in statuses)
    if not n:
        return "No listings"
    if unk == n:
        return "couldn't check this listing" if n == 1 else f"couldn't check these {n} listings"
    if unk:
        return f"{inn} of {n - unk} checked listings in stock · {unk} couldn't be checked"
    return f"{inn} of {n} listings in stock"

def shop_tally(ls):
    shops = len({r["sid"] for r in ls})
    in_shops = len({r["sid"] for r in ls if r["st"] == "in_stock"})
    word = "shop" if shops == 1 else "shops"
    return f"{in_stock_tally([r['st'] for r in ls])} · {in_shops} of {shops} {word} in stock"

def _az_link(r, primary=False):
    if not r.get("az"):
        return ""
    cls = "btn btn-amz btn-sm" if r.get("azm") else "az"
    if primary and r.get("azm"):
        cls = "btn btn-amz btn-sm"
    return f'<a class="{cls}" href="{E(r["az"])}" target="_blank" rel="sponsored noopener">{E(r["azl"])}</a>'

def compare_product(ls):
    """One product, every shop that lists it, so the statuses sit next to each other."""
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    ls = sorted(ls, key=lambda r: (order.get(r["st"], 9), r["s"].lower()))
    h = ls[0]
    same_az = all(r.get("az") == h.get("az") and bool(r.get("azm")) == bool(h.get("azm")) for r in ls)
    name = f'<a href="{E(h["dp"])}">{E(h["gn"])}</a>' if h.get("dp") else E(h["gn"])
    shops = len({r["sid"] for r in ls})
    bits = [E(h.get("t") or ""), f"{shops} {'shop' if shops == 1 else 'shops'}"]
    if h.get("dp"):
        bits.append(f'<a href="{E(h["dp"])}">Design page</a>')
    az = _az_link(h, primary=True) if h.get("az") and same_az else ""
    note = sold_everywhere_html(ls, "st", "sid")
    items = []
    for r in ls:
        region = f' <span class="region" title="Shop\'s home country">{E(r["rg"])}</span>' if r.get("rg") else ""
        variant = f'<span class="sub variant">{E(r["p"])}</span>' if r.get("p") and r["p"] != r.get("gn") else ""
        title = f'<span class="sub">{E(r["title"])}</span>' if r.get("title") and r["title"] not in (r.get("gn"), r.get("p")) else ""
        row_az = _az_link(r) if r.get("az") and not same_az else ""
        items.append(
            f'<li><span class="compare-shop"><a href="{E(r["u"])}" target="_blank" rel="noopener">{E(r["s"])}</a>{region}{variant}{title}{row_az}</span>'
            f'<span class="badge {E(r["st"])}">{STATUS[r["st"]]}</span></li>')
    anchor = f' id="{E(h["g"])}"' if re.fullmatch(r"[A-Za-z][\w-]*", h.get("g") or "") else ""
    return f'''<article class="compare"{anchor}>
  <header class="compare-head"><h3>{name}</h3><p class="compare-tally">{E(shop_tally(ls))}</p><p class="sub">{" · ".join(b for b in bits if b)}</p>{az}{note}</header>
  <ul class="compare-shops">{"".join(items)}</ul>
</article>'''

def tracker_static(rows):
    """No-JS listing groups. Families start closed; the summary is a real control, so they still open."""
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    fam_order = [g["slug"] for g in GROUPS if g_sec(g) == "hobonichi"] + ["other"]
    by_fam = {}
    for r in rows:
        by_fam.setdefault(r.get("fam") or "other", {}).setdefault(r["g"], []).append(r)
    parts = []
    for fam in fam_order:
        products = by_fam.get(fam)
        if not products:
            continue
        groups = sorted(products.values(), key=lambda ls: (
            min(order.get(r["st"], 9) for r in ls),
            -len({r["sid"] for r in ls}),
            ls[0].get("gn", "").lower()))
        name = groups[0][0].get("famn") or "Other"
        all_rows = [r for ls in groups for r in ls]
        body = "".join(compare_product(ls) for ls in groups)
        parts.append(f'''<details class="fam-block" id="{E(fam)}">
  <summary><span class="fam-name">{E(name)}</span><span class="fam-meta">{E(in_stock_tally([r["st"] for r in all_rows]))}</span></summary>
  <div class="fam-products">{body}</div>
</details>''')
    return "".join(parts)

def tracker_block(prods, rows, search_hint, other_opt="", extra="", prefix=""):
    """Filterable list of every listing in `prods` (driven by assets/app.js).
    Without JavaScript the same groups are in the page, inside noscript."""
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    sids = {p["store_id"] for p in prods}
    store_opts = "".join(f'<option value="{E(x["id"])}">{E(x["name"])}</option>' for x in stores["stores"] if x["id"] in sids)
    prod_opts = "".join(f'<option value="{E(k)}">{E(v)}</option>' for k, v in canon.items() if any(p.get("canonical") == k for p in prods))
    type_opts = "".join(f'<option value="{E(t)}">{E(t)}</option>' for t in sorted({p["type"] for p in prods}))
    status_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items() if any(p["status"] == k for p in prods))
    sizes = facet_values(prods, listing_size)
    langs = [v for v in ("English", "Japanese") if any(listing_language(p) == v for p in prods)]
    size_label = (f'<label>Size<select id="f-size"><option value="">All sizes</option>'
                  + "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in sizes) + '</select></label>') if len(sizes) >= 2 else ""
    lang_label = ""
    lang_note = ""
    if show_language_filter(prods, listing_language):
        lang_label = (f'<label>Language<select id="f-lang"><option value="">All languages</option>'
                      + "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in langs) + '</select></label>')
        if any(not listing_language(p) for p in prods):
            lang_note = '<p class="muted small filter-note">Language is taken from the shop\'s own title. Listings that don\'t name one stay under All languages.</p>'
    noscript_rows = tracker_static(rows)
    return f"""<section class="card" id="tracker">
      {prefix}
      <div class="section-head"><h2>Every listing we track</h2><p class="muted small"><span id="count"></span> · {checked_line(prods)}</p></div>
      <form class="filters" id="filters" role="search" aria-label="Filters" onsubmit="return false">
        <details class="filter-more" open>
          <summary>Filters</summary>
          <div class="filter-fields">
            <label>Product<select id="f-product"><option value="">All products</option>{prod_opts}{other_opt}</select></label>
            <label>Type<select id="f-type"><option value="">All types</option>{type_opts}</select></label>
            {size_label}
            {lang_label}
            <label>Store<select id="f-store"><option value="">All stores</option>{store_opts}</select></label>
            <label>Status<select id="f-status"><option value="">Any status</option>{status_opts}</select></label>
          </div>
        </details>
        <label class="grow">Search<input id="f-q" type="search" placeholder="{E(search_hint)}" autocomplete="off"></label>
        <button type="button" class="filter-reset" id="f-reset">Reset</button>
      </form>
      {lang_note}
      <div id="rows" class="tracker-groups"><noscript>{noscript_rows}</noscript></div>
      <button type="button" id="more" class="btn-ghost more" hidden>Show all</button>
      <p class="muted small">Groups can be collapsed. "Not yet on sale" means the store has a preview page up but isn't taking orders yet. "Couldn't check" is a failed check, not a sold-out guess.</p>
      {region_legend(p["store_id"] for p in prods)}
      {extra}
    </section>"""

def tracker_rows(prods, out_everywhere):
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    fam_index = {g["slug"]: i for i, g in enumerate(g for g in GROUPS if g_sec(g) == "hobonichi")}
    rows = []
    for p in prods:
        famn, fam = listing_family(p)
        rows.append(dict(g=product_key(p), p=p["label"], gn=canon.get(p.get("canonical") or "", p["label"]), c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], rg=REGION.get(p["store_id"], ""), st=p["status"],
                 u=p["url"], at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 va=p.get("available_variants"), tv=p.get("total_variants"),
                 sz=listing_size(p), lg=listing_language(p), famn=famn, fam=fam, fo=fam_index.get(fam, 99),
                 az=amazon_for(p.get("canonical"), p["url"])[0], azl=amazon_for(p.get("canonical"), p["url"])[1]))
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

def shop_sets(ls):
    """Tracked shops have a listing. Checked shops have at least one listing whose status is not unknown."""
    tracked = {l["store_id"] for l in ls}
    checked = {l["store_id"] for l in ls if l["status"] != "unknown"}
    buying = {l["store_id"] for l in ls if l["status"] in BUYABLE}
    return tracked, checked, buying

def hero_facts(ls):
    """Status tiles and the line under them, from this page's listings only.
    A zero stays on the tile. Every page shows the same five tiles."""
    s = {k: sum(p["status"] == k for p in ls) for k in ("in_stock", "preorder", "sold_out", "coming_soon", "unknown")}
    tracked, checked_shops, _ = shop_sets(ls)
    return f'''<div class="stats five">
    <div><b>{s["in_stock"]}</b><span>in stock</span></div>
    <div><b>{s["preorder"]}</b><span>preorder</span></div>
    <div><b>{s["sold_out"]}</b><span>sold out</span></div>
    <div><b>{s["coming_soon"]}</b><span>not yet on sale</span></div>
    <div class="unk"><b>{s["unknown"]}</b><span>couldn't check this run</span></div>
  </div>
  <p class="muted small hero-check">Last check: {time_tag(stock["run_finished"])} · {len(ls) - s["unknown"]} of {len(ls)} listings checked successfully · {len(checked_shops)} of {nshops(len(tracked))} checked.</p>'''

def also_tracked(here):
    """The other trackers, in the same place on every tracker hero."""
    here = here if here.endswith("/") else here + "/"
    links = []
    if here != HOBO_TRACKER:
        links.append((HOBO_TRACKER, "Hobonichi tracker"))
    for k in LIVE:
        slug = SECTIONS[k]["slug"] + "/"
        if slug != here:
            links.append((slug, SECTIONS[k]["nav"]))
    return '<p class="small section-switch">Also tracked: ' + " · ".join(f'<a href="{h}">{E(t)}</a>' for h, t in links) + "</p>"

def right_now_sentence(ls):
    """Stock sentence for a hero. Shop counts come from shop_sets, the same sets as the eyebrow."""
    if not ls:
        return "none of the shops we check list this right now."
    tracked, checked, buying = shop_sets(ls)
    unk = [l for l in ls if l["status"] == "unknown"]
    buy = [l for l in ls if l["status"] in BUYABLE]
    if not checked:
        if len(ls) == 1:
            return "we couldn't reach the shop for this listing at the last check, so its status is unknown."
        return f"we couldn't check any of these {len(ls)} listings at the last check, so their status is unknown."
    listed = len(ls) - len(unk)
    listed_word = "checked listings" if unk else "listings"
    sentence = (f"{len(buy)} of {listed} {listed_word} are in stock or on preorder "
                f"at {len(buying)} of {nshops(len(checked))} checked")
    missed = len(tracked) - len(checked)
    if missed:
        sentence += f". {missed} of {nshops(len(tracked))} couldn't be checked this run"
        if len(unk) != missed:
            word = "listing" if len(unk) == 1 else "listings"
            sentence += f" ({len(unk)} {word})"
    elif unk:
        word = "listing" if len(unk) == 1 else "listings"
        sentence += f". {len(unk)} {word} couldn't be checked this run"
    return sentence + "."

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
    # Current status leads. A restock that has since sold out is not styled as still available.
    tone = {"in_stock": "live", "preorder": "hold", "sold_out": "sold"}.get(st, "past")
    return f"""<li class="feed-item" data-tone="{tone}" data-now="{E(st)}"><span class="feed-now">now <span class="badge {E(st)}">{E(label)}</span></span>
  <span class="feed-body"><a href="{E(newest['url'])}" rel="noopener" target="_blank">{E(newest['label'])}</a> <span class="muted">at {E(newest['store'])}</span>
  {ex}<span class="feed-when">restocked {time_tag(newest['at'])}</span></span>{history}</li>"""

def restock_feed(events, extra="", feed_id="restocks", limit=None, fold=False):
    """Grouped restocks. `limit` is how many listings to show, not how many flips. In stock now is CSS-only.
    `fold` adds a disclosure for sold-out rows. It stays open without JavaScript. Narrow screens
    start it closed from app.js and show in-stock rows first. Desktop leaves the time order alone."""
    groups = restock_groups(events)
    if limit is not None:
        groups = groups[:limit]
    fid = E(feed_id)
    items = "".join(restock_feed_item(g, extra) for g in groups)
    fold_html = '<details class="feed-fold" open><summary>Show earlier restocks</summary></details>' if fold else ""
    return f"""<div class="restocks" id="{fid}">
  <div class="feed-controls" role="radiogroup" aria-label="Which restocks to show">
    <label><input type="radio" name="{fid}-view" class="restock-all" checked> All</label>
    <label><input type="radio" name="{fid}-view" class="restock-in"> In stock now</label>
  </div>
  <ol class="feed">{items}</ol>
  {fold_html}
  <p class="feed-empty muted small">None of these are in stock now.</p>
</div>"""

def build_hobo_tracker():
    """The full Hobonichi tracker (the old homepage), now at HOBO_TRACKER. Copy, FAQ and FAQ schema unchanged."""
    prods = hobo_products()  # Hobonichi section only; dot grid shops live on their own page
    s = {k: sum(p["status"] == k for p in prods) for k in STATUS}
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
    out_everywhere = amazon_main(prods)
    rows = tracker_rows(prods, out_everywhere)
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a>: <span class="muted">{E(n["reason"] or "")}</span></li>' for n in stock["not_checked"])

    faq_html, faq_ld = tracker_good_to_know(HOBO_NOTE_Q, HOBO_NOTE)
    more = "".join(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a></li>' for g in GROUPS if g_sec(g) == "hobonichi")
    tracker_html = tracker_block(prods, rows, "Moomin, Cousin, Midnight Blue…", '<option value="__other">Other 2027 items</option>',
        f'<details class="muted small"><summary>Stores we list but don\'t check automatically</summary><ul>{not_checked}</ul></details>',
        prefix=hobo_design_nav())
    body = f"""
{crumbs((HOBO_TRACKER, "Hobonichi tracker"))}
<section class="hero">
  {eyebrow("Hobonichi Techo 2027", f"{len({p['store_id'] for p in prods})} Hobonichi shops", f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}")}
  <h1>Hobonichi 2027 restock tracker</h1>
  <p class="lede">We check the official Hobonichi store and independent shops for sold-out Hobonichi planners and covers, and tell you when they come back.</p>
  {hero_facts(prods)}
  {signup_for("Hobonichi Techo 2027 books and covers")}
  {also_tracked(HOBO_TRACKER)}
</section>

<div class="layout solo">
  <div class="main-col">
    <section class="card" id="restocked">
      <h2>Recent restocks</h2>
      {feed_html}
    </section>
    {tracker_html}
    {faq_html}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{more}</ul></section>
    {guides_block()}
    {soon_block()}
  </div>
</div>
{stock_data(rows)}
"""
    n_shops = len({p['store_id'] for p in prods if p['store_id'] in HOBO_SHOPS})
    return page(HOBO_TRACKER, "Hobonichi 2027 restock tracker",
                f"Hobonichi 2027 restock tracker. Live status for Original A6, Cousin A5, Weeks and covers at {n_shops} shops, plus separate trackers for other brands.",
                body, ld=(faq_ld, crumbs_ld((HOBO_TRACKER, "Hobonichi tracker"))))

HUB_TRACKERS = {  # one line per tracker card on the hub homepage
    "hobonichi": ("Hobonichi Techo 2027", "Original A6, Cousin A5, Weeks, Weeks Mega and covers, at the official store and independent shops."),
    "dotgrid": ("Dot grid journals", ""),  # shop names filled in from stores.json
    # Live listings are the five Regular colors, the ROAD TRIP exclusive, anniversary sets, and 2027 diary
    # accessories. Refills and Passport size are not listings on this tracker (the size guide says so).
    "travelers": ("Traveler's Company", "Regular size colors, plus limited editions: 2027 diary accessories, anniversary sets and shop exclusives."),
    "midori": ("MIDORI MD", "MD Notebook diaries and MIDORI MD seasonal releases."),
}
HUB_FAQ = ("How often do you check the shops?", "What do you track?",
           'What do "Not yet on sale" and "Couldn\'t check" mean?',
           "How do restock alerts work?", "Which shops do you check?", "Do you sell planners?")

def hub_art(kind):
    """Small inline drawing in the existing palette. Not a retailer or manufacturer photo."""
    common = 'viewBox="0 0 160 64" width="160" height="64" aria-hidden="true" focusable="false"'
    ink, paper, accent, sage = "#2d2a32", "#fffdf8", "#c1553b", "#5f8a6b"
    if kind == "hobonichi":
        body = f'<rect x="52" y="6" width="56" height="52" rx="3" fill="{paper}" stroke="{ink}" stroke-width="2"/><path d="M52 16 h56" stroke="{accent}" stroke-width="8"/><path d="M96 6 v16 l5-3 5 3 V6" fill="{accent}"/><path d="M64 30 h32 M64 38 h32 M64 46 h18" stroke="{sage}" stroke-width="2" stroke-linecap="round"/>'
    elif kind == "dotgrid":
        # Portrait journal on the same center as the other icons (80, 32).
        # The terracotta band clears the corner radius; the sage bookmark sits in that band.
        # The square 7×5 grid is centered in the page below the band.
        dots = "".join(f'<circle cx="{x}" cy="{y}" r="1.5" fill="{ink}"/>'
                       for x in range(59, 102, 7) for y in range(23, 52, 7))
        body = (f'<rect x="51" y="6" width="58" height="52" rx="3" fill="#f4ecdc" stroke="{ink}" stroke-width="2"/>'
                f'<path d="M51 14 h58" stroke="{accent}" stroke-width="6"/>'
                f'<path d="M75 6 v11 l5-3 5 3 V6" fill="{sage}"/>{dots}')
    elif kind == "travelers":
        body = f'<rect x="46" y="8" width="68" height="48" rx="2" fill="#f4ecdc" stroke="{ink}" stroke-width="2"/><path d="M46 14 h68 M58 8 v48" stroke="{accent}" stroke-width="2"/><path d="M100 18c8 6 8 22 0 28" fill="none" stroke="{sage}" stroke-width="2"/>'
    else:
        body = f'<rect x="54" y="8" width="52" height="48" rx="2" fill="{paper}" stroke="{ink}" stroke-width="2"/><path d="M54 20 h52" stroke="{sage}" stroke-width="6"/><path d="M66 32 h28 M66 40 h28" stroke="{ink}" stroke-width="1.6" stroke-linecap="round"/>'
    return f'<svg {common}>{body}</svg>'

def trust_strip(prods):
    """Shops, cadence, last check, and the honest checked-successfully count. No availability bar."""
    unknown = sum(p["status"] == "unknown" for p in prods)
    checked = len(prods) - unknown
    missed = (f' <span class="trust-miss">{unknown} couldn\'t be checked this run.</span>'
              if unknown else "")
    # One pattern on every card: the figure first, the short label after it in the text.
    # "Every 30 min" is the same half-hour check; other pages still say CHECK_FREQ.
    facts = f'''<ul class="trust" aria-label="Inventory monitoring">
  <li><b>{N_STORES}</b> <span>shops checked</span></li>
  <li><b>Every 30 min</b> <span>check interval</span></li>
  <li><b class="trust-when">{time_tag(stock["run_finished"])}</b> <span>last check</span></li>
  <li><b>{checked} of {len(prods)}</b> <span>listings checked successfully</span>{missed}</li>
</ul>'''
    # Clip sits beside the cards, about their height on a wide screen. The file is a scaled copy of the approved art, with no caption.
    return f'''<div class="trust-with-clip">
  {facts}
  <img class="clip" src="assets/brand/clip.webp" width="360" height="539" alt="Clip, the Stationery Drop Watch paper clip, checking stock" loading="lazy" decoding="async">
</div>'''

def build_index():
    """Hub homepage: hero and signup, the four trackers, recent restocks from every tracker, guides, FAQ.
    Our own products are not on this page. The header and footer Shop links go to /shop."""
    prods = stock["products"]
    s = {k: sum(p["status"] == k for p in prods) for k in STATUS}
    keys = ["hobonichi", *LIVE]
    href = {"hobonichi": HOBO_TRACKER, **{k: SECTIONS[k]["slug"] + "/" for k in LIVE}}
    cards = []
    for k in keys:
        ps = section_products(k)
        st = {x: sum(p["status"] == x for p in ps) for x in STATUS}
        name, line = HUB_TRACKERS[k]
        if k == "dotgrid":
            line = f"{dotgrid_names()}, each checked on its own store."
        bits = [f"{N_SEC[k]} shops"]
        if st["preorder"]:
            bits.append(f'{st["preorder"]} on preorder')
        if st["unknown"]:
            bits.append(f'{st["unknown"]} couldn\'t be checked')
        # in_stock is status == "in_stock" only. unknown is not counted as in stock.
        cards.append(f"""<li class="hub-card"><a href="{href[k]}">
  <span class="hub-art">{hub_art(k)}</span>
  <h3>{E(name)}</h3><p>{E(line)}</p>
  <p class="hub-count"><b>{st["in_stock"]}</b> of {len(ps)} listings in stock <span class="muted small">{E(" · ".join(bits))}</span></p>
  <span class="hub-go">View tracker</span></a></li>""")
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
        feed_html = restock_feed(recent, hub_tag, feed_id="hub-restocks", limit=12, fold=True)
    else:
        start = tracking_start(prods)
        lead = "No restocks spotted yet." if not restocks else "No restocks in the last 14 days."
        feed_html = f"""<div class="empty"><p><strong>{lead}</strong> Tracking started {time_tag(start)}.
  A restock shows up here the moment a sold-out item flips back to in stock or preorder between two checks.</p>
  <p class="muted">Right now: {s['sold_out']} tracked listings are sold out and {s['coming_soon']} aren't on sale yet.</p></div>"""
    guides = "".join(f'<li><a href="{h}">{E(t)}</a>{f"<p class=\"muted small\">{E(GUIDE_BLURBS[h])}</p>" if h in GUIDE_BLURBS else ""}</li>' for h, t in GUIDES)
    faq_html, faq_ld = faq_block(only=HUB_FAQ, sid="good-to-know")
    body = f"""
<section class="hero">
  {eyebrow(tracker_count_label(), f"{N_STORES} shops", f"checked {CHECK_FREQ}")}
  <h1>Never miss a stationery restock.</h1>
  <p class="hero-shops">We check {N_STORES} shops for you</p>
  <p class="suggest">Know the moment your planner or journal is back.</p>
  <p class="lede">We check official stores and independent shops for sold-out Hobonichi planners, dot grid journals, Traveler's Company notebooks and MIDORI MD releases, and tell you when they come back.</p>
  {signup()}
  {trust_strip(prods)}
  <p class="small section-switch">More on the site: <a href="hobonichi-2027.html">2027 calendar</a> · <a href="guides/">Guides</a> · <a href="shop/">Shop</a> · <a href="sold-out-everywhere/">Sold out everywhere</a>.</p>
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

{faq_html}
"""
    site_ld = {"@context": "https://schema.org", "@type": "WebSite", "name": "Stationery Drop Watch", "url": BASE,
               "description": f"Restock checks {CHECK_FREQ} for Hobonichi Techo 2027 planners and covers across the official store and independent shops, and, in separate sections, {sections_phrase()}.",
               "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE,
                             "description": f"Independent restock tracker for Hobonichi Techo 2027 planners and covers, plus {sections_phrase()}. Statuses come straight from each shop's public product data.",
                             "logo": BASE + "assets/brand/icon-512.png", "email": PUBLIC_EMAIL,
                             "sameAs": [s[2] for s in SOCIALS]}}
    return page("index.html", "Hobonichi, dot grid, Traveler's Company, MIDORI",
                f"Live stock at {N_STORES} shops: Hobonichi Techo 2027, dot grid journals, Traveler's notebooks and MIDORI MD, plus free email alerts for every restock we track.",
                body, ld=(site_ld, faq_ld))

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
  <li><time>February 2027</time><div><h3 class="tl">Spring launch (April-start planners)</h3><p>Paper Mouse describes a second release in February for planners that start on April 1, the beginning of Japan's academic and fiscal year. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
</ol>

<h2>Will it come back?</h2>
<p>Usually, but not always. Standard planner books and core colors tend to be restocked. Special collaborations may only be sold at launch <a href="#s-atlas">[Atlas]</a>. Paper Mouse says almost every item has been restocked at least once after launch in past years <a href="#s-papermouse">[Paper Mouse]</a>. Hobonichi's own restock emails are only for the Techo books and the Drawer Pouch, not accessories, and they don't promise you'll get one <a href="#s-1101">[Hobonichi]</a>.</p>

<h2>How to not miss it</h2>
<ul>
  <li>Check several shops. When one store sells out, another often still has stock. That's the whole point of the <a href=\"""" + HOBO_TRACKER + """#tracker">tracker</a>.</li>
  <li>Live stock by product: """ + " · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS) + """.</li>
  <li>Buying direct from Hobonichi is the only way to get store-exclusive extras, but it ships from Japan and tariffs may apply in the US <a href="#s-papermouse">[Paper Mouse]</a>.</li>
  <li>Which shops have it right now: <a href="where-to-buy-hobonichi-2027/">where to buy the Hobonichi Techo 2027</a>. Choosing a size: <a href="hobonichi-techo-vs-cousin-vs-weeks/">Techo vs Cousin vs Weeks</a>.</li>
  <li><a href="#alerts">Sign up for alerts</a> (above) and we'll email you about every restock we track, so it could be multiple emails a day.</li>
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
<p>{E(AFFILIATE_NOTE)} When you open an Amazon link, Amazon may set its own cookies to credit the referral; that happens on Amazon's side under <a href="https://www.amazon.com/gp/help/customer/display.html?nodeId=GX7NJQ4ZB8MHFRNJ" data-plain-amazon target="_blank" rel="noopener">Amazon's privacy notice</a>. Links to the shops we track are plain links, and what you do on their sites is covered by their own policies.</p>
<h2>Contact</h2>
<p>Questions, or want your email address removed? Email {plain_email()}.</p>
</article>"""
    return page(fname, "Privacy", "How Stationery Drop Watch handles email signups (Buttondown), cookie-free Cloudflare Web Analytics and Amazon affiliate links. We don't set our own cookies.", body, ld=(crumbs_ld((fname, "Privacy")),))

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
<p>Independent stationery shops can book the featured spot on the tracker to promote a restock or launch. It's clearly labeled as sponsored. Shops: want a featured restock slot? Email {plain_email()} for rates and dates.</p>
<h2>Affiliate links</h2>
<p>{E(AFFILIATE_NOTE)} Buying through an Amazon link costs you nothing extra, and it never changes what the tracker shows.</p>
<h2>Contact</h2>
<p>Questions, corrections, or a shop we should track? Email {plain_email()}. The <a href="contact/">contact page</a> is there too.</p>
</article>"""
    return page("about.html", "About Stationery Drop Watch: how we check stock", f"How Stationery Drop Watch checks {n_checked} shops for Hobonichi, dot grid, Traveler's and MIDORI restocks, and why a failed check is never shown as a guess.", body, ld=(crumbs_ld(("about.html", "About")),))

def build_contact():
    """Visible contact page. The address is plain text, wrapped so Cloudflare Email Obfuscation leaves it alone."""
    fname = "contact/"
    shown = plain_email()
    body = f"""
<article class="prose">
{crumbs((fname, "Contact"))}
{eyebrow("Contact", "Stationery Drop Watch")}
<h1>Contact</h1>
<p class="lede">Stationery Drop Watch checks planner and journal stock at official stores and independent shops, and writes down what each shop last reported.</p>
<p>Questions, corrections, a shop we should track, or a featured restock slot: {shown}</p>
<p class="small"><a href="about.html">About</a> explains how the checks work. <a href="privacy.html">Privacy</a> explains the email list.</p>
</article>"""
    desc = ("How to reach Stationery Drop Watch: questions, corrections, a shop to add, "
            "or a featured restock slot. The address is written on this page too.")
    return fname, page(fname, "Contact", desc, body, ld=(crumbs_ld((fname, "Contact")),))

# --- Product restock pages (one indexable page per tracked product group) ---------------------
# Every status on these pages comes from data/stock.json exactly as the checker wrote it.
def _is_a6_book(p):
    return p["type"] == "Book" and (p.get("canonical") in ("original-a6-en", "original-a6-jp")
                                     or (not p.get("canonical") and "a6" in p["label"].lower()))

GROUPS = [
    dict(slug="hobonichi-techo-2027-original-a6", short="Original A6", product="Hobonichi Techo 2027 Original (A6)",
         match=_is_a6_book,
         desc="Is the Hobonichi Original A6 in stock? Live status for the English and Japanese books at {shops} shops, with a link to each shop's listing. See each shop's page.",
         intro="The Original is Hobonichi's A6 one-page-a-day book, sold in an English and a Japanese edition. "
               "Below is what each shop we track reported at its last check: in stock, on preorder, sold out, or not on sale yet. "
               "If a check failed we say \"Couldn't check\" rather than guess."),
    dict(slug="hobonichi-techo-2027-cousin-a5", short="Cousin A5", product="Hobonichi Techo 2027 Cousin (A5)",
         match=lambda p: p.get("canonical") == "cousin-a5-en",
         desc="Is the Hobonichi Cousin A5 in stock? Live status for the English Cousin at {shops} shops, with every restock we spot and a link to each listing. See each listing.",
         intro="The Cousin is the A5 version of the Techo, with a page a day and more room to write. "
               "Here's what each shop we track reported for the English Cousin at its last check."),
    dict(slug="hobonichi-weeks-2027", short="Weeks", product="Hobonichi Weeks 2027",
         match=lambda p: p["type"] == "Weeks",
         desc="Is Hobonichi Weeks 2027 in stock? Live status for Midnight Blue, Canaria Yellow, tanakadaisuke: Starlight and more at {shops} shops. Open a shop's page to confirm.",
         intro="Weeks is Hobonichi's slim, wallet-size weekly planner, and the popular covers sell out fast. "
               "These are the 2027 Weeks listings we track, grouped by design, with the status each shop reported at its last check."),
    dict(slug="hobonichi-weeks-mega-2027", short="Weeks Mega", product="Hobonichi Weeks Mega 2027",
         match=lambda p: p["type"] == "Weeks Mega",
         desc="Is Hobonichi Weeks Mega 2027 in stock? Live status for each tracked design at {shops} shops, with a link to every shop's listing. Open a shop's page to confirm.",
         intro="Weeks Mega is the Weeks planner with extra blank pages at the back. "
               "Here's what each shop we track reported for the 2027 Weeks Mega listings at its last check."),
    dict(slug="hobonichi-techo-2027-hon", short="HON", product="Hobonichi Techo 2027 HON",
         match=lambda p: p["type"] == "HON",
         desc="Is the Hobonichi Techo 2027 HON in stock? Live status for the A5 and A6 Slash (Navy) books at {shops} shops, with a link to each listing. See each shop's page.",
         intro="The HON is Hobonichi's book with the cover attached. Slash (Navy) is tracked here in A5 and in A6. "
               "Hobonichi's own page for each size includes the English and Japanese books. "
               "A shop row names the language that shop sells."),
    dict(slug="hobonichi-techo-2027-covers", short="Covers", product="Hobonichi Techo 2027 cover",
         match=lambda p: p["type"] == "Cover",
         desc="Are Hobonichi Techo 2027 covers in stock? Live status for the tracked A6 and A5 covers at {shops} shops, with a link to each listing. Open a shop's page to confirm.",
         intro="Popular Hobonichi covers can sell out within minutes of a drop. "
               "We track a handful of 2027 covers: A6 covers for the Original, and one A5 cover for the Cousin. "
               "Here's what each shop reported at its last check."),
    dict(slug=DOTGRID_SLUG, short="Dot grid journals", product="Dot grid journal", section="dotgrid", featured=True,
         search_hint="Ice Castle, 8x8, kraft…",
         match=is_dotgrid,
         eyebrow="Dot grid journaling", unit="listings",
         open_hint="Open a row to go straight to that exact size and color on the shop's site",
         guide_q="Do sizes, papers and colors sell out on their own?",
         guide="Dot grid journals come in several sizes, papers and colors, and each one sells out on its own. "
               "We check the exact variant named in each row, so \"In stock\" means that size and color, not just some version of the journal. "
               "To compare paper weight, pages and size across the four brands, see <a href=\"best-dot-grid-journals/\">best dot grid journals compared</a>.",
         # Published URL stays /archer-and-olive-dot-grid-journal/ so existing links keep working.
         # The title, heading, nav, and breadcrumb name every maker we check.
         title=f"Dot grid journal restock tracker: {dotgrid_names()}",
         desc=f"Are {dotgrid_names()} dot grid journals in stock? Live size-by-size status at each maker's shop.",
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Popular dot grid journals and limited editions sell out, and every brand only posts its own restocks. "
               f"We track a focused set of flagship dot grid notebooks from {dotgrid_names()}, each on that maker's own store, size by size and color by color, plus Archer and Olive's dot grid refills. "
               "This page covers those dot grid notebooks and refills, not pens or other paper, and Hobonichi and our other sections have their own pages."),
    dict(slug=SECTIONS["travelers"]["slug"], short="Traveler's Company", product="Traveler's Notebook", section="travelers",
         h1="Traveler's Notebook restock tracker: regular colors and limited editions",
         match=lambda p: section_of(p) == "travelers", eyebrow="Traveler's Company", search_hint="Sticker set, Olive, 20th…",
         guide_q="How do Traveler's Company allocations and Regular notebooks work?",
         guide="Traveler's Company makes its limited editions in small runs, and each shop gets its own allocation, so one shop can sell out while another still has stock. "
               "We also track the five standard Regular size notebooks: Black (No. 13714006), Brown (No. 13715006), Blue (No. 15239006), Camel (No. 15193006) and Olive (No. 15342006). "
               "Traveler's Company warns that counterfeits are sold in the US, so we only list the official US shop and authorized retailers. For refills, check the shops directly. "
               f'Choosing Regular, Passport, or the Card Size anniversary set: <a href="{TN_GUIDE_SLUG}/">Regular vs Passport vs Card Size</a>.',
         # Published URL stays /travelers-company-limited-edition/. The heading names Regular colors and limited editions.
         title="Traveler's Notebook restock tracker: regular colors and limited editions",
         desc="Are Traveler's Notebook Regular colors, 2027 diary accessories and anniversary sets in stock? Live status at {shops} official and independent shops. See each row.",
         og_image=OG_TRAVELERS,
         og_alt=OG_TRAVELERS_ALT,
         intro="We track the five Regular size Traveler's Notebook colors (Black, Brown, Blue, Camel and Olive) plus Traveler's Company limited editions: the yearly diary accessories, anniversary sets and shop exclusives. "
               "We check the official Traveler's Company USA shop and independent shops, item by item. "
               "Hobonichi and our other sections have their own pages."),
    dict(slug=SECTIONS["midori"]["slug"], short="MIDORI MD", product="MIDORI MD seasonal release", section="midori",
         match=lambda p: section_of(p) == "midori", eyebrow="MIDORI MD", search_hint="Diary 2027, 1 Day 1 Page, Stickers…",
         guide_q="When do the dated MD diaries and stickers come back?",
         guide="MIDORI makes the dated MD diaries and diary stickers once a year, so when a shop's allocation is gone it is usually gone until the next year's edition. "
               "The plain MD notebooks stay in the catalog all year, so we don't track them here.",
         title=f"MIDORI MD seasonal release restock tracker",
         desc="Are the MIDORI MD Notebook Diary 2027, the 1 Day 1 Page diary and the 2027 diary stickers in stock? Live status at {shops} shops. Each row links to that shop.",
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

def listing_group_id(l):
    """Group key for a listing. The canonical id is the product, so sizes and colors stay in one group."""
    return l.get("canonical") or ""

# Dot grid product groups follow the maker, not whichever other shop happens to list a Leuchtturm notebook.
# Archer and Olive stays together at the top, including the refill notebooks.
DOTGRID_BRAND_ORDER = ("archerandolive", "leuchtturm1917", "scribblesthatmatter", "notebooktherapy")

def dotgrid_group_key(cid):
    base = cid.split("|", 1)[0]
    brand, pos = "", 10_000
    for i, c in enumerate(stores["canonical"]):
        if c["id"] == base:
            brand = c.get("brand") or ""
            pos = i
            break
    try:
        bi = DOTGRID_BRAND_ORDER.index(brand)
    except ValueError:
        bi = len(DOTGRID_BRAND_ORDER)
    return (bi, pos, cid)

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
        rows.append(f"""<tr data-store="{E(l['store_id'])}" data-status="{E(l['status'])}" data-size="{E(listing_size(l))}" data-lang="{E(listing_language(l))}"><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a>{region_tag(l['store_id'])}<span class="sub">{E(l.get('title') or l['label'])}</span></td>
  <td><span class="badge {E(l['status'])}">{E(STATUS[l['status']])}</span>{since_html}{row_amz(l, oe)}</td></tr>""")
    return "".join(rows)

def list_filter(ls, hint):
    """Search, store, and status for a shop list. The table stays in the HTML, so it works with no JavaScript."""
    if len(ls) < 2:
        return ""
    seen = []
    for l in sorted(ls, key=lambda l: l["store"].lower()):
        if l["store_id"] not in {s for s, _ in seen}:
            seen.append((l["store_id"], l["store"]))
    store_opts = "".join(f'<option value="{E(sid)}">{E(name)}</option>' for sid, name in seen)
    status_opts = "".join(f'<option value="{k}">{STATUS[k]}</option>' for k in STATUS if any(l["status"] == k for l in ls))
    sizes = facet_values(ls, listing_size)
    langs = [v for v in ("English", "Japanese") if any(listing_language(l) == v for l in ls)]
    size_label = (f'<label>Size<select data-filter="size"><option value="">All sizes</option>'
                  + "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in sizes) + '</select></label>') if len(sizes) >= 2 else ""
    lang_label = ""
    lang_note = ""
    if show_language_filter(ls, listing_language):
        lang_label = (f'<label>Language<select data-filter="lang"><option value="">All languages</option>'
                      + "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in langs) + '</select></label>')
        if any(not listing_language(l) for l in ls):
            lang_note = '<p class="muted small filter-note">Language is taken from the shop\'s own title. Listings that don\'t name one stay under All languages.</p>'
    return f"""<form class="filters page-filter card-filter" id="filters" role="search" aria-label="Filters" onsubmit="return false">
      <details class="filter-more" open>
        <summary>Filters</summary>
        <div class="filter-fields">
          {size_label}
          {lang_label}
          <label>Store<select data-filter="store"><option value="">All stores</option>{store_opts}</select></label>
          <label>Status<select data-filter="status"><option value="">Any status</option>{status_opts}</select></label>
        </div>
      </details>
      <label class="grow">Search<input data-filter="q" type="search" placeholder="{E(hint)}" autocomplete="off"></label>
      <button type="button" class="filter-reset" data-filter="reset">Reset</button>
    </form>
    {lang_note}"""

def group_seo_title(g):
    """Short document title. The visible H1 stays the longer product name."""
    sec = g_sec(g)
    if sec == "dotgrid":
        return "Dot grid journal tracker"
    if sec == "travelers":
        return "Traveler's Notebook tracker"
    if sec == "midori":
        return "MIDORI MD tracker"
    return f'Hobonichi {g["short"]} tracker'

def design_family(parent_slug):
    return {
        "hobonichi-weeks-2027": "Weeks",
        "hobonichi-weeks-mega-2027": "Weeks Mega",
        "hobonichi-techo-2027-covers": "cover",
        "hobonichi-techo-2027-hon": "HON",
        "hobonichi-techo-2027-original-a6": "Original A6",
        "hobonichi-techo-2027-cousin-a5": "Cousin",
        DOTGRID_SLUG: "dot grid",
        SECTIONS["travelers"]["slug"]: "Traveler's",
        SECTIONS["midori"]["slug"]: "MIDORI",
    }.get(parent_slug, "stock")

def design_seo_title(d):
    return f'{d["name"]} · {design_family(d["parent"])} stock'

def design_seo_desc(d, shops):
    word = "shop" if shops == 1 else "shops"
    fam = design_family(d["parent"])
    core = (f'Is {d["name"]} in stock? Live {fam} status at {shops} {word}, '
            f'with a link to each shop\'s listing.')
    # Longer pages of true detail are used only while the description stays within 160 characters.
    for extra in (" Open the shop's page to confirm before you buy. Stock can change.",
                  " Open the shop page to confirm this exact listing now.",
                  " Confirm it on the shop's own page."):
        if len(core + extra) <= DESC_LIMIT:
            return core + extra
    return core

def group_signup(g, buy):
    """Section pages (dot grid, Traveler's, MIDORI) name the brand; product pages name the product."""
    if g_sec(g) != "hobonichi" and not g.get("parent"):
        return signup_for(SECTIONS[g_sec(g)]["name"])
    return signup_for(g["product"], back=not buy)

def build_group(g, oe):
    ls = group_listings(g)
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    shops = len({l["store_id"] for l in ls})
    buy = [l for l in ls if l["status"] in BUYABLE]
    sections = {}
    for l in ls:
        sections.setdefault(listing_group_id(l), []).append(l)
    known = [c["id"] for c in stores["canonical"] if c["id"] in sections]
    extra = [k for k in sections if k not in known and k != ""]
    order = known + extra + ([""] if "" in sections else [])
    ext = g_sec(g) != "hobonichi"  # non-Hobonichi sections carry their own tracker table on the page
    per_shop = g.get("per_shop")  # dot grid: every product sits in one maker's store, so the page goes shop by shop
    if g_sec(g) == "dotgrid":
        order.sort(key=dotgrid_group_key)
    elif per_shop:  # shops in stores.json order (Archer and Olive first)
        rank = {s["id"]: i for i, s in enumerate(stores["stores"])}
        order.sort(key=lambda cid: min(rank[l["store_id"]] for l in sections[cid]))
    parts = []
    seen_shop = set()
    for cid in order:
        sl = sections[cid]
        if cid in canon:
            name = canon[cid]
        elif "|" in cid:
            name = cid.split("|", 1)[1]
        else:
            name = "Other designs and editions" if len(order) > 1 else "Listings"
        sold_html = sold_everywhere_html(sl)
        m = page_amz(sl, oe) if cid else None
        if m:
            # The sold-out sentence is its own line in the group. Don't print it again beside the button.
            span = "" if sold_html else f' <span class="muted small">{E(m["note"])}.</span>'
            amz_btn = (f'<p><a class="btn btn-amz" href="{E(m["url"])}" target="_blank">{E(m["label"])}</a>'
                       f'{span}</p>')
        else:
            amz_btn = ""
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
        meta = f"{E(count_line(sl, g.get('unit', 'listings')).capitalize())} · {checked_line(sl)}"
        parts.append(f"""<details class="card group-fold">
  <summary><{hx} class="fam-name">{E(name)}</{hx}><span class="fam-meta">{meta}</span></summary>
  <section class="group-sec" id="{E(re.sub(r'[^A-Za-z0-9]+', '-', cid).strip('-') or 'other')}">
  {sold_html}{amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(sl, oe)}</tbody>
  </table></div>
  <p class="muted small">{g.get('open_hint', "Open a shop's name to go straight to its listing")}{az_sub}{tracker}{dp_link}</p>
  {"" if any("region-legend" in x for x in parts) else region_legend(l["store_id"] for l in ls)}
</section></details>""")
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
        others = f'<li><a href="{HOBO_TRACKER}">Hobonichi tracker</a></li>' + others
        others += f'<li><a href="#tracker">Every {E(SECTIONS[g_sec(g)]["one"])} listing we track (this page)</a></li>'
        # Shop headings keep their anchors. The jump row repeated them.
        shop_nav = ""
        dg_tracker = ""  # per-product tables are the one view; the old grouped table repeated every listing
    else:
        others += f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>'
        shop_nav = dg_tracker = ""
    card_filter = list_filter(ls, g.get("search_hint") or "Shop or design")
    ds = designs_of(g["slug"])
    links = "".join(f'<li><a href="{design_fname(d)}">{E(d["name"])}</a></li>' for d in ds)
    design_nav = (f'<details class="design-fold"><summary>Design pages ({len(ds)})</summary>'
                  f'<ul class="link-list">{links}</ul></details>') if ds else ""
    faq_html, faq_ld = tracker_good_to_know(g.get("guide_q", HOBO_NOTE_Q), g.get("guide", HOBO_NOTE))
    body = f"""
<div class="product-page">
{crumbs((g["slug"] + "/", g["short"]))}
<section class="hero{' hero-compact' if not ext or g.get('parent') else ''}">
  {eyebrow(g.get('eyebrow', 'Hobonichi Techo 2027'), nshops(shops), f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}") if ext and not g.get("parent") else eyebrow(g.get('eyebrow', 'Hobonichi Techo 2027'), nshops(shops), f"checked {CHECK_FREQ}")}
  <h1>{E(g['h1'])}</h1>
  <p class="lede">{E(g['intro'])}</p>
  {hero_facts(ls)}
  {group_signup(g, buy)}
  {also_tracked(g["slug"] + "/") if ext and not g.get("parent") else ""}
</section>
<div class="layout solo">
  <div class="main-col">
    <section class="card"><h2>Recent restocks</h2>{restock_html}</section>
    <div id="tracker"{' class="card-filtered"' if ext else ''}>
    {design_nav}{shop_nav}{card_filter}{''.join(parts)}
    <p class="muted small card-empty" hidden>Nothing on this page matches those filters.</p>
    </div>
    {dg_tracker}
    {faq_html}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {"" if ext else guides_block()}
  </div>
</div>
</div>"""
    fname = g["slug"] + "/"
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": g["h1"] + ": listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: (l.get("canonical") or "~", l["store"])))]}
    title = group_seo_title(g)
    return fname, page(fname, title, g["desc"].format(shops=shops), body, ld=(crumbs_ld((fname, g["short"])), items, faq_ld),
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
    dict(parent="hobonichi-weeks-2027", slug="starlight", name="tanakadaisuke: Starlight", full="Hobonichi Weeks 2027 tanakadaisuke: Starlight",
         match=lambda p: p.get("canonical") == "weeks-starlight",
         why="2027 Weeks hardcover book, January start, Monday start. The official listing includes English and Japanese. The other matched shops sell the English book."),
    dict(parent="hobonichi-weeks-mega-2027", slug="candy-dream", name="Bow & Tie: Candy Dream", full="Hobonichi Weeks Mega 2027 Bow & Tie: Candy Dream",
         match=lambda p: p.get("canonical") == "weeks-mega-candy-dream",
         why="5 shops, including one not yet on sale."),
    dict(parent="hobonichi-weeks-2027", slug="sea-glass", name="Sea Glass", full="Hobonichi Weeks 2027 Sea Glass",
         match=lambda p: p.get("canonical") == "weeks-sea-glass",
         why="Colors Sea Glass, the regular 2027 Weeks hardcover. The official listing includes English and Japanese. The other shops sell the English book."),
    dict(parent="hobonichi-weeks-2027", slug="v-and-a", name="V&A series", full="Hobonichi Weeks 2027 V&A series",
         match=lambda p: p.get("canonical") in ("weeks-va-welcome", "weeks-va-leicester"),
         why="Welcome to the V&A and Leicester stay on one family page. They are separate regular 2027 Weeks books, not one mixed product."),
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
         match=lambda p: p.get("canonical") == "weeks-pink-sapphire",
         why="Colors Pink Sapphire, the regular 2027 Weeks hardcover. The official listing includes English and Japanese. The other shops sell the English book."),
    dict(parent="hobonichi-weeks-2027", slug="paper-series-jade", name="Paper Series: Frosty Jade", full="Hobonichi Weeks 2027 Paper Series Frosty Jade",
         match=lambda p: p.get("canonical") == "weeks-paper-frosty-jade" or p.get("url") == "https://omoionline.com/products/hobonichi-techo-2027-weeks-paper-series-planner-jade",
         why="Hobonichi's English name is Frosty Jade. The removed Omoi listing said Jade. Same Paper Series Weeks book, not a cover."),
    dict(parent="hobonichi-weeks-2027", slug="shirt-fabric-graph-plaid", name="Shirt Fabric: Graph Plaid", full="Hobonichi Weeks 2027 Shirt Fabric Graph Plaid",
         match=lambda p: p.get("canonical") == "weeks-shirt-graph-plaid" or p.get("url") == "https://omoionline.com/products/hobonichi-techo-2027-weeks-shirt-fabric-planner-graph-plaid",
         why="Regular 2027 Weeks hardcover. Not the Weeks cover and not Brownie Plaid."),
    dict(parent="hobonichi-weeks-2027", slug="floral-remedy", name="Liberty Fabrics: Floral Remedy", full="Hobonichi Weeks 2027 Liberty Fabrics Floral Remedy",
         match=lambda p: p.get("canonical") == "weeks-floral-remedy",
         why="Regular 2027 Weeks hardcover, January start. Official listing includes English and Japanese. Retailer rows here are the English book. Not a Weeks cover."),
    dict(parent="hobonichi-weeks-2027", slug="nothing-to-hide-yellow", name="beautiful people: Nothing to Hide (Yellow)", full="Hobonichi Weeks 2027 cover beautiful people Nothing to Hide (Yellow)",
         match=lambda p: p.get("canonical") == "weeks-beautiful-people-yellow",
         why="A cover for the Weeks book, not the Weeks book itself and not a Weeks Mega."),
    dict(parent="hobonichi-techo-2027-hon", slug="a5-slash-navy", name="A5 Slash (Navy)", full="Hobonichi HON 2027 A5 Slash (Navy)",
         match=lambda p: p.get("canonical") == "hon-a5-slash-navy" or p.get("url") == "https://omoionline.com/products/hobonichi-techo-2027-hon-a5-slash-planner-navy"),
    dict(parent="hobonichi-techo-2027-hon", slug="a6-slash-navy", name="A6 Slash (Navy)", full="Hobonichi HON 2027 A6 Slash (Navy)",
         match=lambda p: p.get("canonical") == "hon-a6-slash-navy" or p.get("url") == "https://omoionline.com/products/hobonichi-techo-2027-hon-a6-slash-planner-navy"),
    dict(parent="hobonichi-techo-2027-covers", slug="moomin-my-yard", name="Moomin: My Yard", full="Hobonichi Techo 2027 A6 cover Moomin: My Yard",
         match=lambda p: p.get("canonical") == "cover-a6-moomin"),
    dict(parent="hobonichi-techo-2027-covers", slug="white-cat-house", name="Yumi Kitagishi: White Cat House", full="Hobonichi Techo 2027 A6 cover White Cat House",
         match=lambda p: p.get("canonical") == "cover-a6-white-cat-house"),
    dict(parent="hobonichi-techo-2027-covers", slug="nothing-to-hide-green", name="beautiful people: Nothing to Hide (Green)", full="Hobonichi Techo 2027 A6 cover beautiful people Nothing to Hide (Green)",
         match=lambda p: p.get("canonical") == "cover-a6-beautiful-people-green"),
    dict(parent="hobonichi-techo-2027-covers", slug="nothing-to-hide-pink", name="beautiful people: Nothing to Hide (Pink)", full="Hobonichi Techo 2027 A5 cover beautiful people Nothing to Hide (Pink)",
         match=lambda p: p.get("canonical") == "cover-a5-beautiful-people-pink"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-storybook-navy", name="Archer and Olive Storybook in Navy", full="Archer and Olive Storybook in Navy dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-storybook-navy"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-songbird-blue", name="Archer and Olive Songbird in Blue", full="Archer and Olive Songbird in Blue dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-songbird-blue"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-majestic-skies", name="Archer and Olive Majestic Skies", full="Archer and Olive Majestic Skies dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-majestic-skies"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-apothecary-shelf", name="Archer and Olive Apothecary Shelf", full="Archer and Olive Apothecary Shelf dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-apothecary-shelf"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-ice-castle", name="Archer and Olive Ice Castle", full="Archer and Olive Ice Castle dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-ice-castle"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-cozy-critters", name="Archer and Olive Cozy Critters", full="Archer and Olive Cozy Critters dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-cozy-critters"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-stag", name="Archer and Olive Stag", full="Archer and Olive Stag dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-stag"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-winter-train", name="Archer and Olive Winter Train", full="Archer and Olive Winter Train dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-winter-train"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-songbird-beige", name="Archer and Olive Songbird in Beige", full="Archer and Olive Songbird in Beige dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-songbird-beige"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-storybook-plum", name="Archer and Olive Storybook in Plum", full="Archer and Olive Storybook in Plum dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-storybook-plum"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-songbird-warm-gray", name="Archer and Olive Songbird in Warm Gray", full="Archer and Olive Songbird in Warm Gray dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-songbird-warm-gray"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-storybook-olive", name="Archer and Olive Storybook in Olive", full="Archer and Olive Storybook in Olive dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-storybook-olive"),
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-meteor-shower", name="Archer and Olive Meteor Shower", full="Archer and Olive Meteor Shower dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-meteor-shower"),
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

DESIGN_ABOUT = {'one-piece-edition': 'The One Piece Edition is a Japanese-language Hobonichi Techo 2027 Original book in A6 size, with a page for every day, a January start and Monday-start weeks.', 'hobonichi-weeks-2027/midnight-blue': 'Midnight Blue is a Colors design for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-mega-2027/midnight-blue': 'Midnight Blue is a Colors design for the Hobonichi Weeks Mega 2027 weekly planner.', 'hobonichi-weeks-2027/canaria-yellow': "Canaria Yellow is a Colors design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'hobonichi-weeks-2027/white-cat-wallpaper': 'White Cat Wallpaper is a Yumi Kitagishi artist collaboration for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/moomin-at-the-table': 'Moomin: At the Table is a Moomin collaboration for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/starlight': "Starlight is tanakadaisuke's 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega and not a softcover.", 'hobonichi-weeks-mega-2027/candy-dream': 'Bow & Tie: Candy Dream is a design for the Hobonichi Weeks Mega 2027 weekly planner.', 'hobonichi-weeks-2027/sea-glass': "Sea Glass is a Colors design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'hobonichi-weeks-2027/v-and-a': "Welcome to the V&A and Leicester are two separate 2027 Weeks hardcover books, January start, Monday start. Hobonichi's own listings include the English and Japanese books. The other shops on this page sell the English book. A shop that sells both on one page is checked by the named design, not by whether another design on that page is available. Neither design is a Weeks Mega.", 'hobonichi-weeks-2027/pink-sapphire': "Pink Sapphire is a Colors design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'hobonichi-weeks-2027/paper-series-jade': "Frosty Jade is the English name of this Paper Series Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. One retailer's title shortens the name to Jade; its product search uses the same item code as Frosty Jade. It is not a Weeks Mega and not a cover.", 'hobonichi-weeks-2027/shirt-fabric-graph-plaid': "Graph Plaid is a Shirt Fabric design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. It is not a Weeks Mega and not a cover.", 'hobonichi-weeks-2027/floral-remedy': "Floral Remedy is a Liberty Fabrics design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The checked shops on this page sell the English book. It is not a Weeks cover and not a Weeks Mega. JetPens also lists the English book. JetPens blocks automated checks, so that link is not a stock status and does not send a restock alert.", 'hobonichi-weeks-2027/nothing-to-hide-yellow': "Nothing to Hide (Yellow) is a beautiful people cover for the 2027 Weeks book, cover only, JAN 4580812710121. Hobonichi's listing is that Weeks cover. It is not the Weeks planner itself, not a Weeks Mega, and not the A6 green or A5 pink covers.", 'hobonichi-techo-2027-hon/a5-slash-navy': "Slash (Navy) in A5 is a 2027 HON book, daily pages, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. It is not the A6 HON and not a cover.", 'hobonichi-techo-2027-hon/a6-slash-navy': "Slash (Navy) in A6 is a 2027 HON book, daily pages, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. Pen Boutique has a separate Japanese-book listing. The other checked shops sell the English book. It is not the A5 HON and not a cover.", 'hobonichi-techo-2027-covers/moomin-my-yard': 'Moomin: My Yard (Pale Mint) is a Hobonichi cover for the A6 Original book.', 'hobonichi-techo-2027-covers/white-cat-house': "White Cat House is a Yumi Kitagishi artist collaboration cover for the Hobonichi A6 Original book. Hobonichi's listing is that A6 cover. It is not the Weeks White Cat Wallpaper book.", 'hobonichi-techo-2027-covers/nothing-to-hide-green': "Nothing to Hide (Green) is a beautiful people cover for the 2027 A6 Original book, cover only, JAN 4580812708883. Hobonichi's listing is that one A6 cover. It is not the A5 pink cover, not the 2026 orange cover, and not a Weeks book. JetPens also lists it. JetPens blocks automated checks, so that link is not a stock status and does not send a restock alert.", 'hobonichi-techo-2027-covers/nothing-to-hide-pink': "Nothing to Hide (Pink) is a beautiful people cover for the 2027 A5 Cousin book, cover only, JAN 4580812709163. Hobonichi's listing is that one A5 cover. It is not the A6 green cover and not a 2026 cover. JetPens also lists it. JetPens blocks automated checks, so that link is not a stock status and does not send a restock alert.", 'archer-and-olive-storybook-navy': 'Storybook in Navy is an Archer and Olive dot grid notebook. White dot grid comes in letter, B5, 8x8, A5, TN, B6 and pocket. Kraft and ivory dot grid come in B5, 8x8 and A5.', 'archer-and-olive-songbird-blue': 'Songbird in Blue is an Archer and Olive dot grid notebook in letter, B5, square, A5, TN, B6 and pocket, and each size sells out on its own.', 'archer-and-olive-majestic-skies': 'Majestic Skies is an Archer and Olive dot grid notebook in B5 (160 pages), square (160 pages), A5 (192 pages) and TN (144 pages).', 'archer-and-olive-apothecary-shelf': "Apothecary Shelf is Archer and Olive's Halloween 2026 dot grid notebook. We track the B5 and 8x8 in white dot grid, and the A5 in white and black dot grid.", 'archer-and-olive-ice-castle': 'Ice Castle is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-cozy-critters': 'Cozy Critters is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-stag': 'Stag is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-winter-train': 'Winter Train is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-songbird-beige': 'Songbird in Beige is an Archer and Olive Everyday dot grid notebook in B5, square, A5, TN and B6.', 'archer-and-olive-storybook-plum': 'Storybook in Plum is an Archer and Olive dot grid notebook in letter, B5, 8x8, A5, TN, B6 and pocket.', 'archer-and-olive-songbird-warm-gray': 'Songbird in Warm Gray is an Archer and Olive letter-size dot grid notebook. The shop\'s page says letter size (LS), 160 pages.', 'archer-and-olive-storybook-olive': 'Storybook in Olive is an Archer and Olive dot grid notebook in letter, square, A5, TN and pocket.', 'archer-and-olive-meteor-shower': 'Meteor Shower is an Archer and Olive dot grid notebook in 8x8, A5 and a Travelers size with 144 pages.', 'leuchtturm1917-hardcover-a5-dotted': 'The Leuchtturm1917 Hardcover Medium (A5) with dotted pages comes in several colors, and each one goes out of stock on its own.', 'leuchtturm1917-120g-a5-dotted': 'The Leuchtturm1917 120G edition is the Medium (A5) hardcover with heavier 120 g paper and 203 numbered pages.', 'leuchtturm1917-edition-2': "Bullet Journal Edition 2, as Leuchtturm1917 names it, is the brand's official dot grid journal, tracked here in every color its US shop lists.", 'scribbles-that-matter-pro': 'The Scribbles That Matter Dotted Journal Pro is a 160gsm dot grid journal in A5 and B5 and several colors.', 'scribbles-that-matter-iconic': 'The Scribbles That Matter Dotted Journal Iconic is an A5 dot grid journal with 160gsm paper, here in Bottle Green.', 'scribbles-that-matter-starry-night': 'Starry Night is a Scribbles That Matter A5 dotted journal with black paper.', 'notebook-therapy-tsuki-160gsm': "The Tsuki 160GSM is Notebook Therapy's dot grid journal with heavy 160gsm paper, and each cover color sells out on its own.", 'notebook-therapy-tsuki-dark-academia': 'Dark Academia is a limited edition Tsuki dot grid journal from Notebook Therapy, an A5 with 176 pages.', 'notebook-therapy-tsuki-violet-nocturne': 'Violet Nocturne is a limited edition A5 Tsuki dot grid journal from Notebook Therapy, with white paper.', 'notebook-therapy-tsuki-ravens-secret': "Raven's Secret is a limited edition Tsuki dot grid journal from Notebook Therapy, an A5 with 176 pages.", 'regular-black': "The Traveler's notebook Regular size in Black is a leather notebook cover from Traveler's Company.", 'regular-blue': "The Traveler's notebook Regular size in Blue is a leather notebook cover from Traveler's Company.", 'regular-brown': "The Traveler's notebook Regular size in Brown is a leather notebook cover from Traveler's Company.", 'regular-camel': "The Traveler's notebook Regular size in Camel is a leather notebook cover from Traveler's Company.", 'regular-olive': "The Traveler's notebook Regular size in Olive is a leather notebook cover from Traveler's Company.", 'road-trip-brown': "ROAD TRIP Brown is a Regular size Traveler's notebook that Traveler's Company USA sells as a US exclusive.", 'card-size-20th-anniversary-black': "The Card Size 20th Anniversary Set in Black is a limited Traveler's Company set for the notebook's 20th anniversary.", 'md-diary-2027-a5': 'The MIDORI MD Notebook Diary 2027 in A5 is a dated monthly planner on MD Paper.', 'md-diary-1-day-1-page-2027-a5': 'The MIDORI MD Notebook Diary 1 Day 1 Page 2027 in A5 gives every day of 2027 its own page.'}

# Shops that block the checker. A link here is not a status and is not counted as a checked shop.
UNCHECKED_LINKS = {
    "hobonichi-weeks-2027/floral-remedy": [dict(
        store="JetPens",
        url="https://www.jetpens.com/Hobonichi-Techo-Weeks-English-Liberty-Fabrics-Floral-Remedy-2027-Jan-Start/pd/54089",
        note="JetPens blocks automated checks. This is a link to the English Weeks book, not a stock status, and it does not send a restock alert.",
    )],
    "hobonichi-techo-2027-covers/nothing-to-hide-green": [dict(
        store="JetPens",
        url="https://www.jetpens.com/Hobonichi-Techo-2027-Cover-Only-A6-beautiful-people-Nothing-to-Hide-Green/pd/53982",
        note="JetPens blocks automated checks. This is a link to the A6 cover, not a stock status, and it does not send a restock alert.",
    )],
    "hobonichi-techo-2027-covers/nothing-to-hide-pink": [dict(
        store="JetPens",
        url="https://www.jetpens.com/Hobonichi-Techo-2027-Cover-Only-A5-beautiful-people-Nothing-to-Hide-Pink/pd/53943",
        note="JetPens blocks automated checks. This is a link to the A5 cover, not a stock status, and it does not send a restock alert.",
    )],
}

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
    thanks = ('<p class="suggest">Thank you to our follower Angela for suggesting we track these restocks.</p>'
              if d["slug"] in {"nothing-to-hide-green", "nothing-to-hide-pink", "nothing-to-hide-yellow"} else "")
    table = (f"""<section class="card group-sec" id="stock">
  <div class="section-head"><h2>Stock by shop</h2><p class="muted small">{E(count_line(ls).capitalize())} · {checked_line(ls)}</p></div>
  {list_filter(ls, "Shop name")}
  {amz_btn}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(ls, oe)}</tbody>
  </table></div>
  <p class="muted small card-empty" hidden>Nothing on this page matches those filters.</p>
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
          ("Can I get restock alerts?",
           f"Yes, sign up above. It's one free list for every restock we track, not just {d['full']}, so it could be multiple emails a day. You can unsubscribe anytime.")]
    when_html = time_tag(run)
    faq_html = '<section class="card faq" id="faq"><h2>Questions</h2>' + "".join(
        f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a).replace(E(when), when_html, 1)}</p></details>' for q, a in qa) + "</section>"
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
    sources = "".join(f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(l["store"])}: {E(l.get("title") or l["label"])}</a></li>' for l in sorted(ls, key=lambda l: l["store"]))
    extra_links = UNCHECKED_LINKS.get(d["parent"] + "/" + d["slug"], [])
    extra_html = ""
    if extra_links:
        items = "".join(
            f'<li><a href="{E(x["url"])}" rel="noopener" target="_blank">{E(x["store"])}</a> '
            f'<span class="muted small">{E(x["note"])}</span></li>' for x in extra_links)
        extra_html = f'<p class="muted small">Not checked</p><ul class="link-list">{items}</ul>'
    sources_html = f"""<section class="card" id="sources"><h2>Sources</h2>
  <p class="muted small">Statuses come from each shop's own public product page, read by our checker at the time shown. The raw data for every check is public: <a href="data/stock.json">stock.json</a>.</p>
  <ul class="link-list">{sources}</ul>{extra_html}</section>""" if ls or extra_links else ""
    sibs = "".join(f'<li><a href="{design_fname(x)}">{E(x["name"])}</a></li>' for x in designs_of(d["parent"]) if x is not d)
    others = (f'<li><a href="{parent["slug"]}/">All {E(parent["short"])} designs</a></li>' + sibs
              + (f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>' if sec == "hobonichi" else f'<li><a href="{parent["slug"]}/#tracker">Every listing on the {E(parent["short"])} page</a></li>'))
    intro = (f'{E(design_about(d))} This page shows its stock at every shop we track, checked {CHECK_FREQ}. '
             f'For every design, see the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a>.')
    body = f"""
<div class="product-page">
{crumbs((parent["slug"] + "/", parent["short"]), (fname, d["name"]))}
<section class="hero hero-compact">
  {eyebrow(ey, nshops(shops), f"checked {CHECK_FREQ}")}
  <h1>{E(h1)}</h1>
  <p class="lede">{intro}</p>
  {thanks}
  {hero_facts(ls)}
  {signup_for(d["full"], back=not buy)}
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
    title = design_seo_title(d)
    desc = design_seo_desc(d, shops)
    return fname, page(fname, title, desc, body, ld=(crumbs_ld((parent["slug"] + "/", parent["short"]), (fname, d["name"])), items, faq_ld),
                       og_image=parent.get("og_image", OG_IMAGE), og_alt=parent.get("og_alt", OG_ALT))

def design_lastmod(d):
    ls = design_listings(d)
    return latest(*[l.get("status_since") for l in ls], *[l.get("first_seen") for l in ls], DESIGNS_LASTMOD, CONTENT_LASTMOD)

FAQ = [
    ("How often do you check the shops?",
     "About every 30 minutes. A scheduled job reads each shop's public product data, then rebuilds this site with what it found. "
     "Restock times and last-check times are written as Eastern Time. A browser that can read them shows your local time zone instead and names that zone. "
     "If it cannot, the Eastern Time label stays. Guide dates and the 2027 calendar dates stay as written."),
    ("Which shops do you check?",
     "{n} shops across all trackers, in separate sections per brand family. Hobonichi: {nh} shops, the official Hobonichi Online Store and independent stationery shops. {secs}. Each listing in the tracker links to the shop's own page. JetPens and Nanami Paper are listed as links only, because their sites block automated checks."),
    ("What do you track?",
     "Hobonichi Techo 2027 planners: the Original A6 and Cousin A5 books, Weeks and Weeks Mega, and a few A6 and A5 covers. {tracks} We don't track pens."),
    ('What do "Not yet on sale" and "Couldn\'t check" mean?',
     '"Not yet on sale" means the shop has a preview page up but isn\'t taking orders yet. That\'s different from sold out. '
     '"Couldn\'t check" means our check failed, for example because the shop\'s site didn\'t respond, so we don\'t know. '
     "We show that instead of guessing whether it's in stock."),
    ("Do you sell planners?",
     "Yes, our own: we make planners and journals and sell them on our shop page ({shop}), printed on Amazon and as printable PDFs on Etsy. "
     "The stationery we track is sold by the shops themselves; we just link you to them. "
     "Amazon links on the site are affiliate links, and we say so on every page; links to the shops we track are plain links."),
    ("How do restock alerts work?",
     "Sign up with your email and you'll get an email about every restock we track, so it could be multiple emails a day. "
     "It's one free list, and you can unsubscribe anytime."),
]

FAQ_TRACKS = {  # one sentence per live section for "What do you track?"
    "dotgrid": "On a separate dot grid journals page, we track a focused set of flagship dot grid notebooks from {dg}, size by size and color by color, plus Archer and Olive's dot grid refills.",
    "travelers": "On the Traveler's Company page, we track the five Regular size notebook colors plus limited editions: the 2027 diary accessories, anniversary sets and shop exclusives. We don't track Passport size or refills there.",
    "midori": "On the MIDORI MD page, we track seasonal and limited MD releases (MIDORI's MD line is now sold as MD PRODUCT).",
}

HOBO_NOTE_Q = "Where are launch dates and how restocks usually go?"
HOBO_NOTE = ('For launch dates and how restocks usually go, see the '
             '<a href="hobonichi-2027.html">Hobonichi 2027 launch &amp; restock calendar</a>.')
TRACKER_FAQ = (
    ("What do the statuses mean?",
     "Statuses are exactly what each shop's public product data said at the time shown. Always confirm on the shop's page before you buy."),
    ('What do "Not yet on sale" and "Couldn\'t check" mean?',
     '"Not yet on sale" means the shop has a preview page up but isn\'t taking orders yet. "Couldn\'t check" means our check failed, so we don\'t know.'),
    ("Why don't you show prices?",
     "We don't show prices, because they change and differ by shop. Check the shop's page."),
)

def tracker_good_to_know(question, answer_html):
    """The same three questions on every tracker, then that tracker's own note. All closed."""
    plain = html.unescape(re.sub(r"<[^>]+>", "", answer_html))
    pairs = [(q, E(a), a) for q, a in TRACKER_FAQ] + [(question, answer_html, plain)]
    html_ = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{body}</p></details>' for q, body, _plain in pairs)
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": plain_a}} for q, _body, plain_a in pairs]}
    return f'<section class="card faq" id="faq"><h2>Good to know</h2>{html_}</section>', ld

def faq_block(only=None, sid="faq"):
    """only: questions to show, in that order. None shows the full list."""
    n = len({p["store_id"] for p in stock["products"]})
    # {shop} is a link in the page and the plain URL in the FAQ structured data
    secs = ". ".join(f'{SECTIONS[k]["foot"]}: {N_SEC[k]} shops, {shop_names(k)}' + (", each checked on its own store" if k == "dotgrid" else "") for k in LIVE)
    secs += ". Some shops sell more than one brand, so they're counted once in the total"
    tracks = " ".join(FAQ_TRACKS[k] for k in LIVE)
    answers = []
    for q, a in FAQ:
        if q == "Do you sell planners?" and shop_inserts_public():
            a = ("Yes, our own: we make planners, journals, and printable planner inserts, and sell them on our shop page ({shop}). "
                 "Printed books are on Amazon. Printable PDFs, including undated paper tip-ins, are on Etsy. "
                 "The stationery we track is sold by the shops themselves; we just link you to them. "
                 "Amazon links on the site are affiliate links, and we say so on every page; links to the shops we track are plain links.")
        answers.append((q, a))
    if only is None:
        pairs = answers
    else:
        by_q = dict(answers)
        pairs = [(q, by_q[q]) for q in only]
    qa = [(q, a.format(n=n, nh=N_HOBO, secs=secs, tracks=tracks.format(dg=dotgrid_names()), shop=url_for("shop/")),
           E(a).format(n=n, nh=N_HOBO, secs=E(secs), tracks=E(tracks.format(dg=dotgrid_names())), shop=f'<a href="shop/">{E(SHOP_NAME.lower())}</a>')) for q, a in pairs]
    html_ = "".join(f"<details class=\"faq-item\"><summary>{E(q)}</summary><p>{h}</p></details>" for q, a, h in qa)
    ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, h in qa]}
    return f'<section class="card faq" id="{sid}"><h2>Good to know</h2>{html_}</section>', ld

def hobo_design_nav():
    """Closed design-page list for the Hobonichi tracker, in the same slot as the other trackers."""
    links = []
    for g in GROUPS:
        if g_sec(g) != "hobonichi":
            continue
        for d in designs_of(g["slug"]):
            links.append(f'<li><a href="{design_fname(d)}">{E(d["name"])}</a></li>')
    if not links:
        return ""
    return (f'<details class="design-fold" id="by-product"><summary>Design pages ({len(links)})</summary>'
            f'<ul class="link-list">{"".join(links)}</ul></details>')

STATIC_LASTMOD = {"hobonichi-2027.html": "2026-11-12", "about.html": "2026-11-12", "privacy.html": "2026-11-12"}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes], CONTENT_LASTMOD)
    urls = [(url_for("index.html"), home_mod), (url_for(HOBO_TRACKER), latest(*[p.get("status_since") for p in hobo_products()], *[c["at"] for c in changes], CONTENT_LASTMOD))]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(design_fname(d)), design_lastmod(d)) for d in DESIGNS]
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    hobo_mod = latest(*[p.get("status_since") for p in hobo_products()], GUIDES_LASTMOD)
    tn_mod = json.loads(GUIDE_DATES.read_text())["build_tn_sizes"]["date"]  # written when that guide is built, earlier in main()
    urls += [(url_for(WTB_SLUG + "/"), latest(hobo_mod, CONTENT_LASTMOD)), (url_for(VS_SLUG + "/"), latest(GUIDES_LASTMOD, CONTENT_LASTMOD)), (url_for(JAN_APR_SLUG + "/"), JAN_APR_PUBLISHED), (url_for(DG_GUIDE_SLUG + "/"), latest(*[p.get("status_since") for p in section_products("dotgrid")], DG_GUIDE_LASTMOD, CONTENT_LASTMOD)), (url_for(TN_GUIDE_SLUG + "/"), latest(tn_mod, CONTENT_LASTMOD)), (url_for("guides/"), latest(DG_GUIDE_LASTMOD, tn_mod, CONTENT_LASTMOD)), (url_for("shop/"), shop_lastmod()), (url_for("follow/"), "2026-11-12"), (url_for("contact/"), "2026-11-12"), (url_for(SOLDOUT_SLUG + "/"), latest(*[p.get("status_since") for p in stock["products"]], CONTENT_LASTMOD))]
    def w3c(iso):
        """Every sitemap lastmod is a full W3C datetime, including dates that were stored as YYYY-MM-DD."""
        if len(iso) == 10:
            iso = iso + "T00:00:00+00:00"
        when = dt.datetime.fromisoformat(iso)
        if when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
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
    return page("404.html", "Page not found",
                "This page doesn't exist. The link may be old or mistyped. The Hobonichi, dot grid, Traveler's Notebook and MIDORI MD trackers are linked here. Pick one below.", body, noindex=True)

# --- SEO guides (Hobonichi section) -------------------------------------------------------------
# Editorial pages. Every stock status on them comes from data/stock.json (rebuilt about every 30 minutes by the
# workflow); product facts come only from the sources listed on each page. No prices: the checker
# doesn't record them.
WTB_SLUG = "where-to-buy-hobonichi-2027"
VS_SLUG = "hobonichi-techo-vs-cousin-vs-weeks"
JAN_APR_SLUG = "hobonichi-january-start-vs-april-start"
JAN_APR_PUBLISHED = "2026-11-12"  # owner-approved publication date
DG_GUIDE_SLUG = "best-dot-grid-journals"
HOBO_GUIDES = [(WTB_SLUG + "/", "Where to buy the Techo 2027"), (VS_SLUG + "/", "Techo vs Cousin vs Weeks"), (JAN_APR_SLUG + "/", "January-start vs April-start"), ("hobonichi-2027.html", "2027 launch & restock calendar")]
GUIDES = HOBO_GUIDES + [(DG_GUIDE_SLUG + "/", "Best dot grid journals compared"),
                        (TN_GUIDE_SLUG + "/", "Regular vs Passport vs Card Size")]  # footer, /guides/, 404, related block; Hobonichi pages use HOBO_GUIDES
GUIDES_LASTMOD = "2026-10-29"
DG_GUIDE_LASTMOD = "2026-11-04"  # last copy change on the dot grid guide
GUIDE_BLURBS = {WTB_SLUG + "/": "Which shops have each 2027 Original A6, Cousin A5, Weeks and Weeks Mega in stock right now, checked about every 30 minutes, plus tips for catching a restock.",
                VS_SLUG + "/": "Size, weight, daily vs weekly layout and pages for the three most popular Hobonichi books, from Hobonichi's own specs, and who each one suits.",
                JAN_APR_SLUG + "/": "Hobonichi's April-start (Spring) techo comes in fewer versions than the January-start edition and goes on sale on February 1.",
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

def _fmt_head(icon, label):
    """Drawing above the column name. The label already names it, so the drawing is hidden from assistive tech."""
    return f'<span class="fmt-head"><span class="fmt-art">{icon}</span><span>{label}</span></span>'

def book_icon(kind):
    """Closed book at the same relative scale as the format guide: A6 smaller, A5 larger, Weeks tall and narrow."""
    w, h = {"a6": (99, 142), "a5": (142, 204), "weeks": (88, 182)}[kind]
    scale = 85 / 204
    dw, dh = round(w * scale), round(h * scale)
    spine = round(w * 0.12)
    return (f'<svg class="fmt-icon" style="--iw:{dw}px;--ih:{dh}px" viewBox="0 0 {w} {h}" width="{dw}" height="{dh}" aria-hidden="true" focusable="false">'
            f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" fill="#e9ddc5"/>'
            f'<rect x="3" y="3" width="{spine}" height="{h - 6}" fill="#c5baa0"/>'
            f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" fill="none" stroke="#699173" stroke-width="6"/>'
            f'</svg>')

def cover_icon(kind):
    """Leather cover with a dashed refill inside, sized from the maker's cover measurements."""
    height, width, fill = {
        "regular": (220, 120, "#b2522f"),
        "passport": (134, 98, "#5e7f62"),
        "card": (110, 75, "#d1992e"),
    }[kind]
    scale = 92 / 220
    dw, dh = round(width * scale), round(height * scale)
    # The real refill sits only a few millimetres inside the cover. At icon size that
    # line would fall on the edge, so the dash is inset enough to read as the refill.
    x, y = width * 0.14, height * 0.1
    rw, rh = width - 2 * x, height - 2 * y
    return (f'<svg class="fmt-icon" style="--iw:{dw}px;--ih:{dh}px" viewBox="0 0 {width} {height}" width="{dw}" height="{dh}" aria-hidden="true" focusable="false">'
            f'<rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="4" fill="{fill}"/>'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="2" fill="none" stroke="#f4efe4" stroke-width="4" stroke-dasharray="7 5"/>'
            f'</svg>')


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
        secs.append(f'''<details class="card group-fold" id="{E(g["slug"])}">
  <summary><h2 class="fam-name">{E(g["product"])}</h2><span class="fam-meta">{E(count_line(ls).capitalize())}</span></summary>
  <div class="group-body">
  {_shop_table(ls)}
  {az_html}
  <p class="small"><a href="{g["slug"]}/">Full {E(g["short"])} restock page</a> <span class="muted">· every listing, when it last changed, and recent restocks</span></p>
  </div>
</details>''')
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
         "Sign up for Stationery Drop Watch alerts. We check the shops about every 30 minutes and email you about every restock we track, so it could be multiple emails a day. It's free and you can unsubscribe anytime."),
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
<p class="lede">Which shops have the 2027 Original A6, Cousin A5, Weeks, Weeks Mega, and A6 and A5 covers right now, edition by edition. Every status below is what the shop's own product data said at our last check, {last}.</p>
{signup()}
    <section class="card" id="quick">
      <h2>Quick answer</h2>
      <ul>{"".join(quick)}</ul>
      <p class="muted small">"Not yet on sale" means a preview page is up but the shop isn't taking orders. "Couldn't check" means our check failed, so we don't know. Always confirm on the shop's page before you buy. We don't show prices; check the shop.</p>
    </section>
    {region_legend(l["store_id"] for l in hobo)}
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
        <li><strong>Get our alerts.</strong> We check about every 30 minutes and email you about every restock we track, so it could be multiple emails a day. <a href="#alerts">Sign up above</a>.</li>
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
           "datePublished": "2026-10-29", "dateModified": "2026-10-29", "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, "Where to buy Hobonichi Techo 2027",
                       f"Where to buy the Hobonichi Techo 2027 Original A6, Cousin A5, Weeks and Weeks Mega: which of {n_shops} shops have each one in stock, plus restock tips. Stock changes.",
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
<thead><tr><th></th><th>{_fmt_head(book_icon("a6"), "Original (A6)")}</th><th>{_fmt_head(book_icon("a5"), "Cousin (A5)")}</th><th>{_fmt_head(book_icon("weeks"), "Weeks")}</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p class="muted small">Stock counts are what each shop's product data said at our last check, {time_tag(stock['run_finished'])}.</p>

<h2>Who each one suits</h2>
<h3>Original (A6): a page a day you can carry</h3>
<p>Pick the Original if you want daily room to write, plan, sketch or paste in tickets, but still want something you can carry every day. Each day gets a full page with a to-do list and a 24-hour timetable {s("g_orig")}. The trade-off: there are no weekly pages, so week-at-a-glance planning happens on the monthly calendars. You'll also want a cover, since the book is designed to go in one.</p>
<p><a href="hobonichi-techo-2027-original-a6/">Live Original A6 stock</a> · <a href="hobonichi-techo-2027-covers/">A6 covers</a></p>
<h3>Cousin (A5): the most room</h3>
<p>Pick the Cousin if a daily page in A6 feels cramped. Hobonichi made it for people who wanted more space to write and paste, or who write in larger letters, and suggests it for work notes, a parenting diary, a shared journal, or a desk planner {s("g_cousin")} {s("cousin", "Cousin")}. It's the only one of the three with both daily pages and vertical weekly pages. The trade-off is weight: at about 445 g it's more than twice the Original, so it's less of an everyday carry.</p>
<p><a href="hobonichi-techo-2027-cousin-a5/">Live Cousin A5 stock</a> · <a href="hobonichi-techo-2027-covers/nothing-to-hide-pink/">A5 cover</a></p>
<h3>Weeks: light and weekly</h3>
<p>Pick Weeks if you plan by the week and mostly want your schedule and short notes with you. It's slim and light, and each weekly spread pairs the week with a grid memo page {s("g_weeks")}. Weeks books come as a light hardcover in many designs, so you don't need a separate cover {s("weeks", "Weeks")}. The trade-off: there's no daily page, so it isn't for long daily entries. If you want more blank pages, Weeks Mega has about three times the memo pages (219 in English) at the same height and width {s("mega", "Weeks Mega")}.</p>
<p><a href="hobonichi-weeks-2027/">Live Weeks stock</a> · <a href="hobonichi-weeks-mega-2027/">Weeks Mega</a></p>

<h2>Where to buy</h2>
<p>Stock changes fast, and one shop is often sold out while another has it. See <a href="{WTB_SLUG}/">where to buy the Hobonichi Techo 2027</a> for every shop we track, edition by edition, or <a href="#alerts">sign up above</a> for email alerts on every restock we track. It could be multiple emails a day, and you can unsubscribe anytime.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{src_items}</ol>
<p class="muted small">Hobonichi makes other types too, such as the A5 and A6 HON. This guide covers only the three above.</p>
{design_links_block()}
{related_block(fname)}
</article>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": "Hobonichi Techo vs Cousin vs Weeks: which 2027 planner fits you?",
           "datePublished": GUIDES_LASTMOD, "dateModified": GUIDES_LASTMOD, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, "Hobonichi Techo vs Cousin vs Weeks (2027): sizes, layouts, who each suits · Stationery Drop Watch",
                       "Hobonichi Techo Original A6 vs Cousin A5 vs Weeks for 2027: size, weight, daily vs weekly layout, pages and paper from Hobonichi's specs, plus live stock.",
                       body, ld=(crumbs_ld(("guides/", "Guides"), (fname, "Hobonichi Techo vs Cousin vs Weeks")), art, faq_ld))


def build_january_april():
    """Owner-approved January-start vs April-start guide, published 2026-11-12. Body wording is the approved article."""
    fname = JAN_APR_SLUG + "/"
    title = "Hobonichi Techo January-start vs April-start: which one should you buy?"
    desc = ("Hobonichi's April-start (Spring) techo comes in fewer versions than the January-start edition "
            "and goes on sale on February 1. Here's how the two differ and how to choose.")
    faq = [
        ("When does the April-start Hobonichi go on sale?",
         "Hobonichi says February 1 every year at 11 AM Japan time. Check the official site for the 2027 date."),
        ("Is there an English April-start Hobonichi?",
         "No. April-start editions are Japanese only."),
        ("Is there an April-start Weeks Mega or Day-Free?",
         "No."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    sources = [
        ("https://help.1101.com/hc/en-us/articles/4889929315230", "April-start editions"),
        ("https://help.1101.com/hc/en-us/articles/4889951964190", "Spring lineup guidance"),
        ("https://help.1101.com/hc/en-us/articles/4889935445534", "sale schedule"),
        ("https://help.1101.com/hc/en-us/articles/4889951953566", "Sunday-start editions"),
    ]
    src_items = "".join(
        f'<li><a href="{u}" rel="noopener" target="_blank">{E(t)}</a>, Hobonichi (official).</li>' for u, t in sources)
    body = f"""
<article class="prose guide">
{crumbs(("guides/", "Guides"), (fname, "January-start vs April-start"))}
{eyebrow("Guide", "Hobonichi Techo", guide_updated(build_january_april))}
<h1>Hobonichi Techo January-start vs April-start</h1>
<p class="lede">Hobonichi offers January-start planners and April-start editions called "Spring". Not every book comes in both versions. Which one suits you depends on when you want to begin planning and which book you want.</p>
{signup()}

<h2>The short answer</h2>
<ul>
  <li><strong>Choose January-start</strong> if you want an English edition, the Planner, Avec, HON, Day-Free, Weeks Mega or a 5-Year Techo. None of these comes in an April-start edition.</li>
  <li><strong>Choose April-start</strong> if your year turns over in spring (school, a fiscal year, a new job) and you're happy with a Japanese-edition Original (A6), Cousin (A5) or Weeks.</li>
</ul>

<h2>Which books come in April-start</h2>
<p>Hobonichi's help center says the <strong>Original (A6), Cousin (A5) and Weeks</strong> have April-start editions, <strong>all in Japanese</strong>.</p>
<p>The help center says there are <strong>no April-start editions</strong> of:</p>
<ul>
  <li>English editions of the Original, Cousin and Weeks</li>
  <li>the Planner</li>
  <li>Avec (Original or Cousin)</li>
  <li>Weeks Mega</li>
  <li>HON</li>
  <li>Day-Free</li>
  <li>the 5-Year Techo and Large 5-Year Techo</li>
  <li>some special editions (it names the One Piece Original and the Moomin Weeks)</li>
</ul>

<h2>"April-start" doesn't mean it goes on sale in April</h2>
<p>Hobonichi's help center says the April-start Spring edition <strong>"goes on sale every year on February 1st"</strong>, starting at <strong>11:00 AM Japan time</strong> on the Hobonichi Store (9:00 PM Eastern on January 31). Other shops start selling when they open.</p>
<p>Treat this as Hobonichi's usual sale schedule, not a separately confirmed Spring 2027 announcement. Check the official Spring announcements before planning a purchase.</p>

<h2>Is the Spring lineup the same as January's?</h2>
<p>Not exactly. Hobonichi says many January-start products are offered again in April-start, and <strong>"even if an item sells out in the January-start edition, it may be restocked for the April-start release."</strong> Some products are Spring-only, and the lineup can change depending on fabric availability.</p>
<p>So if a cover you wanted sold out in the fall, the Spring release is worth watching. Hobonichi doesn't promise it will come back.</p>

<h2>The Sunday-start option</h2>
<p>According to Hobonichi, the Sunday-start option is available only for the <strong>Japanese Original (A6)</strong>, in both January-start and April-start editions.</p>

<h2>How to decide</h2>
<ol>
  <li><strong>When does your year start?</strong> If it's January, choose January-start. If it's April (school, work, a fiscal year), choose Spring.</li>
  <li><strong>Do you need English?</strong> Then it's January-start only.</li>
  <li><strong>Which format?</strong> Pick the format first. Our <a href="{VS_SLUG}/">Original vs Cousin vs Weeks guide</a> explains the differences.</li>
  <li><strong>Waiting for a sold-out cover?</strong> It may come back in the Spring release, but it isn't guaranteed.</li>
</ol>

<h2>Related</h2>
<ul>
  <li><a href="{HOBO_TRACKER}">Hobonichi Techo 2027 restock tracker</a></li>
  <li><a href="{WTB_SLUG}/">Where to buy the Hobonichi Techo 2027</a></li>
  <li><a href="{VS_SLUG}/">Original vs Cousin vs Weeks</a></li>
  <li><a href="hobonichi-techo-2027-covers/">Hobonichi Techo 2027 covers</a></li>
</ul>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<p class="muted small">Read Nov 7, 2026.</p>
<ol class="sources">{src_items}</ol>
{design_links_block()}
{related_block(fname)}
</article>"""
    headline = "Hobonichi Techo January-start vs April-start"
    art = {"@context": "https://schema.org", "@type": "Article", "headline": headline,
           "datePublished": JAN_APR_PUBLISHED, "dateModified": JAN_APR_PUBLISHED, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, title, desc, body,
                       ld=(crumbs_ld(("guides/", "Guides"), (fname, "January-start vs April-start")), art, faq_ld))


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
    maker_ids = {sid for _, sid, _ in DG_COLS}
    guide_ls = [p for _, sid, _ in DG_COLS for p in col_ls(sid)]
    maker_ls = [p for p in dg if p["store_id"] in maker_ids]
    # Each column is that maker's own shop. Other shops can sell the same notebooks, so the
    # four columns are the maker listings only, and the tracker total is every shop.
    if sorted(map(id, guide_ls)) != sorted(map(id, maker_ls)) or count_line(trk) != count_line(dg) or len(trk) != len(dg):
        raise SystemExit(f"dot grid guide counts differ from tracker: makers {count_line(guide_ls)!r}, tracker {count_line(trk)!r}")
    dg_total = count_line(guide_ls)
    dg_all = count_line(trk)
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
        ("How do the email alerts work?",
         f"Our dot grid tracker checks every journal above {CHECK_FREQ}. Sign up for the free email alerts. The list covers every restock we track, including sold-out sizes and colors coming back, so it could be multiple emails a day, and you can unsubscribe anytime."),
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
<p class="muted small">Stock in each column is what that maker's own shop said at our last check, {asof}. Each count covers every dot grid listing we track at that shop. Other shops that sell the same notebooks are on the <a href="{DOTGRID_SLUG}/">dot grid tracker</a>. Across the four makers: {E(dg_total)}. Across every shop: {E(dg_all)}.</p>
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
<p>All four sell direct, and sizes and colors sell out often. Our <a href="{DOTGRID_SLUG}/">dot grid journal tracker</a> checks each one at the maker's own shop {CHECK_FREQ}. <a href="#alerts">Sign up above</a> for email alerts on every restock we track. It could be multiple emails a day, and you can unsubscribe anytime. More guides are on the <a href="guides/">guides page</a>.</p>

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
<thead><tr><th></th><th>{_fmt_head(cover_icon("regular"), "Regular")}</th><th>{_fmt_head(cover_icon("passport"), "Passport")}</th><th>{_fmt_head(cover_icon("card"), "Card Size")}</th></tr></thead>
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
    return fname, page(fname, "Stationery buying guides",
                       "Guides from Stationery Drop Watch: where to buy Hobonichi 2027, Techo vs Cousin vs Weeks, the launch calendar, dot grid journals, and Traveler's sizes.",
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
         img="assets/shop/soft-days-narrow-inserts-900.webp", img_class="sheet", img_w=900, img_h=675,
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
                  "Finished cut size is 85 × 175 mm. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Month Dashboard", "Habit Tracker (6 habits, 31 daily rows)", "Mood Tracker",
                    "Weekly Plan (Monday start, undated)", "Monthly Budget", "Reading Log", "Pen & Ink Swatches",
                    "Meal Planner (breakfast and lunch/dinner, Monday start)", "Wishlist & Gifts", "Annual Goals",
                    "Monthly Reset", "Order Tracker", "Stationery Inventory", "Brain Dump", "Dot Grid", "Lined Notes"],
         templates_label="16 templates",
         inside="soft-days"),
    dict(id="lines-grid", kind="insert", sale_confirmed=True, price="$6.99",
         title="Lines for the Grid Page",
         img="assets/shop/lines-for-the-grid-page.webp", img_class="sheet", img_w=2000, img_h=2000,
         url="https://www.etsy.com/listing/4614089507/lines-for-the-grid-page-printable-tip-in",
         alt=("Lines for the Grid Page: a cream cover reading Lines for the Grid Page beside fanned liner pages "
              "titled Task Lines, Cornell Notes, Habit Tracker, and Weekly Overlay."),
         sub="Printable tip-in liners · personal use · instant download from Etsy",
         hub_sub="Printable liners",
         blurb=("Thirteen undated layouts that turn a narrow planner's grid memo page into lined pages. "
                "Finished cut size is 85 × 175 mm. Warm and Soft Gray line colors. A digital download for personal use."),
         details=["One zip: US Letter and A4 files (two liners per sheet, with crop marks and scale bars) plus single-page 85 × 175 mm files, in Warm and Soft Gray",
                  "13 undated layouts. Print at actual size (100%)",
                  "Personal use only: don't share, resell, or redistribute the PDFs",
                  "Digital download only. Not a physical planner",
                  "Finished cut size is 85 × 175 mm, drawn for a narrow weekly planner whose book is about 94 × 188 mm, including the Hobonichi Weeks. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Ruled 5 mm", "Ruled 6 mm", "Ruled 7 mm", "Ruled 8 mm", "Task lines",
                    "Two columns", "AM / PM", "Cornell notes", "Meeting page", "Habit tracker",
                    "Weekly overlay", "Half lined", "Dot grid (5 mm)"],
         templates_label="13 layouts",
         inside="lines-grid"),
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
def _inside_dim(inside, stem):
    """Pixel size of a shop preview, so the image reserves its box before it loads."""
    path = ROOT / "site/assets/shop/inside" / f"{inside}-{stem}.jpg"
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return (800, 600)

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
    "lines-grid": {"class": " samples inserts", "note": "Layouts from the print file, not a photograph of a printed copy.", "items": [
        _sample("/assets/shop/inside/lines-grid-layouts.webp",
                "Lines for the Grid Page print file: the liner layouts, including ruled pages, task lines, Cornell notes, a habit tracker, a weekly overlay, and a dot grid, in Warm and Soft Gray.",
                "The 13 layouts, from the print file.", 2700, 2025),
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

def shop_cta_line():
    if shop_inserts_public():
        return "Planners, journals, and printable inserts we make, printed on Amazon and as PDFs on Etsy"
    return "2027 planners and journals we make, printed on Amazon and printable on Etsy"

def shop_lastmod():
    # Shop facts changed 2026-11-10 (Lines for the Grid Page listing). The Nov 12
    # refresh changed the page HTML, so the sitemap floor is that later date.
    if any(e.get("id") == "lines-grid" and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-12"
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
    for needed in ("Not a Hobonichi product", "not affiliated", "personal use", "85 × 175 mm",
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
        if item.get("id") == "soft-days" and len(item.get("templates") or []) != 16:
            raise SystemExit(f"{item['title']} must list 16 templates")
    def srcset(img):  # Etsy mockups ship 600w + 1200w copies; Amazon covers use their single file
        if img.startswith("assets/shop/") and img.endswith("-planner.jpg"):
            b = img[:-4]
            return f' srcset="/{E(b)}-600.jpg 600w, /{E(b)}-1200.jpg 1200w"'
        if img == "assets/shop/soft-days-narrow-inserts-900.webp":
            return (' srcset="/assets/shop/soft-days-narrow-inserts-900.webp 900w, '
                    '/assets/shop/soft-days-narrow-inserts-1800.webp 1800w"')
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
                figs = "".join(f'<figure><img src="/assets/shop/inside/{inside}-{f}.jpg" alt="{E(title)}: {E(cap)}" width="{_inside_dim(inside, f)[0]}" height="{_inside_dim(inside, f)[1]}" loading="lazy" decoding="async"><figcaption>{E(cap)}</figcaption></figure>'
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
        title = "Our planners and journals"
        desc = ("Planners and journals from Stationery Drop Watch: printed 2027 books on Amazon, and printable planner PDFs plus narrow inserts on Etsy. Both are made by us.")
        etsy_intro = '<p class="muted">Printable planner PDFs, and undated paper tip-ins you print and cut yourself.</p>'
    else:
        lede = "Planners and journals we make. Get a printed copy on Amazon or a printable PDF on Etsy."
        title = "Our planners and journals"
        desc = "Planners and journals from Stationery Drop Watch: printed 2027 books on Amazon, and printable planner PDFs on Etsy. Both are made by us."
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

# Single-color marks. Paths are the Simple Icons glyphs (CC0). The circle stays the
# existing cream, and the mark uses the rust already set on .follow-ico.
SOCIAL_GLYPHS = {
    "X": "M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z",
    "Instagram": "M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077",
    "Threads": "M18.263 11.097c-.03-3.486-1.92-5.586-5.111-5.586-2.13 0-3.922.963-4.863 2.499l2.062 1.438c.535-.84 1.272-1.543 2.628-1.543 1.528 0 2.318.85 2.544 2.431a15 15 0 0 0-2.236-.173c-4.125 0-6.068 1.867-6.068 4.336s1.943 3.99 4.804 3.99c3.139 0 5.013-2.115 5.781-4.735.798.361 1.348 1.204 1.348 2.47 0 3.387-3.907 5.232-7.22 5.232-4.885 0-8.077-3.207-8.077-8.424 0-6.392 4.223-10.487 9.9-10.487 3.808 0 5.69 1.671 6.97 3.914l2.108-1.475C21.44 2.078 18.331 0 13.663 0 6.227 0 1.168 5.277 1.168 12.934c0 7 4.953 11.066 10.856 11.066 4.878 0 9.809-2.846 9.809-7.716 0-2.545-1.46-4.231-3.569-5.187m-6.33 4.855c-1.077 0-2.026-.512-2.026-1.453 0-1.483 1.822-1.934 3.606-1.934.678 0 1.34.045 1.927.173-.422 1.927-1.671 3.215-3.508 3.214Z",
    "Bluesky": "M5.202 2.857C7.954 4.922 10.913 9.11 12 11.358c1.087-2.247 4.046-6.436 6.798-8.501C20.783 1.366 24 .213 24 3.883c0 .732-.42 6.156-.667 7.037-.856 3.061-3.978 3.842-6.755 3.37 4.854.826 6.089 3.562 3.422 6.299-5.065 5.196-7.28-1.304-7.847-2.97-.104-.305-.152-.448-.153-.327 0-.121-.05.022-.153.327-.568 1.666-2.782 8.166-7.847 2.97-2.667-2.737-1.432-5.473 3.422-6.3-2.777.473-5.899-.308-6.755-3.369C.42 10.04 0 4.615 0 3.883c0-3.67 3.217-2.517 5.202-1.026",
    "Pinterest": "M12.017 0C5.396 0 .029 5.367.029 11.987c0 5.079 3.158 9.417 7.618 11.162-.105-.949-.199-2.403.041-3.439.219-.937 1.406-5.957 1.406-5.957s-.359-.72-.359-1.781c0-1.663.967-2.911 2.168-2.911 1.024 0 1.518.769 1.518 1.688 0 1.029-.653 2.567-.992 3.992-.285 1.193.6 2.165 1.775 2.165 2.128 0 3.768-2.245 3.768-5.487 0-2.861-2.063-4.869-5.008-4.869-3.41 0-5.409 2.562-5.409 5.199 0 1.033.394 2.143.889 2.741.099.12.112.225.085.345-.09.375-.293 1.199-.334 1.363-.053.225-.172.271-.401.165-1.495-.69-2.433-2.878-2.433-4.646 0-3.776 2.748-7.252 7.92-7.252 4.158 0 7.392 2.967 7.392 6.923 0 4.135-2.607 7.462-6.233 7.462-1.214 0-2.354-.629-2.758-1.379l-.749 2.848c-.269 1.045-1.004 2.352-1.498 3.146 1.123.345 2.306.535 3.55.535 6.607 0 11.985-5.365 11.985-11.987C23.97 5.39 18.592.026 11.985.026L12.017 0z",
    "Facebook": "M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z",
    "Reddit": "M12 0C5.373 0 0 5.373 0 12c0 3.314 1.343 6.314 3.515 8.485l-2.286 2.286C.775 23.225 1.097 24 1.738 24H12c6.627 0 12-5.373 12-12S18.627 0 12 0Zm4.388 3.199c1.104 0 1.999.895 1.999 1.999 0 1.105-.895 2-1.999 2-.946 0-1.739-.657-1.947-1.539v.002c-1.147.162-2.032 1.15-2.032 2.341v.007c1.776.067 3.4.567 4.686 1.363.473-.363 1.064-.58 1.707-.58 1.547 0 2.802 1.254 2.802 2.802 0 1.117-.655 2.081-1.601 2.531-.088 3.256-3.637 5.876-7.997 5.876-4.361 0-7.905-2.617-7.998-5.87-.954-.447-1.614-1.415-1.614-2.538 0-1.548 1.255-2.802 2.803-2.802.645 0 1.239.218 1.712.585 1.275-.79 2.881-1.291 4.64-1.365v-.01c0-1.663 1.263-3.034 2.88-3.207.188-.911.993-1.595 1.959-1.595Zm-8.085 8.376c-.784 0-1.459.78-1.506 1.797-.047 1.016.64 1.429 1.426 1.429.786 0 1.371-.369 1.418-1.385.047-1.017-.553-1.841-1.338-1.841Zm7.406 0c-.786 0-1.385.824-1.338 1.841.047 1.017.634 1.385 1.418 1.385.785 0 1.473-.413 1.426-1.429-.046-1.017-.721-1.797-1.506-1.797Zm-3.703 4.013c-.974 0-1.907.048-2.77.135-.147.015-.241.168-.183.305.483 1.154 1.622 1.964 2.953 1.964 1.33 0 2.47-.81 2.953-1.964.057-.137-.037-.29-.184-.305-.863-.087-1.795-.135-2.769-.135Z",
}

def social_icon(name):
    """The platform's own mark, one color, inside the existing cream circle."""
    return (f'<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">'
            f'<path fill="currentColor" d="{SOCIAL_GLYPHS[name]}"/></svg>')

SOCIALS = [  # (platform, handle, url, note)
    ("X", "@stationerydrop", "https://x.com/stationerydrop", "Restock alerts the moment we confirm them, plus planner news."),
    ("Instagram", "@stationerydropwatch", "https://www.instagram.com/stationerydropwatch/", "Planner photos and restock alerts."),
    ("Threads", "@stationerydropwatch", "https://www.threads.com/@stationerydropwatch", "Restock alerts and planner chat."),
    ("Bluesky", "@stationerydropwatch.com", "https://bsky.app/profile/stationerydropwatch.com", "Restock alerts and planner news."),
    ("Pinterest", "@stationerydropwatch", "https://www.pinterest.com/stationerydropwatch/", "Planner pins and guides to save for later."),
    ("Facebook", "Stationery Drop Watch", "https://www.facebook.com/stationerydropwatch", "Restock alerts and planner news on our Page."),
    ("Reddit", "u/stationerydropwatch", "https://www.reddit.com/user/stationerydropwatch/", "Where we join planner conversations."),
]

SOLDOUT_SLUG = "sold-out-everywhere"
SEC_LABEL = {"hobonichi": "Hobonichi Techo 2027", **{k: SECTIONS[k]["nav"] for k in SECTIONS}}

def sold_out_everywhere():
    """Items (listings grouped by product_key) that no shop we track has in stock or on preorder, from this run's
    stock.json. Strict, so the page never overstates: at least one listing is sold out, every other listing is sold out
    or not yet on sale, and none failed to check this run (an unchecked shop might have it)."""
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    by = {}
    for p in stock["products"]:
        by.setdefault(product_key(p), []).append(p)
    items, skipped = [], 0
    for key, ls in by.items():
        sts = [l["status"] for l in ls]
        if any(x in BUYABLE for x in sts) or "sold_out" not in sts:
            continue
        if "unknown" in sts:
            skipped += 1
            continue
        name = canon.get(ls[0].get("canonical") or "") or (ls[0].get("title") or ls[0]["label"])
        page_ = design_page_for(ls)
        group = next((g for g in GROUPS if any(g["match"](l) for l in ls)), None)
        items.append(dict(name=name, ls=ls, page=page_, group=group, sec=section_of(ls[0]),
                          sold=len({l["store_id"] for l in ls if l["status"] == "sold_out"}),
                          soon=len({l["store_id"] for l in ls if l["status"] == "coming_soon"}),
                          since=max(l.get("status_since") or l["checked_at"] for l in ls if l["status"] == "sold_out")))
    order = ["hobonichi"] + list(SECTIONS)
    items.sort(key=lambda x: (order.index(x["sec"]) if x["sec"] in order else 99, x["name"].lower()))
    return items, skipped

def build_sold_out():
    fname = SOLDOUT_SLUG + "/"
    items, skipped = sold_out_everywhere()
    run = stock["run_finished"]
    def li(x):
        where = f'Sold out at {nshops(x["sold"])}' + (f', not yet on sale at {nshops(x["soon"])}' if x["soon"] else "")
        since = f' · sold out at every check since {time_tag(x["since"])}'
        if x["page"]:
            link = f'<a href="{x["page"]}">{E(x["name"])}</a>'
            more = ""
        elif x["group"]:
            link = f'<strong>{E(x["name"])}</strong>'
            more = f' <span class="small">No page of its own yet. It\'s listed on the <a href="{x["group"]["slug"]}/">{E(x["group"]["short"])} restock page</a>.</span>'
        else:
            link, more = f'<strong>{E(x["name"])}</strong>', ' <span class="small">No page of its own yet.</span>'
        return f'<li>{link}{more}<br><span class="muted small">{where}{since}</span></li>'
    secs = ""
    for sec in dict.fromkeys(x["sec"] for x in items):
        rows = "".join(li(x) for x in items if x["sec"] == sec)
        secs += f'<section class="card"><h2>{E(SEC_LABEL.get(sec, sec))}</h2><ul class="link-list soldout-list">{rows}</ul></section>'
    if not items:
        secs = '<section class="card"><p>Nothing right now: every item we track is in stock or on preorder at one shop or more, or isn\'t on sale yet.</p></section>'
    n = len(items)
    count = f"{n} item{'s' if n != 1 else ''}"
    note = (f'<p class="muted small">Left out this run: {skipped} item{"s" if skipped != 1 else ""} we couldn\'t check at every shop, '
            'so we can\'t say they\'re sold out everywhere.</p>') if skipped else ""
    body = f"""
<article class="prose soldout">
{crumbs((fname, "Sold out everywhere"))}
{eyebrow("Sold out everywhere", count, f"checked {CHECK_FREQ}")}
<h1>Sold out everywhere we track</h1>
<p class="lede">Items that no shop we track has in stock or on preorder at the last check ({time_tag(run)}). Each one links to its page with every shop's status. This list rebuilds on every check, so items drop off as soon as a shop has them again.</p>
{signup()}
{secs}
{note}
<p class="muted small">"Sold out" is exactly what each shop's public product data said. "Not yet on sale" means the shop has a preview page up but isn't taking orders. The raw data is public: <a href="data/stock.json">stock.json</a>.</p>
</article>"""
    return fname, page(fname, f"Sold out everywhere: {count} to watch",
                       "Items no shop we track has in stock or on preorder, with a link to each item's restock page. Updated about every 30 minutes.",
                       body, ld=(crumbs_ld((fname, "Sold out everywhere")),))

def build_follow():
    fname = "follow/"
    rows = "".join(f"""<li class="follow-card"><span class="follow-ico">{social_icon(n)}</span>
  <div class="follow-text"><h2 class="h3">{E(n)}</h2><p class="muted small">{E(h)}</p><p class="small">{E(note)}</p></div>
  <a class="btn" href="{E(u)}" rel="noopener" target="_blank">Follow on {E(n)}</a></li>""" for n, h, u, note in SOCIALS)
    body = f"""
<article class="prose follow">
{crumbs((fname, "Follow us"))}
{eyebrow("Follow us", f"{len(SOCIALS)} apps")}
<h1>Follow us</h1>
<p class="lede">We post restock alerts and planner news. Pick the app you already use.</p>
{signup()}
<ul class="follow-list">{rows}</ul>
</article>"""
    return fname, page(fname, "Follow us",
                       "Follow Stationery Drop Watch on X, Instagram, Threads, Bluesky, Pinterest, Facebook and Reddit for restock alerts and planner news. Pick one.",
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
    for build in (build_where_to_buy, build_vs, build_january_april, build_dotgrid_guide, build_tn_sizes, build_guides_index, build_shop, build_follow, build_contact, build_sold_out):
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
