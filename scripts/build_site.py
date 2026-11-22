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
DETROIT = ZoneInfo("America/Detroit")
E = html.escape

# Amazon links on this site are only for the owner's own planners and journals on /shop.
# Those stay as plain amazon.com/dp/<ASIN> URLs with no Associates tag.
_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")

def own_amazon_link(url):
    """Plain amazon.com/dp/<ASIN> URL with no tag or ref params (for the owner's own products)."""
    m = _ASIN.search(url)
    return f"https://www.amazon.com/dp/{m.group(1)}" if m else url.split("?")[0]

stores = json.loads((ROOT / "stores.json").read_text())
stock = json.loads((ROOT / "data/stock.json").read_text())
changes = json.loads((ROOT / "data/changes.json").read_text())
picks = json.loads((ROOT / "content/editor_picks.json").read_text())

# Some shops put an availability phrase in the product or variant title ("In Stock - Ships Now",
# "Preorder Only - Ships Mid February", "... In Stock", "[SOLD OUT]"). Our status column already says
# that, and a stale phrase can contradict it, so pages show the title without it. A ship date stays.
# The raw data files keep the shop's exact title.
_TITLE_STATUS = (
    (re.compile(r"\s*/\s*In Stock - Ships Now\b", re.I), ""),
    (re.compile(r"\bPreorder Only - (Ships [^/]+)", re.I), r"\1"),
    (re.compile(r"\s*\[SOLD OUT\]", re.I), ""),
    (re.compile(r"\s+-?\s*In Stock\s*$", re.I), ""),
)
def display_title(t):
    for rx, rep in _TITLE_STATUS:
        t = rx.sub(rep, t)
    return t.strip()
for _p in stock["products"]:
    if _p.get("title"):
        _p["title"] = display_title(_p["title"])

# Traveler's Company and MIDORI were removed on Nov 19, 2026, at TRAVELER'S COMPANY USA's request (owner
# approved). Their old URLs show TAKEDOWN_NOTICE instead. Rows left in data/ from before the removal, and any row
# whose URL is no longer in stores.json, never reach a page, a restock feed or the site/data copies.
TAKEDOWN_SECTIONS = ("travelers", "midori")
TAKEDOWN_STORES = {"travelerscompanyusa", "mdproductusa"}  # the two brands' own stores
_TRACKED_URLS = {p["url"] for s in stores["stores"] for p in s["products"]}

def taken_down(r):
    return r.get("section") in TAKEDOWN_SECTIONS or r.get("store_id") in TAKEDOWN_STORES or r.get("url") not in _TRACKED_URLS

stock["products"] = [p for p in stock["products"] if not taken_down(p)]
changes = [c for c in changes if not taken_down(c)]

# Limited-edition ink tracker (scripts/ink_tracker.py). Its rows live in data/inks/, apart from stock.json, so
# they never reach the Hobonichi or dot grid pages, the restock feeds or the drop-alert webhook. A page shows
# only rows of inks listed in inks.json (owner-approved). Pending finds ("hidden": true) never render.
INK_CFG = json.loads((ROOT / "inks.json").read_text()) if (ROOT / "inks.json").exists() else {"brands": {}, "inks": []}
def _ink_load(name, default):
    f = ROOT / "data/inks" / name
    return json.loads(f.read_text()) if f.exists() else default
INK_STOCK = _ink_load("stock.json", {"products": [], "run_started": None, "run_finished": None})
INKS = {i["id"]: i for i in INK_CFG["inks"]}
_INK_URLS = {l["url"] for i in INK_CFG["inks"] for l in i["listings"]}
_STORE_IDS = {x["id"] for x in stores["stores"]}
def _ink_public(r):
    return (not r.get("hidden") and r.get("ink_id") in INKS and r.get("url") in _INK_URLS
            and r.get("store_id") in _STORE_IDS and r.get("store_id") not in TAKEDOWN_STORES)
for _r in INK_STOCK["products"]:
    if _r.get("title"):
        _r["title"] = display_title(_r["title"])
INK_ROWS = [r for r in INK_STOCK["products"] if _ink_public(r)]
INK_CHANGES = [c for c in _ink_load("changes.json", []) if _ink_public(c)]
INK_RETIRED = {k: v for k, v in _ink_load("retired.json", {}).items() if k in INKS}
INK_SLUG = "limited-edition-fountain-pen-ink"
INK_NAV = "Limited inks"
INK_LIVE = bool(INK_ROWS)

# Canonical products from other brands (e.g. Archer and Olive).
OTHER_BRAND = {c["id"] for c in stores["canonical"] if c.get("brand")}
CANON_SECTION = {c["id"]: c["section"] for c in stores["canonical"] if c.get("section")}
HOBO_SHOPS = {s["id"] for s in stores["stores"] if not s.get("brand") and not s.get("section")}
# The site keeps brand families apart, never mixed: Hobonichi (home tracker, calendar, Hobonichi product pages)
# plus one page per other section below. A listing's section is its own "section", its canonical's "section",
# or (older dot grid entries) a canonical with a "brand" or a store entry with a "brand".
DOTGRID_SHOPS = [s for s in stores["stores"] if s.get("brand")]
SECTIONS = {  # non-Hobonichi sections in nav/footer order; each has one page (the GROUPS entry with that section)
    # Slugs stay on the published URLs. Visible names describe what the page tracks.
    # /dot-grid-journal-restock-tracker/ covers all four dot-grid makers. It used to live at
    # /archer-and-olive-dot-grid-journal/, which is now an Archer and Olive page (AO_SLUG) that links here.
    "dotgrid": dict(slug="dot-grid-journal-restock-tracker", nav="Dot grid journals", name="dot grid journals",
                    foot="Dot grid journaling", link="Dot grid journals", count="dot grid journals",
                    one="dot grid journal", amazon=None),
}

def g_sec(g):
    return g.get("section", "hobonichi")

def hub_trail(g):
    """Breadcrumb steps above a tracker group. Hobonichi groups sit under the Hobonichi tracker hub;
    the other sections' trackers are top level, like Dot grid journals."""
    if g.get("slug") == AO_SLUG:
        return ((DOTGRID_SLUG + "/", SECTIONS["dotgrid"]["nav"]),)
    return ((HOBO_TRACKER, "Hobonichi tracker"),) if g_sec(g) == "hobonichi" else ()

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

N_STORES = len({p["store_id"] for p in stock["products"]} | {r["store_id"] for r in INK_ROWS})  # stores the checkers actually check (inks included)
N_INK = len({r["store_id"] for r in INK_ROWS})  # shops on the ink tracker
N_SEC = {k: len({p["store_id"] for p in section_products(k)}) for k in ("hobonichi", *SECTIONS)}  # shops per section, from data
LIVE = [k for k in SECTIONS if section_products(k)]  # sections that have tracked listings (and so a page)

def section_shops(sec):
    """Store entries with listings in a section, in stores.json order."""
    ids = {p["store_id"] for p in section_products(sec)}
    return [s for s in stores["stores"] if s["id"] in ids]

# Shop's home country, from its own site or domain (stores.json "country", first word). Never a shipping claim.
_REGION_FIX = {}  # id -> country tag, for a shop whose stores.json "country" is missing
REGION = {x["id"]: _REGION_FIX.get(x["id"]) or (x.get("country") or "").split()[0] for x in stores["stores"]}
REGION_NAME = {"US": "United States", "CA": "Canada", "SG": "Singapore", "UK": "United Kingdom", "AU": "Australia", "JP": "Japan"}
assert all(REGION[x["id"]] in REGION_NAME for x in stores["stores"]), "every shop needs a country tag"

# A shop whose name ends with its country (e.g. "Leuchtturm1917 US") shows the plain name plus the
# country tag, like every other shop, so the country never appears twice.
# "Leuchtturm1917 US (official)" becomes "Leuchtturm1917 (official)" plus the tag, so official
# stores stay marked without repeating the country.
_STRIP = {}
for _x in stores["stores"]:
    _raw = _x["name"]
    _name = _raw.rstrip()
    _official = ""
    if re.search(r"\s+\(official\)$", _name, flags=re.I):
        _official = " (official)"
        _name = re.sub(r"\s+\(official\)$", "", _name, flags=re.I).rstrip()
    _sfx = " " + REGION[_x["id"]]
    if _name.upper().endswith(_sfx):
        _name = _name[:-len(_sfx)].rstrip()
    _display = _name + _official
    if _display != _raw:
        _STRIP[_raw] = _display
        _x["name"] = _display
# Older change-log rows predate the "(official)" name and read "Leuchtturm1917 US". Same shop, same display name.
_STRIP.setdefault("Leuchtturm1917 US", "Leuchtturm1917 (official)")
for _r in stock["products"] + changes + stock.get("not_checked", []) + INK_ROWS + INK_CHANGES:
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

def countries_present(store_ids):
    """Country codes actually used by these shops, in REGION_NAME order. No invented countries."""
    present = {REGION.get(i) for i in store_ids if REGION.get(i)}
    return [c for c in REGION_NAME if c in present]

def country_filter_label(store_ids, attr):
    """A Based-in filter, only when two or more countries are present. attr is the select's id or data-filter."""
    cs = countries_present(store_ids)
    if len(cs) < 2:
        return ""
    opts = "".join(f'<option value="{E(c)}">{E(REGION_NAME[c])}</option>' for c in cs)
    return (f'<label>Based in<select {attr}><option value="">All countries</option>{opts}</select></label>')

def group_toggle_html():
    """Hidden until JS runs; without JS the native <details> summaries still open one group at a time."""
    return ('<div class="group-toolbar">'
            '<button type="button" class="group-toggle" data-group-toggle hidden>Expand all</button>'
            '</div>')

def names_and(n):
    return ", ".join(n[:-1]) + " and " + n[-1] if len(n) > 1 else "".join(n)

def dotgrid_names():
    """Store names as shown in shop lists, including an (official) mark when present."""
    return names_and([s["name"] for s in DOTGRID_SHOPS])

def bare_shop_name(name):
    """Store name without a trailing (official) mark, for brand lists in prose."""
    return re.sub(r"\s+\(official\)$", "", name, flags=re.I).rstrip()

def dotgrid_brand_names():
    return names_and([bare_shop_name(s["name"]) for s in DOTGRID_SHOPS])

def _dotgrid_coverage():
    """Maker-only brand names, mixed-coverage phrases, and independent-shop counts."""
    only, mixed, counts = [], [], {}
    listings = section_products("dotgrid")
    for s in DOTGRID_SHOPS:
        canons = {p.get("canonical") for p in s.get("products") or [] if p.get("canonical")}
        shops = {p["store_id"] for p in listings if p.get("canonical") in canons}
        name = bare_shop_name(s["name"])
        independents = shops - {s["id"]}
        if not independents:
            only.append(name)
        else:
            n = len(independents)
            counts[s["id"]] = n
            mixed.append(f"{name} at its official US store and {n} independent {'shop' if n == 1 else 'shops'}")
    return only, mixed, counts

def leuchtturm_independent_count():
    return _dotgrid_coverage()[2].get("leuchtturm-us", 0)

def dotgrid_meta_desc():
    """Tracker meta/og description, kept within DESC_LIMIT so it is not cut mid-phrase."""
    n = leuchtturm_independent_count()
    shops = "shop" if n == 1 else "shops"
    return (
        f"Are {dotgrid_brand_names()} in stock? Official stores, "
        f"plus {n} independent {shops} for Leuchtturm1917."
    )

def dotgrid_where_checked():
    """Which shops we check for each dot-grid brand, from the live stock file."""
    only, mixed, _counts = _dotgrid_coverage()
    if only and mixed:
        return f"We check {names_and(only)} on each maker's own store, and {names_and(mixed)}."
    if mixed:
        return f"We check {names_and(mixed)}."
    return f"We check {names_and(only) or dotgrid_brand_names()} on each maker's own store."

def shop_names(sec):
    return dotgrid_names() if sec == "dotgrid" else names_and([s["name"] for s in section_shops(sec)])

def sections_phrase():
    """'dot grid journals' (live sections only, joined with commas and 'and')."""
    return names_and([SECTIONS[k]["name"] for k in LIVE])

def non_hobonichi_phrase():
    """Every tracker besides Hobonichi, for the home and Organization descriptions: live sections plus the inks."""
    return names_and([SECTIONS[k]["name"] for k in LIVE] + (["limited-edition fountain pen inks"] if INK_LIVE else []))

def organization():
    """Shared Organization JSON-LD. Locality only: no street address."""
    return {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE,
            "description": f"Independent restock tracker for Hobonichi Techo 2027 planners and covers, plus {non_hobonichi_phrase()}. Statuses come straight from each shop's public product data.",
            "logo": BASE + "assets/brand/icon-512.png", "email": PUBLIC_EMAIL,
            "sameAs": [s[2] for s in SOCIALS],
            "address": {"@type": "PostalAddress", "addressLocality": "Hamtramck",
                        "addressRegion": "MI", "addressCountry": "US"}}

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
        e = db[fn.__name__] = {"hash": h, "date": dt.datetime.now(DETROIT).date().isoformat()}
        GUIDE_DATES.write_text(_j.dumps(db, indent=1, sort_keys=True) + "\n")
    d = dt.date.fromisoformat(e["date"])
    return f"updated {d.strftime('%b')} {d.day}, {d.year}"

STATUS = {"in_stock": "In stock", "preorder": "Preorder", "coming_soon": "Not yet on sale",
          "sold_out": "Sold out", "unknown": "Couldn't check"}
DOTGRID_SLUG = SECTIONS["dotgrid"]["slug"]
# The old tracker URL. It is now a page about Archer and Olive only (a GROUPS entry with aux=True).
AO_SLUG = "archer-and-olive-dot-grid-journal"
TN_SLUG = "travelers-company-limited-edition"   # takedown notice since Nov 19, 2026
MIDORI_SLUG = "midori-md-limited-edition"       # takedown notice since Nov 19, 2026
TN_GUIDE_SLUG = "travelers-notebook-regular-vs-passport-vs-card-size"  # old guide URL; 301 to the takedown notice since Nov 22, 2026
TAKEDOWN_ITEMS = {TN_SLUG: ("regular-black", "regular-blue", "regular-brown", "regular-camel", "regular-olive",
                            "road-trip-brown", "card-size-20th-anniversary-black"),
                  MIDORI_SLUG: ("md-diary-2027-a5", "md-diary-1-day-1-page-2027-a5")}
# Old slugs that now redirect (meta refresh + canonical) to their new page. Never listed in the sitemap.
REDIRECTS = {"archer-and-olive-bullet-journal": AO_SLUG + "/",
             MIDORI_SLUG: TN_SLUG + "/",  # duplicate of the Traveler's notice: one canonical page, the other 301s
             "travelers-notebook-regular-size": TN_SLUG + "/",  # takedown notice
             TN_GUIDE_SLUG: TN_SLUG + "/",  # old size guide, retired with the takedown
             "faq": "#good-to-know"}  # /faq -> the homepage FAQ ("Good to know")
# Old Traveler's Company and MIDORI item pages point at their brand's takedown notice.
REDIRECTS.update({f"{parent}/{slug}": TN_SLUG + "/" for parent, slugs in TAKEDOWN_ITEMS.items() for slug in slugs})
# Home is a hub; the Hobonichi tracker (the old homepage content) lives on its own page.
HOBO_TRACKER = "hobonichi-restock-tracker/"
# Header: one link per restock tracker, then the rest of the site. Wraps on narrow screens; nothing is hidden.
# NAV is not part of the tracker count. The calendar, guides, and shop are resources, not extra trackers.
NAV_TRACKERS = ([(HOBO_TRACKER, "Hobonichi tracker")] + [(SECTIONS[k]["slug"] + "/", SECTIONS[k]["nav"]) for k in LIVE]
                + ([(INK_SLUG + "/", INK_NAV)] if INK_LIVE else []))
# Shop stays in the header, after the trackers, and is not one of them.
NAV = [("hobonichi-2027/", "2027 calendar"), ("guides/", "Guides"),
       ("follow/", "Follow us"), ("about/", "About")]

def tracker_count_label():
    """Eyebrow count of restock trackers only (Hobonichi plus each section that has listings)."""
    n = len(NAV_TRACKERS)
    return f"{n} restock tracker" if n == 1 else f"{n} restock trackers"
SHOP_NAME = "Our planners and journals"  # h1 of /shop; the breadcrumb and header link both say Shop.
# The workflow cron is "17,47 * * * *": two runs an hour. Every page says it the same way.
CHECK_FREQ = "about every 30 minutes"
N_HOBO = N_SEC["hobonichi"]   # Hobonichi shops we check
N_DG = N_SEC["dotgrid"]        # dot grid shops we check
TITLE_SUFFIX = " · Stationery Drop Watch"
TITLE_LIMIT = 60  # search-result titles past this are cut off
DESC_LIMIT = 155  # meta descriptions past this can be cut off in search results
BRAND_SHORT = " · Drop Watch"

# Guide templates hash their own source for the visible "updated" date. Short titles for those
# pages are applied here, so the guide functions themselves stay byte-for-byte and the date does not move.
TITLE_OVERRIDES = {
    "Stationery gifts that are actually in stock: holiday gift guide 2026": "Stationery gifts in stock: holiday gift guide 2026",
    "Hobonichi Techo 2027 launch & restock calendar": "Hobonichi Techo 2027 calendar",
    "Hobonichi Techo vs Cousin vs Weeks (2027): sizes, layouts, who each suits": "Hobonichi Techo vs Cousin vs Weeks",
    "Best dot grid journals compared: Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy": "Best dot grid journals compared",
    "Hobonichi Techo January-start vs April-start: which one should you buy?": "Hobonichi Techo January-start vs April-start",
}
DESC_OVERRIDES = {
    "Dot grid journals compared: paper weight (gsm), pages, size and features for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, from each maker's page, plus live stock.":
    "Dot grid journals compared by paper, pages, size and features: Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy.",
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

SEO_WARNINGS = []

def seo_warn(kind, fname, text, limit):
    """Build-time warning for a title or description over its limit. Printed, never silent."""
    msg = f"SEO warning: {kind} over {limit} characters ({len(text)}) on {fname}: {text}"
    SEO_WARNINGS.append(msg)
    print(msg)

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
OG_ALT = f"Stationery Drop Watch: restock tracker for Hobonichi, dot grid journals and limited-edition inks, checked {CHECK_FREQ}"
OG_DOTGRID = BASE + "assets/brand/og-dotgrid.png"  # same script; used on the dot grid journaling page
OG_DOTGRID_ALT = "Stationery Drop Watch: dot grid journal restock tracker for Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy, checked " + CHECK_FREQ
CONTENT_LASTMOD = "2026-11-12"  # floor for pages whose HTML changed in the Nov 12 refresh
X_HANDLE = "@stationerydrop"
LOCAL_LINK = re.compile(r'\b(href|src|srcset)="(?!https?:|mailto:|#|/|\.\./|data:)([^"]*)"')

def page(fname, title, desc, body, ld=(), og_type="website", og_image=OG_IMAGE, og_alt=OG_ALT, noindex=False):
    return _page(fname, title, desc, body, ld, og_type, og_image, og_alt, noindex)

def pretty(path):
    """Public form of a local page path: 'index.html' -> '', everything else keeps its trailing slash
    ('about/', 'guides/', 'about/#x'). Every page is a directory with an index.html and one canonical URL
    that ends in a slash. Only 404.html is a flat file."""
    if re.match(r"index\.html(?=[?#]|$)", path):
        return path[len("index.html"):]
    return re.sub(r"^([^?#]*?)\.html(?=[?#]|$)", r"\1", path)

# One URL style: trailing slash on every page. The three pages that used to be flat files.
LEGACY_FLAT_PAGES = ("hobonichi-2027.html", "about.html", "privacy.html")

def url_for(fname):
    """Absolute public URL: index.html -> BASE, 'slug/' -> BASE + 'slug/'."""
    return BASE + pretty(fname)

PUBLIC_EMAIL = "admin@stationerydropwatch.com"
# One sentence, on every page footer and on About and Contact.
INDEPENDENT_NOTE = (
    "Stationery Drop Watch is an independent site. "
    "It is not affiliated with or endorsed by any brand or shop we track. "
    "Brands or shops can ask to be removed at {email}."
)

def independent_note():
    return INDEPENDENT_NOTE.format(email=plain_email())

def plain_email():
    """Visible address, not a mailto link. The comments keep Cloudflare from obfuscating it."""
    return f"<!--email_off-->{E(PUBLIC_EMAIL)}<!--/email_off-->"

def mailto_email():
    """The visible address as a mailto link (Contact, About, Privacy). Same comments, same literal address."""
    return f'<!--email_off--><a href="mailto:{E(PUBLIC_EMAIL)}">{E(PUBLIC_EMAIL)}</a><!--/email_off-->'

def jsonld(obj):
    payload = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    script = '<script type="application/ld+json">' + payload + "</script>"
    if PUBLIC_EMAIL in payload:  # keep the publisher address literal in the page source
        return "<!--email_off-->" + script + "<!--/email_off-->"
    return script

def _page(fname, title, desc, body, ld=(), og_type="website", og_image=OG_IMAGE, og_alt=OG_ALT, noindex=False):
    url = url_for(fname)
    raw_desc = DESC_OVERRIDES.get(" ".join(str(desc).split()), " ".join(str(desc).split()))
    title = seo_title(title)  # brand suffix only when the title still fits in a search result
    if len(title) > TITLE_LIMIT:
        seo_warn("title", fname, title, TITLE_LIMIT)
    if len(raw_desc) > DESC_LIMIT:  # the template ran long, so seo_desc() will cut it on a word
        seo_warn("description", fname, raw_desc, DESC_LIMIT)
    desc = seo_desc(desc)
    guide_page = fname in ("where-to-buy-hobonichi-2027/", "hobonichi-techo-vs-cousin-vs-weeks/", "hobonichi-january-start-vs-april-start/", "best-dot-grid-journals/", GIFT_SLUG + "/")  # guides sit under Guides (the calendar keeps its own nav item)
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
        ("guides/", "Guides"), ("hobonichi-2027/", "2027 calendar"), ("sold-out-everywhere/", "Sold out everywhere"), ("shop/", "Shop"),
        ("follow/", "Follow us"),
        ("about/", "About"), ("/#good-to-know", "FAQ"), ("contact/", "Contact"), ("privacy/", "Privacy")]
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
<link rel="preload" href="assets/fonts/liberation-sans-regular.woff2" as="font" type="font/woff2" crossorigin>
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
  <a class="brand" href="index.html" aria-label="Stationery Drop Watch home"><picture><source media="(max-width:340px)" srcset="assets/brand/icon.svg"><img class="brand-logo" src="assets/brand/logo.svg" alt="Stationery Drop Watch" width="248" height="44"></picture></a>
  <nav class="site-nav" aria-label="Main">{nav}</nav>
</div></header>
<main id="content" class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p class="foot-brand"><strong>Stationery Drop Watch</strong> checks {N_STORES} shops {CHECK_FREQ}.</p>
  <nav class="foot-nav" aria-label="Footer">{foot_nav}</nav>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it.</p>
  <p class="muted">{independent_note()}</p>
  <p class="foot-badge"><a href="https://www.saashub.com/stationery-drop-watch?utm_source=badge&utm_campaign=badge&utm_content=stationery-drop-watch&badge_variant=color&badge_kind=approved" target="_blank" rel="noopener"><img class="badge-saashub" src="/assets/badges/saashub_v2_150x50.png" srcset="/assets/badges/saashub_v2_150x50.png 1x, /assets/badges/saashub_v2_300x100.png 2x" alt="Stationery Drop Watch on SaaSHub" width="150" height="50" loading="lazy"></a> <a href="/privacy/"><picture><source type="image/webp" srcset="/assets/badges/zero-cookies-badge_v1_300x126.webp 1x, /assets/badges/zero-cookies-badge_v1_600x252.webp 2x"><img class="badge-zero-cookies" src="/assets/badges/zero-cookies-badge_v1_300x126.png" srcset="/assets/badges/zero-cookies-badge_v1_300x126.png 1x, /assets/badges/zero-cookies-badge_v1_600x252.png 2x" alt="Zero cookies: this site sets no cookies" width="150" height="63" loading="lazy"></picture></a> <picture><source type="image/webp" srcset="/assets/badges/made-in-hamtramck_v2_300x100.webp 300w, /assets/badges/made-in-hamtramck_v2_900x300.webp 900w" sizes="150px"><img class="badge-hamtramck" src="/assets/badges/made-in-hamtramck_v2_300x100.png" srcset="/assets/badges/made-in-hamtramck_v2_300x100.png 300w, /assets/badges/made-in-hamtramck_v2_900x300.png 900w" sizes="150px" alt="Made in Hamtramck, MI" width="150" height="50" loading="lazy"></picture></p>
</div></footer>
<script src="assets/local-time.js?v={ASSET_V['local-time.js']}" defer></script>
<script src="assets/app.js?v={ASSET_V['app.js']}" defer></script>
</body></html>"""
    # The site is served at the domain root, so make every local link root-relative ("assets/x" -> "/assets/x").
    # "index.html" becomes "/" and directory links stay "/about/" so internal links match the canonical URLs.
    doc = LOCAL_LINK.sub(lambda m: f'{m.group(1)}="/{pretty(m.group(2))}"', doc)
    return doc

NEWSLETTER = "dropwatch"  # Buttondown username (kept for the cutover fallback; signups now go to Kit)
KIT_FORM_ID = "10225471"  # Kit form "Never miss a stationery restock" (data-uid ada05fa216)
# Signups post to our own Pages Function (site/functions/api/subscribe.js), which checks Cloudflare Turnstile and then
# calls the Kit API (Kit's plain HTML form post is quarantined by Kit's captcha, so it cannot be used directly).
KIT_SIGNUP_ACTION = "/api/subscribe"
# Public Turnstile sitekey for stationerydropwatch.com (managed mode). SDW_TURNSTILE_SITEKEY overrides it for local and
# preview builds (Cloudflare's always-pass test key 1x00000000000000000000AA).
TURNSTILE_SITEKEY = os.environ.get("SDW_TURNSTILE_SITEKEY", "0x4AAAAAAGM1G3F90gZdAcnK")
# Kit tag ids (hobonichi, dot-grid, inks). The form posts them as tags[]; alerts send to one tag per tracker.
KIT_TAGS = (("hobonichi", "26280763", "Hobonichi"), ("dot-grid", "26280764", "Dot grid journals"), ("inks", "26280765", "Limited-edition inks"))
KIT_PRIVACY_URL = "https://kit.com/privacy"

# Page types: trackers (home + GROUPS) use hero + .layout with a sidebar; guides and info pages use article.prose.
# Guides, the homepage, about, follow and the shop keep one signup box under the intro.
# Tracker, product and design pages add a compact repeat at the bottom (id="alerts-bottom").
SIGNUP_ACTION = KIT_SIGNUP_ACTION

# One Kit list with a tag per tracker (Hobonichi, dot grid journals, limited-edition inks): a subscriber gets restock emails
# for the trackers they tick, plus occasional site updates. Tracker, product and design labels name the brand or category
# on that page, never a single design or SKU. The signup note is the same on every box,
# including the shop, and mentions confirmation because Kit's form is double opt-in.
# It must not give a daily number.
# SPEED_LINE is backed by data/changes.json (Oct 26-Nov 11, 2026): of 19 restocks where we also saw the sell-out,
# 7 sold out within an hour and 14 within 6 hours. Re-check it before changing the wording.
SPEED_LINE = "Restocks often sell out within hours."
LIST_LINE = (
    "Free restock emails for the trackers you pick: Hobonichi, dot grid journals and limited-edition inks. "
    "Pick at least one, plus an occasional update when we add a tracker or release something new. "
    "Unsubscribe anytime. We'll email you a confirmation link. You aren't on the list until you click it."
)
SIGNUP_COPY = {
    "alerts": ("Get an email when anything we track restocks", LIST_LINE),
    "shop": ("Get an email when anything we track restocks", LIST_LINE),
}
TAGLINE = "Never miss a stationery restock"
ONE_LIST_LABEL = "Get an email when anything we track restocks"
SIGNUP_LABELS = {
    "hobonichi": "Get an email when Hobonichi items restock",
    "dotgrid": "Get an email when dot grid journals restock",
    "inks": "Get an email when limited-edition inks restock",
}

def signup_for(subject=None, back=None, section=None, placement="top"):
    """Signup box for a product, design, or tracker page. Label is brand-level, never a single item.
    subject and back stay on the signature so older callers still work; section picks the label."""
    label = SIGNUP_LABELS.get(section, ONE_LIST_LABEL)
    pre = {"hobonichi": "hobonichi", "dotgrid": "dot-grid", "inks": "inks"}.get(section)
    return signup(label=label, note=LIST_LINE, placement=placement, kicker=TAGLINE, preselect=pre)

def signup(kind="alerts", label=None, note=None, placement="top", kicker=TAGLINE, preselect=None):
    """Kit's HTML form (form 10225471): a plain POST to app.kit.com/forms/<id>/subscriptions with email_address and one
    tags[] checkbox per tracker, so it works without JavaScript. Kit's form is double opt-in. The top box is always
    id="alerts", so "#alerts" links work on every page. A bottom repeat uses id="alerts-bottom" and distinct field ids so
    the markup stays valid. Every box carries the TAGLINE kicker except the home hero, whose h1 already says it.
    preselect is a tag slug to tick by default on a tracker page; otherwise every tracker is ticked."""
    d_label, d_note = SIGNUP_COPY[kind]
    label, note = label or d_label, note or d_note
    sid = "alerts" if placement == "top" else "alerts-bottom"
    eid = "email-top" if placement == "top" else "email-bottom"
    extra = " signup-strip-bottom" if placement == "bottom" else ""
    kicker_html = f'<p class="strip-kicker">{E(kicker)}</p>\n  ' if kicker else ""
    boxes = "".join(
        f'<label class="strip-check"><input type="checkbox" name="tags[]" value="{tid}" id="{sid}-tag-{slug}"'
        f'{" checked" if (preselect is None or preselect == slug) else ""}> {E(name)}</label>'
        for slug, tid, name in KIT_TAGS)
    return f"""<section class="signup-strip{extra}" id="{sid}" aria-label="{E(label)}">
  {kicker_html}<form class="signup-form kit-signup-form" action="{SIGNUP_ACTION}" method="post" data-turnstile="1">
    <label class="strip-label" for="{eid}">{E(label)}</label>
    <input id="{eid}" type="email" name="email_address" placeholder="you@example.com" required autocomplete="email">
    <fieldset class="strip-trackers"><legend>Email me about</legend>{boxes}</fieldset>
    <input type="text" name="website" class="hp-field" tabindex="-1" autocomplete="off" aria-hidden="true">
    <div class="cf-turnstile" data-sitekey="{TURNSTILE_SITEKEY}" data-appearance="interaction-only" data-theme="light"></div>
    <button type="submit">Notify me</button>
    <p class="signup-status" role="status" aria-live="polite" hidden></p>
  </form>
  <p class="strip-note">{E(note)} Emails are sent via <a href="https://kit.com" target="_blank" rel="noopener">Kit</a>. <a href="privacy/">Privacy</a></p>
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

def is_restock_event(c):
    """A restock is a listing becoming buyable. coming_soon -> sold_out is not one, and it must not alert."""
    return c.get("to") in BUYABLE and c.get("from") in NOT_BUYABLE

def listed_unchecked():
    """Link-only shops still configured in stores.json.

    An older stock.json can name a shop that was removed (Nanami Paper). The
    pages follow stores.json, which is the list the checker will write next.
    """
    allowed = {s["id"] for s in stores["stores"] if s.get("platform") not in ("shopify", "hobonichi")}
    return [n for n in stock.get("not_checked", []) if n.get("id") in allowed]

def link_only_clause():
    """FAQ sentence. Singular when JetPens is the only shop we link and do not check."""
    names = [n["name"] for n in listed_unchecked()]
    if len(names) == 1:
        return f"{names[0]} is listed as a link only, because its site blocks automated checks."
    if len(names) == 2:
        return f"{names[0]} and {names[1]} are listed as links only, because their sites block automated checks."
    if not names:
        return "Every shop we list is checked automatically."
    return f"{', '.join(names[:-1])}, and {names[-1]} are listed as links only, because their sites block automated checks."

def product_key(p):
    """Group listings of the same product across stores: canonical id, else a normalized title."""
    if p.get("canonical"):
        return p["canonical"]
    t = re.sub(r"\[[^\]]*\]", " ", p["label"].lower())
    t = re.sub(r"\b(hobonichi|techo|2027|planner)\b", " ", t)
    return "t:" + " ".join(re.findall(r"[a-z0-9&]+", t))

def sold_everywhere_html(items, status="status", shop="store_id"):
    """The sold-out sentence, inside a product group.

    Shown only when every listing in that group is sold out. A coming-soon or unchecked
    listing keeps the group quiet."""
    if not items or {item[status] for item in items} != {"sold_out"}:
        return ""
    n = len({item[shop] for item in items})
    text = (f"Sold out at every shop we track ({n} shops)." if n > 1
            else "Sold out at the only shop we track.")
    return f'<p class="muted small">{text}</p>'

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

def official_note(l):
    """Optional note from Hobonichi's own feed (checker.hobonichi_note), only on sold-out official rows.
    Older stock.json rows don't have the field, so they render as before."""
    note = l.get("official_note")
    return note if note and l.get("store_id") == "1101" and l.get("status") == "sold_out" else None

def compare_product(ls):
    """One product, every shop that lists it, so the statuses sit next to each other."""
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    ls = sorted(ls, key=lambda r: (order.get(r["st"], 9), r["s"].lower()))
    h = ls[0]
    name = f'<a href="{E(h["dp"])}">{E(h["gn"])}</a>' if h.get("dp") else E(h["gn"])
    shops = len({r["sid"] for r in ls})
    bits = [E(h.get("t") or ""), f"{shops} {'shop' if shops == 1 else 'shops'}"]
    if h.get("dp"):
        bits.append(f'<a href="{E(h["dp"])}">Design page</a>')
    note = sold_everywhere_html(ls, "st", "sid")
    items = []
    for r in ls:
        region = f' <span class="region" title="Shop\'s home country">{E(r["rg"])}</span> ' if r.get("rg") else ""
        variant = f'<span class="sub variant">{E(r["p"])}</span>' if r.get("p") and r["p"] != r.get("gn") else ""
        title = f'<span class="sub">{E(r["title"])}</span>' if r.get("title") and r["title"] not in (r.get("gn"), r.get("p")) else ""
        items.append(
            f'<li><span class="compare-shop"><a href="{E(r["u"])}" target="_blank" rel="noopener">{E(r["s"])}</a>{region}{variant}{title}</span>'
            f'<span class="badge {E(r["st"])}">{STATUS[r["st"]]}</span>'
            + (f'<span class="official-note">{E(r["on"])}</span>' if r.get("on") and r.get("st") == "sold_out" else "") + '</li>')
    anchor = f' id="{E(h["g"])}"' if re.fullmatch(r"[A-Za-z][\w-]*", h.get("g") or "") else ""
    return f'''<article class="compare"{anchor}>
  <header class="compare-head"><h3>{name}</h3><p class="compare-tally">{E(shop_tally(ls))}</p><p class="sub">{" · ".join(b for b in bits if b)}</p>{note}</header>
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
    country_label = country_filter_label(sids, 'id="f-country"')
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
            {country_label}
            <label>Status<select id="f-status"><option value="">Any status</option>{status_opts}</select></label>
          </div>
        </details>
        <label class="grow">Search<input id="f-q" type="search" placeholder="Search design or shop…" aria-label="Search design or shop, for example {E(search_hint.rstrip("…"))}" autocomplete="off"></label>
        <button type="button" class="filter-reset" id="f-reset">Reset</button>
        {group_toggle_html()}
      </form>
      {lang_note}
      <div id="rows" class="tracker-groups"><noscript>{noscript_rows}</noscript></div>
      <button type="button" id="more" class="btn-ghost more" hidden>Show all</button>
      <p class="muted small">Groups can be collapsed. "Not yet on sale" means the store has a preview page up but isn't taking orders yet. "Couldn't check" is a failed check, not a sold-out guess.</p>
      {region_legend(p["store_id"] for p in prods)}
      {extra}
    </section>"""

def tracker_rows(prods, out_everywhere=None):
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    fam_index = {g["slug"]: i for i, g in enumerate(g for g in GROUPS if g_sec(g) == "hobonichi")}
    rows = []
    for p in prods:
        famn, fam = listing_family(p)
        rows.append(dict(g=product_key(p), p=p["label"], gn=canon.get(p.get("canonical") or "", p["label"]), c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], rg=REGION.get(p["store_id"], ""), st=p["status"],
                 u=p["url"], at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 va=p.get("available_variants"), tv=p.get("total_variants"),
                 sz=listing_size(p), lg=listing_language(p), famn=famn, fam=fam, fo=fam_index.get(fam, 99)))
        note = official_note(p)
        if note:
            rows[-1]["on"] = note  # app.js shows it under the shop, like compare_product does
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
    if INK_LIVE and here != INK_SLUG + "/":
        links.append((INK_SLUG + "/", INK_NAV))
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

def pack_rows(rows):
    """Compact form of the listing rows for the page (decoded back to the same row objects by assets/app.js):
    {"k": [keys], "d": {key: [distinct values]}, "r": [[value or dictionary index per key, null = key absent]]}.
    Repeated strings (product, shop, status, family...) are stored once. Falls back to the plain list if any value is null."""
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    if any(v is None for r in rows for v in r.values()):
        return rows
    d = {}
    for k in keys:
        vals = [r[k] for r in rows if k in r]
        distinct = []
        for v in vals:
            if v not in distinct and isinstance(v, str):
                distinct.append(v)
        if len(distinct) * 3 < len(vals) and len(distinct) == len({r[k] for r in rows if k in r}):
            d[k] = distinct
    out = []
    for r in rows:
        out.append([(d[k].index(r[k]) if k in d else r[k]) if k in r else None for k in keys])
    return {"k": keys, "d": d, "r": out}

def stock_data(rows):
    return f'<script id="stock-data" type="application/json">{json.dumps(pack_rows(rows), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")}</script>'

def soon_block():
    """Sections we plan to track but don't have listings for yet. Disappears once every one is live."""
    soon = [k for k in SECTIONS if k not in LIVE]
    if not soon:
        return ""
    items = "".join(f'<li>{E(SECTIONS[k]["name"])}</li>' for k in soon)
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

def restock_feed(events, extra="", feed_id="restocks", limit=None):
    """Grouped restocks, newest first. `limit` is how many listings to show, not how many flips.
    All shows every listing with its latest status; In stock now is CSS-only and hides the rest.
    Without :has support (or without CSS) the controls stay hidden and every row shows."""
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
    urls = {p["url"] for p in prods}
    restocks = [c for c in changes if c["url"] in urls and is_restock_event(c)]
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
    rows = tracker_rows(prods)
    unchecked = listed_unchecked()
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a>: <span class="muted">{E(n["reason"] or "")}</span></li>' for n in unchecked)
    unchecked_summary = "Store we list but don't check automatically" if len(unchecked) == 1 else "Stores we list but don't check automatically"

    faq_html, faq_ld = tracker_good_to_know(HOBO_NOTE_Q, HOBO_NOTE)
    more = "".join(f'<li><a href="{g["slug"]}/">{E(g["short"])}</a></li>' for g in GROUPS if g_sec(g) == "hobonichi")
    tracker_html = tracker_block(prods, rows, "Moomin, Cousin, Midnight Blue…", '<option value="__other">Other 2027 items</option>',
        f'<details class="muted small"><summary>{unchecked_summary}</summary><ul>{not_checked}</ul></details>',
        prefix=hobo_design_nav())
    body = f"""
{crumbs((HOBO_TRACKER, "Hobonichi tracker"))}
<section class="hero">
  {eyebrow("Hobonichi Techo 2027", f"{len({p['store_id'] for p in prods})} Hobonichi shops", f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}")}
  <h1>Hobonichi 2027 restock tracker</h1>
  <p class="lede">We check the official Hobonichi store and independent shops for sold-out Hobonichi planners and covers, and tell you when they come back.</p>
  {hero_facts(prods)}
  {signup_for(section="hobonichi")}
  {also_tracked(HOBO_TRACKER)}
</section>

<div class="layout solo">
  <div class="main-col">
    <section class="card" id="restocked">
      <h2>Recent restocks</h2>
      {feed_html}
    </section>
    {tracker_html}{holiday_planner_card()}
    {faq_html}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{more}</ul></section>
    {guides_block()}
    {soon_block()}
  </div>
</div>
{signup_for(section="hobonichi", placement="bottom")}
{stock_data(rows)}
"""
    n_shops = len({p['store_id'] for p in prods if p['store_id'] in HOBO_SHOPS})
    return page(HOBO_TRACKER, "Hobonichi 2027 restock tracker",
                f"Hobonichi 2027 restock tracker. Live status for Original A6, Cousin A5, Weeks and covers at {n_shops} shops, plus separate trackers for other brands.",
                body, ld=(faq_ld, crumbs_ld((HOBO_TRACKER, "Hobonichi tracker"))))

HUB_TRACKERS = {  # one line per tracker card on the hub homepage
    "hobonichi": ("Hobonichi Techo 2027", "Original A6, Cousin A5, the English Planner A6, HON, Weeks, Weeks Mega and covers, at the official store and independent shops."),
    "dotgrid": ("Dot grid journals", ""),  # short homepage blurb is filled in below; official-store detail stays on the hub
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
    elif kind == "inks":
        # An ink bottle on the same center (80, 32): terracotta cap, sage ink line.
        body = (f'<rect x="72" y="6" width="16" height="10" rx="2" fill="{accent}" stroke="{ink}" stroke-width="2"/>'
                f'<path d="M66 20 h28 l4 6 v26 a4 4 0 0 1 -4 4 h-28 a4 4 0 0 1 -4 -4 v-26 z" fill="{paper}" stroke="{ink}" stroke-width="2" stroke-linejoin="round"/>'
                f'<path d="M66 16 h28 v4 h-28 z" fill="{ink}"/>'
                f'<path d="M64 38 h32 v14 a2 2 0 0 1 -2 2 h-28 a2 2 0 0 1 -2 -2 z" fill="{sage}"/>')
    elif kind == "notice":
        # A letter on the same center (80, 32): envelope flap in terracotta, two sage lines.
        body = (f'<rect x="50" y="12" width="60" height="42" rx="3" fill="{paper}" stroke="{ink}" stroke-width="2"/>'
                f'<path d="M51 13 L80 36 L109 13" fill="none" stroke="{accent}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M60 46 h18 M60 50 h12" stroke="{sage}" stroke-width="2" stroke-linecap="round"/>')
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
            # Short homepage blurb only. Official-store / independent-shop detail stays on the hub.
            line = f"Flagship notebooks from {dotgrid_brand_names()}, plus Archer and Olive refills."
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
    if INK_LIVE:
        ist = {x: sum(r["status"] == x for r in INK_ROWS) for x in STATUS}
        ibits = [nshops(N_INK)]
        if ist["preorder"]:
            ibits.append(f'{ist["preorder"]} on preorder')
        if ist["coming_soon"]:
            ibits.append(f'{ist["coming_soon"]} not yet on sale')
        if ist["unknown"]:
            ibits.append(f'{ist["unknown"]} couldn\'t be checked')
        cards.append(f"""<li class="hub-card"><a href="{INK_SLUG}/">
  <span class="hub-art">{hub_art("inks")}</span>
  <h3>Limited-edition inks</h3><p>{E(INK_HUB_LINE)}</p>
  <p class="hub-count"><b>{ist["in_stock"]}</b> of {len(INK_ROWS)} listings in stock <span class="muted small">{E(" · ".join(ibits))}</span></p>
  <span class="hub-go">View tracker</span></a></li>""")
    # Third card: the takedown notice. Same card and button as the trackers; no counts or stock badges.
    # The line is verbatim phrases from TAKEDOWN_NOTICE, including the Nov 20 lines.
    cards.append(f"""<li class="hub-card hub-notice"><a href="{TN_SLUG}/">
  <span class="hub-art">{hub_art("notice")}</span>
  <h3>{E(TAKEDOWN_HEADING)}</h3><p>{E(HOME_NOTICE_LINE)}</p>
  <span class="hub-go">Read the notice</span></a></li>""")
    sec_of_url = {p["url"]: section_of(p) for p in prods}
    restocks = [c for c in changes if c["url"] in sec_of_url and is_restock_event(c)]
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
    faq_html, faq_ld = faq_block(only=HUB_FAQ, sid="good-to-know")
    body = f"""
<section class="hero">
  {eyebrow(tracker_count_label(), f"{N_STORES} shops", f"checked {CHECK_FREQ}")}
  <h1>Never miss a stationery restock.</h1>
  <p class="hero-shops">We check {N_STORES} shops for you</p>
  <p class="suggest">Know the moment your planner, journal or ink is back.</p>
  <p class="lede">We check official stores and independent shops for sold-out Hobonichi planners, dot grid journals and limited-edition inks, and tell you when they come back.</p>
  {signup(kicker=None)}
  {trust_strip(prods + (INK_ROWS if INK_LIVE else []))}
  <p class="small section-switch">More on the site: <a href="hobonichi-2027/">2027 calendar</a> · <a href="guides/">Guides</a> · <a href="shop/">Shop</a> · <a class="nobr" href="sold-out-everywhere/">Sold out everywhere</a>.</p>
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
               "description": f"Restock checks {CHECK_FREQ} for Hobonichi Techo 2027 planners and covers across the official store and independent shops, and, in separate sections, {non_hobonichi_phrase()}.",
               "publisher": organization()}
    return page("index.html", "Hobonichi, dot grid and ink restock tracker",
                f"Live stock at {N_STORES} shops: Hobonichi Techo 2027, flagship dot grid journals and limited-edition inks, plus free restock emails for all three trackers.",
                body, ld=(site_ld, faq_ld))

def build_hobonichi():
    body = """
<article class="prose guide">
""" + crumbs(("guides/", "Guides"), ("hobonichi-2027/", "2027 calendar")) + eyebrow("Guide", "Hobonichi Techo 2027", guide_updated(build_hobonichi)) + """
<h1>Hobonichi Techo 2027 launch &amp; restock calendar</h1>
<p class="lede">Hobonichi sells its planners in two big drops a year, and popular covers can sell out within minutes. Here's how the 2027 season has gone so far and when stock usually comes back.</p>
""" + signup() + """

<h2 class="sr">2027 timeline</h2>
<ol class="timeline">
  <li><time>Aug 25, 2026</time><div><h3 class="tl">Previews go up</h3><p>Shops post the 2027 lineup as "out of stock" or "coming soon" pages. They aren't sold out; they're just not on sale yet. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Aug 31, 2026 · 10 PM ET</time><div><h3 class="tl">Official online launch (January-start planners)</h3><p>September 1, 2026 at 11:00 AM Japan time (August 31, 2026 at 10:00 PM ET / 9:00 PM CT) is the official Hobonichi Store's online launch time <a href="#s-1101">[Hobonichi]</a> <a href="#s-faq-release">[Hobonichi, release time]</a>. Indie shops split online and in-store times. Hobonichi's FAQ says each retail store opens at its own store hours <a href="#s-faq-schedule">[Hobonichi, sale schedule]</a>.<br>Paper Mouse opened online Aug 31 at 10 PM ET and in-store Sep 1 at 11 AM ET <a href="#s-papermouse">[Paper Mouse]</a>.<br>Atlas opened online Aug 31 at 9 PM CT, with retail expected the week of September 7. Atlas warned that popular styles and collaborations "often sell out within minutes." <a href="#s-atlas">[Atlas]</a></p></div></li>
  <li><time>Sep 30 – Oct 1, 2026</time><div><h3 class="tl">Second fall wave</h3><p>Hobonichi notes that some products begin sales on October 1 <a href="#s-1101">[Hobonichi]</a>.<br>One Piece sales began October 1, 2026 at 11:00 AM Japan time (September 30, 2026 at 10:00 PM ET). One Piece 2027 editions are January-start and Monday-start only <a href="#s-hon">[Hobonichi]</a>.<br>Paper Mouse, a US shop, listed the Weeksdays 2027 desk calendar in this wave, plus a large restock of earlier sell-outs (as preorders at some shops) <a href="#s-papermouse">[Paper Mouse]</a>.</p></div></li>
  <li><time>Early–mid Oct 2026</time><div><h3 class="tl">First restocks land at indie shops</h3><p>Atlas expected its first restock in early October. Paper Mouse's shipment arrived October 15 and preorders began shipping. <a href="#s-atlas">[Atlas]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Feb 1, 2027</time><div><h3 class="tl">Spring launch (April-start planners)</h3><p>The official Hobonichi Store launches April-start planners on February 1, 2027 at 11:00 AM Japan time (January 31, 2027 at 9:00 PM ET) <a href="#s-1101">[Hobonichi]</a>. Other shops start at their own opening hours. Hobonichi has not published the Spring 2027 cover and book lineup yet.</p></div></li>
</ol>

<h2>Which 2027 books have an April-start</h2>
<p>April-start is only available for the Japanese Original (A6), the Japanese Cousin (A5), and the Japanese Weeks <a href="#s-faq-april">[Hobonichi]</a> <a href="#s-hon">[Hobonichi]</a>.</p>
<p>These do not come in an April-start edition:</p>
<ul>
  <li>English Original, Cousin, and Weeks</li>
  <li>the Planner</li>
  <li>Avec</li>
  <li>Weeks Mega (English and Japanese)</li>
  <li>HON (Japanese and English, A6 and A5)</li>
  <li>One Piece Original</li>
  <li>Moomin Weeks Japanese Special Edition</li>
  <li>Day-Free</li>
  <li>5-Year and Large 5-Year</li>
</ul>
<p>Many January-start products return for April-start. Sold-out January-start items may be restocked for the April-start launch, some items are April-only, and fabric availability can change the lineup <a href="#s-faq-spring">[Hobonichi]</a>. Choosing between the two: <a href="hobonichi-january-start-vs-april-start/">January-start vs April-start</a>.</p>

<h2>Will it come back?</h2>
<p>Usually, but not always. While some standard planners and accessories may be replenished, special or limited collaborations may only be available during the initial launch <a href="#s-atlas">[Atlas]</a>. Paper Mouse says almost every item has been restocked at least once after launch in past years <a href="#s-papermouse">[Paper Mouse]</a>.</p>
<p>Hobonichi posts restock decisions on each product page. "If there is no notice, a restock has not been decided or is under consideration" <a href="#s-faq-restock">[Hobonichi]</a>. Restock notification emails apply only to Techo books and Drawer Pouches, not accessories or stationery, and they do not guarantee a purchase <a href="#s-faq-restock">[Hobonichi]</a>.</p>
<p>Sold-out official Hobonichi Store rows on our <a href=\"""" + HOBO_TRACKER + """#tracker">tracker</a> show that product-page note directly: "Official store notes a restock is planned," "Restock undecided at official store," or "Sales ended at official store."</p>

<section class="card" id="ordering-direct">
  <h2>Ordering direct from Hobonichi (1101.com)</h2>
  <ul>
    <li>Normal dispatch is 1–3 business days, and up to 10 business days after a new release. Restocked items may take longer. Check the product page <a href="#s-1101">[Hobonichi]</a>.</li>
    <li>Combined orders ship together once the latest item is ready <a href="#s-1101">[Hobonichi]</a>.</li>
    <li>International orders ship from Japan via FedEx. Customs and import fees vary by country, and Hobonichi cannot estimate them in advance <a href="#s-1101">[Hobonichi]</a>.</li>
    <li>The 2027 store-exclusive bonus is a Plain Old Acorn Charm and a 3-Color Jetstream Ballpoint Pen. It comes with an eligible Techo book bought from the official Hobonichi Store website or an official Hobonichi physical store (Tokyo Station Branch, Tobichi Tokyo/Kyoto, Hobono Eki AKAGI), while supplies last. Cover-only purchases and Avec Book 2 alone do not qualify <a href="#s-hon">[Hobonichi]</a>.</li>
  </ul>
</section>

<h2>How to not miss it</h2>
<ul>
  <li>Check several shops. When one store sells out, another often still has stock. That's the whole point of the <a href=\"""" + HOBO_TRACKER + """#tracker">tracker</a>.</li>
  <li>Live stock by product: """ + " · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS if not g.get("aux")) + """.</li>
  <li>Want the 2027 store-exclusive bonus? Check eligibility, shipping times, and customs notes in <a href="#ordering-direct">Ordering direct from Hobonichi</a> above.</li>
  <li>Which shops have it right now: <a href="where-to-buy-hobonichi-2027/">where to buy the Hobonichi Techo 2027</a>. Choosing a size: <a href="hobonichi-techo-vs-cousin-vs-weeks/">Techo vs Cousin vs Weeks</a>.</li>
  <li><a href="#alerts">Sign up for alerts</a> (above) for free restock emails for Hobonichi, dot grid journals and limited-edition inks. You can unsubscribe anytime.</li>
</ul>

<h2>Sources</h2>
<ol class="sources">
  <li id="s-1101"><a href="https://www.1101.com/store/techo/en/2027/pc/shopping_guide/" rel="noopener" target="_blank">Hobonichi Techo 2027 shopping guide</a>, Hobonichi (official). Official online launch time, the February 1, 2027 Spring launch, and shipping.</li>
  <li id="s-hon"><a href="https://www.1101.com/store/techo/en/magazine/hon/" rel="noopener" target="_blank">Hobonichi 2027 lineup page</a>, Hobonichi (official). One Piece sale time, which books have an April-start, and the store-exclusive bonus.</li>
  <li id="s-faq-april"><a href="https://www.1101.com/store/techo/en/faq/articles/4889929315230.html" rel="noopener" target="_blank">April-start editions</a>, Hobonichi FAQ (official). Which 2027 books come in April-start.</li>
  <li id="s-faq-spring"><a href="https://www.1101.com/store/techo/en/faq/articles/4889951964190.html" rel="noopener" target="_blank">Spring lineup guidance</a>, Hobonichi FAQ (official). How April-start overlaps with sold-out January-start items.</li>
  <li id="s-faq-restock"><a href="https://www.1101.com/store/techo/en/faq/articles/4889935437854.html" rel="noopener" target="_blank">Restock notices</a>, Hobonichi FAQ (official). Product-page restock decisions, and which items restock emails cover.</li>
  <li id="s-faq-release"><a href="https://www.1101.com/store/techo/en/faq/articles/4889938317854.html" rel="noopener" target="_blank">Official store release time</a>, Hobonichi FAQ (official). The 11:00 AM Japan time official Hobonichi Store online release time.</li>
  <li id="s-faq-schedule"><a href="https://www.1101.com/store/techo/en/faq/articles/4889935445534.html" rel="noopener" target="_blank">Sale schedule</a>, Hobonichi FAQ (official). The annual February 1 April-start schedule, and each retail store opening at its own hours.</li>
  <li id="s-papermouse"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Online and in-store launch times, the Weeksdays 2027 desk calendar, the October 15 arrival, and restock history.</li>
  <li id="s-atlas"><a href="https://www.atlasstationers.com/blogs/news/hobonichi-faq-2027" rel="noopener" target="_blank">Hobonichi FAQ – 2027</a>, Atlas Stationers. Online launch time, retail expected the week of September 7, sell-out warning, the early-October restock, and which standard planners and accessories may be replenished.</li>
</ol>
""" + design_links_block() + related_block("hobonichi-2027/") + """
</article>"""
    return page("hobonichi-2027/", "Hobonichi Techo 2027 launch & restock calendar · Stationery Drop Watch",
                "When Hobonichi Techo 2027 planners launch, sell out and restock: launch times, the October wave, and when restocks usually land, with sources.",
                body, ld=(crumbs_ld(("guides/", "Guides"), ("hobonichi-2027/", "2027 calendar")),))

def related_block(current):
    """Same closing card on every guide: the other guides, then the live restock pages."""
    others = "".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in GUIDES if h != current)
    pages = " · ".join(f'<a href="{g["slug"]}/">{E(g["short"])}</a>' for g in GROUPS if not g.get("aux"))
    return f"""<section class="card related" aria-label="More guides and restock pages">
  <h2>More guides</h2>
  <ul>{others}</ul>
  <p class="small">Live stock: <a href="{HOBO_TRACKER}">Hobonichi tracker</a> · {pages}</p>
</section>"""

def build_privacy():
    fname = "privacy/"
    body = f"""
<article class="prose">
{crumbs((fname, "Privacy"))}
{eyebrow("Privacy", "updated Nov 22, 2026")}
<h1>Privacy</h1>
<p class="lede">What this site collects, who handles it, and how to reach us. In short: your email address if you sign up for alerts, plus page-view and performance statistics from Cloudflare Web Analytics. The site sets no cookies and runs no ad trackers.</p>
<h2>Email alerts (Kit)</h2>
<p>If you sign up for restock alerts, your email address and the trackers you pick (Hobonichi, dot grid journals, limited-edition inks) go to <a href="https://kit.com" target="_blank" rel="noopener">Kit</a>, the service that stores the list and sends the emails. Kit sends a confirmation email first; we only add the address to the list after you click the link. We use it only to send restock alerts for the trackers you chose and occasional site updates. Every email has an unsubscribe link, and you can also email us to be removed. Kit's own privacy policy is at <a href="https://kit.com/privacy" target="_blank" rel="noopener">kit.com/privacy</a>.</p>
<p>Before November 22, 2026, signups went to <a href="https://buttondown.com" target="_blank" rel="noopener">Buttondown</a>, our previous email service. While we finish moving to Kit, readers who joined through Buttondown also get Hobonichi and dot grid alerts from Buttondown through December 7, 2026. From December 8, alerts go out through Kit only. Buttondown's privacy policy is at <a href="https://buttondown.com/legal/privacy" target="_blank" rel="noopener">buttondown.com/legal/privacy</a>.</p>
<p>The signup form is protected from bots by <a href="https://www.cloudflare.com/application-services/products/turnstile/" target="_blank" rel="noopener">Cloudflare Turnstile</a>, an anti-spam check. On pages with the form, your browser loads a script from Cloudflare (challenges.cloudflare.com) and, when you submit, sends Cloudflare a token that we verify on our server. Cloudflare may look at things like your IP address and browser details to tell people from bots, and may use browser storage for that, under <a href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener">its privacy policy</a>. The form goes through our own server at stationerydropwatch.com/api/subscribe, which passes your email address and chosen trackers to Kit and doesn't store them itself.</p>
<h2>Hosting</h2>
<p>The site is hosted on Cloudflare Pages. Cloudflare handles standard request data, such as your IP address, to deliver and protect the site. See <a href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener">Cloudflare's privacy policy</a>.</p>
<p>The site uses <a href="https://www.cloudflare.com/web-analytics/" target="_blank" rel="noopener">Cloudflare Web Analytics</a>, a privacy-focused analytics service from our host, Cloudflare. It loads a small script (beacon.min.js from static.cloudflareinsights.com) that counts page views and measures how pages perform. The statistics we can see include pages visited, referrer, browser and device type, country, and load times. Cloudflare says Web Analytics collects the minimum information needed to show how a site performs and does not track individual end users across its customers' Internet properties.</p>
<p>The source code, the checker, and a backup copy of the site are hosted on GitHub (GitHub Pages).</p>
<p>This site doesn't set its own cookies and doesn't run ad trackers.</p>
<h2>Links to other sites</h2>
<p>When you follow a link to a shop we track, or to Amazon, Etsy, or Teachers Pay Teachers for our own planners, journals, and printables, that site has its own privacy policy. This site doesn't set cookies to credit those visits.</p>
<h2>Contact</h2>
<p>Questions, or want your email address removed? Email {mailto_email()}.</p>
</article>"""
    return page(fname, "Privacy", "How Stationery Drop Watch handles email signups, plus page-view stats from Cloudflare Web Analytics. No cookies set by the site, no ad trackers.", body, ld=(crumbs_ld((fname, "Privacy")),))

def build_about():
    n_checked = N_STORES  # same count as the FAQ and footer: shops the checker actually checks
    body = f"""
<article class="prose">
{crumbs(("about/", "About"))}
{eyebrow("About", "how we check stock")}
<h1>About Stationery Drop Watch</h1>
<p class="lede">Limited planners sell out fast, and every shop only posts its own restocks. This site checks them all in one place.</p>
<p>{independent_note()}</p>
{signup()}
<section class="couple" aria-labelledby="couple-h">
<h2 id="couple-h">The couple behind Drop Watch</h2>
<p>Drop Watch is run by Andrew Robinson. He built the tracker after seeing how frustrating it was for his partner, Arden, to keep up with planner restocks, and now they run it together. Stationery Drop Watch is built in Hamtramck, Michigan.</p>
</section>
<h2>How it works</h2>
<p>A small script visits the public product pages of {n_checked} stores {CHECK_FREQ}, at a polite pace and following each store's robots.txt. It reads whether each listing can be bought right now. On a sold-out Hobonichi Store row, a short note passes on what Hobonichi's own store data says: a restock is planned, a restock is undecided, or sales have ended. Each brand family has its own section, never mixed: the <a href="{HOBO_TRACKER}">Hobonichi tracker</a> (the official store and independent shops){"".join(f', <a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["name"])}</a> ({E(shop_names(k))})' for k in LIVE)}{f', and <a href="{INK_SLUG}/">limited-edition fountain pen inks</a> (Diamine and Sailor, only at shops on each brand\'s own dealer list)' if INK_LIVE else ''}. When a sold-out Hobonichi or dot grid listing becomes available again, it shows up in <a href="index.html#restocked">Recent restocks</a>. Restocks from all three trackers (Hobonichi, dot grid journals and limited-edition inks) also go out by email to the people who picked that tracker. Ink restocks show on the inks page.</p>
<p>We only show what the stores report. If a check fails, we say so instead of guessing.</p>
<h2>Contact</h2>
<p>Questions, corrections, or a shop we should track? Email {mailto_email()}. The <a href="contact/">contact page</a> is there too.</p>
</article>"""
    org_ld = {"@context": "https://schema.org", **organization()}
    return page("about/", "About Stationery Drop Watch: how we check stock", f"How Stationery Drop Watch checks {n_checked} shops for Hobonichi planner, dot grid and limited-edition ink restocks. A failed check is never shown as a guess.", body, ld=(crumbs_ld(("about/", "About")), org_ld))

def build_contact():
    """Visible contact page. The address is a mailto link, wrapped so Cloudflare Email Obfuscation leaves it alone.
    The independent-site note is in the footer, so the body doesn't repeat it."""
    fname = "contact/"
    shown = mailto_email()
    body = f"""
<article class="prose">
{crumbs((fname, "Contact"))}
{eyebrow("Contact", "Stationery Drop Watch")}
<h1>Contact</h1>
<p class="lede">Stationery Drop Watch checks planner, journal and limited-edition ink stock at official stores and independent shops, and writes down what each shop last reported.</p>
<p>Andrew Robinson runs the site and can be reached at {shown}. Questions, corrections, or a shop we should track are welcome.</p>
<p class="small"><a href="about/">About</a> explains how the checks work. <a href="privacy/">Privacy</a> explains the email list.</p>
</article>"""
    desc = ("How to reach Stationery Drop Watch with questions, corrections, or a shop to add to the stock trackers. "
            "Email us at the address on this page.")
    return fname, page(fname, "Contact", desc, body, ld=(crumbs_ld((fname, "Contact")),))

# --- Product restock pages (one indexable page per tracked product group) ---------------------
# Every status on these pages comes from data/stock.json exactly as the checker wrote it.
def _is_a6_book(p):
    return p.get("canonical") in ("original-a6-en", "original-a6-jp", "original-a6-jp-one-piece") or (
        p["type"] == "Book" and not p.get("canonical") and "a6" in p["label"].lower()
        and "planner book" not in p["label"].lower())

GROUPS = [
    dict(slug="hobonichi-techo-2027-original-a6", short="Original A6", product="Hobonichi Techo 2027 Original (A6)",
         match=_is_a6_book,
         desc="Is the Hobonichi Original A6 in stock? Live status for the English and Japanese books at {shops} shops, with a link to each shop's listing.",
         intro="The Original is Hobonichi's A6 one-page-a-day book, sold in an English and a Japanese edition. "
               "Below is what each shop we track reported at its last check: in stock, on preorder, sold out, or not on sale yet. "
               "If a check failed we say \"Couldn't check\" rather than guess."),
    dict(slug="hobonichi-techo-2027-planner-a6", short="Planner A6", product="Hobonichi Techo 2027 Planner (A6)",
         match=lambda p: p.get("canonical") == "planner-a6-en",
         desc="Is the Hobonichi Planner A6 in stock? Live status for the English Planner Book at {nshops}, with a link to each shop's listing. See each shop's page.",
         intro="The Planner is Hobonichi's English-language A6 one-page-a-day book, with a January start and Monday-start weeks. "
               "Hobonichi lists it as a separate line from the Original book (English Planner Book on the official store). "
               "Below is what each shop we track reported at its last check: in stock, on preorder, sold out, or not on sale yet. "
               "If a check failed we say \"Couldn't check\" rather than guess."),
    dict(slug="hobonichi-techo-2027-cousin-a5", short="Cousin A5", product="Hobonichi Techo 2027 Cousin (A5)",
         match=lambda p: p.get("canonical") in ("cousin-a5-en", "cousin-avec-a5-jp"),
         desc="Is the Hobonichi Cousin A5 in stock? Live status for the English Cousin and the Japanese Avec set at {shops} shops, with every restock we spot.",
         intro="The Cousin is the A5 version of the Techo, with a page a day and more room to write. "
               "Here's what each shop we track reported for the English Cousin and for the Japanese Cousin Avec, the two-book set with January to June and July to December, at its last check."),
    dict(slug="hobonichi-weeks-2027", short="Weeks", product="Hobonichi Weeks 2027",
         match=lambda p: p["type"] == "Weeks",
         desc="Is Hobonichi Weeks 2027 in stock? Live status for Midnight Blue, Canaria Yellow, tanakadaisuke: Starlight and more at {shops} shops. Check each shop's page.",
         intro="Weeks is Hobonichi's slim, wallet-size weekly planner, and the popular covers sell out fast. "
               "These are the 2027 Weeks listings we track, grouped by design, with the status each shop reported at its last check."),
    dict(slug="hobonichi-weeks-mega-2027", short="Weeks Mega", product="Hobonichi Weeks Mega 2027",
         match=lambda p: p["type"] == "Weeks Mega",
         desc="Is Hobonichi Weeks Mega 2027 in stock? Live status for each tracked design at {shops} shops, with a link to every shop's listing. Check each shop's page.",
         intro="Weeks Mega is the Weeks planner with extra blank pages at the back. "
               "Here's what each shop we track reported for the 2027 Weeks Mega listings at its last check."),
    dict(slug="hobonichi-techo-2027-hon", short="HON", product="Hobonichi Techo 2027 HON",
         match=lambda p: p["type"] == "HON",
         desc="Is the Hobonichi Techo 2027 HON in stock? Live status for each tracked A5 and A6 HON book at {shops} shops, with a link to each listing. Check each shop's page.",
         intro="The HON is Hobonichi's book with the cover attached. Slash (Navy) and Bow & Tie: Sheep Sheep Sheep are tracked here in A5 and in A6. "
               "Hobonichi's own page for each size includes the English and Japanese books. "
               "A shop row names the language that shop sells."),
    dict(slug="hobonichi-techo-2027-covers", short="Covers", product="Hobonichi Techo 2027 cover",
         match=lambda p: p["type"] == "Cover",
         desc="Are Hobonichi Techo 2027 covers in stock? Live status for the tracked A6 and A5 covers at {shops} shops, with a link to each listing. Check each shop's page.",
         intro="Popular Hobonichi covers can sell out within minutes of a drop. "
               "We track the covers that sold best in Hobonichi's first-week overseas ranking, plus more: A6 covers for the Original and A5 covers for the Cousin. Weeks covers are on the Weeks page. "
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
         # The Archer and Olive page keeps the old URL (AO_SLUG) and links back here.
         # The title, heading, nav, and breadcrumb name every maker we check.
         title=f"Dot grid journal restock tracker: {dotgrid_brand_names()}",
         desc=dotgrid_meta_desc(),
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Popular dot grid journals and limited editions sell out, and every brand only posts its own restocks. "
               f"We track a focused set of flagship dot grid notebooks from {dotgrid_brand_names()}, size by size and color by color, plus Archer and Olive's dot grid refills. {dotgrid_where_checked()} "
               "This page covers those dot grid notebooks and refills, not pens or other paper, and Hobonichi and our other sections have their own pages."),
    # Archer and Olive only. Keeps the old tracker URL, links to the four-brand tracker (DOTGRID_SLUG).
    dict(slug=AO_SLUG, short="Archer and Olive", product="Archer and Olive dot grid journal", section="dotgrid", aux=True,
         parent=DOTGRID_SLUG, seo_title="Archer and Olive dot grid journal restock tracker",
         match=lambda p: is_dotgrid(p) and (p["store_id"] == "archerolive" or (p.get("canonical") or "").startswith("ao-")),
         search_hint="Ice Castle, Stag, refill…",
         eyebrow="Archer and Olive", unit="listings",
         open_hint="Open a row to go straight to that exact size and color on the Archer and Olive store",
         guide_q="Do Archer and Olive sizes and colors sell out on their own?",
         guide="Archer and Olive dot grid notebooks come in several sizes and colors, and each one sells out on its own. "
               "We check the exact variant named in each row, so \"In stock\" means that size and color, not just some version of the design. "
               "To compare paper weight, pages and size across the four brands, see <a href=\"best-dot-grid-journals/\">best dot grid journals compared</a>.",
         title="Archer and Olive dot grid journal restock tracker",
         desc="Are Archer and Olive dot grid notebooks and refills in stock? Live status for each design, size and color, checked on the Archer and Olive store itself.",
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Archer and Olive designs and limited editions sell out, and each size and color goes on its own. "
               "This page tracks Archer and Olive's dot grid notebooks and dot grid refills on the Archer and Olive store, size by size and color by color.",
         after_lede=lambda: f'<p class="small">Looking for Leuchtturm1917, Scribbles That Matter or Notebook Therapy too? '
                            f'See the <a href="{DOTGRID_SLUG}/">dot grid journal restock tracker</a>, which covers all four brands.</p>'),
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

def status_rows(ls, oe=None):
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4}
    rows = []
    for l in sorted(ls, key=lambda l: (order.get(l["status"], 9), l["store"])):
        since = l.get("status_since")
        since_html = f'<span class="sub">since {time_tag(since)}</span>' if since and l["status"] != "unknown" else ""
        note = official_note(l)
        if note:
            since_html += f'<span class="sub official-note">{E(note)}</span>'
        rows.append(f"""<tr data-store="{E(l['store_id'])}" data-status="{E(l['status'])}" data-size="{E(listing_size(l))}" data-lang="{E(listing_language(l))}" data-country="{E(REGION.get(l['store_id'], ''))}"><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a>{region_tag(l['store_id'])}<span class="sub">{E(l.get('title') or l['label'])}</span></td>
  <td><span class="badge {E(l['status'])}">{E(STATUS[l['status']])}</span>{since_html}</td></tr>""")
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
    country_label = country_filter_label((sid for sid, _ in seen), 'data-filter="country"')
    return f"""<form class="filters page-filter card-filter" id="filters" role="search" aria-label="Filters" onsubmit="return false">
      <details class="filter-more" open>
        <summary>Filters</summary>
        <div class="filter-fields">
          {size_label}
          {lang_label}
          <label>Store<select data-filter="store"><option value="">All stores</option>{store_opts}</select></label>
          {country_label}
          <label>Status<select data-filter="status"><option value="">Any status</option>{status_opts}</select></label>
        </div>
      </details>
      <label class="grow">Search<input data-filter="q" type="search" placeholder="Search design or shop…" aria-label="Search design or shop, for example {E(hint.rstrip("…"))}" autocomplete="off"></label>
      <button type="button" class="filter-reset" data-filter="reset">Reset</button>
      {group_toggle_html()}
    </form>
    {lang_note}"""

def group_seo_title(g):
    """Short document title. The visible H1 stays the longer product name."""
    sec = g_sec(g)
    if g.get("seo_title"):
        return g["seo_title"]
    if sec == "dotgrid":
        return "Dot grid journal tracker"
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
    }.get(parent_slug, "stock")

def design_seo_title(d):
    return f'{d["name"]} · {design_family(d["parent"])} stock'

def design_seo_desc(d, shops):
    word = "shop" if shops == 1 else "shops"
    fam = design_family(d["parent"])
    head = f'Is {d["name"]} in stock? Live {fam} status at {shops} {word}'
    # Longest wording first. The first complete sentence pair that fits DESC_LIMIT is used.
    cores = (f"{head}, with a link to each shop's listing.", f"{head}, with a link to each listing.", f"{head}.")
    extras = (" Open the shop's page to confirm before you buy. Stock can change.",
              " Open the shop page to confirm this exact listing now.",
              " Confirm it on the shop's own page.",
              " Confirm before you buy.", "")
    for core in cores:
        for extra in extras:
            if len(core + extra) <= DESC_LIMIT:
                return core + extra
    return cores[-1]

def group_signup(g, buy, placement="top"):
    """Section, product and design trackers use a brand-level label, never a single item."""
    return signup_for(section=g_sec(g), placement=placement)

def build_group(g, oe=None):
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
  {sold_html}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(sl)}</tbody>
  </table></div>
  <p class="muted small">{g.get('open_hint', "Open a shop's name to go straight to its listing")}{tracker}{dp_link}</p>
  {"" if any("region-legend" in x for x in parts) else region_legend(l["store_id"] for l in ls)}
</section></details>""")
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and is_restock_event(c)],
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
{crumbs(*hub_trail(g), (g["slug"] + "/", g["short"]))}
<section class="hero{' hero-compact' if not ext or g.get('parent') else ''}">
  {eyebrow(g.get('eyebrow', 'Hobonichi Techo 2027'), nshops(shops), f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}") if ext and not g.get("parent") else eyebrow(g.get('eyebrow', 'Hobonichi Techo 2027'), nshops(shops), f"checked {CHECK_FREQ}")}
  <h1>{E(g['h1'])}</h1>
  <p class="lede">{E(g['intro'])}</p>
  {g["after_lede"]() if g.get("after_lede") else ""}
  {hero_facts(ls)}
  {group_signup(g, buy)}
  {also_tracked(g["slug"] + "/") if ext and not g.get("parent") else ""}
</section>
<div class="layout solo">
  <div class="main-col">
    <section class="card"><h2>Recent restocks</h2>{restock_html}</section>
    <div id="tracker"{' class="card-filtered"' if ext else ''}>
    {design_nav}{shop_nav}{card_filter or group_toggle_html()}{''.join(parts)}
    <p class="muted small card-empty" hidden>Nothing on this page matches those filters.</p>
    </div>
    {dg_tracker}{lines_grid_card() if g.get("slug") == "hobonichi-weeks-2027" else ""}
    {faq_html}
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {"" if ext else guides_block()}
  </div>
</div>
{group_signup(g, buy, placement="bottom")}
</div>"""
    fname = g["slug"] + "/"
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": g["h1"] + ": listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: (l.get("canonical") or "~", l["store"])))]}
    title = group_seo_title(g)
    return fname, page(fname, title, g["desc"].format(shops=shops, nshops=nshops(shops)), body, ld=(crumbs_ld(*hub_trail(g), (fname, g["short"])), items, faq_ld),
                       og_image=g.get("og_image", OG_IMAGE), og_alt=g.get("og_alt", OG_ALT))

def group_lastmod(g):
    ls = group_listings(g)
    return latest(*[l.get("status_since") for l in ls], *[l.get("first_seen") for l in ls], CONTENT_LASTMOD)

# FIX-09: one indexable page per high-demand design, nested under its book-type restock page
# (e.g. /hobonichi-weeks-2027/midnight-blue/). Same template pieces and SEO pattern as the restock pages.
# Picked from data/stock.json on 2026-11-04; "why" records the reason each design got a page.
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
    # --- Round 3: one page per tracked planner or journal design. Facts come from the shops' own listing titles in data/stock.json.
    dict(parent="hobonichi-techo-2027-original-a6", slug="one-piece-edition", name="One Piece Edition", full="Hobonichi Techo 2027 One Piece Edition",
         match=lambda p: p.get("canonical") == "original-a6-jp-one-piece" or (p["type"] == "Book" and "one piece edition" in p["label"].lower())),
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
    dict(parent="hobonichi-weeks-2027", slug="once-in-spring", name="Akiko Miyakoshi: Once, in Spring", full="Hobonichi Weeks 2027 Akiko Miyakoshi Once, in Spring",
         match=lambda p: p.get("canonical") == "weeks-once-in-spring",
         why="Regular 2027 Weeks hardcover book, January start, Monday start. The official listing includes English and Japanese. The other matched shops sell the English book."),
    dict(parent="hobonichi-weeks-2027", slug="meteor-shower-in-the-light-blue-forest", name="Meteor Shower in the Light Blue Forest", full="Hobonichi Weeks 2027 Hiroko Kubota Meteor Shower in the Light Blue Forest",
         match=lambda p: p.get("canonical") == "weeks-meteor-shower",
         why="Regular 2027 Weeks hardcover book, January start, Monday start. The official listing includes English and Japanese. The other matched shops sell the English book."),
    dict(parent="hobonichi-weeks-2027", slug="nothing-to-hide-yellow", name="beautiful people: Nothing to Hide (Yellow)", full="Hobonichi Weeks 2027 cover beautiful people Nothing to Hide (Yellow)",
         match=lambda p: p.get("canonical") == "weeks-beautiful-people-yellow",
         why="A cover for the Weeks book, not the Weeks book itself and not a Weeks Mega."),
    dict(parent="hobonichi-techo-2027-hon", slug="a5-slash-navy", name="A5 Slash (Navy)", full="Hobonichi HON 2027 A5 Slash (Navy)",
         match=lambda p: p.get("canonical") == "hon-a5-slash-navy" or p.get("url") == "https://omoionline.com/products/hobonichi-techo-2027-hon-a5-slash-planner-navy"),
    dict(parent="hobonichi-techo-2027-hon", slug="a6-slash-navy", name="A6 Slash (Navy)", full="Hobonichi HON 2027 A6 Slash (Navy)",
         match=lambda p: p.get("canonical") == "hon-a6-slash-navy" or p.get("url") == "https://omoionline.com/products/hobonichi-techo-2027-hon-a6-slash-planner-navy"),
    dict(parent="hobonichi-techo-2027-hon", slug="a5-sheep-sheep-sheep", name="A5 Bow & Tie: Sheep Sheep Sheep", full="Hobonichi HON 2027 A5 Bow & Tie: Sheep Sheep Sheep",
         match=lambda p: p.get("canonical") == "hon-a5-sheep",
         why="2027 HON book, daily pages, January start, Monday start. The official listing includes English and Japanese. Retailer rows here are the English book, except as noted."),
    dict(parent="hobonichi-techo-2027-hon", slug="a6-sheep-sheep-sheep", name="A6 Bow & Tie: Sheep Sheep Sheep", full="Hobonichi HON 2027 A6 Bow & Tie: Sheep Sheep Sheep",
         match=lambda p: p.get("canonical") == "hon-a6-sheep",
         why="2027 HON book, daily pages, January start, Monday start. The official listing includes English and Japanese. Pen Boutique has a separate Japanese-book listing."),
    dict(parent="hobonichi-weeks-2027", slug="bow-tie-sheep-sheep-sheep", name="Bow & Tie: Sheep Sheep Sheep", full="Hobonichi Weeks 2027 Bow & Tie: Sheep Sheep Sheep",
         match=lambda p: p.get("canonical") == "weeks-sheep",
         why="2027 Weeks hardcover book in the Bow & Tie series, January start, Monday start. The official listing includes English and Japanese. The other matched shops sell the English book."),
    dict(parent="hobonichi-weeks-mega-2027", slug="bow-tie-sheep-sheep-sheep", name="Bow & Tie: Sheep Sheep Sheep", full="Hobonichi Weeks Mega 2027 Bow & Tie: Sheep Sheep Sheep",
         match=lambda p: p.get("canonical") == "weeks-mega-sheep",
         why="2027 Weeks Mega hardcover book in the Bow & Tie series, with extra grid pages. The official listing includes English and Japanese. The other matched shops sell the English book."),
    dict(parent="hobonichi-weeks-2027", slug="leather-forest-green", name="Leather: Forest Green", full="Hobonichi Weeks 2027 Leather: Forest Green",
         match=lambda p: p.get("canonical") == "weeks-leather-forest",
         why="2027 Weeks hardcover book in the Leather series, cow hide in Forest Green, January start, Monday start. The official listing includes English and Japanese. The other matched shops sell the English book."),
    dict(parent="hobonichi-techo-2027-covers", slug="moomin-my-yard", name="Moomin: My Yard", full="Hobonichi Techo 2027 A6 cover Moomin: My Yard",
         match=lambda p: p.get("canonical") == "cover-a6-moomin"),
    dict(parent="hobonichi-techo-2027-covers", slug="white-cat-house", name="Yumi Kitagishi: White Cat House", full="Hobonichi Techo 2027 A6 cover White Cat House",
         match=lambda p: p.get("canonical") == "cover-a6-white-cat-house"),
    dict(parent="hobonichi-techo-2027-covers", slug="nothing-to-hide-green", name="beautiful people: Nothing to Hide (Green)", full="Hobonichi Techo 2027 A6 cover beautiful people Nothing to Hide (Green)",
         match=lambda p: p.get("canonical") == "cover-a6-beautiful-people-green"),
    dict(parent="hobonichi-techo-2027-covers", slug="nothing-to-hide-pink", name="beautiful people: Nothing to Hide (Pink)", full="Hobonichi Techo 2027 A5 cover beautiful people Nothing to Hide (Pink)",
         match=lambda p: p.get("canonical") == "cover-a5-beautiful-people-pink"),
    dict(parent="hobonichi-techo-2027-covers", slug="akiko-miyakoshi-airport-a6", name="Akiko Miyakoshi: An Airport at Night (A6)", full="Hobonichi Techo 2027 A6 cover Akiko Miyakoshi: An Airport at Night",
         match=lambda p: p.get("canonical") == "cover-a6-akiko-miyakoshi-airport"),
    dict(parent="hobonichi-techo-2027-covers", slug="va-strawberry-thief-a6", name="V&A Series: Strawberry Thief", full="Hobonichi Techo 2027 A6 cover V&A Series: Strawberry Thief",
         match=lambda p: p.get("canonical") == "cover-a6-va-strawberry-thief"),
    dict(parent="hobonichi-techo-2027-covers", slug="puppet-sunsun-wa-a6", name="PUPPET SUNSUN: Wa!", full="Hobonichi Techo 2027 A6 cover PUPPET SUNSUN: Wa!",
         match=lambda p: p.get("canonical") == "cover-a6-puppet-sunsun-wa"),
    dict(parent="hobonichi-techo-2027-covers", slug="yoshie-watanabe-petit-bloom-a6", name="Yoshie Watanabe: Petit Bloom", full="Hobonichi Techo 2027 A6 cover Yoshie Watanabe: Petit Bloom",
         match=lambda p: p.get("canonical") == "cover-a6-yoshie-watanabe-petit-bloom"),
    dict(parent="hobonichi-techo-2027-covers", slug="colors-bordeaux-terracotta-a6", name="Colors: Bordeaux Terracotta", full="Hobonichi Techo 2027 A6 cover Colors: Bordeaux Terracotta",
         match=lambda p: p.get("canonical") == "cover-a6-colors-bordeaux-terracotta"),
    dict(parent="hobonichi-techo-2027-covers", slug="colors-blue-parasol-a6", name="Colors: Blue Parasol", full="Hobonichi Techo 2027 A6 cover Colors: Blue Parasol",
         match=lambda p: p.get("canonical") == "cover-a6-colors-blue-parasol"),
    dict(parent="hobonichi-techo-2027-covers", slug="tanakadaisuke-white-handkerchief-diary-a6", name="tanakadaisuke: White Handkerchief Diary (A6)", full="Hobonichi Techo 2027 A6 cover tanakadaisuke: White Handkerchief Diary",
         match=lambda p: p.get("canonical") == "cover-a6-tanakadaisuke-handkerchief"),
    dict(parent="hobonichi-techo-2027-covers", slug="glow-chianti-a6", name="Glow: Chianti (A6)", full="Hobonichi Techo 2027 A6 cover Glow: Chianti",
         match=lambda p: p.get("canonical") == "cover-a6-glow-chianti"),
    dict(parent="hobonichi-techo-2027-covers", slug="natal-hello-new-day-camo-a6", name="Natal Design: Hello New Day! (Camo)", full="Hobonichi Techo 2027 A6 cover Natal Design: Hello New Day! (Camo)",
         match=lambda p: p.get("canonical") == "cover-a6-natal-hello-new-day-camo"),
    dict(parent="hobonichi-techo-2027-covers", slug="arts-science-wax-coating-kip-a6", name="Arts&Science: Wax Coating Kip", full="Hobonichi Techo 2027 A6 cover Arts&Science: Wax Coating Kip",
         match=lambda p: p.get("canonical") == "cover-a6-arts-science-wax-coating-kip"),
    dict(parent="hobonichi-techo-2027-covers", slug="yumi-kitagishi-white-cat-village-a5", name="Yumi Kitagishi: White Cat Village", full="Hobonichi Techo 2027 A5 cover Yumi Kitagishi: White Cat Village",
         match=lambda p: p.get("canonical") == "cover-a5-yumi-kitagishi-white-cat-village"),
    dict(parent="hobonichi-techo-2027-covers", slug="va-blackthorn-a5", name="V&A Series: Blackthorn", full="Hobonichi Techo 2027 A5 cover V&A Series: Blackthorn",
         match=lambda p: p.get("canonical") == "cover-a5-va-blackthorn"),
    dict(parent="hobonichi-techo-2027-covers", slug="akiko-miyakoshi-airport-a5", name="Akiko Miyakoshi: An Airport at Night (A5)", full="Hobonichi Techo 2027 A5 cover Akiko Miyakoshi: An Airport at Night",
         match=lambda p: p.get("canonical") == "cover-a5-akiko-miyakoshi-airport"),
    dict(parent="hobonichi-techo-2027-covers", slug="puppet-sunsun-s-a5", name="PUPPET SUNSUN: S", full="Hobonichi Techo 2027 A5 cover PUPPET SUNSUN: S",
         match=lambda p: p.get("canonical") == "cover-a5-puppet-sunsun-s"),
    dict(parent="hobonichi-techo-2027-covers", slug="colors-chiffon-greige-a5", name="Colors: Chiffon Greige", full="Hobonichi Techo 2027 A5 cover Colors: Chiffon Greige",
         match=lambda p: p.get("canonical") == "cover-a5-colors-chiffon-greige"),
    dict(parent="hobonichi-techo-2027-covers", slug="colors-misty-cedar-a5", name="Colors: Misty Cedar", full="Hobonichi Techo 2027 A5 cover Colors: Misty Cedar",
         match=lambda p: p.get("canonical") == "cover-a5-colors-misty-cedar"),
    dict(parent="hobonichi-techo-2027-covers", slug="colors-mango-latte-a5", name="Colors: Mango Latte", full="Hobonichi Techo 2027 A5 cover Colors: Mango Latte",
         match=lambda p: p.get("canonical") == "cover-a5-colors-mango-latte"),
    dict(parent="hobonichi-techo-2027-covers", slug="moomin-my-yard-pink-gray-a5", name="Moomin: My Yard (Pink Gray)", full="Hobonichi Techo 2027 A5 cover Moomin: My Yard (Pink Gray)",
         match=lambda p: p.get("canonical") == "cover-a5-moomin-my-yard-pink-gray"),
    dict(parent="hobonichi-techo-2027-covers", slug="mina-perhonen-felice-blue-a5", name="minä perhonen: felice (Blue) (A5)", full="Hobonichi Techo 2027 A5 cover minä perhonen: felice (Blue)",
         match=lambda p: p.get("canonical") == "cover-a5-mina-perhonen-felice-blue"),
    dict(parent="hobonichi-techo-2027-covers", slug="tanakadaisuke-white-handkerchief-diary-a5", name="tanakadaisuke: White Handkerchief Diary (A5)", full="Hobonichi Techo 2027 A5 cover tanakadaisuke: White Handkerchief Diary",
         match=lambda p: p.get("canonical") == "cover-a5-tanakadaisuke-handkerchief"),
    dict(parent="hobonichi-techo-2027-covers", slug="glow-chianti-a5", name="Glow: Chianti (A5)", full="Hobonichi Techo 2027 A5 cover Glow: Chianti",
         match=lambda p: p.get("canonical") == "cover-a5-glow-chianti"),
    dict(parent="hobonichi-weeks-2027", slug="tragen-bitter-plaid-cover", name="Tragen: Bitter Plaid (Weeks cover)", full="Hobonichi Weeks 2027 cover Tragen: Bitter Plaid",
         match=lambda p: p.get("canonical") == "weeks-cover-tragen-bitter-plaid"),
    dict(parent="hobonichi-weeks-2027", slug="alettone-sweets-cover", name="Alettone: Sweets (Weeks cover)", full="Hobonichi Weeks 2027 cover Alettone: Sweets",
         match=lambda p: p.get("canonical") == "weeks-cover-alettone-sweets"),
    dict(parent="hobonichi-weeks-2027", slug="mina-perhonen-felice-blue-weeks-cover", name="minä perhonen: felice (Blue) (Weeks cover)", full="Hobonichi Weeks 2027 cover minä perhonen: felice (Blue)",
         match=lambda p: p.get("canonical") == "weeks-cover-mina-perhonen-felice-blue"),
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
    dict(parent=DOTGRID_SLUG, slug="archer-and-olive-storybook-olive", name="Archer and Olive Storybook in Olive", full="Archer and Olive Storybook in Olive dot grid notebook",
         match=lambda p: p.get("canonical") == "ao-storybook-olive"),
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
]
DESIGNS_LASTMOD = "2026-11-04"

DESIGN_ABOUT = {'hobonichi-weeks-2027/bow-tie-sheep-sheep-sheep': "Bow & Tie: Sheep Sheep Sheep is a design in the Bow & Tie series of the 2027 Weeks hardcover book, January start, Monday start. The cover is necktie-style fabric in green with rows of sheep, and 2027 is the Year of the Sheep. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega and not the HON Sheep Sheep Sheep book.", 'hobonichi-weeks-mega-2027/bow-tie-sheep-sheep-sheep': "Bow & Tie: Sheep Sheep Sheep is a design in the Bow & Tie series of the 2027 Weeks Mega hardcover book, January start, Monday start. Hobonichi lists the Mega with 219 pages of grid paper in the English version (215 in the Japanese), about three times the grid pages of the standard Weeks, and it weighs 180 g and is 15 mm thick. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not the standard Weeks.", 'hobonichi-weeks-2027/leather-forest-green': "Leather: Forest Green is a design in the Leather series of the 2027 Weeks hardcover book, January start, Monday start. The cover is cow hide dyed forest green, with 2027 foil-pressed in gold on the front, a beige and white headband and satin ribbon bookmarks. It ships in a special paper envelope. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'one-piece-edition': 'The One Piece Edition is a Japanese-language Hobonichi Techo 2027 Original book in A6 size, with a page for every day, a January start and Monday-start weeks.', 'hobonichi-weeks-2027/midnight-blue': 'Midnight Blue is a Colors design for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-mega-2027/midnight-blue': 'Midnight Blue is a Colors design for the Hobonichi Weeks Mega 2027 weekly planner.', 'hobonichi-weeks-2027/canaria-yellow': "Canaria Yellow is a Colors design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'hobonichi-weeks-2027/white-cat-wallpaper': 'White Cat Wallpaper is a Yumi Kitagishi artist collaboration for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/moomin-at-the-table': 'Moomin: At the Table is a Moomin collaboration for the Hobonichi Weeks 2027 weekly planner.', 'hobonichi-weeks-2027/starlight': "Starlight is tanakadaisuke's 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega and not a softcover.", 'hobonichi-weeks-mega-2027/candy-dream': 'Bow & Tie: Candy Dream is a design for the Hobonichi Weeks Mega 2027 weekly planner.', 'hobonichi-weeks-2027/sea-glass': "Sea Glass is a Colors design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'hobonichi-weeks-2027/v-and-a': "Welcome to the V&A and Leicester are two separate 2027 Weeks hardcover books, January start, Monday start. Hobonichi's own listings include the English and Japanese books. The other shops on this page sell the English book. A shop that sells both on one page is checked by the named design, not by whether another design on that page is available. Neither design is a Weeks Mega.", 'hobonichi-weeks-2027/pink-sapphire': "Pink Sapphire is a Colors design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega.", 'hobonichi-weeks-2027/paper-series-jade': "Frosty Jade is the English name of this Paper Series Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. One retailer's title shortens the name to Jade; its product search uses the same item code as Frosty Jade. It is not a Weeks Mega and not a cover.", 'hobonichi-weeks-2027/shirt-fabric-graph-plaid': "Graph Plaid is a Shirt Fabric design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. It is not a Weeks Mega and not a cover.", 'hobonichi-weeks-2027/floral-remedy': "Floral Remedy is a Liberty Fabrics design, a 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The checked shops on this page sell the English book. It is not a Weeks cover and not a Weeks Mega. JetPens also lists the English book. JetPens blocks automated checks, so that link is not a stock status and does not send a restock alert.", 'hobonichi-weeks-2027/nothing-to-hide-yellow': "Nothing to Hide (Yellow) is a beautiful people cover for the 2027 Weeks book, cover only, JAN 4580812710121. Hobonichi's listing is that Weeks cover. It is not the Weeks planner itself, not a Weeks Mega, and not the A6 green or A5 pink covers.", 'hobonichi-techo-2027-hon/a5-slash-navy': "Slash (Navy) in A5 is a 2027 HON book, daily pages, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. It is not the A6 HON and not a cover.", 'hobonichi-techo-2027-hon/a6-slash-navy': "Slash (Navy) in A6 is a 2027 HON book, daily pages, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. Pen Boutique has a separate Japanese-book listing. The other checked shops sell the English book. It is not the A5 HON and not a cover.", 'hobonichi-techo-2027-hon/a5-sheep-sheep-sheep': "Bow & Tie: Sheep Sheep Sheep in A5 is a 2027 HON book, daily pages, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other checked shops sell the English book. It is not the A6 HON, not the Weeks Sheep Sheep Sheep book, and not a cover.", 'hobonichi-techo-2027-hon/a6-sheep-sheep-sheep': "Bow & Tie: Sheep Sheep Sheep in A6 is a 2027 HON book, daily pages, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. Pen Boutique has a separate Japanese-book listing. The other checked shops sell the English book. It is not the A5 HON, not the Weeks Sheep Sheep Sheep book, and not a cover.", 'hobonichi-weeks-2027/once-in-spring': "Once, in Spring is Akiko Miyakoshi's 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega and not a cover.", 'hobonichi-weeks-2027/meteor-shower-in-the-light-blue-forest': "Meteor Shower in the Light Blue Forest is Hiroko Kubota's 2027 Weeks hardcover book, January start, Monday start. Hobonichi's own listing includes the English and Japanese books. The other shops on this page sell the English book. It is not a Weeks Mega, not a cover, and not the Archer and Olive Meteor Shower notebook.", 'hobonichi-techo-2027-covers/moomin-my-yard': 'Moomin: My Yard (Pale Mint) is a Hobonichi cover for the A6 Original book.', 'hobonichi-techo-2027-covers/white-cat-house': "White Cat House is a Yumi Kitagishi artist collaboration cover for the Hobonichi A6 Original book. Hobonichi's listing is that A6 cover. It is not the Weeks White Cat Wallpaper book.", 'hobonichi-techo-2027-covers/nothing-to-hide-green': "Nothing to Hide (Green) is a beautiful people cover for the 2027 A6 Original book, cover only, JAN 4580812708883. Hobonichi's listing is that one A6 cover. It is not the A5 pink cover, not the 2026 orange cover, and not a Weeks book. JetPens also lists it. JetPens blocks automated checks, so that link is not a stock status and does not send a restock alert.", 'hobonichi-techo-2027-covers/nothing-to-hide-pink': "Nothing to Hide (Pink) is a beautiful people cover for the 2027 A5 Cousin book, cover only, JAN 4580812709163. Hobonichi's listing is that one A5 cover. It is not the A6 green cover and not a 2026 cover. JetPens also lists it. JetPens blocks automated checks, so that link is not a stock status and does not send a restock alert.", 'archer-and-olive-storybook-navy': 'Storybook in Navy is an Archer and Olive dot grid notebook. White dot grid comes in letter, B5, 8x8, A5, TN, B6 and pocket. Kraft and ivory dot grid come in B5, 8x8 and A5.', 'archer-and-olive-songbird-blue': 'Songbird in Blue is an Archer and Olive dot grid notebook in letter, B5, square, A5, TN, B6 and pocket, and each size sells out on its own.', 'archer-and-olive-majestic-skies': 'Majestic Skies is an Archer and Olive dot grid notebook in B5 (160 pages), square (160 pages), A5 (192 pages) and TN (144 pages).', 'archer-and-olive-apothecary-shelf': "Apothecary Shelf is Archer and Olive's Halloween 2026 dot grid notebook. We track the B5 and 8x8 in white dot grid, and the A5 in white and black dot grid.", 'archer-and-olive-ice-castle': 'Ice Castle is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-cozy-critters': 'Cozy Critters is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-stag': 'Stag is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-winter-train': 'Winter Train is an Archer and Olive Winter 2026 dot grid notebook. The shop lists B5, 8x8, A5, TN, B6 and pocket, and each size has a separate preorder variant that says it ships mid February.', 'archer-and-olive-songbird-beige': 'Songbird in Beige is an Archer and Olive Everyday dot grid notebook in B5, square, A5, TN and B6.', 'archer-and-olive-storybook-plum': 'Storybook in Plum is an Archer and Olive dot grid notebook in letter, B5, 8x8, A5, TN, B6 and pocket.', 'archer-and-olive-songbird-warm-gray': 'Songbird in Warm Gray is an Archer and Olive letter-size dot grid notebook. The shop\'s page says letter size (LS), 160 pages.', 'archer-and-olive-storybook-olive': 'Storybook in Olive is an Archer and Olive dot grid notebook in letter, square, A5, TN and pocket.', 'archer-and-olive-meteor-shower': 'Meteor Shower is an Archer and Olive dot grid notebook in 8x8, A5 and a Travelers size with 144 pages.', 'leuchtturm1917-hardcover-a5-dotted': 'The Leuchtturm1917 Hardcover Medium (A5) with dotted pages comes in several colors, and each one goes out of stock on its own.', 'leuchtturm1917-120g-a5-dotted': 'The Leuchtturm1917 120G edition is the Medium (A5) hardcover with heavier 120 g paper and 203 numbered pages.', 'leuchtturm1917-edition-2': "Bullet Journal Edition 2, as Leuchtturm1917 names it, is the brand's official dot grid journal, tracked here in every color its US shop lists.", 'scribbles-that-matter-pro': 'The Scribbles That Matter Dotted Journal Pro is a 160gsm dot grid journal in A5 and B5 and several colors.', 'scribbles-that-matter-iconic': 'The Scribbles That Matter Dotted Journal Iconic is an A5 dot grid journal with 160gsm paper, here in Bottle Green.', 'scribbles-that-matter-starry-night': 'Starry Night is a Scribbles That Matter A5 dotted journal with black paper.', 'notebook-therapy-tsuki-160gsm': "The Tsuki 160GSM is Notebook Therapy's dot grid journal with heavy 160gsm paper, and each cover color sells out on its own.", 'notebook-therapy-tsuki-dark-academia': 'Dark Academia is a limited edition Tsuki dot grid journal from Notebook Therapy, an A5 with 176 pages.', 'notebook-therapy-tsuki-violet-nocturne': 'Violet Nocturne is a limited edition A5 Tsuki dot grid journal from Notebook Therapy, with white paper.', 'notebook-therapy-tsuki-ravens-secret': "Raven's Secret is a limited edition Tsuki dot grid journal from Notebook Therapy, an A5 with 176 pages.", 'regular-black': "The Traveler's notebook Regular size in Black is a leather notebook cover from Traveler's Company.", 'regular-blue': "The Traveler's notebook Regular size in Blue is a leather notebook cover from Traveler's Company.", 'regular-brown': "The Traveler's notebook Regular size in Brown is a leather notebook cover from Traveler's Company.", 'regular-camel': "The Traveler's notebook Regular size in Camel is a leather notebook cover from Traveler's Company.", 'regular-olive': "The Traveler's notebook Regular size in Olive is a leather notebook cover from Traveler's Company.", 'road-trip-brown': "ROAD TRIP Brown is a Regular size Traveler's notebook that Traveler's Company USA sells as a US exclusive.", 'card-size-20th-anniversary-black': "The Card Size 20th Anniversary Set in Black is a limited Traveler's Company set for the notebook's 20th anniversary.", 'md-diary-2027-a5': 'The MIDORI MD Notebook Diary 2027 in A5 is a dated monthly planner on MD Paper.', 'md-diary-1-day-1-page-2027-a5': 'The MIDORI MD Notebook Diary 1 Day 1 Page 2027 in A5 gives every day of 2027 its own page.'}

DESIGN_ABOUT.update({
    "hobonichi-techo-2027-covers/akiko-miyakoshi-airport-a6": "Akiko Miyakoshi: An Airport at Night is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover. The same design is also listed as an A5 cover, which has its own page; stock is tracked separately for each size. Kinokuniya USA lists it under JAN 4580812708784.",
    "hobonichi-techo-2027-covers/va-strawberry-thief-a6": "V&A Series: Strawberry Thief is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover.",
    "hobonichi-techo-2027-covers/puppet-sunsun-wa-a6": "PUPPET SUNSUN: Wa! is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover.",
    "hobonichi-techo-2027-covers/yoshie-watanabe-petit-bloom-a6": "Yoshie Watanabe: Petit Bloom is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover. Kinokuniya USA lists it under JAN 4580812708807.",
    "hobonichi-techo-2027-covers/colors-bordeaux-terracotta-a6": "Colors: Bordeaux Terracotta is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover. Kinokuniya USA lists it under JAN 4580812708777.",
    "hobonichi-techo-2027-covers/colors-blue-parasol-a6": "Colors: Blue Parasol is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover. Kinokuniya USA lists it under JAN 4580812708753.",
    "hobonichi-techo-2027-covers/tanakadaisuke-white-handkerchief-diary-a6": "tanakadaisuke: White Handkerchief Diary is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover. The same design is also listed as an A5 cover, which has its own page; stock is tracked separately for each size.",
    "hobonichi-techo-2027-covers/glow-chianti-a6": "Glow: Chianti is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover. The same design is also listed as an A5 cover, which has its own page; stock is tracked separately for each size. Kinokuniya USA lists it under JAN 4580812708968.",
    "hobonichi-techo-2027-covers/natal-hello-new-day-camo-a6": "Natal Design: Hello New Day! (Camo) is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover.",
    "hobonichi-techo-2027-covers/arts-science-wax-coating-kip-a6": "Arts&Science: Wax Coating Kip is a cover for the Hobonichi A6 Original book, cover only. Hobonichi's listing is that one A6 cover.",
    "hobonichi-techo-2027-covers/yumi-kitagishi-white-cat-village-a5": "Yumi Kitagishi: White Cat Village is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. Kinokuniya USA lists it under JAN 4580812709071.",
    "hobonichi-techo-2027-covers/va-blackthorn-a5": "V&A Series: Blackthorn is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover.",
    "hobonichi-techo-2027-covers/akiko-miyakoshi-airport-a5": "Akiko Miyakoshi: An Airport at Night is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. The same design is also listed as an A6 cover, which has its own page; stock is tracked separately for each size.",
    "hobonichi-techo-2027-covers/puppet-sunsun-s-a5": "PUPPET SUNSUN: S is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover.",
    "hobonichi-techo-2027-covers/colors-chiffon-greige-a5": "Colors: Chiffon Greige is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. Kinokuniya USA lists it under JAN 4580812709033.",
    "hobonichi-techo-2027-covers/colors-misty-cedar-a5": "Colors: Misty Cedar is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. Kinokuniya USA lists it under JAN 4580812709057.",
    "hobonichi-techo-2027-covers/colors-mango-latte-a5": "Colors: Mango Latte is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. Kinokuniya USA lists it under JAN 4580812709040.",
    "hobonichi-techo-2027-covers/moomin-my-yard-pink-gray-a5": "Moomin: My Yard (Pink Gray) is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. Kinokuniya USA lists it under JAN 4580812709132.",
    "hobonichi-techo-2027-covers/mina-perhonen-felice-blue-a5": "minä perhonen: felice (Blue) is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. The same design is also listed as a Weeks cover, which has its own page; stock is tracked separately for each size.",
    "hobonichi-techo-2027-covers/tanakadaisuke-white-handkerchief-diary-a5": "tanakadaisuke: White Handkerchief Diary is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. The same design is also listed as an A6 cover, which has its own page; stock is tracked separately for each size.",
    "hobonichi-techo-2027-covers/glow-chianti-a5": "Glow: Chianti is a cover for the 2027 A5 Cousin book, cover only. Hobonichi's listing is that one A5 cover. The same design is also listed as an A6 cover, which has its own page; stock is tracked separately for each size. Kinokuniya USA lists it under JAN 4580812709248.",
    "hobonichi-weeks-2027/tragen-bitter-plaid-cover": "Tragen: Bitter Plaid is a cover for the Hobonichi Weeks 2027 book, cover only. Hobonichi's listing is that one Weeks cover.",
    "hobonichi-weeks-2027/alettone-sweets-cover": "Alettone: Sweets is a cover for the Hobonichi Weeks 2027 book, cover only. Hobonichi's listing is that one Weeks cover. Kinokuniya USA lists it under JAN 4580812710138.",
    "hobonichi-weeks-2027/mina-perhonen-felice-blue-weeks-cover": "minä perhonen: felice (Blue) is a cover for the Hobonichi Weeks 2027 book, cover only. Hobonichi's listing is that one Weeks cover. The same design is also listed as an A5 cover, which has its own page; stock is tracked separately for each size. Kinokuniya USA lists it under JAN 4580812701945.",
})

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

# The old tracker URL used to hold every dot grid design page. They moved under DOTGRID_SLUG.
REDIRECTS.update({f"{AO_SLUG}/{d['slug']}": f"{DOTGRID_SLUG}/{d['slug']}/" for d in DESIGNS if d["parent"] == DOTGRID_SLUG})
# Designs Archer and Olive took off its store (product page and catalog entry gone, checked Nov 22, 2026).
# Their pages now point at the dot grid tracker, from both the current and the old URL.
RETIRED_DOTGRID_DESIGNS = ("archer-and-olive-songbird-warm-gray", "archer-and-olive-meteor-shower")
REDIRECTS.update({f"{parent}/{slug}": DOTGRID_SLUG + "/" for slug in RETIRED_DOTGRID_DESIGNS for parent in (DOTGRID_SLUG, AO_SLUG)})

def designs_of(parent_slug):
    if parent_slug == AO_SLUG:  # the Archer and Olive page lists its own designs; the pages live under DOTGRID_SLUG
        return [d for d in DESIGNS if d["parent"] == DOTGRID_SLUG and d["slug"].startswith("archer-and-olive-")]
    return [d for d in DESIGNS if d["parent"] == parent_slug]

def build_design(d, oe=None):
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
    thanks = ('<p class="suggest">Thank you to our follower Angela for suggesting we track these restocks.</p>'
              if d["slug"] in {"nothing-to-hide-green", "nothing-to-hide-pink", "nothing-to-hide-yellow"} else "")
    table = (f"""<section class="card group-sec" id="stock">
  <div class="section-head"><h2>Stock by shop</h2><p class="muted small">{E(count_line(ls).capitalize())} · {checked_line(ls)}</p></div>
  {list_filter(ls, "Shop name")}
  {sold_everywhere_html(ls)}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(ls)}</tbody>
  </table></div>
  <p class="muted small card-empty" hidden>Nothing on this page matches those filters.</p>
  <p class="muted small">Open a shop's name to go straight to its listing.</p>
  {region_legend(l["store_id"] for l in ls)}
</section>""" if ls else f'<section class="card group-sec" id="stock"><h2>Stock by shop</h2><div class="empty"><p>No shop we check lists this design right now. See the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a> for everything we track.</p></div></section>')
    urls = {l["url"] for l in ls}
    rs = sorted([c for c in changes if c["url"] in urls and is_restock_event(c)],
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
                  f"Not at the shops we track. At the last check ({when}) the {'one shop we could check' if unk else 'one shop we track'} didn't have it in stock or on preorder.")
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
           f"Yes, sign up above. We'll email you a confirmation link; you aren't on the list until you click it. Once you confirm, you'll get free restock emails for the trackers you pick (Hobonichi, dot grid journals, limited-edition inks), plus an occasional update when we add a tracker or release something new, not just {d['full']}. You can unsubscribe anytime.")]
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
{crumbs(*hub_trail(parent), (parent["slug"] + "/", parent["short"]), (fname, d["name"]))}
<section class="hero hero-compact">
  {eyebrow(ey, nshops(shops), f"checked {CHECK_FREQ}")}
  <h1>{E(h1)}</h1>
  <p class="lede">{intro}</p>
  {thanks}
  {hero_facts(ls)}
  {signup_for(section=sec)}
</section>
<div class="layout">
  <div class="main-col">
    <div class="m-lead">{table}</div>
    <section class="card"><h2>Recent restocks</h2>{restock_html}</section>
    {faq_html}
    {sources_html}
  </div>
  <aside class="side-col">
    <section class="card"><p class="eyebrow">More restock pages</p><ul class="link-list">{others}</ul></section>
    {section_guides(sec)}
  </aside>
</div>
{signup_for(section=sec, placement="bottom")}
</div>"""
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": h1.replace(" restock tracker", "") + ": listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: l["store"]))]}
    title = design_seo_title(d)
    desc = design_seo_desc(d, shops)
    return fname, page(fname, title, desc, body, ld=(crumbs_ld(*hub_trail(parent), (parent["slug"] + "/", parent["short"]), (fname, d["name"])), items, faq_ld),
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
     "{n} shops across all trackers, in separate sections per brand family. Hobonichi: {nh} shops, the official Hobonichi Online Store and independent stationery shops. {secs}. Each listing in the tracker links to the shop's own page. {unchecked}"),
    ("What do you track?",
     "Hobonichi Techo 2027: the Original A6 and Cousin A5 books, the English Planner A6 book, HON, Weeks and Weeks Mega, and @@COVERS@@. {tracks} @@PENS@@"),
    ('What do "Not yet on sale" and "Couldn\'t check" mean?',
     '"Not yet on sale" means the shop has a preview page up but isn\'t taking orders yet. That\'s different from sold out. '
     '"Couldn\'t check" means our check failed, for example because the shop\'s site didn\'t respond, so we don\'t know. '
     "We show that instead of guessing whether it's in stock."),
    ("Do you sell planners?",
     "Yes, our own: we make planners and journals and sell them on our shop page ({shop}), printed on Amazon, as printable PDFs on Etsy, and as classroom printables on Teachers Pay Teachers. "
     "The stationery we track is sold by the shops themselves; we just link you to them. "),
    ("How do restock alerts work?",
     "Sign up with your email and we'll send a confirmation link. Once you confirm, you'll get free restock emails for the trackers you pick: Hobonichi, dot grid journals and limited-edition inks, plus an occasional update when we add a tracker or release something new. "
     "Ink restocks also show on the inks page. "
     "You can unsubscribe anytime."),
]

FAQ_TRACKS = {  # one sentence per live section for "What do you track?"
    "dotgrid": "On a separate dot grid journals page, we track a focused set of flagship dot grid notebooks from {dg}, size by size and color by color, plus Archer and Olive's dot grid refills.",
}

HOBO_NOTE_Q = "Where are launch dates and how restocks usually go?"
HOBO_NOTE = ('For launch dates and how restocks usually go, see the '
             '<a href="hobonichi-2027/">Hobonichi 2027 launch &amp; restock calendar</a>.')
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
    # rstrip the coverage sentence so the ". " join does not add a second period after "shops."
    secs = ". ".join(f'{SECTIONS[k]["foot"]}: {N_SEC[k]} shops, {shop_names(k)}' + ((". " + dotgrid_where_checked().rstrip(".")) if k == "dotgrid" else "") for k in LIVE)
    if INK_LIVE:
        secs += f". Limited-edition inks: {N_INK} shops, {ink_shop_names()}, each on the brand's own dealer list"
    secs += ". Some shops sell more than one brand, so they're counted once in the total"
    tracks = " ".join(FAQ_TRACKS[k] for k in LIVE) + ((" " + INK_FAQ_TRACK) if INK_LIVE else "")
    _cn = [p.get("canonical", "") for p in stock["products"]]
    _cv = {c for c in _cn if c.startswith(("cover-a6-", "cover-a5-", "weeks-cover-"))}
    _n6 = sum(c.startswith("cover-a6-") for c in _cv)
    _n5 = sum(c.startswith("cover-a5-") for c in _cv)
    _nw = sum(c.startswith("weeks-cover-") for c in _cv)
    covers_txt = f"{_n6} A6 covers, {_n5} A5 covers and {_nw} Weeks covers"
    # The Sailor x Pentel advent box (ink tracker) includes "limited edition writing instruments" (Yoseka's listing).
    pens_txt = ("We don't track pens on their own, though the Sailor x Pentel advent box on the ink tracker includes writing instruments."
                if INK_LIVE and any(r.get("ink_id") == "sailor-advent-2026" for r in INK_ROWS) else "We don't track pens.")
    answers = []
    for q, a in FAQ:
        a = a.replace("@@COVERS@@", covers_txt).replace("@@PENS@@", pens_txt)
        if q == "Do you sell planners?" and shop_inserts_public():
            a = ("Yes, our own: we make planners, journals, and printable planner inserts, and sell them on our shop page ({shop}). "
                 "Printed books are on Amazon. Printable PDFs, including undated paper tip-ins, are on Etsy. "
                 "Classroom printables are on Teachers Pay Teachers. "
                 "The stationery we track is sold by the shops themselves; we just link you to them. ")
        answers.append((q, a))
    if only is None:
        pairs = answers
    else:
        by_q = dict(answers)
        pairs = [(q, by_q[q]) for q in only]
    unchecked = link_only_clause()
    qa = [(q, a.format(n=n, nh=N_HOBO, secs=secs, tracks=tracks.format(dg=dotgrid_brand_names()), shop=url_for("shop/"), unchecked=unchecked),
           E(a).format(n=n, nh=N_HOBO, secs=E(secs), tracks=E(tracks.format(dg=dotgrid_brand_names())), shop=f'<a href="shop/">{E(SHOP_NAME.lower())}</a>', unchecked=E(unchecked))) for q, a in pairs]
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

STATIC_LASTMOD = {"hobonichi-2027/": "2026-11-22", "about/": "2026-11-22", "privacy/": "2026-11-22"}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes], CONTENT_LASTMOD)
    urls = [(url_for("index.html"), home_mod), (url_for(HOBO_TRACKER), latest(*[p.get("status_since") for p in hobo_products()], *[c["at"] for c in changes], CONTENT_LASTMOD))]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(design_fname(d)), design_lastmod(d)) for d in DESIGNS]
    if INK_LIVE:
        urls.append((url_for(INK_SLUG + "/"), ink_lastmod()))
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    urls += [(url_for(slug + "/"), TAKEDOWN_DATE) for slug in (TN_SLUG,)]  # the indexed takedown notices
    hobo_mod = latest(*[p.get("status_since") for p in hobo_products()], GUIDES_LASTMOD)
    urls += [(url_for(WTB_SLUG + "/"), latest(hobo_mod, CONTENT_LASTMOD)), (url_for(VS_SLUG + "/"), latest(GUIDES_LASTMOD, CONTENT_LASTMOD)), (url_for(JAN_APR_SLUG + "/"), JAN_APR_MODIFIED), (url_for(DG_GUIDE_SLUG + "/"), latest(*[p.get("status_since") for p in section_products("dotgrid")], DG_GUIDE_LASTMOD, CONTENT_LASTMOD)), (url_for(GIFT_SLUG + "/"), latest(*[p.get("status_since") for k in GIFT_PICKS for p in gift_listings(k)], json.loads(GUIDE_DATES.read_text())["build_gift_guide"]["date"])), (url_for("guides/"), latest(DG_GUIDE_LASTMOD, TAKEDOWN_DATE, CONTENT_LASTMOD)), (url_for("shop/"), shop_lastmod()), (url_for("follow/"), "2026-11-12"), (url_for("contact/"), "2026-11-20"), (url_for(SOLDOUT_SLUG + "/"), latest(*[p.get("status_since") for p in stock["products"]], CONTENT_LASTMOD))]
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
</head><body>
<p>This page moved to <a href="{E(u)}">{E(u)}</a>.</p>
<footer class="foot"><p class="muted">{independent_note()}</p></footer>
</body></html>
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
<p><a class="btn" href="{HOBO_TRACKER}">Go to the Hobonichi tracker</a> {" ".join([f'<a class="btn-ghost" href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a>' for k in LIVE] + ([f'<a class="btn-ghost" href="{INK_SLUG}/">{E(INK_NAV)}</a>'] if INK_LIVE else []))}</p>
<section class="card"><h2>Restock pages</h2>
  <p class="eyebrow">Hobonichi Techo 2027</p><ul class="link-list"><li><a href="{HOBO_TRACKER}">Hobonichi tracker</a></li>{hobo}</ul>
{"".join(f'  <p class="eyebrow">{E(SECTIONS[k]["foot"])}</p><ul class="link-list"><li><a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a> <span class="muted small">· {E(shop_names(k))}</span></li></ul>' + chr(10) for k in LIVE)}{f'  <p class="eyebrow">Limited-edition fountain pen ink</p><ul class="link-list"><li><a href="{INK_SLUG}/">{E(INK_NAV)}</a> <span class="muted small">· {E(ink_shop_names())}</span></li></ul>' + chr(10) if INK_LIVE else ""}
  <p class="eyebrow">Guides</p><ul class="link-list">{"".join(f'<li><a href="{h}">{E(t)}</a></li>' for h, t in GUIDES)}</ul>
</section>
</article>"""
    return page("404.html", "Page not found",
                "This page doesn't exist. The link may be old or mistyped. The Hobonichi, dot grid journal and limited-edition ink trackers are linked here. Pick one below.", body, noindex=True)

# --- SEO guides (Hobonichi section) -------------------------------------------------------------
# Editorial pages. Every stock status on them comes from data/stock.json (rebuilt about every 30 minutes by the
# workflow); product facts come only from the sources listed on each page. No prices: the checker
# doesn't record them.
WTB_SLUG = "where-to-buy-hobonichi-2027"
VS_SLUG = "hobonichi-techo-vs-cousin-vs-weeks"
JAN_APR_SLUG = "hobonichi-january-start-vs-april-start"
JAN_APR_PUBLISHED = "2026-11-12"  # owner-approved publication date
JAN_APR_MODIFIED = "2026-11-19"  # official 2027 Spring launch date added from the shopping guide
DG_GUIDE_SLUG = "best-dot-grid-journals"
HOBO_GUIDES = [(WTB_SLUG + "/", "Where to buy the Techo 2027"), (VS_SLUG + "/", "Techo vs Cousin vs Weeks"), (JAN_APR_SLUG + "/", "January-start vs April-start"), ("hobonichi-2027/", "2027 launch & restock calendar")]
GUIDES = HOBO_GUIDES + [(DG_GUIDE_SLUG + "/", "Best dot grid journals compared"),
                        ("holiday-stationery-gift-guide-2026/", "Holiday gift guide 2026")]  # footer, /guides/, 404, related block; Hobonichi pages use HOBO_GUIDES
GUIDES_LASTMOD = "2026-10-29"
DG_GUIDE_LASTMOD = "2026-11-20"  # STM Pro sizes, Leuchtturm formats, and TN wording (America/Detroit)
GUIDE_BLURBS = {WTB_SLUG + "/": "Which shops have each 2027 Original A6, Cousin A5, Weeks and Weeks Mega in stock right now, checked about every 30 minutes, plus tips for catching a restock.",
                VS_SLUG + "/": "Size, weight, daily vs weekly layout and pages for the three most popular Hobonichi books, from Hobonichi's own specs, and who each one suits.",
                JAN_APR_SLUG + "/": "Hobonichi's April-start (Spring) techo comes in fewer versions than the January-start edition and goes on sale on February 1.",
                "hobonichi-2027/": "When the 2027 planners launched, the October wave, and when restocks usually land, with sources.",
                DG_GUIDE_SLUG + "/": "Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy: paper gsm, pages, size and features from each maker's own page, with live stock.",
                "holiday-stationery-gift-guide-2026/": "Hobonichi, Leuchtturm1917, Archer and Olive and other dot grid gifts, each with live stock from our last check, plus planners and printables we make."}  # last copy change on the guide pages (sitemap lastmod floor)
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
    fam = [("hobonichi", "Hobonichi"), ("dotgrid", "Dot grid journals")]
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
    """Guide links on a design page. Hobonichi keeps its guides; dot grid links its own."""
    if sec == "hobonichi":
        return guides_block()
    link = {"dotgrid": (DG_GUIDE_SLUG + "/", "Best dot grid journals compared")}.get(sec)
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
        secs.append(f'''<details class="card group-fold" id="{E(g["slug"])}">
  <summary><h2 class="fam-name">{E(g["product"])}</h2><span class="fam-meta">{E(count_line(ls).capitalize())}</span></summary>
  <div class="group-body">
  {_shop_table(ls)}
  <p class="small"><a href="{g["slug"]}/">Full {E(g["short"])} restock page</a> <span class="muted">· every listing, when it last changed, and recent restocks</span></p>
  </div>
</details>''')
    unchecked = listed_unchecked()
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a> <span class="muted">· {E(n["reason"] or "")}</span></li>' for n in unchecked)
    if len(unchecked) == 1:
        unchecked_head, unchecked_blurb = "Shop we list but can't check", "Its site blocks automated checks, so we link to it without a status."
    else:
        unchecked_head, unchecked_blurb = "Shops we list but can't check", "Their sites block automated checks, so we link to them without a status."
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
         "Sign up for Stationery Drop Watch alerts. We'll email you a confirmation link. Once you confirm, we send free restock emails for the trackers you pick (Hobonichi, dot grid journals and limited-edition inks), plus an occasional update when we add a tracker or release something new. We check the shops about every 30 minutes. You can unsubscribe anytime."),
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
    <section class="card"><h2>{unchecked_head}</h2>
      <p class="muted small">{unchecked_blurb}</p>
      <ul>{not_checked}</ul></section>
    <section class="card" id="tips"><h2>Tips for catching a restock</h2>
      <ul>
        <li><strong>Check more than one shop.</strong> When one store sells out, another often still has it.{tip_split} The <a href="{HOBO_TRACKER}#tracker">full tracker</a> puts every shop side by side.</li>
        <li><strong>Watch for preorders.</strong> Restocks don't always show up as "in stock". At the October 1 wave, some shops took preorders for earlier sell-outs. We count preorders as available. <a href="hobonichi-2027/">See the 2027 calendar</a>.</li>
        <li><strong>Don't mistake "not yet on sale" for sold out.</strong> Shops put up preview pages before items go on sale.</li>
        <li><strong>Sign up at the official store too.</strong> Hobonichi's restock notification emails cover the Techo books and the Drawer Pouch, not accessories, and don't guarantee you'll get one <a href="#src-shop">[Hobonichi]</a>. Many independent shops offer their own restock sign-ups on product pages <a href="#src-pm">[Paper Mouse]</a>.</li>
        <li><strong>Get our alerts.</strong> We check about every 30 minutes and send free restock emails for the trackers you pick. <a href="#alerts">Sign up above</a>.</li>
      </ul>
    </section>
<h2>Which one should you get?</h2>
<p>Not sure between the A6 Original, the A5 Cousin and the slim Weeks? Read <a href="{VS_SLUG}/">Hobonichi Techo vs Cousin vs Weeks</a>: sizes, layouts and who each one suits, from Hobonichi's own specs.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">
  <li id="src-shop"><a href="{H_SRC['shop'][0]}" rel="noopener" target="_blank">{E(H_SRC['shop'][1])}</a>, Hobonichi (official). Restock notification emails.</li>
  <li id="src-pm"><a href="https://www.thepapermouse.com/pages/hobonichi-faq" rel="noopener" target="_blank">Hobonichi FAQ</a>, The Paper Mouse. Restock history (restocks not guaranteed; almost all items restocked at least once after launch in past years), product-page restock sign-ups.</li>
  <li>Stock statuses: each shop's public product data, read by our checker; see <a href="about/">how it works</a>.</li>
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
                       f"Where to buy the Hobonichi Techo 2027 Original A6, Cousin A5, Weeks and Weeks Mega: which of {n_shops} shops have each one in stock, plus restock tips.",
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
<p>Stock changes fast, and one shop is often sold out while another has it. See <a href="{WTB_SLUG}/">where to buy the Hobonichi Techo 2027</a> for every shop we track, edition by edition, or <a href="#alerts">sign up above</a> for free restock emails for the trackers you pick. You can unsubscribe anytime.</p>

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
         "February 1, 2027 at 11:00 AM Japan time on the official Hobonichi Store (9:00 PM ET on January 31). Other shops start at their own opening hours. Hobonichi has not published the Spring 2027 cover and book lineup yet."),
        ("Is there an English April-start Hobonichi?",
         "No. April-start editions are Japanese only."),
        ("Is there an April-start Weeks Mega or Day-Free?",
         "No."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    sources = [
        ("https://www.1101.com/store/techo/en/faq/articles/4889929315230.html", "April-start editions"),
        ("https://www.1101.com/store/techo/en/faq/articles/4889951964190.html", "Spring lineup guidance"),
        ("https://www.1101.com/store/techo/en/faq/articles/4889935445534.html", "sale schedule"),
        ("https://www.1101.com/store/techo/en/faq/articles/4889951953566.html", "Sunday-start editions"),
        ("https://www.1101.com/store/techo/en/2027/pc/shopping_guide/", "Hobonichi Techo 2027 shopping guide"),
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
<p>The <a href="https://www.1101.com/store/techo/en/2027/pc/shopping_guide/" rel="noopener" target="_blank">2027 shopping guide</a> confirms this year's official Hobonichi Store launch: February 1, 2027 at 11:00 AM Japan time (January 31, 2027 at 9:00 PM ET). Hobonichi has not published the Spring 2027 cover and book lineup yet. See the <a href="hobonichi-2027/">2027 calendar</a>.</p>

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
<p class="muted small">Help-center pages read Nov 7, 2026. The 2027 shopping guide is the source for this year's February 1 launch.</p>
<ol class="sources">{src_items}</ol>
{design_links_block()}
{related_block(fname)}
</article>"""
    headline = "Hobonichi Techo January-start vs April-start"
    art = {"@context": "https://schema.org", "@type": "Article", "headline": headline,
           "datePublished": JAN_APR_PUBLISHED, "dateModified": JAN_APR_MODIFIED, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, title, desc, body,
                       ld=(crumbs_ld(("guides/", "Guides"), (fname, "January-start vs April-start")), art, faq_ld))


DG_SRC = {  # each maker's own product page; STM Pro sizes rechecked Nov 20, 2026. Every spec cites one of these.
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
    jump = {sid: canons[0] for _, sid, canons in DG_COLS}  # tracker section ids are the canonical ids
    def avail(store_id, canons):
        ls = col_ls(store_id)
        if not ls:
            return f'<a href="{DOTGRID_SLUG}/#{jump[store_id]}">Live stock</a>'
        buy = [l["label"] for l in ls if l["status"] in BUYABLE]
        names = f'<br><span class="muted small">In stock: {E("; ".join(buy))}</span>' if buy else ""
        return f'<strong>{len(buy)} of {len(ls)}</strong> versions we track · <a href="{DOTGRID_SLUG}/#{jump[store_id]}">live stock</a>{names}'
    na = "Not listed on the product page"
    rows = [  # (row, A&O, Leuchtturm1917, Scribbles That Matter, Notebook Therapy), each cell (text, source keys)
        ("Paper weight", ("160gsm (Storybook also comes in kraft dot grid, 150gsm)", "ao ao2"), ("80 g/m² (the 120G edition is 120 gsm)", "lt lt120"),
         ("160gsm or 120gsm, your choice", "stm"), ("160 GSM", "nt")),
        ("Pages", ("192 (A5)", "ao ao2"), ("251 numbered pages (120G edition: 203)", "lt lt120"), (na, "stm"), ("128, with gilded edges", "nt")),
        ("Size", ('A5: 5.75 × 8.25 in', "ao"), ("Medium (A5): 5.71 × 8.27 in", "lt"),
         ("A5: 5.75 × 8.5 in (14.5 × 21 cm); B5: 7 × 10 in; B6: 5 × 7 in (from STM's size chart)", "stm"), ("135 × 195 mm", "nt")),
        ("Dot grid", ("Dot grid (spacing not listed)", "ao"), ("Dots 5 mm apart", "lt"), ("5 mm dot grid", "stm"), ("5 mm, light grey dots", "nt")),
        ("Paper color", ("White, kraft or ivory dot grid (Storybook)", "ao2"), ("Slightly chamois-colored", "lt"), ("Bright white", "stm"), ("Bright white", "nt")),
        ("Cover", ("Vegan leather (hard or soft not listed)", "ao"), ("Hardcover; softcover also sold", "lt"), ("Vegan leather hardcover", "stm"), ("Vegan leather (hard or soft not listed)", "nt")),
        ("Lays flat", ("Yes, lay-flat binding", "ao"), ("Yes, thread-bound, opens flat", "lt"), ("Yes, lay-flat binding", "stm"), ("Yes, 180° lay flat", "nt")),
        ("Page numbers and index", (na, "ao"), ("Numbered pages and a blank table of contents", "lt"), ("Numbered pages, index, key and pen test page", "stm"), (na, "nt")),
        ("Bookmarks", (na, "ao"), ("Two page markers", "lt"), ("Two ribbon bookmarks", "stm"), (na, "nt")),
        ("Extras", (na, "ao"), ("Gusseted pocket, elastic band, 8 perforated sheets, stickers", "lt"),
         ("Back pocket, elastic, pen loop; comes with a 0.7 mm fineliner, layout guide and box", "stm"), ("Back pocket with a sticker sheet, elastic band", "nt")),
        ("Other sizes", ("B5, 8x8 square, B6, TN, Pocket and Letter (Songbird)", "ao"),
         ("Pocket (A6), Paperback (B6+), Medium (A5), Composition (B5), Master Slim (A4+) and Master (A4+)", "lt"),
         ("B5 (160gsm or 120gsm) and B6 (120gsm only)", "stm"), ("None listed on this page", "nt")),
    ]
    def n(k):  # numbered citation, matching the Sources list order
        return f'<a href="#src-{k}">[{list(DG_SRC).index(k) + 1}]</a>'
    def cell(t, keys):
        return f'{E(t)} <span class="small">{"".join(n(k) for k in keys.split())}</span>'
    rows_html = "".join(f'<tr><th scope="row">{E(r[0])}</th>' + "".join(f"<td>{cell(*c)}</td>" for c in r[1:]) + "</tr>" for r in rows)
    rows_html += '<tr><th scope="row">In stock now</th>' + "".join(f"<td>{avail(sid, cs)}</td>" for _, sid, cs in DG_COLS) + "</tr>"
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
         f"Our dot grid tracker checks every journal above {CHECK_FREQ}. Sign up and we'll email you a confirmation link. Once you confirm, you'll get free restock emails for the trackers you pick (Hobonichi, dot grid journals, limited-edition inks), plus an occasional update when we add a tracker or release something new, including sold-out sizes and colors coming back. You can unsubscribe anytime."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    src_items = "".join(f'<li id="src-{k}"><a href="{u}" rel="noopener" target="_blank">{E(t)}</a>, {E(b)} (official product page).</li>'
                        for k, (u, t, b) in DG_SRC.items())
    asof = time_tag(stock["run_finished"])
    revised = dt.date.fromisoformat(DG_GUIDE_LASTMOD)
    specs_asof = f"{revised.strftime('%b')} {revised.day}, {revised.year}"
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
<p class="muted small">A5 dot grid versions (the Tsuki comes in one size), from each maker's US product page as of {specs_asof}. Numbers in brackets point to the sources below. Where a page doesn't list something, we say so instead of guessing. We don't show prices, because they change and differ by edition.</p>
<div class="table-wrap"><table class="stock compare">
<thead><tr><th></th>{"".join(f"<th>{E(h)}</th>" for h, _, _ in DG_COLS)}</tr></thead>
<tbody>{rows_html}</tbody></table></div>
<p class="muted small">Stock in each column is what that maker's own shop said at our last check, {asof}. Each count covers every dot grid listing we track at that shop. Other shops that sell the same notebooks are on the <a href="{DOTGRID_SLUG}/">dot grid tracker</a>. Across the four makers: {E(dg_total)}. Across every shop: {E(dg_all)}.</p>

<h2>Who each one suits</h2>
<h3>Archer and Olive: for markers, paint and lots of size choices</h3>
<p>Pick Archer and Olive if you want thick paper and a specific size. Its notebooks use 160gsm paper, and the A5 has 192 pages {s("ao")}. Sizes run from Pocket to Letter, including B5, B6, square and a TN size {s("ao")}. Some designs also offer kraft (150gsm) or ivory dot grid paper {s("ao2")}. The product page doesn't mention page numbers, an index or bookmarks, so plan to set those up yourself.</p>
<p><a href="{DOTGRID_SLUG}/#{jump['archerolive']}">Live Archer and Olive stock</a></p>
<h3>Leuchtturm1917: for writing, and the most pages</h3>
<p>Pick the Leuchtturm1917 Hardcover Medium (A5) if you mostly write and want room. It has 251 numbered pages, a blank table of contents, two page markers, a gusseted pocket and 8 perforated sheets {s("lt")}. The paper is 80 g/m² and slightly chamois-colored, the thinnest here {s("lt")}. If you want thicker paper with the same setup, the 120G edition has 120 gsm paper and 203 numbered pages {s("lt120")}.</p>
<p><a href="{DOTGRID_SLUG}/#{jump['leuchtturm-us']}">Live Leuchtturm1917 stock</a></p>
<h3>Scribbles That Matter: for starting right away</h3>
<p>Pick the Scribbles That Matter Dotted Journal Pro if you want the setup done. It comes with numbered pages, an index, a key page and a pen test page, two ribbon bookmarks, a pen loop and a 0.7 mm fineliner in the box {s("stm")}. A5 and B5 come in 160gsm or 120gsm, and B6 comes in 120gsm only {s("stm")}. The Pro has a plain matte cover; the Iconic is the same idea with an embossed cover {s("stm2")}. The page doesn't list a page count.</p>
<p><a href="{DOTGRID_SLUG}/#{jump['scribbles']}">Live Scribbles That Matter stock</a></p>
<h3>Notebook Therapy Tsuki: for a smaller book</h3>
<p>Pick the Tsuki 160GSM if you want thick 160 GSM paper in a book you'll finish sooner. It's 135 × 195 mm with 128 pages, gilded edges, a 5 mm light grey dot grid, a back pocket with a sticker sheet and an elastic band {s("nt")}. The product page doesn't mention page numbers, an index or bookmarks. Notebook Therapy also releases limited-edition Tsuki designs, which we track too.</p>
<p><a href="{DOTGRID_SLUG}/#{jump['notebooktherapy']}">Live Notebook Therapy stock</a></p>

<h2>Where to buy</h2>
<p>All four sell direct, and sizes and colors sell out often. Our <a href="{DOTGRID_SLUG}/">dot grid journal tracker</a> checks each one at the maker's own shop {CHECK_FREQ}. <a href="#alerts">Sign up above</a> for free restock emails for the trackers you pick. You can unsubscribe anytime. More guides are on the <a href="guides/">guides page</a>.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{src_items}</ol>
<p class="muted small">Each maker sells other dot grid journals too. This guide covers the A5 versions above.</p>
{design_links_block("dotgrid")}
{related_block(fname)}
</article>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title,
           "datePublished": "2026-11-04", "dateModified": DG_GUIDE_LASTMOD, "url": url_for(fname), "image": OG_DOTGRID,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    return fname, page(fname, title + TITLE_SUFFIX, desc, body,
                       ld=(crumbs_ld(("guides/", "Guides"), (fname, "Dot grid journals compared")), art, faq_ld),
                       og_type="article", og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT)


# --- Holiday gift guide ------------------------------------------------------------------------
# Every availability line on this page is rendered from data/stock.json at build time (each checker
# run rebuilds it), the same way the Where to Buy guide counts shops. Prices come from the same run:
# the checker records each Shopify listing's price (price_cents) when the shop sells in USD, and the
# table shows the lowest one among shops that had the pick in stock or on preorder. No price is ever
# typed in here; a pick with no recorded price says so. Our own Amazon books show list price only
# (AMAZON_LIST_PRICES) and printables the shared ETSY_PRICE line, the way /shop does. Printables and
# our own books are not in stock.json, so they get no availability claim.
GIFT_SLUG = "holiday-stationery-gift-guide-2026"
# key -> (canonical, label filter or None, live page, short name). The live page is the item's design
# page when one exists, otherwise its tracker page.
GIFT_PICKS = {
    "moomin": ("weeks-moomin-table", None, "hobonichi-weeks-2027/moomin-at-the-table/", "Weeks, Moomin: At the Table (English)"),
    "whitecat": ("weeks-white-cat", None, "hobonichi-weeks-2027/white-cat-wallpaper/", "Weeks, White Cat Wallpaper (English)"),
    "candy": ("weeks-mega-candy-dream", None, "hobonichi-weeks-mega-2027/candy-dream/", "Weeks Mega, Bow & Tie: Candy Dream (English)"),
    "cousin": ("cousin-a5-en", None, "hobonichi-techo-2027-cousin-a5/", "English Cousin A5 book"),
    "original": ("original-a6-en", None, "hobonichi-techo-2027-original-a6/", "English Original A6 book"),
    "cathouse": ("cover-a6-white-cat-house", None, "hobonichi-techo-2027-covers/white-cat-house/", "A6 cover, White Cat House"),
    "myyard": ("cover-a6-moomin", None, "hobonichi-techo-2027-covers/moomin-my-yard/", "A6 cover, Moomin: My Yard"),
    # For the traveler (reworked Nov 19, 2026, after the Traveler's Company and MIDORI removal).
    "plannera6": ("planner-a6-en", None, "hobonichi-techo-2027-planner-a6/", "English Planner A6 book"),
    "tragen": ("cover-a6-tragen-black", None, "hobonichi-techo-2027-covers/#cover-a6-tragen-black", "A6 cover, Tragen: Black"),
    "aostag": ("ao-stag", "pocket dot grid · ships now", DOTGRID_SLUG + "/archer-and-olive-stag/", "Archer and Olive Stag, pocket size"),
    "lta5": ("lt-hardcover-a5", None, DOTGRID_SLUG + "/leuchtturm1917-hardcover-a5-dotted/", "Leuchtturm1917 Hardcover Medium (A5), dotted"),
    "lted2": ("lt-bullet-journal-ed2", None, DOTGRID_SLUG + "/leuchtturm1917-edition-2/", "Leuchtturm1917 Bullet Journal Edition 2"),
    "aonavy": ("ao-storybook-navy", "A5 ", DOTGRID_SLUG + "/archer-and-olive-storybook-navy/", "Archer and Olive Storybook in Navy, A5"),
    "aobeige": ("ao-songbird-beige", "B5 ", DOTGRID_SLUG + "/archer-and-olive-songbird-beige/", "Archer and Olive Songbird in Beige, B5"),  # B5 since Nov 22, 2026: the A5 dot grid sold out
    # Winter 2026 designs: only the ships-now A5 dot grid option (the Feb preorder option is a separate listing).
    "aoice": ("ao-ice-castle", "A5 dot grid · ships now", DOTGRID_SLUG + "/archer-and-olive-ice-castle/", "Archer and Olive Ice Castle, A5"),
    "aotrain": ("ao-winter-train", "A5 dot grid · ships now", DOTGRID_SLUG + "/archer-and-olive-winter-train/", "Archer and Olive Winter Train, A5"),
}
GIFT_SRC = {  # (url, title, publisher)
    "h_moomin": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_moomintable/", "Moomin: At the Table, Weeks (ENG edition)", "Hobonichi (official)"),
    "h_whitecat": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_kitagishi/", "Yumi Kitagishi: White Cat Wallpaper, Weeks", "Hobonichi (official)"),
    "h_candy": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_m_tiecandy/", "Bow & Tie: Candy Dream, Weeks Mega", "Hobonichi (official)"),
    "h_cousin": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/cb27_jan_en/", "English Cousin Book A5", "Hobonichi (official)"),
    "h_original": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/ob27_jan_en/", "English Original Book A6", "Hobonichi (official)"),
    "h_cathouse": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_kitagishi/", "Yumi Kitagishi: White Cat House, A6 cover", "Hobonichi (official)"),
    "h_myyard": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_moomin/", "Moomin: My Yard, A6 cover", "Hobonichi (official)"),
    "pm_moomin": ("https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-moomin-at-the-table-english", "Hobonichi Techo 2027 Weeks Planner, Moomin: At the Table, English", "The Paper Mouse"),
    "as_whitecat": ("https://www.atlasstationers.com/products/hobonichi-techo-weeks-yumi-kitagishi-white-cat-wallpaper", "Hobonichi Techo Weeks, Yumi Kitagishi: White Cat Wallpaper", "Atlas Stationers"),
    "as_myyard": ("https://www.atlasstationers.com/products/hobonichi-techo-a6-original-planner-cover-moomin-my-yard-pale-mint", "Hobonichi Techo A6 Original cover, Moomin: My Yard (Pale Mint)", "Atlas Stationers"),
    "h_avec": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/cb27_avec/", "Japanese Cousin Avec Books A5, 6-month x 2 book set", "Hobonichi (official)"),
    "h_planner": ("https://www.1101.com/store/techo/en/2027/pc/detail_cover/pb27_jan/", "English Planner Book A6", "Hobonichi (official)"),
    "as_tragen": ("https://www.atlasstationers.com/products/hobonichi-techo-a6-original-planner-cover-tragen-black", "Hobonichi Techo A6 Original Planner Cover, Tragen: Black", "Atlas Stationers"),
    "pm_tragen": ("https://www.thepapermouse.com/products/hobonichi-techo-a6-original-cover-tragen-black", "Hobonichi Techo A6 Original Cover, Tragen (Black)", "The Paper Mouse"),
    "ao_stag": ("https://www.archerandolive.com/products/stag-notebook", "Stag | Notebook", "Archer and Olive (official)"),
    "lt_hc": ("https://www.leuchtturm1917.us/products/hardcover-notebook", "Hardcover Notebook", "Leuchtturm1917 (official)"),
    "lt_ed2": ("https://www.leuchtturm1917.us/products/bullet-journal-edition-2", "Bullet Journal Edition 2", "Leuchtturm1917 (official)"),
    "pm_lt": ("https://www.thepapermouse.com/products/leuchtturm1917-hardcover-dot-grid-a5-notebook-black", "Leuchtturm1917 Hardcover Dot Grid A5 Notebook, Black", "The Paper Mouse"),
    "ao_navy": ("https://www.archerandolive.com/products/storybook-in-navy-books", "Storybook in Navy", "Archer and Olive (official)"),
    "ao_beige": ("https://www.archerandolive.com/products/songbird-in-beige-notebook", "Songbird in Beige", "Archer and Olive (official)"),
    "ao_ice": ("https://www.archerandolive.com/products/ice-castle-notebook", "Ice Castle | Notebook", "Archer and Olive (official)"),
    "ao_train": ("https://www.archerandolive.com/products/winter-train-notebook", "Winter Train | Notebook", "Archer and Olive (official)"),
    "shop": ("shop/", "Our planners and journals", "Stationery Drop Watch"),
}

def gift_listings(key):
    canon, has, _, _ = GIFT_PICKS[key]
    return [p for p in stock["products"] if p.get("canonical") == canon and (not has or has in p["label"])]

def gift_status(key):
    """(badge class, badge text, sentence) for one pick, from this build's stock.json. Never a fixed claim."""
    ls = gift_listings(key)
    if not ls:
        return None
    checked = [l for l in ls if l["status"] != "unknown"]
    if not checked:
        return ("unknown", STATUS["unknown"], "We couldn't check it on our last run.")
    shops = sorted({l["store_id"] for l in checked})
    buy = [l for l in checked if l["status"] in BUYABLE]
    missed = len({l["store_id"] for l in ls} - set(shops))
    tail = f" {nshops(missed)} couldn't be checked this run." if missed else ""
    if len(shops) == 1:  # one shop (the maker's own): count the versions we track there
        shop = checked[0]["store"]
        if buy:
            cls = "in_stock" if any(l["status"] == "in_stock" for l in buy) else "preorder"
            return (cls, STATUS[cls],
                    f"<strong>{len(buy)} of {nshops(len(checked), 'version')}</strong> we track in stock or on preorder at {E(shop)}." + tail)
        if all(l["status"] == "sold_out" for l in checked):
            return ("sold_out", STATUS["sold_out"], f"Sold out at {E(shop)}, the one shop we track for it." + tail)
        return ("coming_soon", STATUS["coming_soon"], f"Not in stock or on preorder at {E(shop)}, the one shop we track for it." + tail)
    bshops = _buy_shops(buy)
    if bshops:
        named = f" ({E(_names(bshops))})" if len(bshops) <= 3 else ""
        cls = "in_stock" if any(l["status"] == "in_stock" for l in buy) else "preorder"
        return (cls, STATUS[cls],
                f"In stock or on preorder at <strong>{len(bshops)} of {len(shops)}</strong> shops we track{named}." + tail)
    if all(l["status"] == "sold_out" for l in checked):
        return ("sold_out", STATUS["sold_out"], f"Sold out at all {len(shops)} shops we track." + tail)
    return ("coming_soon", STATUS["coming_soon"], f"Not in stock or on preorder at any of the {len(shops)} shops we track." + tail)

def gift_glance(key):
    """Short stock cell for the table, from the same data as gift_status: badge plus a shop count."""
    st = gift_status(key)
    if not st:
        return '<span class="muted">Not tracked now</span>'
    cls, badge, _ = st
    ls = gift_listings(key)
    checked = [l for l in ls if l["status"] != "unknown"]
    missed = len({l["store_id"] for l in ls} - {l["store_id"] for l in checked})
    tail = f' <span class="muted small">({missed} not checked)</span>' if missed else ""
    shops = sorted({l["store_id"] for l in checked})
    if not checked:
        text = ""
    elif len(shops) == 1:
        text = f"at {E(checked[0]['store'])}"
    elif cls == "sold_out":
        text = f"at all {len(shops)} shops"
    else:
        text = f"{len(_buy_shops([l for l in checked if l['status'] in BUYABLE]))} of {len(shops)} shops"
    return f'<span class="badge {cls}">{E(badge)}</span> {text}{tail}'

def gift_stock_line(key, live_text=None):
    """Inline live line at the end of a pick: badge from this build's stock.json and a link to its restock
    page. The shop counts are in the table at the top."""
    _, _, live, name = GIFT_PICKS[key]
    st = gift_status(key)
    link = f'<a href="{live}">{E(live_text or "Live stock")}</a>'
    if not st:  # no longer tracked: no availability claim at all
        return f'<span class="small">{link}</span>'
    cls, badge, _ = st
    return f'<span class="small"><span class="badge {cls}">{E(badge)}</span> {link}</span>'

def _usd(cents):
    return f"${cents / 100:,.2f}"

def gift_price(key):
    """Price cell for one pick, from this build's stock.json: the lowest USD price at the shops that had
    it in stock or on preorder at the last check. Never a fixed number; missing prices say so."""
    ls = gift_listings(key)
    if not ls:
        return '<span class="muted">Not tracked now</span>'
    buy = [l for l in ls if l["status"] in BUYABLE]
    # One price per listing: a product whose variants are priced differently (sizes, sets) is left
    # unpriced rather than showing a price that might be another size's.
    priced = [l for l in buy if l.get("currency") == "USD" and isinstance(l.get("price_cents"), int)
              and l["price_cents"] > 0 and "price_max_cents" not in l]
    if priced:
        lo = min(l["price_cents"] for l in priced)
        hi = max(l["price_cents"] for l in priced)
        at_lo = sorted({l["store"] for l in priced if l["price_cents"] == lo})
        shops = _names(at_lo) if len(at_lo) <= 2 else f"{at_lo[0]} +{len(at_lo) - 1} more"
        more = len({l["store"] for l in buy} - {l["store"] for l in priced})
        tail = f' <span class="muted small">· {more} unpriced</span>' if more else ""
        if hi == lo:
            return f'<strong>{_usd(lo)}</strong> at {E(shops)}{tail}'
        return f'<strong>{_usd(lo)}</strong> to {_usd(hi)} <span class="muted small">lowest at {E(shops)}</span>{tail}'
    if buy:
        return '<span class="muted">See price at the shop</span>'
    if all(l["status"] == "unknown" for l in ls):
        return f'<span class="muted">{STATUS["unknown"]}</span>'
    return '<span class="muted">No price: not in stock or on preorder</span>'

GIFT_SALE_ENDS = dt.date(2026, 12, 1)  # last day of the Etsy Cyber sale named in ETSY_PRICE[1]

def gift_today():
    return dt.datetime.now(ET).date()

def etsy_item_price(item):
    """Regular price shown for an Etsy printable: the item's own price, or the shared ETSY_PRICE."""
    return item.get("price", ETSY_PRICE[0])

def gift_shared_price_listings():
    """Etsy printables that use the shared ETSY_PRICE, not a different regular price."""
    return [e for e in etsy_listings() if etsy_item_price(e) == ETSY_PRICE[0]]

def gift_sale_note():
    """The Etsy sale line used on every printables price-table row. Empty once the sale has ended
    (each checker run rebuilds the page, so it comes off on Dec 2 by itself), when /shop drops the
    sale line, or when a shared-price printable isn't on that sale."""
    items = gift_shared_price_listings()
    if not items or gift_today() > GIFT_SALE_ENDS or "% off" not in ETSY_PRICE[1]:
        return ""
    if not all(e.get("sale_confirmed", True) for e in items):
        return ""
    return ETSY_PRICE[1]

def gift_printable_rows():
    """Price-table rows for our Etsy printables, using each listing's data-source price.
    Shared-price printables share one 'Our printables' row. A printable at a different
    regular price gets its own row. Both rows use the same sale line, which drops after Dec 1."""
    items = etsy_listings()
    if not items:
        return []
    rows = []
    sale = gift_sale_note()
    sale_suffix = f", {E(sale)}" if sale else ""
    if gift_shared_price_listings():
        rows.append(
            '<tr><td><a href="shop/">Our printables</a></td>'
            '<td><span class="muted small">Instant download</span></td>'
            f'<td><strong>{E(ETSY_PRICE[0])}</strong> each on Etsy{sale_suffix}</td></tr>'
        )
    seen = set()
    for e in items:
        price = etsy_item_price(e)
        if price == ETSY_PRICE[0]:
            continue
        key = (e.get("id") or e.get("title"), price)
        if key in seen:
            continue
        seen.add(key)
        href = f"shop/#{e['id']}" if e.get("id") else "shop/"
        rows.append(
            f'<tr><td><a href="{E(href)}">{E(e["title"])}</a></td>'
            '<td><span class="muted small">Instant download</span></td>'
            f'<td><strong>{E(price)}</strong> on Etsy{sale_suffix}</td></tr>'
        )
    return rows

# The one place this guide names Traveler's Company or MIDORI: the owner asked (Nov 19, 2026) that the
# traveler section say we meant to feature them, and why we can't. Facts only from the approved notice
# (takedown-2026-11-19/announcement-facts.json); the only quote is the one allowed from their email.
GIFT_NOTE = ("We planned to feature Traveler's Company and MIDORI here. On November 17, we politely asked Traveler's Company "
             "and MIDORI's parent company, Designphil, for permission to use their official product photos. On November 19, "
             "TRAVELER'S COMPANY USA didn't answer that request. Instead, they asked us to remove every Traveler's Company "
             "and MIDORI product, saying that a tracker telling everyone when something is back in stock "
             "\"pushes that stock toward resellers.\" We complied. "
             "Bots don't wait for our email, they're already running auto-checkout. "
             "Want to stop scalpers? Purchase limits. Real bot protection. Fair regional stock. Not shutting down the little guy. "
             "So here's what we'd pack instead.")

def gift_note_html():
    return (f'<aside class="gift-note"><p>{E(GIFT_NOTE)} '
            f'<a href="{TN_SLUG}/">Read the full story</a>.</p></aside>')

def gift_own(asin, label):
    """Our own Amazon book: plain link (data-own-product), no availability claim. Its list price is in the table."""
    return f'<a href="https://www.amazon.com/dp/{E(asin)}" data-own-product rel="noopener" target="_blank">{E(label)}</a>'

def build_gift_guide():
    fname = GIFT_SLUG + "/"
    title = "Stationery gifts that are actually in stock: holiday gift guide 2026"
    desc = ("Planner and journal gifts you can still buy: Hobonichi Weeks, Techo books and covers, Leuchtturm1917, "
            "Archer and Olive, with live stock and prices.")
    missing = [k for k in GIFT_PICKS if not gift_listings(k)]
    if missing:
        print("gift guide: no tracked listings for", ", ".join(missing), "(rendered with no availability claim)")
    def s(*keys):
        return '<span class="small">' + "".join(f'<a href="#src-{k}">[{list(GIFT_SRC).index(k) + 1}]</a>' for k in keys) + "</span>"
    L = gift_stock_line
    asof = time_tag(stock["run_finished"])
    glance = []
    for k, (_, _, live, name) in GIFT_PICKS.items():
        glance.append(f'<tr><td><a href="{live}">{E(name)}</a></td><td>{gift_glance(k)}</td><td>{gift_price(k)}</td></tr>')
    # Our own products: the list prices /shop shows (we set them), and the shared Etsy price line.
    own_rows = [("Our 2027 Planner, Blush or for Men, A5 paperback",
                 AMAZON_LIST_PRICES.get("B0HRTLMZ1M") if AMAZON_LIST_PRICES.get("B0HRTLMZ1M") == AMAZON_LIST_PRICES.get("B0HRTTCH4D") else None),
                ("Our Habit & Mood Tracker Journal", AMAZON_LIST_PRICES.get("B0HQ5TLDK3")),
                ("Our Reading Journal", AMAZON_LIST_PRICES.get("B0HQ5X3C7D")),
                ("Level Up! My 2027 Planner, paperback", AMAZON_LIST_PRICES.get("B0HQW8273V"))]
    own = [f'<tr><td><a href="shop/">{E(n)}</a></td><td><span class="muted small">Ours; not stock-checked</span></td><td>'
           + (f'<strong>{E(lp)}</strong> <span class="muted small">Amazon list price</span>' if lp else '<span class="muted">See price on Amazon</span>') + '</td></tr>'
           for n, lp in own_rows]
    own.extend(gift_printable_rows())
    faq = [
        ("Will these still be in stock when I click?",
         f"Not guaranteed. Stock and prices are from our last check, which runs {CHECK_FREQ}; each pick's restock page shows every shop we track. "
         "If something sells out, sign up for restock emails and we'll tell you when it comes back."),
        ("Are the prices current?",
         "Stock is checked live at every shop we track. Tracked rows link you to the shop for the current price. "
         "Amazon and Etsy prices are the listed prices for our own books and printables."),
    ]
    faq_html = "".join(f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
    src_items = "".join(f'<li id="src-{k}"><a href="{u}"{"" if u == "shop/" else " rel=\"noopener\" target=\"_blank\""}>{E(t)}</a>, {E(b)}.</li>'
                        for k, (u, t, b) in GIFT_SRC.items())
    src_items += f'<li id="src-stock"><a href="data/stock.json">Live stock data</a>, Stationery Drop Watch, last check {asof}.</li>'
    printables = [e for e in etsy_listings() if e.get("id") == "holiday-planner"]
    hp = printables[0] if printables else None
    hp_html = (f'<li><strong>The Holiday Planner Pages,</strong> our printable: ten undated pages in three sizes, including a Gift Tracker, Holiday Budget and December Countdown. '
               f'<a href="{E(etsy_listing_url(hp))}" rel="noopener" target="_blank">See it on Etsy</a></li>') if hp else ""
    levelup = next((e for e in etsy_listings() if e.get("inside") == "levelup-etsy"), None)
    lu_etsy = f' · <a href="{E(etsy_listing_url(levelup))}" rel="noopener" target="_blank">printable on Etsy</a>' if levelup else ""
    body = f"""
<article class="prose guide vs-page">
{crumbs(("guides/", "Guides"), (fname, "Holiday gift guide"))}
{eyebrow("Guide", "Gifts", guide_updated(build_gift_guide))}
<h1>Stationery gifts that are actually in stock</h1>
<p class="lede">Every stock line and price below is from our last check, {asof}, and each pick links to its live restock page. Specs come from the maker's or the shop's own product page.</p>
{signup(label="Get an email when these gifts restock", note=LIST_LINE)}

<h2 id="prices">Every pick: stock and price</h2>
<p class="small"><strong>Stock checked {asof}.</strong> We check stock live at every shop we track, and the counts are those shops. Each tracked row links you to the shop for the current price. Amazon and Etsy prices are the listed prices for our own books and printables.</p>
<div class="table-wrap"><table class="stock gift-table">
<thead><tr><th>Gift</th><th>Stock</th><th>Price</th></tr></thead>
<tbody>{"".join(glance)}{"".join(own)}</tbody></table></div>

<h2 id="hobonichi">For the Hobonichi fan</h2>
<p>Weeks is the easiest Hobonichi gift because the cover is part of the book: the 2027 English Weeks are 188 × 94 × 11 mm, 240 pages of Tomoe River paper, January start, Monday start. {s("h_moomin", "h_whitecat")}</p>
<ul class="picks">
  <li><strong>Weeks, Moomin: At the Table (English).</strong> A scene from <em>Moominsummer Madness</em> around the Moomin family's dinner table, with Little My in a sewing basket on the back; the English version doesn't include the Japanese edition's special illustrations. {s("h_moomin", "pm_moomin")} {L("moomin")}</li>
  <li><strong>Weeks, Yumi Kitagishi: White Cat Wallpaper (English).</strong> A wallpaper-style pattern of the white cat and other animals, with gold-foil flowers and ribbons along the spine. {s("h_whitecat", "as_whitecat")} {L("whitecat")}</li>
  <li><strong>Weeks Mega, Bow &amp; Tie: Candy Dream (English),</strong> for someone who fills every page: candies woven in necktie fabric, 384 pages with 219 grid memo pages in the English edition. {s("h_candy")} {L("candy")}</li>
  <li><strong>English Cousin A5 book,</strong> for the most room: one page per day, 544 pages, thread-stitched so it opens flat. Book only; it takes a Cousin (A5) cover. {s("h_cousin")} {L("cousin")}</li>
  <li><strong>English Original A6 book,</strong> a page a day they can carry: 464 pages with English Daily Quotes and a 3.7 mm grid. Book only, so pair it with an A6 cover. {s("h_original")} {L("original")}</li>
  <li><strong>A6 cover, Yumi Kitagishi: White Cat House.</strong> A dollhouse-themed illustration on polyester, with butterfly-stopper pen holders. {s("h_cathouse")} {L("cathouse")}</li>
  <li><strong>A6 cover, Moomin: My Yard (Pale Mint).</strong> Navy embroidery on pale mint cotton of Moominmamma asleep in her garden, with "We've time for that tomorrow." stitched in pink. {s("h_myyard", "as_myyard")} {L("myyard")}</li>
</ul>
<p class="small">Not sure which book suits them? See <a href="{VS_SLUG}/">Techo vs Cousin vs Weeks</a> or <a href="{JAN_APR_SLUG}/">January-start vs April-start</a>.</p>

<h2 id="journaling">For someone new to journaling</h2>
<ul class="picks">
  <li><strong>Hobonichi Techo 2027 Cousin Avec (A5),</strong> the one my partner and I both use: the A5 Cousin's page a day split into two slim books, January to June and July to December, each 210 × 148 × 10 mm, about 260 g, with 288 pages of Tomoe River paper. The 2027 set is the Japanese edition (Japanese daily quotes and holidays), January start, Monday start, and it takes a Cousin (A5) cover. <a href="{GIFT_SRC["h_avec"][0]}" rel="noopener" target="_blank">See it at the Hobonichi Store</a> {s("h_avec")}</li>
  <li><strong>Our 2027 Planner, Blush (A5).</strong> A calm, blush-toned planner dated January 1 to December 31, 2027, Monday start, with every week across two facing pages and dot grid space for each day; 5.83 × 8.27 in paperback, 174 pages, color interior. {gift_own("B0HRTLMZ1M", "See it on Amazon")}</li>
  <li><strong>Our 2027 Planner for Men (A5).</strong> A clean, no-nonsense planner with a charcoal and navy cover, dated January 1 to December 31, 2027, Monday start, with every week across two facing pages and dot grid space for each day; 5.83 × 8.27 in paperback, 174 pages, color interior. {gift_own("B0HRTTCH4D", "See it on Amazon")}</li>
</ul>

<h2 id="traveler">For the traveler</h2>
{gift_note_html()}
<ul class="picks">
  <li><strong>English Planner A6 book,</strong> a page a day in A6 size: 148 × 105 × 15 mm, about 190 g, 448 pages of Tomoe River paper, with The Ultimate Packing List and International Size Charts in the back. Book only, so pair it with an A6 cover. {s("h_planner")} {L("plannera6")}</li>
  <li><strong>A6 cover, Tragen: Black.</strong> A black nylon cover with a zippered pocket for pens and a loop for a pen's clip; it holds an A6 Original or Planner book, sold separately. {s("as_tragen", "pm_tragen")} {L("tragen")}</li>
  <li><strong>Archer and Olive Stag, pocket size.</strong> A midnight blue vegan leather hardcover with a gold-foil stag; 112 pages of 160 gsm dot grid paper, lay-flat binding, pen loop and elastic band. {s("ao_stag")} {L("aostag")}</li>
</ul>

<h2 id="dot-grid">For the dot grid journaler</h2>
<ul class="picks">
  <li><strong>Leuchtturm1917 Hardcover Medium (A5), dotted.</strong> 251 numbered pages of 80 gsm paper, a blank table of contents, two page markers, a pocket and an elastic band. {s("lt_hc", "pm_lt")} {L("lta5")}</li>
  <li><strong>Leuchtturm1917 Bullet Journal Edition 2,</strong> for heavier paper: A5 hardcover, dotted, 206 numbered pages of 120 gsm paper. {s("lt_ed2")} {L("lted2")}</li>
  <li><strong>Archer and Olive Storybook in Navy, A5.</strong> Vegan leather with gold detailing; 192 pages of 160 gsm dot grid paper. {s("ao_navy")} {L("aonavy")}</li>
  <li><strong>Archer and Olive Songbird in Beige, B5.</strong> Vegan leather, 160 gsm paper, lay-flat binding, 160 pages. {s("ao_beige")} {L("aobeige")}</li>
  <li><strong>Archer and Olive Ice Castle, A5,</strong> a winter design: an icy blue vegan leather hardcover with a frozen castle in platinum foil and gilded page edges; 192 pages of 160 gsm dot grid paper, lay-flat binding, elastic band and pen loop. {s("ao_ice")} {L("aoice")}</li>
  <li><strong>Archer and Olive Winter Train, A5,</strong> a winter design: a deep olive-green vegan leather hardcover with a steam train through a snowy village in gold and white foil; 192 pages of 160 gsm dot grid paper, lay-flat binding, elastic band and pen loop. {s("ao_train")} {L("aotrain")}</li>
</ul>
<p class="small">More options: <a href="{DG_GUIDE_SLUG}/">Best dot grid journals compared</a>.</p>

<h2 id="small-gifts">Small gifts and stocking stuffers</h2>
<ul class="picks">
  {hp_html}
</ul>

<h2 id="we-make">Planners and journals we make</h2>
<p class="small">List prices for our books are in the table above. {s("shop")}</p>
<ul class="picks">
  <li><strong>2027 Planners, Blush and for Men:</strong> the A5 editions are under <a href="#journaling">For someone new to journaling</a>. For Men also comes as an {gift_own("B0HP9PXSR1", "8.5 × 11 Sunday-start paperback")}.</li>
  <li><strong>Level Up! My 2027 Planner,</strong> for a child aged 7 to 11: a kids planner that plays like a video game, with a Reading Quest Log, Trophy Room and Coin Bank; 8.5 × 11 in. {gift_own("B0HQW8273V", "Paperback on Amazon")}{lu_etsy}</li>
  <li><strong>Undated journals:</strong> {gift_own("B0HQ5TLDK3", "Habit & Mood Tracker Journal")} (6 × 9 in, 166 pages) · {gift_own("B0HQ5X3C7D", "Reading Journal")} (7 × 10 in, 152 pages).</li>
</ul>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources two-col">{src_items}</ol>
{related_block(fname)}
</article>"""
    upd = json.loads(GUIDE_DATES.read_text())["build_gift_guide"]["date"]
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title,
           "datePublished": upd, "dateModified": upd, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    doc = page(fname, title + TITLE_SUFFIX, desc, body,
               ld=(crumbs_ld(("guides/", "Guides"), (fname, "Holiday gift guide")), art, faq_ld), og_type="article")
    check_none_claim(fname, doc)
    return fname, doc


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
                       "Guides on where to buy Hobonichi 2027, Techo vs Cousin vs Weeks, the launch calendar, dot grid journals compared and holiday gifts.",
                       body, ld=(crumbs_ld((fname, "Guides")), lst))

# Soft Days listing confirmed by the owner on 2026-11-06.
# Public permalink is the url below. The shopwide sale applies, so the card uses the
# same price line as the other Etsy printables: regular $6.99 plus "25% off all listings, Cyber sale
# Nov 23 to Dec 1". Do not print the intro amount (it would read as the lasting price),
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
                  "Printable PDF. The paperback is a separate book on this page.",
                  "Personal-use edition on Etsy. The classroom-license editions are on Teachers Pay Teachers."]),
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
    # Listed 2026-11-13. Same card as the other Etsy tip-ins: regular $6.99 and the shared
    # launch-sale note. Do not print the sale price or the sale code.
    dict(id="holiday-planner", kind="insert", sale_confirmed=True, price="$6.99",
         title="The Holiday Planner Pages",
         img="assets/shop/holiday-planner-pages-600.webp", img_class="sheet", img_w=600, img_h=600,  # 2000px original kept beside it
         url="https://www.etsy.com/listing/4616108634/holiday-planner-printable-tip-ins-gift",
         alt=("The Holiday Planner Pages: three cream covers labeled Narrow Weekly 85 × 175 mm, "
              "Pocket A6 95 × 138 mm, and Standard A5 138 × 198 mm, each with a green wreath and a snowflake."),
         sub="Printable holiday tip-ins · personal use · instant download from Etsy",
         hub_sub="Printable tip-ins",
         blurb=("Ten undated pages in three sizes: Narrow Weekly 85 × 175 mm, Pocket A6 95 × 138 mm, and Standard A5 138 × 198 mm. "
                "Seven trackers and planners, plus a cover, a branding page, and a printing and tip-in guide. "
                "A digital download for personal use."),
         details=["Three sizes, 10 pages each: Narrow Weekly 85 × 175 mm, Pocket A6 95 × 138 mm, and Standard A5 138 × 198 mm",
                  "For each size: a US Letter file and an A4 file, with crop marks, dashed cut lines, and 25 mm / 1 inch scale bars, plus a single-page PDF at the exact trim size",
                  "Narrow Weekly and Pocket A6 print 2 pages per sheet. Standard A5 prints 1 page per sheet",
                  "Undated. Print at actual size (100%), then tip in with washi tape or a thin line of glue",
                  "Personal use only: don't share, resell, or redistribute the PDFs",
                  "Digital download only. Not a physical planner, and not affiliated with any planner brand."],
         templates=["Gift Tracker", "Holiday Budget", "Order & Package Tracker", "Card Mailing List",
                    "Party & Menu Planner", "Baking & Meal Prep Timeline", "December Countdown & Bucket List"],
         templates_label="7 trackers & planners",
         inside="holiday-planner"),
    # Listed 2026-11-18. Same card as the other Etsy tip-ins: regular price and the shared
    # launch-sale note. Do not print the sale price or the sale code.
    dict(id="happy-mail", kind="insert", sale_confirmed=True, price="$5.99",
         title="Happy Mail & Washi Club",
         img="assets/shop/happy-mail-washi-club.webp", img_class="sheet", img_w=2000, img_h=2000,
         url="https://www.etsy.com/listing/4620269140/happy-mail-washi-club-printable-tip-ins",
         alt=("Happy Mail & Washi Club: four fanned cream tip-in sheets titled Washi Swatch Club, "
              "Happy Mail Tracker, Snapshot Memories, and Color Palette Lab, on a pale pink background. "
              "The header reads \"4 printable tip-ins · washi swatches · happy mail · snapshots · palettes\" "
              "and \"85 × 175 mm tip-ins for 94 × 188 mm slim weekly planners\"."),
         sub="Printable paper tip-ins · personal use · instant download from Etsy",
         hub_sub="Printable tip-ins",
         blurb=("Four cozy pastel tip-ins you print, cut, and tip in yourself, with a little bunny mascot "
                "on every page: a washi swatch, a happy mail tracker, snapshot memories, and a color palette lab. "
                "Finished cut size is 85 × 175 mm (3.35 × 6.89 in). A digital download for personal use."),
         details=["Four print PDFs, 3 pages each: US Letter and A4, cream and white editions, plus a 1-page printing guide",
                  "Two tip-ins per US Letter or A4 sheet. Print at actual size (100%) and measure the 50 mm scale check bar before you trim",
                  "Each tip-in trims to 85 × 175 mm, including a 4 mm hinge strip on the left edge for washi tape or glue. Sized for planners with a 94 × 188 mm (3.7 × 7.4 in) cover. Planner sizes vary, so please measure yours or test-print on plain paper first",
                  "Personal use only: don't share, resell, or redistribute the PDFs",
                  "Digital download only. Not a physical planner. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Washi Swatch Club", "Happy Mail Tracker", "Snapshot Memories", "Color Palette Lab"],
         templates_label="4 tip-ins",
         inside="happy-mail"),
    dict(id="seasonal-dashboards", kind="insert", sale_confirmed=True, price="$6.99",
         title="Seasonal Reset Dashboards & Slip Pocket",
         img="assets/shop/seasonal-reset-dashboards.webp", img_class="sheet", img_w=2000, img_h=2000,
         url="https://www.etsy.com/listing/4620269960/seasonal-reset-dashboard-printable",
         alt=("Seasonal Reset Dashboards: four fanned cream tip-in sheets titled Spring, Summer, Autumn, "
              "and Winter, each with a line-art arch illustration and a CURRENTLY section, on a pale background. "
              "The header reads \"FOUR PRINTABLE TIP-INS · CUT-AND-FOLD SLIP POCKET\" "
              "and \"85 × 175 mm tip-ins for 94 × 188 mm slim weekly planners\"."),
         sub="Printable paper tip-ins · personal use · instant download from Etsy",
         hub_sub="Printable tip-ins",
         blurb=("Four calm, minimal seasonal reset dashboards to tip into your weekly planner, plus a "
                "cut-and-fold slip pocket for the inside cover. Dashboards trim to 85 × 175 mm (3.35 × 6.89 in). "
                "The slip pocket is 84 × 138 mm (3.31 × 5.43 in) when folded. A digital download for personal use."),
         details=["Four print PDFs, 4 pages each: US Letter and A4, cream and no-fill editions, plus a 2-page printing and assembly guide",
                  "Dashboards print two per US Letter or A4 sheet. Print at actual size (100%) and measure the 50 mm scale check bar before you trim",
                  "Dashboards trim to 85 × 175 mm, including a 4 mm hinge strip on the left edge for washi tape, a vellum strip or glue. The slip pocket is 84 × 138 mm when folded. Sized for planners with a 94 × 188 mm (3.7 × 7.4 in) cover. Planner sizes vary, so please measure yours or test-print on plain paper first",
                  "The no-fill edition is line art only, for vellum or white paper. On vellum, print the no-fill edition",
                  "Personal use only: don't share, resell, or redistribute the PDFs",
                  "Digital download only. Not a physical planner. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Spring", "Summer", "Autumn", "Winter", "Slip pocket"],
         templates_label="4 dashboards & slip pocket",
         inside="seasonal-dashboards"),
]


# Teachers Pay Teachers is two collection cards. Individual listings stay on the store,
# so a new listing does not need a site change. No prices, and no bundle listing.
TPT_STORE = "https://www.teacherspayteachers.com/store/stationery-drop-watch"
_TPT_LISTING = re.compile(r"^https://www\.teacherspayteachers\.com/Product/[A-Za-z0-9-]+$")
_TPT_STORE = re.compile(r"^https://www\.teacherspayteachers\.com/store/[a-z0-9-]+$")
def _tile(stem, alt, url):
    """A square listing cover: 600px file, with a 300px srcset candidate for phones."""
    return dict(src=f"/assets/shop/tiles/{stem}-600.webp", src300=f"/assets/shop/tiles/{stem}-300.webp",
                w=600, h=600, alt=alt, url=url)

SHOP_TPT = [
    dict(id="level-up-collection",
         title="Level Up!",
         blurb="Pixel-art, video-game classroom printables for grades 2-5.",
         url=TPT_STORE,
         tiles=[
             _tile("level-up-student-planner",
                   "Level Up! 2027 Student Planner cover: pixel-art title, sample planner pages, grades 2-5, 170 pages, Monday start.",
                   "https://www.teacherspayteachers.com/Product/Level-Up-2027-Student-Planner-Video-Game-Theme-Printable-Planner-Grades-2-5-18365192"),
             _tile("level-up-goal-quest",
                   "Level Up! Goal Setting Quest Pack cover: pixel-art title, a goal sheet, an XP tracker, and achievement badges.",
                   "https://www.teacherspayteachers.com/Product/Level-Up-Goal-Setting-Quest-Pack-Video-Game-Theme-Goal-Habit-Trackers-18365256"),
             _tile("level-up-end-of-year",
                   "Level Up! End of Year and Summer Review cover: pixel-art title, a word search, a math page, and a logic grid.",
                   "https://www.teacherspayteachers.com/Product/Level-Up-End-of-Year-Review-Packet-Video-Game-Theme-Summer-Review-Puzzles-18365295"),
             _tile("level-up-classroom-kit",
                   "Level Up! Classroom Quest Kit cover: pixel-art title, a reading map, a rank ladder, and brag tags.",
                   "https://www.teacherspayteachers.com/Product/Level-Up-Classroom-Quest-Kit-Video-Game-Reading-Log-XP-Chart-Brag-Tags-18365332"),
         ]),
    dict(id="cute-pastel-collection",
         title="Cute Pastel",
         blurb="Soft pastel picture supports for PreK-2 and special ed.",
         url=TPT_STORE,
         tiles=[
             _tile("cute-pastel-visual-schedule",
                   "Cute Pastel Visual Schedule Cards cover: kawaii routine cards for arrival, circle time, lunch, and recess.",
                   "https://www.teacherspayteachers.com/Product/Cute-Pastel-Visual-Schedule-Cards-43-Kawaii-Daily-Routine-Cards-PreK2-SpEd-18381500"),
             _tile("cute-pastel-first-then",
                   "Cute Pastel First/Then and Now/Next boards cover: a Work First card and a Sticker reward.",
                   "https://www.teacherspayteachers.com/Product/Cute-Pastel-First-Then-Now-Next-Boards-Kawaii-Visual-Supports-Reward-Cards-18381421"),
             _tile("cute-pastel-classroom-labels",
                   "Cute Pastel Classroom Labels cover: crayon, marker, reading center, and name labels.",
                   "https://www.teacherspayteachers.com/Product/Cute-Pastel-Classroom-Labels-Editable-Kawaii-Supply-Bin-Labels-with-Pictures-18381372"),
             _tile("cute-pastel-calm-down",
                   "Cute Pastel Calm Down Corner Kit cover: a calm corner poster and breathing shape cards.",
                   "https://www.teacherspayteachers.com/Product/Cute-Pastel-Calm-Down-Corner-Kit-Kawaii-Breathing-Cards-Calm-Choices-SEL-18381516"),
         ]),
]

# FIX-06: prices on /shop. Amazon list prices were read from each product's own amazon.com page on
# 2026-11-04 (buy box and format swatch; no strikethrough or deal shown). A None here shows "See price on Amazon".
# A missing ASIN, or a None value, shows "See price on Amazon".
# B0HRTLMZ1M and B0HRTTCH4D list prices were $14.99 on their Amazon pages on 2026-11-16
# (07:57 AM ET / America/Detroit; both In Stock). Owner asked to show $14.99 on both cards.
# B0HQW8273V (Level Up! paperback) was $19.99 in the buy box and Paperback swatch on its Amazon page
# on 2026-11-16 (11:48 AM ET). Owner approved showing it in the same format as the other cards.
AMAZON_LIST_PRICES = {"B0HPBDNS7F": "$19.99", "B0HQ5TLDK3": "$14.99", "B0HQ5X3C7D": "$16.99",
                      "B0HP9PXSR1": "$14.99", "B0HRTLMZ1M": "$14.99", "B0HRTTCH4D": "$14.99",
                      "B0HQW8273V": "$19.99"}
SHOP_LABELS = {"B0HRTLMZ1M": "2027 Planner, Blush", "B0HQ5TLDK3": "Habit & Mood Tracker Journal", "B0HQ5X3C7D": "Reading Journal",
               "B0HRTTCH4D": "2027 Planner for Men", "B0HQW8273V": "Level Up! My 2027 Planner"}
SHOP_ORDER = ("B0HRTLMZ1M", "B0HQ5TLDK3", "B0HQ5X3C7D", "B0HRTTCH4D", "B0HQW8273V")
# Optional note under the detail bullets. The 8.5x11 editions remain linked notes on
# the A5 cards, not featured cards of their own. Link text matches the owner-approved phrasing.
SHOP_ALSO = {
    "B0HRTLMZ1M": {
        "before": "Also comes in ",
        "link_text": "8.5x11 hardcover, Sunday start",
        "url": "https://www.amazon.com/dp/B0HPBDNS7F",
    },
    "B0HRTTCH4D": {
        "before": "Also comes in ",
        "link_text": "8.5x11 paperback, Sunday start",
        "url": "https://www.amazon.com/dp/B0HP9PXSR1",
    },
}
ETSY_PRICE = ("$6.99", "25% off all listings, Cyber sale Nov 23 to Dec 1")
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

def _local_img_dim(src):
    """Pixel size of a site-local cover, so a lazy image reserves its box (no width/height left it 0px tall and it could
    stay blank). Returns None for a missing file or an external URL."""
    path = ROOT / "site" / src.split("?")[0].lstrip("/")
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None

SHOP_INSIDE = {
    "B0HRTLMZ1M": [("january-month-pages", "January calendar and Goals & Priorities pages"),
                   ("weekly-spread-dec28-2026-jan3-2027", "Weekly spread, Dec 28, 2026 to Jan 3, 2027")],
    "B0HRTTCH4D": [("january-month-pages", "January calendar and Goals & Priorities pages"),
                   ("weekly-spread-dec28-2026-jan3-2027", "Weekly spread, Dec 28, 2026 to Jan 3, 2027")],
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
                "Level Up! printable planner sample page: January 2027 Monday-start World Map calendar.",
                "January 2027 calendar, page 9. Sample from the printable PDF.", 812, 1050),
        _sample("/assets/shop/inside/levelup-etsy-p012.webp",
                "Level Up! printable planner sample page: Week 2 dated Monday-start Week Plan.",
                "Week 2 plan, January 4 to 10, page 12. Sample from the printable PDF.", 812, 1050),
        _sample("/assets/shop/inside/levelup-etsy-p013.webp",
                "Level Up! printable planner sample page: Week 2 Save Point with habit tracker, mood and XP.",
                "Week 2 save point, page 13. Sample from the printable PDF.", 812, 1050),
    ]},
    "B0HQW8273V": {
        "class": " samples",
        "note": "Sample pages from the print-ready file, not photographs of a printed copy.",
        "items": [
        _sample("/assets/shop/inside/levelup-print-p009.webp",
                "Level Up! paperback planner sample page: January 2027 Monday-start World Map calendar.",
                "January 2027 calendar, page 9.", 812, 1050),
        _sample("/assets/shop/inside/levelup-print-p012.webp",
                "Level Up! paperback planner sample page: Week 2 dated Monday-start Week Plan.",
                "Week 2 plan, January 4 to 10, page 12.", 812, 1050),
        _sample("/assets/shop/inside/levelup-print-p013.webp",
                "Level Up! paperback planner sample page: Week 2 Save Point with habit tracker, mood and XP.",
                "Week 2 save point, page 13.", 812, 1050),
    ]},
    "soft-days": {"class": " samples inserts", "items": [
        _sample("/assets/shop/inside/softdays-weekly-color.webp",
                "Soft Days printable insert sample, soft colour: Weekly Plan, Monday start.",
                "Weekly Plan, Monday start. Sample of a colour insert.", 511, 1051),
        _sample("/assets/shop/inside/softdays-habit-gray.webp",
                "Soft Days printable insert sample, grayscale: Habit Tracker with six-habit key.",
                "Habit Tracker. Sample of a grayscale insert.", 511, 1051),
        _sample("/assets/shop/inside/softdays-swatches-color.webp",
                "Soft Days printable insert sample, soft colour: Pen & Ink Swatches.",
                "Pen & Ink Swatches. One Soft Days insert, not a separate swatch product.", 511, 1051),
    ]},
    "lines-grid": {"class": " samples inserts", "note": "Layouts from the print file, not a photograph of a printed copy.", "items": [
        _sample("/assets/shop/inside/lines-grid-layouts.webp",
                "Lines for the Grid Page print file: the liner layouts, including ruled pages, task lines, Cornell notes, a habit tracker, a weekly overlay, and a dot grid, in Warm and Soft Gray.",
                "The 13 layouts, from the print file.", 2700, 2025),
    ]},
    "holiday-planner": {"class": " samples inserts", "note": "Layouts from the print file, not a photograph of a printed copy.", "items": [
        _sample("/assets/shop/inside/holiday-planner-layouts.webp",
                "The Holiday Planner Pages print file: Gift Tracker, Holiday Budget, Order and Package Tracker, Card Mailing List, Party and Menu Planner, Baking and Meal Prep Timeline, and December Countdown, shown in Standard A5.",
                "The 7 trackers and planners, shown in Standard A5. The same layouts come in Narrow Weekly and Pocket A6.", 2700, 2025),
    ]},
    "happy-mail": {"class": " samples inserts", "note": "Layouts from the print file, not a photograph of a printed copy.", "items": [
        _sample("/assets/shop/inside/happy-mail-washi-club-included.webp",
                "Happy Mail & Washi Club print file: Sheet 1 and Sheet 2 in the cream and white editions, showing Washi Swatch Club, Happy Mail Tracker, Snapshot Memories, and Color Palette Lab.",
                "The four tip-ins, shown as cream and white print sheets.", 2000, 2000),
    ]},
    "seasonal-dashboards": {"class": " samples inserts", "note": "Layouts from the print file, not a photograph of a printed copy.", "items": [
        _sample("/assets/shop/inside/seasonal-reset-dashboards-included.webp",
                "Seasonal Reset Dashboards print file: Spring and Summer, Autumn and Winter, the slip pocket template, and the no-fill edition for vellum.",
                "The four dashboards, the slip pocket, and the no-fill edition, from the print file.", 2000, 2000),
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

def tpt_listing_url(item):
    """A plain Teachers Pay Teachers product URL, with no tracking query."""
    url = (item.get("url") or "").strip()
    if not _TPT_LISTING.match(url):
        raise SystemExit(f"{item.get('title', 'TpT item')}: listing URL must be a plain https://www.teacherspayteachers.com/Product/... link")
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
    # Shop facts changed 2026-11-18 (Happy Mail & Washi Club and Seasonal Reset Dashboards).
    if any(e.get("id") in {"happy-mail", "seasonal-dashboards"} and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-18"
    # Shop facts changed 2026-11-17 (Teachers Pay Teachers section is two collection cards).
    if SHOP_TPT:
        return "2026-11-17"
    # Shop facts changed 2026-11-13 (The Holiday Planner Pages listing).
    if any(e.get("id") == "holiday-planner" and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-13"
    # Shop facts changed 2026-11-10 (Lines for the Grid Page listing). The Nov 12
    # refresh changed the page HTML, so the sitemap floor is that later date.
    if any(e.get("id") == "lines-grid" and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-12"
    if any(e.get("kind") == "insert" and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-08"
    return "2026-11-03"

HOLIDAY_CARD_ENDS = dt.date(2026, 12, 31)  # last day the Hobonichi tracker shows The Holiday Planner Pages

def site_today():
    """Calendar date for this build, in Eastern Time, the same zone as other site dates."""
    return dt.datetime.now(ET).date()

def shop_item(item_id):
    """A live /shop Etsy item, or None when that listing is not in this build."""
    return next((e for e in etsy_listings() if e.get("id") == item_id), None)

def _require_shop_phrases(item, source, phrases):
    for phrase in phrases:
        if phrase not in source:
            raise SystemExit(f"{item['title']}: made-by-us copy is missing source phrase {phrase!r}")

def made_by_us_markup(item, body, disclaimer):
    """A small, understated card. Plain Etsy link, no price or sale line."""
    url = etsy_listing_url(item)
    if not url:
        return ""
    img = "/" + item["img"].lstrip("/")
    dims = ""
    if item.get("img_w") and item.get("img_h"):
        dims = f' width="{int(item["img_w"])}" height="{int(item["img_h"])}"'
    sheet = " sheet" if item.get("img_class") == "sheet" else ""
    return f"""<aside class="card made-by-us" id="made-by-us-{E(item['id'])}" aria-label="Made by us">
  <a class="made-by-us-thumb shop-img{sheet}" href="{E(url)}" rel="noopener" target="_blank">
    <img src="{E(img)}" alt="{E(item['alt'])}"{dims} loading="lazy" decoding="async">
  </a>
  <div class="made-by-us-body">
    <p class="eyebrow">Made by us</p>
    <h2>{E(item['title'])}</h2>
    <p>{E(body)}</p>
    <p class="muted small">{E(disclaimer)}</p>
    <a class="btn" href="{E(url)}" rel="noopener" target="_blank">View on Etsy</a>
  </div>
</aside>"""

def lines_grid_card():
    """Weeks tracker card. Every sentence is stitched from the existing /shop item."""
    item = shop_item("lines-grid")
    if not item:
        return ""
    source = " ".join((item.get("sub") or "", item.get("blurb") or "", *(item.get("details") or [])))
    lead, layouts = "Printable tip-in liners", "13 undated layouts"
    fit = ("Finished cut size is 85 × 175 mm, drawn for a narrow weekly planner whose book is "
           "about 94 × 188 mm, including the Hobonichi Weeks")
    digital = "A digital download for personal use"
    disc = "Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."
    _require_shop_phrases(item, source, (lead, layouts, fit, digital, disc.rstrip(".")))
    return made_by_us_markup(item, f"{lead} in {layouts}. {fit}. {digital}.", disc)

def holiday_planner_card(today=None):
    """Hobonichi tracker card. Present through Dec 31, 2026; omitted on later builds."""
    if (today if today is not None else site_today()) > HOLIDAY_CARD_ENDS:
        return ""
    item = shop_item("holiday-planner")
    if not item:
        return ""
    source = " ".join((item.get("sub") or "", item.get("blurb") or "", *(item.get("details") or [])))
    lead = "Printable holiday tip-ins"
    sizes = "Narrow Weekly 85 × 175 mm, Pocket A6 95 × 138 mm, and Standard A5 138 × 198 mm"
    pages, digital = "Ten undated pages", "A digital download for personal use"
    disc = "Not a physical planner, and not affiliated with any planner brand."
    _require_shop_phrases(item, source, (lead, sizes, pages, digital, disc.rstrip(".")))
    return made_by_us_markup(item, f"{lead} in three sizes: {sizes}. {pages}. {digital}.", disc)

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
    for item in SHOP_TPT:
        if not _TPT_STORE.match(item["url"]):
            raise SystemExit(f"{item['title']}: store URL must be a plain teacherspayteachers.com/store link")
        if len(item.get("tiles") or []) != 4:
            raise SystemExit(f"{item['title']}: a collection card has four covers")
        for tile in item["tiles"]:
            if not _TPT_LISTING.match(tile["url"]):
                raise SystemExit(f"{item['title']}: cover URL must be a plain product link")
            for key in ("src", "src300"):
                if not (SITE / tile[key].lstrip("/")).is_file():
                    raise SystemExit(f"missing shop asset {tile[key]}")
    def srcset(img):  # Etsy mockups ship 600w + 1200w copies; Amazon covers use their single file
        if img.startswith("assets/shop/") and img.endswith("-planner.jpg"):
            b = img[:-4]
            return f' srcset="/{E(b)}-600.jpg 600w, /{E(b)}-1200.jpg 1200w"'
        if img == "assets/shop/soft-days-narrow-inserts-900.webp":
            return (' srcset="/assets/shop/soft-days-narrow-inserts-900.webp 900w, '
                    '/assets/shop/soft-days-narrow-inserts-1800.webp 1800w"')
        return ""
    def card(img, alt, title, sub, blurb, details, href, btn, own, price, inside=None, *,
             img_class="", dims=None, note="", templates=None, templates_label="Templates", card_id="",
             also=None, thumbs=None, sizes="", collapse_details=False):
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
                # Amazon ASIN interiors are two landscape page images and stack in one column,
                # whether or not a list price is on the card. Etsy womens/mens keys stay 2-up.
                grid = "inside-grid" + (" spreads" if inside.startswith("B0") else "")
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
        if not dims and img:
            dims = _local_img_dim(img)
        dim = f' width="{int(dims[0])}" height="{int(dims[1])}"' if dims else ""
        img_sizes = sizes or "(max-width:600px) 240px, 150px"
        image = f'<img src="{E(img)}"{srcset(img)}{dim} sizes="{E(img_sizes)}" alt="{E(alt)}" loading="lazy" decoding="async">'
        if href:
            media = f'<a class="{cls}" href="{E(href)}"{attr} rel="noopener" target="_blank">{image}</a>'
            action = f'<a class="btn" href="{E(href)}"{attr} rel="noopener" target="_blank">{E(btn)}</a>'
        else:
            media = f'<div class="{cls}">{image}</div>'
            action = f'<p class="btn is-disabled" role="note">{E(btn)}</p>'
        note_html = f'<p class="release-gate">{E(note)}</p>' if note else ""
        also_html = ""
        if also:
            also_html = (
                f'<p class="muted small">{E(also["before"])}'
                f'<a href="{E(own_amazon_link(also["url"]))}" data-own-product rel="noopener" target="_blank">'
                f'{E(also["link_text"])}</a></p>'
            )
        idattr = f' id="{E(card_id)}"' if card_id else ""
        sub_html = f'<p class="muted small">{E(sub)}</p>' if sub else ""
        list_html = f'<ul class="small">{dl}</ul>' if details else ""
        if list_html and collapse_details:
            list_html = f'<details class="shop-inside"><summary>Details</summary>{list_html}</details>'

        thumb_html = ""
        if thumbs:
            links = "".join(
                f'<a href="{E(t["url"])}" rel="noopener" target="_blank">'
                f'<img src="{E(t["src"])}" srcset="{E(t["src300"])} 300w, {E(t["src"])} 600w" '
                f'sizes="(max-width:760px) calc((100vw - 64px) / 2), 220px" '
                f'alt="{E(t["alt"])}" width="{t["w"]}" height="{t["h"]}" loading="lazy" decoding="async"></a>'
                for t in thumbs)
            thumb_html = f'<div class="collection-grid">{links}</div>'
        # A collection has no separate cover. The product grid leads the card.
        if not img and thumb_html:
            media = thumb_html
            thumb_html = ""
        return f"""<li class="shop-card"{idattr}>
  {media}
  <div class="shop-body">{note_html}<h3>{E(title)}</h3>{sub_html}{price}<p>{E(blurb)}</p>{also_html}{list_html}
  {ins}{thumb_html}{action}</div></li>"""
    def amz_price(a):
        lp = AMAZON_LIST_PRICES.get(a)
        if not lp:
            return '<p class="shop-price"><span class="muted">See price on Amazon</span></p>'
        return f'<p class="shop-price"><strong>{E(lp)}</strong> <span class="muted small">List price, check current price on Amazon</span></p>'
    amz = "".join(card(books[a]["cover"], books[a]["cover_alt"], labels[a], books[a]["format"] + " · on Amazon",
                       books[a].get("blurb", ""), books[a].get("details", []), own_amazon_link(books[a]["url"]), "View on Amazon", True,
                       amz_price(a), a if a in SHOP_INSIDE or a in SHOP_SAMPLES else None,
                       dims=(books[a]["cover_w"], books[a]["cover_h"]) if books[a].get("cover_w") and books[a].get("cover_h") else None,
                       also=SHOP_ALSO.get(a), collapse_details=True)
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
                    "The price shown is the approved regular price, US$6.99. sale eligibility is not confirmed.")
        return card(item["img"], item["alt"], item["title"], sub, item["blurb"],
                    item.get("details", ["US Letter 8.5 x 11 in", "172 pages"]), url, btn, False, etsy_price_html(item),
                    item.get("inside"), img_class=item.get("img_class", ""),
                    dims=(item["img_w"], item["img_h"]) if item.get("img_w") and item.get("img_h") else None,
                    note=note, templates=item.get("templates"), templates_label=item.get("templates_label", "Templates"),
                    card_id=item.get("id", ""), collapse_details=True)
    def tpt_card(item):
        return card("", "", item["title"], "", item["blurb"],
                    [], item["url"], "See the collection on TpT", False, "",
                    card_id=item.get("id", ""), thumbs=item.get("tiles"))
    etsy = "".join(etsy_card(e) for e in etsy_listings())
    tpt = "".join(tpt_card(e) for e in SHOP_TPT)
    if shop_inserts_public():
        lede = ("Planners, journals, and printable pages we make. Printed books are on Amazon. "
                "Printable PDFs and tip-ins are on Etsy. Classroom printables are on Teachers Pay Teachers.")
        title = "Our planners and journals"
        desc = ("Planners and journals from Stationery Drop Watch: printed books on Amazon, printable PDFs on Etsy, "
                "and classroom printables on Teachers Pay Teachers.")
        etsy_intro = '<p class="muted">Printable planner PDFs, and undated paper tip-ins you print and cut yourself.</p>'
    else:
        lede = ("Planners and journals we make. Printed books are on Amazon, printable PDFs are on Etsy, "
                "and classroom printables are on Teachers Pay Teachers.")
        title = "Our planners and journals"
        desc = ("Planners and journals from Stationery Drop Watch: printed books on Amazon, printable PDFs on Etsy, "
                "and classroom printables on Teachers Pay Teachers.")
        etsy_intro = ""
    tpt_intro = "Printable classroom resources from our Teachers Pay Teachers store."
    body = f"""
<article class="prose shop shop-wide">
{crumbs((fname, "Shop"))}
{eyebrow("Shop", "made by Stationery Drop Watch")}
<h1>{SHOP_NAME}</h1>
<p class="lede">{E(lede)}</p>
{signup("shop")}
<h2>Printed planners and journals on Amazon</h2>
<ul class="shop-list">{amz}</ul>
<h2>Printable PDFs on Etsy</h2>
{etsy_intro}<ul class="shop-list">{etsy}</ul>
<h2 id="classroom-printables">Classroom printables on Teachers Pay Teachers</h2>
<p class="muted">{E(tpt_intro)}</p>
<ul class="shop-list">{tpt}</ul>
</article>"""
    return fname, page(fname, title, desc, body, ld=(crumbs_ld((fname, "Shop")),))

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

# --- Limited-edition fountain pen ink tracker ----------------------------------------------------------
# Rows come from data/inks/stock.json (scripts/ink_tracker.py), filtered to owner-approved inks in inks.json.
# Only shop + brand pairs on each brand's own dealer list are tracked. Ink restock emails go to the Kit 'inks' tag.
INK_HUB_LINE = "Diamine Inkvent, Sailor Manyo and other limited inks, at shops on each brand's own dealer list."
INK_FAQ_TRACK = ("On a separate limited inks page, we track limited-edition fountain pen inks from Diamine and Sailor, "
                 "only at shops on each brand's own dealer list. Ink restocks show on that page, and you can get them by email.")
INK_DEALER_LABEL = {"diamine": "Diamine's retailer list", "sailor": "Sailor's dealer list", "robert-oster": "Robert Oster's where-to-buy page"}
INK_INTRO = ("Limited, seasonal and shop-exclusive fountain pen inks, checked at shops that each brand lists as its own dealer. "
             "We show what each shop's product data says, including inks that aren't on sale yet.")

def ink_shops():
    ids = {r["store_id"] for r in INK_ROWS}
    return [s for s in stores["stores"] if s["id"] in ids]

def ink_shop_names():
    return names_and([s["name"] for s in ink_shops()])

def ink_lastmod():
    return latest(*[r.get("status_since") for r in INK_ROWS], *[r.get("first_seen") for r in INK_ROWS],
                  *[c["at"] for c in INK_CHANGES], INK_CONTENT_LASTMOD)

INK_CONTENT_LASTMOD = "2026-11-22"

def ink_hero_facts(ls):
    """Same five tiles as the other trackers. The check time is the ink checker's own run."""
    s = {k: sum(p["status"] == k for p in ls) for k in ("in_stock", "preorder", "sold_out", "coming_soon", "unknown")}
    tracked, checked_shops, _ = shop_sets(ls)
    when = INK_STOCK.get("run_finished")
    last = f'Last check: {time_tag(when)} · ' if when else ""
    return f'''<div class="stats five">
    <div><b>{s["in_stock"]}</b><span>in stock</span></div>
    <div><b>{s["preorder"]}</b><span>preorder</span></div>
    <div><b>{s["sold_out"]}</b><span>sold out</span></div>
    <div><b>{s["coming_soon"]}</b><span>not yet on sale</span></div>
    <div class="unk"><b>{s["unknown"]}</b><span>couldn't check this run</span></div>
  </div>
  <p class="muted small hero-check">{last}{len(ls) - s["unknown"]} of {len(ls)} listings checked successfully · {len(checked_shops)} of {nshops(len(tracked))} checked.</p>'''

def ink_checked_line():
    return f'checked {time_tag(INK_STOCK["run_finished"])}' if INK_STOCK.get("run_finished") else ""

def ink_color_table(ink, rows):
    """One row per color, one column per shop: for single bottles sold color by color."""
    shop_ids = []
    for l in ink["listings"]:
        if l["store_id"] not in shop_ids:
            shop_ids.append(l["store_id"])
    names = {s["id"]: s["name"] for s in stores["stores"]}
    colors = sorted({r.get("color") or r["label"] for r in rows}, key=str.lower)
    by = {(r.get("color") or r["label"], r["store_id"]): r for r in rows}
    head = "".join(f'<th>{E(names[sid])}{region_tag(sid)}</th>' for sid in shop_ids)
    body = []
    for c in colors:
        cells = []
        for sid in shop_ids:
            r = by.get((c, sid))
            if not r:
                cells.append('<td><span class="muted small">Not listed</span></td>')
                continue
            cells.append(f'<td><a href="{E(r["url"])}" rel="noopener" target="_blank" aria-label="{E(c)} at {E(r["store"])}">'
                         f'<span class="badge {E(r["status"])}">{E(STATUS[r["status"]])}</span></a></td>')
        body.append(f'<tr data-status="{E(" ".join(sorted({by[(c, s)]["status"] for s in shop_ids if (c, s) in by})))}"><td>{E(c)}</td>{"".join(cells)}</tr>')
    return (f'<div class="table-wrap"><table class="stock ink-colors"><thead><tr><th>Color</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>'
            '<p class="muted small">Open a status to go straight to that shop\'s listing.</p>')

def ink_card(ink):
    rows = [r for r in INK_ROWS if r["ink_id"] == ink["id"]]
    if not rows:
        return ""
    meta = f"{E(count_line(rows).capitalize())} · {ink_checked_line()}"
    about = " · ".join(E(x) for x in (ink.get("kind"), ink.get("note")) if x)
    kind, note = (f'<p class="muted small">{about}</p>' if about else ""), ""
    if ink.get("display") == "colors":
        table = ink_color_table(ink, rows)
    else:
        table = f'''<div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(rows)}</tbody>
  </table></div>
  <p class="muted small">Open a shop's name to go straight to its listing.</p>'''
    return f"""<details class="card group-fold" id="ink-{E(ink['id'])}">
  <summary><h3 class="fam-name">{E(ink['name'])}</h3><span class="fam-meta">{meta}</span></summary>
  <section class="group-sec">
  {kind}{note}
  {sold_everywhere_html(rows)}
  {table}
</section></details>"""

def ink_restock_html():
    rs = sorted([c for c in INK_CHANGES if is_restock_event(c)], key=lambda c: c["at"], reverse=True)[:10]
    if not rs:
        start = min((r["first_seen"] for r in INK_ROWS if r.get("first_seen")), default=INK_STOCK.get("run_started"))
        since = f" Tracking started {time_tag(start)}." if start else ""
        return f'''<div class="empty"><p><strong>No restocks spotted yet.</strong>{since}
  A restock shows up here when a sold-out or not-yet-on-sale ink becomes available between two checks.</p></div>'''
    now = {r["url"]: r["status"] for r in INK_ROWS}  # every ink listing URL is unique (ink_tracker.validate)
    items = []
    for c in rs:
        st = now.get(c["url"], "unknown")
        tone = {"in_stock": "live", "preorder": "hold", "sold_out": "sold"}.get(st, "past")
        ink = INKS[c["ink_id"]]["name"]
        items.append(f'''<li class="feed-item" data-tone="{tone}" data-now="{E(st)}"><span class="feed-now">now <span class="badge {E(st)}">{E(STATUS.get(st, "Couldn't check"))}</span></span>
  <span class="feed-body"><a href="{E(c['url'])}" rel="noopener" target="_blank">{E(ink)}{(" · " + E(c["label"])) if c.get("label") and c["label"] != ink else ""}</a> <span class="muted">at {E(c['store'])}</span>
  <span class="feed-when">restocked {time_tag(c['at'])}</span></span></li>''')
    return f'<p class="muted small">{RESTOCK_NOW_NOTE}</p><div class="restocks" id="ink-restocks"><ol class="feed">{"".join(items)}</ol></div>'

def build_inks():
    fname = INK_SLUG + "/"
    ls = INK_ROWS
    shops = ink_shops()
    parts = []
    for b, info in INK_CFG["brands"].items():
        inks = [i for i in INK_CFG["inks"] if i["brand"] == b and i["id"] not in INK_RETIRED and any(r["ink_id"] == i["id"] for r in ls)]
        if not inks:
            continue
        bshops = names_and([s["name"] for s in stores["stores"] if s["id"] in info["shops"]])
        parts.append(f'''<h2 class="shop-head" id="brand-{E(b)}"><span>{E(info["name"])}</span>
  <span class="muted small">Checked at {E(bshops)}, from <a href="{E(info["dealer_list"])}" rel="noopener" target="_blank">{E(INK_DEALER_LABEL.get(b, info["name"] + "'s dealer list"))}</a></span></h2>''')
        parts.extend(ink_card(i) for i in inks)
    watching = [b for b, info in INK_CFG["brands"].items() if not any(i["brand"] == b and any(r["ink_id"] == i["id"] for r in ls) for i in INK_CFG["inks"])]
    watch_html = ""
    if watching:
        lines = "".join(f'<li>{E(INK_CFG["brands"][b]["name"])}: {E(names_and([s["name"] for s in stores["stores"] if s["id"] in INK_CFG["brands"][b]["shops"]]))} '
                        f'(<a href="{E(INK_CFG["brands"][b]["dealer_list"])}" rel="noopener" target="_blank">{E(INK_DEALER_LABEL.get(b, "dealer list"))}</a>)</li>' for b in watching)
        watch_html = f'<p>No limited ink from these brands is on the tracker yet. We look for new ones at the shops their dealer lists name:</p><ul>{lines}</ul>'
    retired_html = ""
    if INK_RETIRED:
        rl = "".join(f'<li>{E(v["name"])} <span class="muted small">· sold out at every shop we checked since {time_tag(v["sold_out_since"])}; no longer checked</span></li>' for v in INK_RETIRED.values())
        retired_html = f'<section class="card"><h2>No longer tracked</h2><p class="muted small">An ink leaves the tracker after it has been sold out at every shop we check for 60 days.</p><ul class="link-list">{rl}</ul></section>'
    soon_rows = [r for r in ls if r["status"] == "coming_soon"]
    soon_html = ""
    if soon_rows:
        by_ink = {}
        for r in soon_rows:
            by_ink.setdefault(r["ink_id"], set()).add(r["store"])
        li = "".join(f'<li><a href="#ink-{E(k)}">{E(INKS[k]["name"])}</a> <span class="muted small">· not yet on sale at {E(names_and(sorted(v)))}</span></li>' for k, v in by_ink.items())
        soon_html = f'<section class="card"><h2>Not yet on sale</h2><p class="muted small">Listed by the shop, but not taking orders yet. That is different from sold out.</p><ul class="link-list">{li}</ul></section>'
    faq_html, faq_ld = tracker_good_to_know(
        "Do restock emails cover inks?",
        "Yes. Tick \"Limited-edition inks\" in the signup box and we'll email you when a tracked ink comes back. Ink restocks also show on this page.")
    how = f'''<section class="card"><h2>How we pick shops</h2>
  <p>We track a brand's limited inks only at shops that appear on that brand's own dealer list. A shop calling itself an authorized dealer isn't enough. Some shops on our other trackers sell these inks too, but if the brand doesn't list them, we leave them out.</p>
  {watch_html}
  <p class="muted small">We also look through these shops' catalogs every day for new limited inks, including ones listed as coming soon or on preorder. A new find is checked right away, and it appears here once we've confirmed it.</p>
</section>'''
    body = f"""
<div class="product-page">
{crumbs((fname, INK_NAV))}
<section class="hero">
  {eyebrow("Limited-edition fountain pen ink", nshops(len(shops)), f"{N_STORES} across all trackers", f"checked {CHECK_FREQ}")}
  <h1>Limited-edition fountain pen ink tracker</h1>
  <p class="lede">{E(INK_INTRO)}</p>
  {ink_hero_facts(ls)}
  {also_tracked(fname)}
  {signup_for(section="inks")}
</section>
<div class="layout solo">
  <div class="main-col">
    <section class="card"><h2>Recent restocks</h2>{ink_restock_html()}</section>
    {soon_html}
    <div id="tracker">
    {group_toggle_html()}{''.join(parts)}
    </div>
    {retired_html}
    {how}
    {faq_html}
    {signup_for(section="inks", placement="bottom")}
  </div>
</div>
</div>"""
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": "Limited-edition fountain pen inks: listings we track",
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: (l["ink_id"], l.get("color") or "", l["store"])))]}
    desc = (f"Is a limited-edition fountain pen ink in stock? Live status for Diamine Inkvent, Sailor limiteds and more "
            f"at {nshops(len(shops))} on each brand's own dealer list.")
    return fname, page(fname, "Limited-edition fountain pen ink tracker", desc, body,
                       ld=(crumbs_ld((fname, INK_NAV)), items, faq_ld))

# --- Traveler's Company and MIDORI takedown notice ----------------------------------------------------
# Owner-approved wording (Nov 19, 2026, with two lines added Nov 20, 2026).
# Do not edit a word of the earlier paragraphs. The Nov 20 lines are the owner's exact words.
# On the notice pages the bot sentence closes the "why" paragraph. The scalpers
# line is a card after that paragraph and before the newsletter sentence.
# The homepage card is separate and keeps the line as one sentence.
TAKEDOWN_DATE = "2026-11-19"
TAKEDOWN_HEADING = "Why Traveler's Company and MIDORI are gone"
TAKEDOWN_BOTS = "Bots don't wait for our email, they're already running auto-checkout."
TAKEDOWN_SCALPERS_Q = "Want to stop scalpers?"
TAKEDOWN_SCALPERS_ITEMS = ("Purchase limits.", "Real bot protection.", "Fair regional stock.")
TAKEDOWN_SCALPERS_CLOSE = "Not shutting down the little guy."
TAKEDOWN_PULL = "Want to stop scalpers? Purchase limits. Real bot protection. Fair regional stock. Not shutting down the little guy."
TAKEDOWN_NOTICE = (
    "On November 17, 2026, we reached out to Traveler's Company and to MIDORI's parent company, Designphil, through their official contact forms. We asked politely for permission to use their official product photos on our tracker pages.",
    "Two days later, on November 19, TRAVELER'S COMPANY USA replied. They didn't answer our request. Instead they asked us to remove every Traveler's Company and MIDORI product from Stationery Drop Watch, saying Designphil would not approve of them being here. Their reason was that a tracker telling everyone when something is back in stock \"pushes that stock toward resellers,\" and they would rather announce restocks only to their own email list.",
    "We've complied. Every listing, alert and restock email for both brands has stopped.",
    "We think you deserve to know why. Stationery Drop Watch is free, and it exists for regular people who are tired of refreshing shop pages, not for resellers. We never bought, resold or held a single item. We only pointed you to the official shops' own pages, the moment they had stock. " + TAKEDOWN_BOTS,
    "If you'd like restock news for these brands, the only route they've left you is their newsletter.",
)
# Homepage card: the original two phrases, then the Nov 20 lines, all verbatim from TAKEDOWN_NOTICE.
HOME_NOTICE_LINE = ("We asked politely for permission to use their official product photos. "
                    "Instead they asked us to remove every Traveler's Company and MIDORI product. "
                    "Bots don't wait for our email, they're already running auto-checkout. "
                    "Want to stop scalpers? Purchase limits. Real bot protection. Fair regional stock. Not shutting down the little guy.")
TAKEDOWN_DESC = ("On November 19, 2026, TRAVELER'S COMPANY USA asked us to remove every Traveler's Company and MIDORI product. "
                 "We've complied. Here is why.")

def build_takedown_notice(slug, noindex=False):
    """The notice that replaced the Traveler's Company page, the MIDORI page and the Traveler's size guide."""
    fname = slug + "/"
    items = "".join(f"<li>{E(x)}</li>" for x in TAKEDOWN_SCALPERS_ITEMS)
    callout = f'''<aside class="notice-stand" aria-labelledby="stop-scalpers">
  <h2 id="stop-scalpers">{E(TAKEDOWN_SCALPERS_Q)}</h2>
  <ul>{items}</ul>
  <p class="notice-stand-close">{E(TAKEDOWN_SCALPERS_CLOSE)}</p>
</aside>'''
    paras = "\n".join(f"<p>{E(x)}</p>" for x in TAKEDOWN_NOTICE[:4]) + "\n" + callout + "\n" + f"<p>{E(TAKEDOWN_NOTICE[4])}</p>"
    still = " · ".join([f'<a href="{HOBO_TRACKER}">Hobonichi tracker</a>']
                       + [f'<a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a>' for k in LIVE]
                       + ([f'<a href="{INK_SLUG}/">{E(INK_NAV)}</a>'] if INK_LIVE else []))
    body = f"""
<article class="prose takedown-notice">
{crumbs((fname, TAKEDOWN_HEADING))}
{eyebrow("Notice", "Nov 19, 2026")}
<h1>{E(TAKEDOWN_HEADING)}</h1>
{paras}
<p class="small section-switch">Still tracked here: {still}.</p>
</article>"""
    return fname, page(fname, TAKEDOWN_HEADING, TAKEDOWN_DESC, body,
                       ld=(crumbs_ld((fname, TAKEDOWN_HEADING)),), og_type="article", noindex=noindex)

def publish_ink_data():
    """Ink status and changes for the drop-alert routine (it reads the LIVE site data): site/data/inks/{stock,changes}.json.
    Pending finds ("hidden": true) are never published."""
    out = SITE / "data" / "inks"
    out.mkdir(parents=True, exist_ok=True)
    stock_p, changes_p = ROOT / "data/inks/stock.json", ROOT / "data/inks/changes.json"
    if stock_p.exists():
        stock = json.loads(stock_p.read_text())
        stock["products"] = [r for r in stock.get("products") or [] if not r.get("hidden")]
        (out / "stock.json").write_text(json.dumps(stock, indent=1, ensure_ascii=False) + "\n")
    if changes_p.exists():
        changes = [c for c in json.loads(changes_p.read_text()) if not c.get("hidden")]
        (out / "changes.json").write_text(json.dumps(changes, indent=1, ensure_ascii=False) + "\n")


def main():
    if shop_preview() and SITE.resolve() == (ROOT / "site").resolve():
        raise SystemExit("Refusing to write a shop preview into site/. Set DROPWATCH_SITE_OUT to another directory.")
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "data/stock.json", SITE / "data/stock.json")
    shutil.copy(ROOT / "data/changes.json", SITE / "data/changes.json")
    publish_ink_data()
    (SITE / "index.html").write_text(build_index())
    (SITE / HOBO_TRACKER).mkdir(parents=True, exist_ok=True)
    (SITE / HOBO_TRACKER / "index.html").write_text(build_hobo_tracker())
    for fname, doc in (("hobonichi-2027/", build_hobonichi()), ("about/", build_about()), ("privacy/", build_privacy())):
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for flat in LEGACY_FLAT_PAGES:  # pre-Nov-21 flat files; /x.html now 301s to /x/ (cloudflare/_redirects)
        (SITE / flat).unlink(missing_ok=True)
    (SITE / "404.html").write_text(build_404())
    for g in GROUPS:
        fname, doc = build_group(g)
        check_none_claim(fname, doc)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for d in DESIGNS:
        fname, doc = build_design(d)
        check_none_claim(fname, doc)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    if INK_LIVE:
        fname, doc = build_inks()
        check_none_claim(fname, doc)
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for build in (build_where_to_buy, build_vs, build_january_april, build_dotgrid_guide, build_gift_guide, build_guides_index, build_shop, build_follow, build_contact, build_sold_out):
        fname, doc = build()
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    for slug, hide in ((TN_SLUG, False),):
        fname, doc = build_takedown_notice(slug, noindex=hide)
        for old in SITE.joinpath(slug).glob("*/index.html"):  # old item pages; REDIRECTS rewrites the ones it knows
            old.unlink()
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
