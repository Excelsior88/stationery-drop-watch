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

# Links that go into page data and data/search-index.json must be https:// or a same-site path ("/x", never "//host").
# site/assets/app.js applies the same rule (safeHref) when it renders them; this catches bad store data at build time.
_SAFE_HREF = re.compile(r"^(?:https://|/(?![/\\]))", re.I)


def safe_href(url, where=""):
    """Return url if it is https:// or a same-site path, else "#" with a build warning (never fail the 30-minute build)."""
    u = str(url or "").strip()
    if _SAFE_HREF.match(u):
        return u
    print(f"WARNING: unsafe link replaced with '#'{' (' + where + ')' if where else ''}: {u[:120]!r}")
    return "#"

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
    (re.compile(r"\s*\u263e"), ""),  # Notebook Therapy's decorative crescent moon in its titles
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

# Link-only shops ("link_only": true in stores.json; permission to check stock is pending). The checker never requests
# them. Their listings stay on the site as plain links to the shop's own product page: no status, no "last checked", no
# stock counts, no restock events. Rows or events for them still sitting in data/ from before the switch are dropped
# here too, so no page, feed or site/data copy shows them. To turn a shop back on, delete its "link_only" lines in
# stores.json: nothing in this file changes.
LINK_ONLY = {s["id"] for s in stores["stores"] if s.get("link_only")}
stock["products"] = [p for p in stock["products"] if p.get("store_id") not in LINK_ONLY]
changes = [c for c in changes if c.get("store_id") not in LINK_ONLY]
LINK_ROWS = [dict(store_id=s["id"], store=s["name"], canonical=p.get("canonical"), label=p["label"], type=p["type"], url=p["url"],
                  status="link_only", title=display_title(p.get("source_title") or ""),
                  **({"section": p["section"]} if p.get("section") else {}))
             for s in stores["stores"] if s.get("link_only") for p in s["products"]]
LINK_LABEL = "Link only"
MORE_INFO_LABEL = "More Information"
MORE_INFO_HREF = "/transparency/"

def status_badge(st):
    """Status pill. A link-only pill gets a "More Information" link to /transparency/ immediately to its left
    (owner t1866u, Nov 23, 2026). app.js statusBadge() does the same for rows it renders in the browser."""
    if st == "link_only":
        return (f'<span class="lo-wrap"><a class="more-info" href="{MORE_INFO_HREF}" aria-label="More information about link-only listings (Transparency page)">{MORE_INFO_LABEL}</a>'
                f'<span class="badge link_only">{LINK_LABEL}</span></span>')
    return f'<span class="badge {E(st)}">{STATUS.get(st, LINK_LABEL)}</span>'
LINK_HINT = "Check stock at the shop"
# One switch for the shop totals ("We check 27 shops"). False (Nov 23, 2026, owner t1796u) counts only shops the checker
# actually requests, so link-only shops are never in "N shops". They still show on the trackers with their "Link only" label.
COUNT_LINK_ONLY_IN_SHOP_TOTALS = False

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

# Lamy special and limited edition release calendar (lamy.json, owner-approved design Nov 23, 2026). A resource page, not a
# restock tracker: it is not in NAV_TRACKERS or the tracker count, and no script requests any shop for it. Pens, dates,
# sources and shop URLs are entered by hand from pages someone opened. A stock status shows only when the existing checker
# already reports that exact URL (data/stock.json or the ink rows); otherwise the shop is a plain link with no status.
# Only shops listed in lamy.json "shops" (each with authorization evidence) may be linked. No Amazon or affiliate links.
LAMY_CFG = json.loads((ROOT / "lamy.json").read_text()) if (ROOT / "lamy.json").exists() else {"pens": [], "shops": {}}
LAMY_SLUG = "lamy-special-edition-release-calendar"
LAMY_NAV = "Lamy releases"
LAMY_LIVE = bool(LAMY_CFG.get("pens"))
LAMY_LATEST_MAX = int(LAMY_CFG.get("latest_max", 20))
LAMY_OLDER_MAX = int(LAMY_CFG.get("older_max", 50))
_LAMY_BANNED_HOSTS = re.compile(r"amazon\.|amzn\.|a\.co/|[?&]tag=|[?&](aff|affiliate|ref)=|skimlinks|awin|shareasale|rakuten", re.I)

def lamy_validate(cfg):
    """Refuse to build a calendar that links a shop without authorization evidence, an unknown or link-only-by-rule shop,
    an Amazon or affiliate URL, or a Designphil brand."""
    known = {s["id"]: s for s in stores["stores"]}
    for sid, info in cfg.get("shops", {}).items():
        if sid not in known:
            raise SystemExit(f"lamy.json: shop {sid!r} is not in stores.json")
        if info.get("evidence") not in ("own_site", "owner_list"):
            raise SystemExit(f"lamy.json: shop {sid!r} has no authorization evidence")
    blob = json.dumps(cfg).lower()
    for word in ("midori", "traveler", "designphil"):
        if word in blob:
            raise SystemExit(f"lamy.json: contains {word!r}")
    for p in cfg.get("pens", []):
        urls = [l["url"] for l in p.get("listings", [])] + [s[1] for s in p.get("sources", [])] + ([p["lamy_us_url"]] if p.get("lamy_us_url") else [])
        for u in urls:
            if _LAMY_BANNED_HOSTS.search(u):
                raise SystemExit(f"lamy.json: {p['id']}: Amazon or affiliate URL {u}")
        for l in p.get("listings", []):
            if l["store_id"] not in cfg.get("shops", {}):
                raise SystemExit(f"lamy.json: {p['id']}: {l['store_id']} is not an authorized Lamy shop in lamy.json")
        if p.get("lamy_us_url") and not p["lamy_us_url"].startswith("https://www.lamy.com/en-us/"):
            raise SystemExit(f"lamy.json: {p['id']}: Lamy US link must be on www.lamy.com/en-us/")
        for k in ("official_date", "first_listed"):
            if p.get(k):
                dt.date.fromisoformat(p[k])
lamy_validate(LAMY_CFG)

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

N_STORES = len({p["store_id"] for p in stock["products"]} | {r["store_id"] for r in INK_ROWS} | ({r["store_id"] for r in LINK_ROWS} if COUNT_LINK_ONLY_IN_SHOP_TOTALS else set()))  # stores the checkers actually check (inks included)
N_INK = len({r["store_id"] for r in INK_ROWS})  # shops on the ink tracker
N_SEC = {k: len({p["store_id"] for p in section_products(k)} | ({r["store_id"] for r in LINK_ROWS if section_of(r) == k} if COUNT_LINK_ONLY_IN_SHOP_TOTALS else set())) for k in ("hobonichi", *SECTIONS)}  # shops per section, from data
LIVE = [k for k in SECTIONS if section_products(k)]  # sections that have tracked listings (and so a page)

def section_shops(sec):
    """Store entries with listings in a section, in stores.json order."""
    ids = {p["store_id"] for p in section_products(sec)}
    if COUNT_LINK_ONLY_IN_SHOP_TOTALS:
        ids |= {r["store_id"] for r in LINK_ROWS if section_of(r) == sec}
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
for _r in stock["products"] + changes + stock.get("not_checked", []) + LINK_ROWS + INK_ROWS + INK_CHANGES:
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
    """Store names as shown in shop lists, including an (official) mark when present.
    Only shops we check: a link-only maker store (Notebook Therapy since Nov 23, 2026) is left out."""
    return names_and([s["name"] for s in DOTGRID_SHOPS if not s.get("link_only")])

def bare_shop_name(name):
    """Store name without a trailing (official) mark, for brand lists in prose."""
    return re.sub(r"\s+\(official\)$", "", name, flags=re.I).rstrip()

def dotgrid_brand_names():
    return names_and([bare_shop_name(s["name"]) for s in DOTGRID_SHOPS])

def dotgrid_checked_brand_names():
    """Brands whose own store we check. A link-only maker (Notebook Therapy since Nov 23, 2026) is left out."""
    return names_and([bare_shop_name(s["name"]) for s in DOTGRID_SHOPS if not s.get("link_only")])

def dotgrid_link_only_clause():
    """'Notebook Therapy is listed as a link only: we don't check its stock.' or '' when every maker is checked."""
    lo = [bare_shop_name(s["name"]) for s in DOTGRID_SHOPS if s.get("link_only")]
    if not lo:
        return ""
    one = len(lo) == 1
    return f"{names_and(lo)} {'is' if one else 'are'} listed as {'a link only' if one else 'links only'}: we don't check {'its' if one else 'their'} stock."

def _dotgrid_coverage():
    """Maker-only brand names, mixed-coverage phrases, and independent-shop counts."""
    only, mixed, counts = [], [], {}
    listings = section_products("dotgrid")
    for s in DOTGRID_SHOPS:
        if s.get("link_only"):
            continue  # not checked (Notebook Therapy since Nov 23, 2026): never "We check ... on each maker's own store"
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
        f"Are {dotgrid_checked_brand_names()} in stock right now? Official stores, "
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
    return {"@type": "Organization", "name": "Stationery Drop Watch", "legalName": "Stationery Drop Watch LLC", "url": BASE,
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

def guide_modified(fn):
    """ISO date behind a guide's visible "updated" line, for its Article dateModified and sitemap lastmod,
    so the structured data and the page say the same day. Call after guide_updated(fn) has run."""
    import json as _j
    return _j.loads(GUIDE_DATES.read_text())[fn.__name__]["date"]

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
             "faq": "#good-to-know"}  # /faq -> the homepage FAQ ("Good to know")
# Old Traveler's Company and MIDORI pages are gone for good (owner t2081u, Nov 27, 2026): the item pages, the old
# Regular-size page and the old size guide return HTTP 410 from site/functions/_middleware.js (Pages _redirects can't
# send 410). The takedown notice (TN_SLUG) and the MIDORI_SLUG 301 to it stay. Never in the sitemap or linked.
GONE_PATHS = tuple([f"{parent}/{slug}" for parent, slugs in TAKEDOWN_ITEMS.items() for slug in slugs]
                   + ["travelers-notebook-regular-size", TN_GUIDE_SLUG])
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
    "Hobonichi Techo 2027 launch & restock calendar": "Hobonichi 2027 restock calendar: when stock comes back",
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
OG_IMAGE = BASE + "assets/brand/og-image.png"  # 1200x630, made by scripts/brand/make_og.py (site-wide default card)
# The default card covers all three trackers and shows Clip. It prints the shop count from when it was made,
# recorded beside it in og-image.json; main() warns when that no longer matches N_STORES (re-run make_og.py).
_OG_META = ROOT / "site/assets/brand/og-image.json"
OG_SHOPS = json.loads(_OG_META.read_text())["shops"] if _OG_META.exists() else None
OG_ALT = ("Stationery Drop Watch: Never miss a stationery restock. "
          + (f"We check {OG_SHOPS} shops for you: " if OG_SHOPS else "Restock tracker for ")
          + f"Hobonichi Techo 2027, dot grid journals and limited-edition inks, checked {CHECK_FREQ}. Clip, the paper clip mascot, holds a magnifying glass.")
OG_DOTGRID = BASE + "assets/brand/og-dotgrid.png"  # same script; used on the dot grid journaling page
OG_DOTGRID_ALT = ("Stationery Drop Watch: dot grid journal restock tracker for " + dotgrid_checked_brand_names() + ", checked " + CHECK_FREQ
                  + ("." + " " + dotgrid_link_only_clause() if dotgrid_link_only_clause() else ""))
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
    if LAMY_LIVE:  # the Lamy release calendar sits beside the trackers but is not one (not in NAV_TRACKERS or the count)
        trk += nav_a(LAMY_SLUG + "/", LAMY_NAV)
    # Trackers lead. Shop is a separate link at the end of the rest of the nav, not a fifth tracker.
    rest = "".join(nav_a(h, t) for h, t in NAV) + nav_a("shop/", "Shop")
    nav_inner = f'<span class="nav-trackers">{trk}</span><span class="nav-rest">{rest}</span>'
    # Desktop shows the bar. Narrow screens use a Menu disclosure, which opens without JavaScript.
    # The wrapper is a div, not a nav: the bar and the menu are separate landmarks, never nested.
    nav = (f'<nav class="site-nav site-nav-bar" aria-label="Main">{nav_inner}</nav>'
           f'<details class="nav-menu"><summary>Menu</summary>'
           f'<nav class="site-nav site-nav-panel" aria-label="Menu">{nav_inner}</nav></details>')
    foot_items = list(NAV_TRACKERS) + ([(LAMY_SLUG + "/", LAMY_NAV)] if LAMY_LIVE else []) + [
        ("guides/", "Guides"), ("hobonichi-2027/", "2027 calendar"), ("sold-out-everywhere/", "Sold out everywhere"), ("shop/", "Shop"),
        ("follow/", "Follow us"),
        ("about/", "About"), ("/#good-to-know", "FAQ"), ("contact/", "Contact"), ("privacy/", "Privacy"), ("terms/", "Terms"), ("transparency/", "Transparency"), ("for-shops/", "For shops and brands")]
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
  <div class="site-nav">{nav}</div>
</div></header>
<main id="content" class="wrap">{body}</main>
<footer class="foot"><div class="wrap">
  <p class="foot-brand"><strong>Stationery Drop Watch</strong> checks {N_STORES} shops {CHECK_FREQ}.</p>
  <p class="muted foot-legal">&copy; {dt.datetime.now(ET).year} Stationery Drop Watch LLC. All rights reserved.</p>
  <nav class="foot-nav" aria-label="Footer">{foot_nav}</nav>
  <p class="muted">Statuses come straight from each store's public product data at the time shown. Always confirm on the store's page before you plan around it.</p>
  <p class="muted">{independent_note()}</p>
  <p class="foot-badge"><a href="https://www.saashub.com/stationery-drop-watch?utm_source=badge&utm_campaign=badge&utm_content=stationery-drop-watch&badge_variant=color&badge_kind=approved" target="_blank" rel="noopener"><img class="badge-saashub" src="/assets/badges/saashub_v2_150x50.png" srcset="/assets/badges/saashub_v2_150x50.png 1x, /assets/badges/saashub_v2_300x100.png 2x" alt="Stationery Drop Watch on SaaSHub" width="150" height="63" loading="lazy"></a> <a href="/privacy/"><picture><source type="image/webp" srcset="/assets/badges/zero-cookies-badge_v1_300x126.webp 1x, /assets/badges/zero-cookies-badge_v1_600x252.webp 2x"><img class="badge-zero-cookies" src="/assets/badges/zero-cookies-badge_v1_300x126.png" srcset="/assets/badges/zero-cookies-badge_v1_300x126.png 1x, /assets/badges/zero-cookies-badge_v1_600x252.png 2x" alt="Zero cookies: this site sets no cookies" width="150" height="63" loading="lazy"></picture></a> <picture><source type="image/webp" srcset="/assets/badges/made-in-hamtramck_v2_300x100.webp 300w, /assets/badges/made-in-hamtramck_v2_900x300.webp 900w" sizes="150px"><img class="badge-hamtramck" src="/assets/badges/made-in-hamtramck_v2_300x100.png" srcset="/assets/badges/made-in-hamtramck_v2_300x100.png 300w, /assets/badges/made-in-hamtramck_v2_900x300.png 900w" sizes="150px" alt="Made in Hamtramck, MI" width="150" height="63" loading="lazy"></picture></p>
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
    <div class="cf-turnstile" data-sitekey="{TURNSTILE_SITEKEY}" data-appearance="interaction-only" data-theme="light" data-size="flexible"></div>
    <button type="submit">Notify me</button>
    <p class="signup-status" role="status" aria-live="polite" hidden></p>
  </form>
  <p class="strip-note">{E(note)} Emails are sent via <a href="https://kit.com" target="_blank" rel="noopener">Kit</a>.</p>
  <p class="strip-agree">By signing up, you agree to our <a href="terms/">Terms</a> (personal use only, no reselling or bots) and <a href="privacy/">Privacy notice</a>.</p>
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

def link_listings(match):
    """Link-only listings that a page's own matcher (group or design) covers."""
    return [r for r in LINK_ROWS if match(r)]

def link_status_rows(ls):
    """Table rows for link-only listings: the shop's own page, no status and no check time."""
    rows = []
    for l in sorted(ls, key=lambda l: (l["store"], l["label"])):
        rows.append(f"""<tr class="link-only-row" data-store="{E(l['store_id'])}" data-status="link_only" data-size="{E(listing_size(l))}" data-lang="{E(listing_language(l))}" data-country="{E(REGION.get(l['store_id'], ''))}"><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a>{region_tag(l['store_id'])} <span class="sub">{E(l.get('title') or l['label'])}</span></td>
  <td>{status_badge("link_only")} <span class="sub">{LINK_HINT}</span></td></tr>""")
    return "".join(rows)

def link_note(ls):
    """One line under a table that has link-only rows."""
    if not ls:
        return ""
    n = len({l["store_id"] for l in ls})
    return (f'<p class="muted small link-only-note">{n} {"shop is" if n == 1 else "shops are"} listed as a link only. '
            f'We don\'t check {"its" if n == 1 else "their"} stock, so no status is shown. Open the shop\'s page to see what it has.</p>')

def listed_unchecked():
    """Link-only shops still configured in stores.json.

    An older stock.json can name a shop that was removed (Nanami Paper). The
    pages follow stores.json, which is the list the checker will write next.
    """
    allowed = {s["id"] for s in stores["stores"] if s.get("platform") not in ("shopify", "hobonichi")}
    return [n for n in stock.get("not_checked", []) if n.get("id") in allowed]

def listed_link_only():
    """Link-only shops (stores.json "link_only"): name, url and reason, for the "we list but don't check" notes."""
    return [dict(id=x["id"], name=x["name"], url=x["url"], reason="Link only for now: we don't check its stock, so no status is shown.")
            for x in stores["stores"] if x.get("link_only")]

def link_only_shops_sentence():
    names = [n["name"] for n in listed_link_only()]
    if not names:
        return ""
    return (f"{names_and(names)} {'is' if len(names) == 1 else 'are'} listed as {'a link only' if len(names) == 1 else 'links only'} for now: "
            f"we don't check {'its' if len(names) == 1 else 'their'} stock, so no status is shown.")

def link_only_clause():
    """FAQ sentence. Singular when JetPens is the only shop we link and do not check."""
    blocked = _blocked_clause()
    extra = link_only_shops_sentence()
    if blocked == "Every shop we list is checked automatically.":
        return extra or blocked
    return blocked + (" " + extra if extra else "")

def _blocked_clause():
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
    """Counts only listings we check. Link-only listings are named, never counted as stock or as checked."""
    chk = [r for r in ls if r["st"] != "link_only"]
    links = len({r["sid"] for r in ls if r["st"] == "link_only"})
    link_bit = f" · {links} {'shop' if links == 1 else 'shops'} link only" if links else ""
    if not chk:
        return "Link only, we don't check stock"
    shops = len({r["sid"] for r in chk})
    in_shops = len({r["sid"] for r in chk if r["st"] == "in_stock"})
    if shops == 1:  # one checked shop: name it instead of "N of 1 shop in stock"
        shop = chk[0]["s"]
        if in_shops:
            phrase = f"In stock at {shop}"
        elif all(r["st"] == "unknown" for r in chk):
            phrase = f"Couldn't check {shop} this run"
        else:
            phrase = f"Not in stock at {shop}"
        lead = f"{phrase} · {in_stock_tally([r['st'] for r in chk])}" if len(chk) > 1 else phrase
        return f"{lead}{link_bit}"
    return f"{in_stock_tally([r['st'] for r in chk])} · {in_shops} of {shops} shops in stock{link_bit}"

def official_note(l):
    """Optional note from Hobonichi's own feed (checker.hobonichi_note), only on sold-out official rows.
    Older stock.json rows don't have the field, so they render as before."""
    note = l.get("official_note")
    return note if note and l.get("store_id") == "1101" and l.get("status") == "sold_out" else None

def compare_product(ls):
    """One product, every shop that lists it, so the statuses sit next to each other."""
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4, "link_only": 5}
    ls = sorted(ls, key=lambda r: (order.get(r["st"], 9), r["s"].lower()))
    h = ls[0]
    name = f'<a href="{E(h["dp"])}">{E(h["gn"])}</a>' if h.get("dp") and not h.get("dpl") else E(h["gn"])
    shops = len({r["sid"] for r in ls})
    bits = [E(h.get("t") or ""), f"{shops} {'shop' if shops == 1 else 'shops'}"]
    if h.get("dp"):
        bits.append(f'<a href="{E(h["dp"])}">{E(h.get("dpl") or "Design page")}</a>')
    note = sold_everywhere_html(ls, "st", "sid")
    items = []
    for r in ls:
        region = f' <span class="region" title="Shop\'s home country">{E(r["rg"])}</span> ' if r.get("rg") else ""
        variant = f'<span class="sub variant">{E(r["p"])}</span>' if r.get("p") and r["p"] != r.get("gn") else ""
        title = f'<span class="sub">{E(r["title"])}</span>' if r.get("title") and r["title"] not in (r.get("gn"), r.get("p")) else ""
        items.append(
            f'<li><span class="compare-shop"><a href="{E(r["u"])}" target="_blank" rel="noopener">{E(r["s"])}</a>{region}{variant}{title}</span>'
            f'{status_badge(r["st"])}'
            + (f'<span class="official-note">{E(r["on"])}</span>' if r.get("on") and r.get("st") == "sold_out" else "") + '</li>')
    anchor = f' id="{E(h["g"])}"' if re.fullmatch(r"[A-Za-z][\w-]*", h.get("g") or "") else ""
    return f'''<article class="compare"{anchor}>
  <header class="compare-head"><h3>{name}</h3><p class="compare-tally">{E(shop_tally(ls))}</p><p class="sub">{" · ".join(b for b in bits if b)}</p>{note}</header>
  <ul class="compare-shops">{"".join(items)}</ul>
</article>'''

def tracker_static(rows):
    """No-JS listing groups. Families start closed; the summary is a real control, so they still open."""
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4, "link_only": 5}
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
  <summary><span class="fam-name">{E(name)}</span><span class="fam-meta">{E(in_stock_tally([r["st"] for r in all_rows if r["st"] != "link_only"]))}</span></summary>
  <div class="fam-products">{body}</div>
</details>''')
    return "".join(parts)

def tracker_block(prods, rows, search_hint, other_opt="", extra="", prefix=""):
    """Filterable list of every listing in `prods` (driven by assets/app.js).
    Without JavaScript the same groups are in the page, inside noscript."""
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    sids = {p["store_id"] for p in prods} | {r["sid"] for r in rows if r["st"] == "link_only"}
    store_opts = "".join(f'<option value="{E(x["id"])}">{E(x["name"])}</option>' for x in stores["stores"] if x["id"] in sids)
    prod_opts = "".join(f'<option value="{E(k)}">{E(v)}</option>' for k, v in canon.items() if any(p.get("canonical") == k for p in prods))
    type_opts = "".join(f'<option value="{E(t)}">{E(t)}</option>' for t in sorted({p["type"] for p in prods}))
    status_opts = "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items() if any(p["status"] == k for p in prods))
    if any(r["st"] == "link_only" for r in rows):
        status_opts += f'<option value="link_only">{LINK_LABEL}</option>'
    link_help = (' "Link only" means we don\'t check that shop\'s stock, so no status is shown; the link goes to the shop\'s own page.'
                 if any(r["st"] == "link_only" for r in rows) else "")
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
      <p class="muted small">Groups can be collapsed. "Not yet on sale" means the store has a preview page up but isn't taking orders yet. "Couldn't check" is a failed check, not a sold-out guess.{link_help}</p>
      {region_legend(p["store_id"] for p in prods)}
      {extra}
    </section>"""

def tracker_rows(prods, out_everywhere=None, links=()):
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    fam_index = {g["slug"]: i for i, g in enumerate(g for g in GROUPS if g_sec(g) == "hobonichi")}
    rows = []
    for p in prods:
        famn, fam = listing_family(p)
        rows.append(dict(g=product_key(p), p=p["label"], gn=canon.get(p.get("canonical") or "", p["label"]), c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], rg=REGION.get(p["store_id"], ""), st=p["status"],
                 u=safe_href(p["url"], p.get("store_id", "")), at=p["checked_at"], since=p.get("status_since"), title=p.get("title") or "",
                 **{k: p[f] for k, f in (("va", "available_variants"), ("tv", "total_variants")) if p.get(f) is not None},  # left out when a shop doesn't report variants, so pack_rows can pack (no nulls)
                 sz=listing_size(p), lg=listing_language(p), famn=famn, fam=fam, fo=fam_index.get(fam, 99)))
        note = official_note(p)
        if note:
            rows[-1]["on"] = note  # app.js shows it under the shop, like compare_product does
    for r, p in zip(rows, prods):  # design page link (FIX-09), shown on the product's group header
        dp = design_page_for([p])
        if dp:
            r["dp"] = "/" + pretty(dp)
        elif merged_parent_link([p]):  # merged design: the row stays, its link goes to the page it folded into
            r["dp"], r["dpl"] = "/" + pretty(merged_parent_link([p])[0]), merged_parent_link([p])[1]
    for p in links:  # link-only listings: no status time, no variant counts (keys left out on purpose)
        famn, fam = listing_family(p)
        r = dict(g=product_key(p), p=p["label"], gn=canon.get(p.get("canonical") or "", p["label"]), c=p.get("canonical") or "", t=p["type"], s=p["store"], sid=p["store_id"], rg=REGION.get(p["store_id"], ""), st="link_only",
                 u=safe_href(p["url"], p.get("store_id", "")), title=p.get("title") or "", sz=listing_size(p), lg=listing_language(p), famn=famn, fam=fam, fo=fam_index.get(fam, 99))
        dp = design_page_for([p])
        if dp:
            r["dp"] = "/" + pretty(dp)
        elif merged_parent_link([p]):
            r["dp"], r["dpl"] = "/" + pretty(merged_parent_link([p])[0]), merged_parent_link([p])[1]
        rows.append(r)
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

def shops_checked_phrase(tracked, checked):
    """The shop part of the hero check line. "3 of 4 shops checked"; with one shop, "1 shop checked",
    or, if that one shop's check failed, a plain sentence saying so."""
    if len(tracked) == 1:
        return "1 shop checked" if checked else "the one shop we track couldn't be checked this run"
    return f"{len(checked)} of {nshops(len(tracked))} checked"

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
  <p class="muted small hero-check">Last check: {time_tag(stock["run_finished"])} · {len(ls) - s["unknown"]} of {len(ls)} listings checked successfully · {shops_checked_phrase(tracked, checked_shops)}.</p>'''

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

# Listing rows for the interactive tracker live in their own file, named by content hash, so the page HTML stays
# small and the file can be cached for good (cloudflare/_headers: /data/tracker/*). Every status the page shows is
# still in the HTML (the Recent restocks card and the <noscript> table), so readers without JS and crawlers see it.
TRACKER_DATA_DIR = "data/tracker"
TRACKER_DATA_FILES = {}  # site-relative path -> JSON text; written by main()

def stock_data(rows, name="hobonichi"):
    import hashlib as _h
    payload = json.dumps(pack_rows(rows), ensure_ascii=False, separators=(",", ":"))
    path = f"{TRACKER_DATA_DIR}/{name}-{_h.sha256(payload.encode()).hexdigest()[:12]}.json"
    TRACKER_DATA_FILES[path] = payload
    return f'<script id="stock-data" type="application/json" data-src="/{path}"></script>'

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
  <p class="feed-empty muted small" hidden>None of these are in stock now.</p>
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
    rows = tracker_rows(prods, links=[r for r in LINK_ROWS if section_of(r) == "hobonichi"])
    unchecked = listed_unchecked() + listed_link_only()
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
    n_shops = len({p['store_id'] for p in prods if p['store_id'] in HOBO_SHOPS} | ({r['store_id'] for r in LINK_ROWS if section_of(r) == "hobonichi"} if COUNT_LINK_ONLY_IN_SHOP_TOTALS else set()))
    return page(HOBO_TRACKER, "Hobonichi Techo 2027 restock tracker",
                f"Is your Hobonichi Techo 2027 back in stock? Live restock status for Original A6, Cousin A5, Weeks and covers at {n_shops} shops, checked {CHECK_FREQ}.",
                body, ld=(faq_ld, crumbs_ld((HOBO_TRACKER, "Hobonichi tracker"))))

HUB_TRACKERS = {  # one line per tracker card on the hub homepage
    "hobonichi": ("Hobonichi Techo 2027", "Original A6, Cousin A5, the English Planner A6, HON, Weeks, Weeks Mega and covers, at the official store and independent shops."),
    "dotgrid": ("Dot grid journals", ""),  # short homepage blurb is filled in below; official-store detail stays on the hub
}
HUB_FAQ = ("How often do you check the shops?", "What do you track?",
           'What do "Not yet on sale" and "Couldn\'t check" mean?',
           "How do restock alerts work?", "Which shops do you check?", "Do you sell planners?",
           "Can I use alerts for reselling?")

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

def find_bar():
    """Compact homepage search. Without JavaScript the form opens the Hobonichi tracker search.
    With JavaScript, app.js loads the search index on focus and shows matches under the field."""
    return """<div class="find-bar">
  <form class="find-form" id="find-form" action="/hobonichi-restock-tracker/" method="get" role="search" aria-label="Find my item">
    <label id="find-label" for="find-q">Find my item</label>
    <div class="find-row">
      <span class="find-field"><input id="find-q" type="search" name="q" placeholder="Planner, dot grid, ink, Lamy pen, guide or shop" autocomplete="off" enterkeyhint="search" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="find-list" aria-autocomplete="list" aria-haspopup="listbox" aria-keyshortcuts="/ Control+K Meta+K"><kbd class="find-kbd" aria-hidden="true">/</kbd></span>
      <button type="submit">Search</button>
    </div>
    <p id="find-count" class="find-count" role="status" aria-live="polite"></p>
    <ul id="find-list" class="find-list" role="listbox" aria-label="Matching items" hidden></ul>
  </form>
</div>"""

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
            line = f"Flagship notebooks from {dotgrid_checked_brand_names()}, plus Archer and Olive refills."
        bits = [f"{N_SEC[k]} shops"]
        if st["preorder"]:
            bits.append(f'{st["preorder"]} on preorder')
        if st["unknown"]:
            bits.append(f'{st["unknown"]} couldn\'t be checked')
        # in_stock is status == "in_stock" only. unknown is not counted as in stock.
        cards.append(f"""<li class="hub-card"><a href="{href[k]}" aria-labelledby="hub-h-{k}" aria-describedby="hub-c-{k}">
  <span class="hub-art">{hub_art(k)}</span>
  <h3 id="hub-h-{k}">{E(name)}</h3><p>{E(line)}</p>
  <p class="hub-count" id="hub-c-{k}"><b>{st["in_stock"]}</b> of {len(ps)} listings in stock <span class="muted small">{E(" · ".join(bits))}</span></p>
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
        cards.append(f"""<li class="hub-card"><a href="{INK_SLUG}/" aria-labelledby="hub-h-inks" aria-describedby="hub-c-inks">
  <span class="hub-art">{hub_art("inks")}</span>
  <h3 id="hub-h-inks">Limited-edition inks</h3><p>{E(INK_HUB_LINE)}</p>
  <p class="hub-count" id="hub-c-inks"><b>{ist["in_stock"]}</b> of {len(INK_ROWS)} listings in stock <span class="muted small">{E(" · ".join(ibits))}</span></p>
  <span class="hub-go">View tracker</span></a></li>""")
    # The takedown notice card left the homepage on Nov 23, 2026 (owner t1797u). The notice page itself stays live at
    # /{TN_SLUG}/, in the sitemap, and linked from the gift guide.
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
  {find_bar()}
  {trust_strip(prods + (INK_ROWS if INK_LIVE else []))}
  <p class="small section-switch">More on the site: <a href="hobonichi-2027/">2027 calendar</a> · {f'<a href="{LAMY_SLUG}/">Lamy release calendar</a> · ' if LAMY_LIVE else ""}<a href="guides/">Guides</a> · <a href="shop/">Shop</a> · <a class="nobr" href="sold-out-everywhere/">Sold out everywhere</a>.</p>
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

{print_drop_card()}

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

<h2 class="sr">2027 timeline</h2>
<ol class="timeline">
  <li><time>Aug 25, 2026</time><div><h3 class="tl">Previews go up</h3><p>Shops post the 2027 lineup as "out of stock" or "coming soon" pages. They aren't sold out; they're just not on sale yet. <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Aug 31, 2026 · 10 PM ET</time><div><h3 class="tl">Official online launch (January-start planners)</h3><p>September 1, 2026 at 11:00 AM Japan time (August 31, 2026 at 10:00 PM ET / 9:00 PM CT) is the official Hobonichi Store's online launch time <a href="#s-1101">[Hobonichi]</a> <a href="#s-faq-release">[Hobonichi, release time]</a>. Indie shops split online and in-store times. Hobonichi's FAQ says each retail store opens at its own store hours <a href="#s-faq-schedule">[Hobonichi, sale schedule]</a>.<br>Paper Mouse opened online Aug 31 at 10 PM ET and in-store Sep 1 at 11 AM ET <a href="#s-papermouse">[Paper Mouse]</a>.<br>Atlas opened online Aug 31 at 9 PM CT, with retail expected the week of September 7. Atlas warned that popular styles and collaborations "often sell out within minutes." <a href="#s-atlas">[Atlas]</a></p></div></li>
  <li><time>Sep 30 – Oct 1, 2026</time><div><h3 class="tl">Second fall wave</h3><p>Hobonichi notes that some products begin sales on October 1 <a href="#s-1101">[Hobonichi]</a>.<br>One Piece sales began October 1, 2026 at 11:00 AM Japan time (September 30, 2026 at 10:00 PM ET). One Piece 2027 editions are January-start and Monday-start only <a href="#s-hon">[Hobonichi]</a>.<br>Paper Mouse, a US shop, listed the Weeksdays 2027 desk calendar in this wave, plus a large restock of earlier sell-outs (as preorders at some shops) <a href="#s-papermouse">[Paper Mouse]</a>.</p></div></li>
  <li><time>Early–mid Oct 2026</time><div><h3 class="tl">First restocks land at indie shops</h3><p>Atlas expected its first restock in early October. Paper Mouse's shipment arrived October 15 and preorders began shipping. <a href="#s-atlas">[Atlas]</a> <a href="#s-papermouse">[Paper Mouse]</a></p></div></li>
  <li><time>Feb 1, 2027</time><div><h3 class="tl">Spring launch (April-start planners)</h3><p>The official Hobonichi Store launches April-start planners on February 1, 2027 at 11:00 AM Japan time (January 31, 2027 at 9:00 PM ET) <a href="#s-1101">[Hobonichi]</a>. Other shops start at their own opening hours. Hobonichi has not published the Spring 2027 cover and book lineup yet.</p></div></li>
</ol>
""" + signup() + """

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

<h2>When will Hobonichi 2027 restock?</h2>
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
                "When will Hobonichi Techo 2027 restock? Launch dates, the October wave, and when restocks usually land, with sources.",
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
{eyebrow("Privacy", "updated Nov 23, 2026")}
<h1>Privacy</h1>
<p class="lede">What this site collects, who handles it, and how to reach us. In short: your email address if you sign up for alerts, plus page-view and performance statistics from Cloudflare Web Analytics. The site sets no cookies and runs no ad trackers.</p>
<h2>Email alerts (Kit)</h2>
<p>If you sign up for restock alerts, your email address and the trackers you pick (Hobonichi, dot grid journals, limited-edition inks) go to <a href="https://kit.com" target="_blank" rel="noopener">Kit</a>, the service that stores the list and sends the emails. Kit sends a confirmation email first; we only add the address to the list after you click the link. We use it only to send restock alerts for the trackers you chose and occasional site updates. Every email has an unsubscribe link, and you can also email us to be removed. Kit's own privacy policy is at <a href="https://kit.com/privacy" target="_blank" rel="noopener">kit.com/privacy</a>.</p>
<p>Kit tracks basic email opens and link clicks, for example through Kit tracking links such as click.kit-mail3.com and a standard open pixel, so we can see whether restock alerts are read and clean out inactive addresses. Those are email delivery stats, separate from this website, which sets no cookies and runs no ad trackers.</p>
<p>Before November 22, 2026, signups went to <a href="https://buttondown.com" target="_blank" rel="noopener">Buttondown</a>, our previous email service. While we finish moving to Kit, readers who joined through Buttondown also get Hobonichi and dot grid alerts from Buttondown through December 7, 2026. From December 8, alerts go out through Kit only. After December 8, 2026, when the move from Buttondown to Kit finishes, we will delete the old Buttondown subscriber list. Buttondown's privacy policy is at <a href="https://buttondown.com/legal/privacy" target="_blank" rel="noopener">buttondown.com/legal/privacy</a>.</p>
<p>Clicking unsubscribe stops future alerts by placing your address on a suppression list so we don't re-email you, whereas emailing {mailto_email()} permanently deletes your record.</p>
<p>We never sell, rent, or share subscriber emails. Alerts run on your consent, and you can email {mailto_email()} anytime to request access, export, or permanent deletion. Data is processed in the United States. The site and alerts are for people 13 and older. If a child under 13 signed up, email {mailto_email()} and we will delete it.</p>
<p>The signup form is protected from bots by <a href="https://www.cloudflare.com/application-services/products/turnstile/" target="_blank" rel="noopener">Cloudflare Turnstile</a>, an anti-spam check. On pages with the form, your browser loads a script from Cloudflare (challenges.cloudflare.com) and, when you submit, sends Cloudflare a token that we verify on our server. Cloudflare may look at things like your IP address and browser details to tell people from bots, and may use browser storage for that, under <a href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener">its privacy policy</a>. The form goes through our own server at stationerydropwatch.com/api/subscribe, which passes your email address and chosen trackers to Kit and doesn't store them itself.</p>
<h2>Hosting</h2>
<p>The site is hosted on Cloudflare Pages. Cloudflare handles standard request data, such as your IP address, to deliver and protect the site. See <a href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener">Cloudflare's privacy policy</a>.</p>
<p>The site uses <a href="https://www.cloudflare.com/web-analytics/" target="_blank" rel="noopener">Cloudflare Web Analytics</a>, a cookie-free analytics service from our host, Cloudflare. It loads a small script (beacon.min.js from static.cloudflareinsights.com) that counts page views and measures how pages perform, and sends those counts to this site at /cdn-cgi/rum. The statistics we can see include pages visited, referrer, browser and device type, country, and load times. Cloudflare says Web Analytics collects the minimum information needed to show how a site performs and does not track individual end users across its customers' Internet properties.</p>
<p>This site doesn't set its own cookies and doesn't run ad trackers.</p>
<h2>Links to other sites</h2>
<p>When you follow a link to a shop we track, or to Amazon, Etsy, or Teachers Pay Teachers for our own planners, journals, and printables, that site has its own privacy policy. This site doesn't set cookies to credit those visits.</p>
<p>We don't use affiliate links on Stationery Drop Watch.</p>
<h2>Contact</h2>
<p>This site is operated by Stationery Drop Watch LLC.</p>
<p>Questions, or want your email address removed? Email {mailto_email()}.</p>
<p>How the site may be used, including our ban on reselling, is covered in our <a href="terms/">Terms of Use</a>.</p>
</article>"""
    return page(fname, "Privacy", "How Stationery Drop Watch handles email signups, plus page-view stats from Cloudflare Web Analytics. No cookies set by the site, no ad trackers.", body, ld=(crumbs_ld((fname, "Privacy")),))

# Readable anchors for the 21 Terms headings. The jump menu and the h2 ids share this list.
TERMS_SECTIONS = (
    ("agreeing-to-these-terms", "Agreeing to these terms"),
    ("who-may-use-the-service", "Who may use the Service"),
    ("what-the-service-is", "What the Service is, and what it isn't"),
    ("no-guarantee-of-stock", "No guarantee of stock, prices, or accuracy"),
    ("third-party-sites", "Third-party sites and purchases"),
    ("prohibited-uses", "Prohibited uses"),
    ("restrict-or-end-access", "Our right to restrict or end access"),
    ("email-restock-alerts", "Email restock alerts"),
    ("our-content", "Our content"),
    ("feedback-and-suggestions", "Feedback and suggestions"),
    ("copyright-and-trademark", "Copyright and trademark concerns"),
    ("for-shops-and-brands", "For shops and brands"),
    ("disclaimer-of-warranties", "Disclaimer of warranties"),
    ("limitation-of-liability", "Limitation of liability"),
    ("indemnification", "Indemnification and hold harmless"),
    ("changes-to-these-terms", "Changes to these terms"),
    ("events-beyond-our-control", "Events beyond our control"),
    ("governing-law", "Governing law and venue"),
    ("outside-the-united-states", "Users outside the United States"),
    ("general-terms", "General terms"),
    ("contact", "Contact"),
)

def terms_heading(n):
    slug, title = TERMS_SECTIONS[n - 1]
    return f'<h2 id="{slug}">{n}. {title}</h2>'

def terms_jump_menu():
    """Collapsed list of the 21 sections. No open attribute, so phones are not pushed down."""
    items = "".join(
        f'<li><a href="#{slug}">{title}</a></li>'
        for n, (slug, title) in enumerate(TERMS_SECTIONS, 1))
    return ('<details class="terms-jump"><summary>Jump to a section</summary>'
            f'<ol>{items}</ol></details>')

TERMS_UPDATED = "Nov 23, 2026"

def build_terms():
    """Terms of Use: same template as Privacy. Owner-approved text (Nov 23, 2026), not legal advice."""
    fname = "terms/"
    body = f"""
<article class="prose">
{crumbs((fname, "Terms of Use"))}
{eyebrow("Terms", "updated " + TERMS_UPDATED)}
<h1>Terms of Use</h1>
<p class="lede">These terms explain how you may use Stationery Drop Watch, what we do and don't promise, and what we ask of you in return. They are written to be read, so please take a few minutes with them.</p>
{terms_jump_menu()}
{terms_heading(1)}
<p>Stationery Drop Watch LLC, a Michigan limited liability company ("Stationery Drop Watch", "we", "us" or "our"), runs the website at stationerydropwatch.com, its restock trackers, its guides, and its email restock alerts (together, the "Service"). By visiting the site, signing up for alerts, or otherwise using the Service, you agree to these Terms of Use and to our <a href="privacy/">Privacy</a> page. If you do not agree, please do not use the Service.</p>
{terms_heading(2)}
<p>You must be at least 13 years old to use the Service or sign up for email alerts. If you are under 18, or under the age of majority where you live, please use the Service only with the involvement of a parent or guardian, who agrees to these terms on your behalf. The Service does not require or offer user accounts.</p>
{terms_heading(3)}
<p>Stationery Drop Watch is a free, independent restock tracker. About every 30 minutes, an automated checker reads the public product data of most of the shops we list and records whether each listing can be bought at that time. Some shops are listed as "Link only", which means we link to them but don't check their stock, so no status is shown. We show those results on our trackers, link each listing to the shop's own product page, and, if you sign up, email you when something on the trackers you chose comes back in stock.</p>
<p>We are an information service, not a store. We do not sell, hold, reserve, or ship any of the stationery we track, and we do not take orders or payments for it. Every purchase of a tracked item happens on the shop's own website.</p>
<p>We separately sell planners, journals, and printables that we make ourselves. Those are listed on our <a href="shop/">Shop</a> page and are sold through Amazon, Etsy, and Teachers Pay Teachers, under those platforms' own terms.</p>
<p>Stationery Drop Watch is not affiliated with, sponsored by, or endorsed by any brand or shop we track, unless we clearly say otherwise. Brand names, product names, logos, and trademarks shown on the site belong to their owners and are used only to identify the products we track.</p>
{terms_heading(4)}
<p>Stock changes quickly, and our information reflects only what a shop reported at the time of our last check. It may already be out of date when you see it, and it may be wrong. A check can also fail, in which case we show "Couldn't check" rather than guess. "Not yet on sale" means a shop has a preview page up but is not yet taking orders.</p>
<p>We do not guarantee that any item is in stock, that any price, edition, color, or size is correct, that any alert will arrive promptly or at all, or that you will be able to buy an item before it sells out. Always confirm availability, price, shipping, and other details on the shop's own page before you buy or make plans around it.</p>
{terms_heading(5)}
<p>Our links take you to websites we do not own or control, including the shops we track and Amazon, Etsy, and Teachers Pay Teachers. Those sites have their own terms and privacy policies, and we are not responsible for their content, products, pricing, availability, shipping, customer service, or conduct.</p>
<p>Any purchase you make from a shop is a transaction between you and that shop. Questions about orders, payments, delivery, returns, refunds, or product quality should go to the shop you bought from.</p>
{terms_heading(6)}
<p>Stationery Drop Watch exists to help individual people find planners, journals, and inks for their own use, and to give everyone a fair chance at a restock. <strong>We prohibit anyone from using the Service to engage in reselling activities.</strong></p>
<p>Specifically, you may not use the site, its trackers, its alerts, its data, or its emails to:</p>
<ul>
<li>Buy tracked items for the purpose of reselling them, including scalping, flipping, or reselling at a markup on any marketplace or platform.</li>
<li>Make bulk, automated, or bot-assisted purchases, including auto-checkout tools, purchasing scripts, or running many accounts or payment methods to get around a shop's purchase limits.</li>
<li>Trigger, feed, or power any bot, script, or automated buying service.</li>
<li>Sell, rent, share, or otherwise provide access to our alerts, stock information, or data, whether as a paid service, a "cook group", a private channel, or any other arrangement.</li>
</ul>
<p>You also may not:</p>
<ul>
<li>Scrape, crawl, or otherwise access the Service with automated tools, other than standard search engine indexing and ordinary web browsers used by a person.</li>
<li>Copy, republish, redistribute, mirror, or build a product or service on our stock data, alerts, or content without our prior written permission.</li>
<li>Interfere with or disrupt the Service, including by overloading it, probing or bypassing its security or anti-spam protections, or introducing malicious code.</li>
<li>Abuse the email alerts, including signing up addresses you do not own or control, using fake or disposable addresses at scale, or attempting to automate signups.</li>
<li>Use the Service in any way that is unlawful, misleading, or harmful to us, the shops we track, or other readers.</li>
</ul>
{terms_heading(7)}
<p>We may, at our discretion and without notice, block access to the Service, remove an email address from our alerts, cancel alerts, or refuse service to anyone we reasonably believe has broken these terms, is reselling, or is using the Service in a way that harms others. We may also change, pause, or discontinue any part of the Service, including any tracker, shop, or alert, at any time. You may stop using the Service at any time, and you can unsubscribe from alerts whenever you like.</p>
{terms_heading(8)}
<p>Alerts are free. When you sign up, we send a confirmation link, and you are not added to the list until you click it. You will then receive restock emails for the trackers you choose, plus occasional updates when we add a tracker or release something new. Every email includes an unsubscribe link, and you can also ask to be removed by emailing {mailto_email()}.</p>
<p>Alerts are a convenience. Delivery depends on our checker, our email provider, and your own email service, and alerts can be delayed, filtered as spam, or missed. How we handle your email address is explained on our <a href="privacy/">Privacy</a> page.</p>
{terms_heading(9)}
<p>The site's text, guides, design, graphics, mascot, compiled stock data, and other original material are owned by Stationery Drop Watch LLC or used with permission, and are protected by copyright and other laws. You may view and share links to our pages for your own personal, non-commercial use. Any other use, including copying or republishing our content or data, requires our prior written permission.</p>
{terms_heading(10)}
<p>We welcome questions, corrections, and suggestions for shops to track. If you send us feedback or ideas, you agree that we may use them to improve the Service without any obligation or payment to you. Please do not send anything confidential.</p>
{terms_heading(11)}
<p>If you believe something on the site uses your copyrighted work or trademark without permission, email {mailto_email()} with a description of the work, where it appears on our site, and how to reach you. We review every request in good faith.</p>
{terms_heading(12)}
<p>Any shop or brand can ask us at any time to remove its products or shop from our trackers, or to switch to link only, by emailing {mailto_email()}. We will honor every such request as promptly as possible.</p>
<section class="terms-callout">
{terms_heading(13)}
<p><strong>The Service is provided "as is" and "as available".</strong> To the fullest extent permitted by law, we make no warranties of any kind, express or implied, including warranties of accuracy, availability, merchantability, fitness for a particular purpose, and non-infringement. We do not warrant that the Service will be uninterrupted, timely, secure, or error-free.</p>
</section>
<section class="terms-callout">
{terms_heading(14)}
<p>To the fullest extent permitted by law, Stationery Drop Watch LLC and its members and managers <strong>will not be liable for any indirect, incidental, special, consequential, or punitive damages, or for any lost profits, lost purchases, missed restocks, or lost data</strong>, arising from or related to your use of, or inability to use, the Service, even if we were told such damages were possible.</p>
<p>Because the Service is free, <strong>our total liability for any claim arising from or related to the Service is limited to fifty US dollars (US$50)</strong>. Some jurisdictions do not allow certain of these limits, so some of them may not apply to you.</p>
</section>
{terms_heading(15)}
<p>You agree to defend, indemnify, and hold harmless Stationery Drop Watch LLC and its members and managers from and against any claims, demands, losses, liabilities, damages, costs, and expenses, including reasonable attorneys' fees, arising from or related to:</p>
<ul>
<li>your use or misuse of the Service;</li>
<li>your violation of these terms or of any law or the rights of any third party;</li>
<li>any purchase you make from, or dispute you have with, a shop or other third-party site; and</li>
<li>any resale, attempted resale, or other reselling activity connected to items, alerts, or data you obtained through the Service.</li>
</ul>
{terms_heading(16)}
<p>We may update these terms from time to time. When we do, we will change the "updated" date at the top of this page. If you keep using the Service after an update is posted, you accept the updated terms.</p>
{terms_heading(17)}
<p>We are not responsible for any delay or failure in the Service caused by events beyond our reasonable control, including outages at our hosting, email, or other service providers, changes or outages at the shops we track, internet failures, or natural disasters.</p>
{terms_heading(18)}
<p>These terms are governed by the laws of the State of Michigan, United States, without regard to its conflict-of-laws rules. Any dispute arising from or related to these terms or the Service will be brought only in the state courts located in Wayne County, Michigan, or the United States District Court for the Eastern District of Michigan, and you consent to the jurisdiction of those courts.</p>
{terms_heading(19)}
<p>Stationery Drop Watch is run from Michigan, in the United States, and some of the shops we track are in other countries. If you use the Service from outside the United States, you do so on your own initiative and are responsible for following your local laws.</p>
{terms_heading(20)}
<ul>
<li><strong>Severability.</strong> If any part of these terms is found unenforceable, that part will be enforced to the fullest extent possible and the rest will remain in full effect.</li>
<li><strong>No waiver.</strong> Our failure to enforce any provision is not a waiver of our right to enforce it later.</li>
<li><strong>Assignment.</strong> You may not transfer your rights under these terms. We may transfer ours, for example to a company that operates the Service in the future.</li>
<li><strong>Survival.</strong> The sections on prohibited uses, our content, disclaimers, limitation of liability, indemnification, and governing law continue to apply after your use of the Service ends.</li>
<li><strong>Entire agreement.</strong> These terms, together with our <a href="privacy/">Privacy</a> page, are the entire agreement between you and us about the Service.</li>
</ul>
{terms_heading(21)}
<p>Questions about these terms? Email {mailto_email()}, or visit our <a href="contact/">Contact</a> page.</p>
</article>"""
    return page(fname, "Terms of Use", "The terms for using Stationery Drop Watch, a free restock tracker: information only, no reselling or bot buying, no guarantee of stock, and Michigan law.", body, ld=(crumbs_ld((fname, "Terms of Use")),))

def build_transparency():
    """Transparency page: businesses that asked us to remove or change information, and what we did.
    Owner-approved mockup (Nov 23, 2026). Dates are US Eastern Time."""
    fname = "transparency/"
    def row(name, sub, asked, requested, done, stays, complied):
        subhtml = f'<span class="sub">{sub}</span>' if sub else ""
        return (f'<tr><th scope="row">{name}{subhtml}</th>\n'
                f'<td data-label="What they asked for">{asked}</td>\n'
                f'<td class="date" data-label="Date requested">{requested}</td>\n'
                f'<td data-label="What we removed (and what stayed)">{done}<span class="stays"><b>Stayed:</b> {stays}</span></td>\n'
                f'<td class="date" data-label="Date we complied">{complied}</td></tr>')
    rows = "\n".join([
        row("MIDORI*", "(a division of Designphil)", "Removal of all MIDORI products from the site.", "Nov 19, 2026",
            "Every MIDORI listing, stock tracker row, restock alert and restock email.",
            "a notice page explaining why these brands are no longer tracked.", "Nov 19, 2026"),
        row("Traveler&rsquo;s Company*", "(a division of Designphil)", "Removal of all Traveler&rsquo;s Company products from the site.", "Nov 19, 2026",
            "Every Traveler&rsquo;s Company listing, stock tracker row, restock alert and restock email.",
            "a notice page explaining why these brands are no longer tracked.", "Nov 19, 2026"),
        row("Kinokuniya Singapore", "", "Declined our request to check their stock.", "Nov 23, 2026",
            "All stock checking and stock status for this shop.",
            "a link to the shop, marked &ldquo;link only&rdquo;.", "Nov 23, 2026"),
    ])
    # Outstanding requests: permission emails to link-only shops (sent by the owner from admin@, Proton).
    # Records: drop-watch-drafts/permission-emails/ and STATUS. Update a row when a shop replies.
    ASK = "Written permission to check their stock."
    def orow(name, sent, status):
        return (f'<tr><th scope="row">{name}</th>\n'
                f'<td data-label="What we asked">{ASK}</td>\n'
                f'<td class="date" data-label="Sent">{sent}</td>\n'
                f'<td data-label="Status">{status}</td></tr>')
    outstanding = "\n".join([
        orow("Blesket Canada", "Nov 23, 2026", "Waiting for reply"),
        orow("Kinokuniya USA", "Nov 23, 2026", "Waiting for reply"),
        orow("Milligram", "Nov 23, 2026", "Waiting for reply"),
        orow("Notebook Therapy", "Nov 23, 2026", "Waiting for reply"),
    ])
    body = f"""
<article class="prose">
{crumbs((fname, "Transparency"))}
{eyebrow("Transparency", "updated Nov 26, 2026")}
<h1>Transparency</h1>
<p class="lede">We value transparency, and we believe you have a right to know what is and is not on this site so you can make your own decisions. The businesses below have asked us to remove or change information on Stationery Drop Watch. We have listed each one here, with what they asked for, what we removed or changed, what remains, and when.</p>
<div class="table-wrap"><table class="tp-table">
<thead><tr><th scope="col">Brand or shop</th><th scope="col">What they asked for</th><th scope="col">Date requested</th><th scope="col">What we removed (and what stayed)</th><th scope="col">Date we complied</th></tr></thead>
<tbody>
{rows}
</tbody></table></div>
<p class="tp-foot">* Both requests came in a single email from Traveler&rsquo;s Company.</p>
<h2 id="outstanding-requests">Outstanding requests</h2>
<p>These shops are listed as link only. We do not check their stock until they give us written permission. We emailed each one to ask, and this table shows where each request stands.</p>
<div class="table-wrap"><table class="tp-table">
<thead><tr><th scope="col">Brand/Shop</th><th scope="col">What we asked</th><th scope="col">Sent</th><th scope="col">Status</th></tr></thead>
<tbody>
{outstanding}
</tbody></table></div>
<p>Dates are US Eastern Time. If you run a shop or brand and would like something removed, write to {mailto_email()}.</p>
</article>"""
    desc = "Businesses that asked Stationery Drop Watch to remove or change information, what we removed, and our open permission requests to link-only shops."
    return page(fname, "Transparency", desc, body, ld=(crumbs_ld((fname, "Transparency")),))

# For shops page (/for-shops/): what our checker does on a shop's site, in plain words, for shop owners
# deciding whether to let us check their stock. Every claim is read from the code at build time or is a
# standing site rule: the User-Agent and per-shop delay come from scripts/checker.py, the check frequency is
# CHECK_FREQ, link-only shops are never requested (checker LINK_ONLY_HOSTS), and shop links carry no affiliate tag.
FOR_SHOPS_SLUG = "for-shops"
FOR_SHOPS_DATE = "2026-11-24"
_CHECKER_SRC = (ROOT / "scripts/checker.py").read_text()
CHECKER_UA = re.search(r'^UA = "([^"]+)"', _CHECKER_SRC, re.M).group(1)
CHECKER_DELAY = re.search(r'^DELAY = ([0-9.]+)', _CHECKER_SRC, re.M).group(1)
CHECKER_TOKEN = re.search(r'^ROBOTS_TOKEN = "([^"]+)"', _CHECKER_SRC, re.M).group(1)

def build_for_shops():
    fname = FOR_SHOPS_SLUG + "/"
    title = "For shops and brands"
    robots_name = "StationeryDropWatch"
    assert robots_name.lower() == CHECKER_TOKEN, "robots.txt example must match checker ROBOTS_TOKEN"
    body = f"""
<article class="prose">
{crumbs((fname, title))}
{eyebrow("For shops and brands", "updated Nov 24, 2026")}
<h1>For shops and brands</h1>
<p class="lede">Stationery Drop Watch is a free restock tracker for people who buy planners, journals and inks for themselves. If you run a shop, this page explains exactly what our checker does on your site, what it doesn't do, and how you stay in control.</p>

<h2>What we do</h2>
<ul>
<li>We check {CHECK_FREQ}. Each check reads the same public product information your shop already shows every visitor: whether a product or option is available, and the product title.</li>
<li>Every listing links straight to your own product page, so readers buy from you, on your site, at your price.</li>
<li>Our links carry no affiliate tag and no referral code. We don't charge shops anything, and we don't take a cut of any sale.</li>
</ul>

<h2>How our checker behaves on your site</h2>
<ul>
<li><strong>It says who it is.</strong> Every request identifies itself with this User-Agent, including a link back to us and an email address:<br><code>{E(CHECKER_UA)}</code></li>
<li><strong>It follows your robots.txt.</strong> It reads your robots.txt before checking. If you add a group for <code>{robots_name}</code>, that group is followed ahead of the general <code>*</code> rules.</li>
<li><strong>It goes slowly.</strong> It makes one request at a time to your shop and waits at least {CHECKER_DELAY} seconds between requests.</li>
<li><strong>It asks only for what we track.</strong> In each check that's about one request per product page we track, plus a small request for your store's currency setting. Two listings on the same product page share one request. For limited inks we also read your shop's own pre-order and coming-soon lists, and once a day your public product list, to spot new limited inks.</li>
<li><strong>It never shops.</strong> It doesn't log in, add to cart, reserve stock or check out.</li>
</ul>

<h2>Why this can't power checkout bots</h2>
<p>A status on our site is only as fresh as our last check, which is often half an hour old, sometimes more. Checkout bots work in seconds, so a page that updates {CHECK_FREQ} is no use to them. Our <a href="terms/#prohibited-uses">Terms</a> also forbid using the site, its alerts or its data for reselling, bulk or automated buying, or to feed any bot or buying service.</p>

<h2>You're in control</h2>
<ul>
<li><strong>Link only.</strong> We can list your shop as a plain link with no stock checks. Once your shop is link only, our checker sends your site no requests at all.</li>
<li><strong>Removal.</strong> We'll remove your products or your whole shop from our trackers on request (see section 12 of our <a href="terms/#for-shops-and-brands">Terms</a>). Our <a href="transparency/">Transparency</a> page lists every request like this, and what we changed.</li>
<li><strong>Block us yourself.</strong> Adding these two lines to your robots.txt stops our checks from the next check on:<br><code>User-agent: {robots_name}</code><br><code>Disallow: /</code></li>
</ul>

<h2>Want to be tracked, or have a question?</h2>
<p>If you'd like us to check your stock, or you'd like to talk about how we do it, email {mailto_email()}.</p>
</article>"""
    desc = "How our checker treats your shop: a named User-Agent, robots.txt respected, slow requests, no affiliate tags, and link only or removal on request."
    return fname, page(fname, title, desc, body, ld=(crumbs_ld((fname, title)),))

# Teachers Pay Teachers products page (/shop/teachers-pay-teachers/). Titles, grades, formats, page counts and
# bundle membership are copied from each product's own TpT page (checked Nov 27, 2026, 19 products).
# Page counts are the ones the TpT description states. The Complete Classroom Bundle Highlights field
# still showed 148 pages on that date; the description, cover and itemized list state 191 pages across 8 resources.
# No prices or availability anywhere on the page.
TPT_PAGE_PATH = "shop/teachers-pay-teachers/"
TPT_PAGE_DATE = "2026-11-27"
TPT_PRODUCTS = [
    dict(line='cp', bundle=False, slug='cute-pastel-calm-down-corner-kit',
         title='Cute Pastel Calm Down Corner Kit | Kawaii Breathing Cards + Calm Choices SEL',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Calm-Down-Corner-Kit-Kawaii-Breathing-Cards-Calm-Choices-SEL-18381516',
         grades='PreK-2', fmt='PDF', count='16 pages',
         desc='A calm corner kit: corner signs, breathing cards, a My Calm Choices board, break passes, a timer card and a Body Check poster. Learners notice the feeling, choose a tool, set the timer, check the body and head back to learning.',
         member_of=['Cute Pastel Complete Classroom Bundle', 'Cute Pastel Feelings & Behavior Mini Bundle']),
    dict(line='cp', bundle=False, slug='cute-pastel-classroom-jobs-chart',
         title='Cute Pastel Classroom Jobs Chart | Editable Job Cards with Pictures + Name Clips',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Classroom-Jobs-Chart-Editable-Job-Cards-with-Pictures-Name-Clips-18536234',
         grades='PreK-2', fmt='PDF and editable PowerPoint', count='19 pages',
         desc='24 classroom jobs, each with a picture, in two sizes, plus matching How to Do My Job cards, name cards and clips, two header banners and an editable PowerPoint.',
         member_of=['Cute Pastel Complete Classroom Bundle']),
    dict(line='cp', bundle=False, slug='cute-pastel-classroom-labels',
         title='Cute Pastel Classroom Labels | Editable Kawaii Supply Bin Labels with Pictures',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Classroom-Labels-Editable-Kawaii-Supply-Bin-Labels-with-Pictures-18381372',
         grades='PreK-2', fmt='PDF and editable PowerPoint', count='27 pages',
         desc='Picture-and-word labels for supply bins, centers, cubbies and teacher toolboxes, with 45 supply labels, 14 center signs and 16 cubby and name labels. Every label page comes as a print-ready PDF and as an editable file.',
         member_of=['Cute Pastel Complete Classroom Bundle', 'Cute Pastel Routines & Visuals Mini Bundle']),
    dict(line='cp', bundle=True, slug='cute-pastel-complete-classroom-bundle',
         title='Cute Pastel Complete Classroom Bundle | Visual Schedule, Labels, SEL & Behavior',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Complete-Classroom-Bundle-Visual-Schedule-Labels-SEL-Behavior-18381628',
         grades='PreK-2', fmt='', count='191 pages across 8 resources',
         desc='Eight matching Cute Pastel sets for a PreK-2 classroom: Visual Schedule Cards, First / Then & Now / Next Boards, Classroom Labels, Emotions & Feelings Check-In, Token Boards & Reward Charts, the Calm-Down Corner Kit, Classroom Jobs Chart and Morning Meeting Kit.',
         member_of=[]),
    dict(line='cp', bundle=True, slug='cute-pastel-feelings-behavior-mini-bundle',
         title='Cute Pastel Feelings & Behavior Mini Bundle | Emotions, Calm Corner & Tokens',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Feelings-Behavior-Mini-Bundle-Emotions-Calm-Corner-Tokens-18381659',
         grades='PreK-2', fmt='', count='70 pages across 3 resources',
         desc='Three matching Cute Pastel sets to help learners notice feelings, calm their bodies and celebrate good choices: Emotions & Feelings Check-In, Calm-Down Corner Kit and Token Boards & Reward Charts.',
         member_of=[]),
    dict(line='cp', bundle=False, slug='cute-pastel-feelings-check-in',
         title='Cute Pastel Feelings Check-In Cards & Posters | Kawaii Emotions + Calm Down SEL',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Feelings-Check-In-Cards-Posters-Kawaii-Emotions-Calm-Down-SEL-18381465',
         grades='PreK-2', fmt='PDF', count='16 pages',
         desc='Helps little learners name their feelings and choose a calm-down strategy, with 24 feelings cards, 8 coping cards, a class check-in poster, a desk mat and a Calm Down Choices poster.',
         member_of=['Cute Pastel Complete Classroom Bundle', 'Cute Pastel Feelings & Behavior Mini Bundle']),
    dict(line='cp', bundle=False, slug='cute-pastel-first-then-now-next',
         title='Cute Pastel First Then & Now Next Boards | Kawaii Visual Supports + Reward Cards',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-First-Then-Now-Next-Boards-Kawaii-Visual-Supports-Reward-Cards-18381421',
         grades='PreK-2', fmt='PDF', count='37 pages',
         desc='First / Then and Now / Next boards with bold labels, a clear arrow and drop zones that show what comes next. Includes 12 boards, 3 reward boards, desk strips and 32 reward and behavior cards.',
         member_of=['Cute Pastel Complete Classroom Bundle', 'Cute Pastel Routines & Visuals Mini Bundle']),
    dict(line='cp', bundle=False, slug='cute-pastel-morning-meeting-kit',
         title='Cute Pastel Morning Meeting Kit | Calendar, Weather, Feelings + Greeting Cards',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Morning-Meeting-Kit-Calendar-Weather-Feelings-Greeting-Cards-18536267',
         grades='PreK-2', fmt='PDF', count='24 pages',
         desc='A matching morning meeting set: calendar and weather pieces, feelings and greeting cards, a days-in-school tracker and a 4-step morning meeting poster.',
         member_of=['Cute Pastel Complete Classroom Bundle']),
    dict(line='cp', bundle=True, slug='cute-pastel-routines-visuals-mini-bundle',
         title='Cute Pastel Routines & Visuals Mini Bundle | Visual Schedule, First Then, Labels',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Routines-Visuals-Mini-Bundle-Visual-Schedule-First-Then-Labels-18381644',
         grades='PreK-2', fmt='', count='78 pages across 3 resources',
         desc='Three matching Cute Pastel sets to build clear, calm routines: Visual Schedule Cards, First / Then & Now / Next Boards and Classroom Labels.',
         member_of=[]),
    dict(line='cp', bundle=False, slug='cute-pastel-token-boards',
         title='Cute Pastel Token Boards & Reward Charts | Kawaii Token Economy + Sticker Charts',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Token-Boards-Reward-Charts-Kawaii-Token-Economy-Sticker-Charts-18381481',
         grades='PreK-2', fmt='PDF', count='38 pages',
         desc='Token boards that start with 3 tokens and move up to 5 and 10, with sticker charts and punch cards that can fade the board or go home. Includes 18 token boards, 24 reward choice cards, 216 tokens, 6 sticker charts and 8 mini punch cards.',
         member_of=['Cute Pastel Complete Classroom Bundle', 'Cute Pastel Feelings & Behavior Mini Bundle']),
    dict(line='cp', bundle=False, slug='cute-pastel-visual-schedule-cards',
         title='Cute Pastel Visual Schedule Cards | 43 Kawaii Daily Routine Cards PreK–2 & SpEd',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Visual-Schedule-Cards-43-Kawaii-Daily-Routine-Cards-PreK2-SpEd-18381500',
         grades='PreK-2', fmt='PDF', count='14 pages',
         desc='43 visual schedule cards from Arrival to Dismissal, each pairing a clear picture with a bold label and a color-coded border. Cards are 3.75 x 5 in, 4 per page, with a bonus blank card.',
         member_of=['Cute Pastel Complete Classroom Bundle', 'Cute Pastel Routines & Visuals Mini Bundle']),
    dict(line='cp', bundle=False, slug='cute-pastel-visual-schedule-free-starter',
         title='Cute Pastel Visual Schedule Cards FREE Starter Pack | 6 Kawaii Routine Cards',
         url='https://www.teacherspayteachers.com/Product/Cute-Pastel-Visual-Schedule-Cards-FREE-Starter-Pack-6-Kawaii-Routine-Cards-18381694',
         grades='PreK-2', fmt='PDF', count='4 pages',
         desc='Six Cute Pastel visual schedule cards (Lunch, Art, Music, Reading, Recess and Bathroom) plus a blank card, in the same size, style and print quality as the full Visual Schedule Cards set.',
         member_of=[]),
    dict(line='lu', bundle=False, slug='level-up-2027-student-planner',
         title='Level Up! 2027 Student Planner | Video Game Theme Printable Planner Grades 2-5',
         url='https://www.teacherspayteachers.com/Product/Level-Up-2027-Student-Planner-Video-Game-Theme-Printable-Planner-Grades-2-5-18365192',
         grades='2-5', fmt='PDF', count='170 pages',
         desc='A printable planner for 2027 where every month is a new Level with its own world, Main Quests, Side Quests and a Boss Battle. Dated 2027, Monday start; students plan their week, color their habits and earn XP up to Level 12.',
         member_of=['Level Up! Bundle']),
    dict(line='lu', bundle=False, slug='level-up-behavior-reward-system',
         title='Level Up! Behavior & Reward System | Video Game XP Chart, Badges & Coupons',
         url='https://www.teacherspayteachers.com/Product/Level-Up-Behavior-Reward-System-Video-Game-XP-Chart-Badges-Coupons-18536327',
         grades='2-5', fmt='PDF', count='24 pages, plus a low-ink version',
         desc='Students earn XP for kind choices, teamwork and trying their best, climb a 10-level ladder, collect badges and trade XP for power-up coupons. Includes an XP Menu, posters, class and player trackers, 18 badges and 24 coupons.',
         member_of=['Level Up! Bundle']),
    dict(line='lu', bundle=True, slug='level-up-bundle',
         title='Level Up! Bundle | Video Game Planner, Goals, Review, Behavior & Reading Log',
         url='https://www.teacherspayteachers.com/Product/Level-Up-Bundle-Video-Game-Planner-Goals-Review-Classroom-Kit-18365866',
         grades='2-5', fmt='PDF', count='',
         desc='The complete Level Up! set in one download: the 2027 Student Planner, Goal Setting Quest Pack, End of Year & Summer Review Packet, Classroom Quest Kit, Behavior & Reward System and XP Reading Log, all in the same original pixel-art video game world.',
         member_of=[]),
    dict(line='lu', bundle=False, slug='level-up-classroom-quest-kit',
         title='Level Up! Classroom Quest Kit | Video Game Reading Log, XP Chart & Brag Tags',
         url='https://www.teacherspayteachers.com/Product/Level-Up-Classroom-Quest-Kit-Video-Game-Reading-Log-XP-Chart-Brag-Tags-18365332',
         grades='2-5', fmt='PDF', count='21 pages',
         desc='Students earn XP for reading, homework, kindness and teamwork and climb the rank ladder from Rookie to Legend. Includes a reading quest log and map, brag tags, certificates and a pennant banner.',
         member_of=['Level Up! Bundle']),
    dict(line='lu', bundle=False, slug='level-up-end-of-year-review',
         title='Level Up! End of Year Review Packet | Video Game Theme Summer Review Puzzles',
         url='https://www.teacherspayteachers.com/Product/Level-Up-End-of-Year-Review-Packet-Video-Game-Theme-Summer-Review-Puzzles-18365295',
         grades='2-5', fmt='PDF', count='31 pages',
         desc='A review packet where students travel through 5 worlds of 4 challenges each: a word search, a math power-up, a maze and a logic grid. Includes a Level Map progress tracker and a 4-page answer key.',
         member_of=['Level Up! Bundle']),
    dict(line='lu', bundle=False, slug='level-up-goal-setting-quest-pack',
         title='Level Up! Goal Setting Quest Pack | Video Game Theme Goal & Habit Trackers',
         url='https://www.teacherspayteachers.com/Product/Level-Up-Goal-Setting-Quest-Pack-Video-Game-Theme-Goal-Habit-Trackers-18365256',
         grades='2-5', fmt='PDF', count='18 pages, plus a low-ink version',
         desc='Students pick a big goal (their Boss Challenge), break it into quest steps, earn XP as they practice and level up when they reach it. Includes habit trackers, a Quest Map, XP trackers and 12 achievement badges.',
         member_of=['Level Up! Bundle']),
    dict(line='lu', bundle=False, slug='level-up-xp-reading-log',
         title='Level Up! XP Reading Log | Video Game Reading Challenge, Quest Map & Bookmarks',
         url='https://www.teacherspayteachers.com/Product/Level-Up-XP-Reading-Log-Video-Game-Reading-Challenge-Quest-Map-Bookmarks-18536356',
         grades='2-5', fmt='PDF', count='20 pages, plus a low-ink version',
         desc='Readers earn XP for minutes or pages, explore genres on a quest map, write a Boss Battle book review and level up from Book Rookie to Super Reader. Includes weekly and monthly logs, a streak tracker, 16 bookmarks, a certificate and awards.',
         member_of=['Level Up! Bundle']),
]
TPT_LINES = (("lu", "Level Up!", "Pixel-art, video-game classroom printables for grades 2-5. Original pixel art, no characters from real games."),
             ("cp", "Cute Pastel", "Kawaii picture supports for PreK-2 and special education: visual schedules, First / Then boards, labels, classroom jobs, morning meeting, feelings and calm-down tools, and token boards."))



def build_tpt_page():
    """Low-prominence index of every product in our Teachers Pay Teachers store, with cover cards and plain TpT links."""
    fname = TPT_PAGE_PATH
    def asset(slug, w):
        return f"assets/tpt/{slug}-{w}.webp"
    def card(p):
        facts = [f"Grades {p['grades']}"]
        if p["fmt"]:
            facts.append(p["fmt"])
        if p["count"]:
            facts.append(p["count"])
        fl = "".join(f"<li>{E(f)}</li>" for f in facts)
        mem = ""
        if p["member_of"]:
            mem = '<p class="small"><b>Part of:</b> ' + "; ".join(E(m) for m in p["member_of"]) + ".</p>"
        kind = "Bundle" if p["bundle"] else "Resource"
        return (f'<li><article class="shop-card" id="{p["slug"]}">'
                f'<div class="shop-img"><img src="{asset(p["slug"], 600)}" srcset="/{asset(p["slug"], 300)} 300w, /{asset(p["slug"], 600)} 600w" sizes="(max-width:600px) 240px, 150px" '
                f'width="600" height="600" alt="Cover image of {E(p["title"])}" loading="lazy" decoding="async"></div>'
                f'<div><p class="eyebrow">{kind}</p><h3>{E(p["title"])}</h3><ul>{fl}</ul>'
                f'<p>{E(p["desc"])}</p>{mem}'
                f'<a class="btn" href="{E(p["url"])}" rel="noopener" target="_blank">View on Teachers Pay Teachers</a></div></article></li>')
    sections = ""
    for key, name, blurb in TPT_LINES:
        items = [p for p in TPT_PRODUCTS if p["line"] == key]
        bundles = [p for p in items if p["bundle"]]
        singles = [p for p in items if not p["bundle"]]
        sections += f'<h2 id="{key}">{E(name)}</h2><p class="muted">{E(blurb)}</p>'
        if bundles:
            sections += '<h3 class="tpt-sub">Bundles</h3><ul class="shop-list">' + "".join(card(p) for p in bundles) + "</ul>"
        sections += '<h3 class="tpt-sub">Individual resources</h3><ul class="shop-list">' + "".join(card(p) for p in singles) + "</ul>"
    n = len(TPT_PRODUCTS)
    body = f"""
<article class="prose shop shop-wide">
{crumbs(("shop/", "Shop"), (fname, "Teachers Pay Teachers"))}
{eyebrow("Shop", "Teachers Pay Teachers")}
<h1>Our Teachers Pay Teachers resources</h1>
<p class="lede">All {n} printable classroom resources in the Stationery Drop Watch store on Teachers Pay Teachers, in two lines: Level Up! (video-game theme, grades 2-5) and Cute Pastel (PreK-2 and special education).</p>
<p class="muted">Each card links to the product's own Teachers Pay Teachers page. Titles, grades, formats and page counts are copied from those pages. For current price and availability, check the Teachers Pay Teachers page. You can also <a href="{E(TPT_STORE)}" rel="noopener" target="_blank">see the whole store on Teachers Pay Teachers</a>, or go back to <a href="shop/">our shop</a>.</p>
{sections}
</article>"""
    def prod_ld(p):
        return {"@type": "Product", "name": p["title"], "url": p["url"],
                "image": BASE + asset(p["slug"], 600), "description": p["desc"]}
    items_ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Stationery Drop Watch on Teachers Pay Teachers",
                "numberOfItems": n,
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": prod_ld(p)} for i, p in enumerate(TPT_PRODUCTS)]}
    title = "Teachers Pay Teachers resources: Level Up! and Cute Pastel"
    desc = f"All {n} classroom printables in our Teachers Pay Teachers store: Level Up! planner and sets for grades 2-5, and Cute Pastel visual supports for PreK-2."
    return fname, page(fname, title, desc, body, ld=(crumbs_ld(("shop/", "Shop"), (fname, "Teachers Pay Teachers")), items_ld))

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
<p>Stationery Drop Watch is operated by Stationery Drop Watch LLC, a Michigan limited liability company.</p>
</section>
<h2>How it works</h2>
<p>A small script visits the public product pages of {n_checked} stores {CHECK_FREQ}, at a polite pace and following each store's robots.txt. It reads whether each listing can be bought right now. On a sold-out Hobonichi Store row, a short note passes on what Hobonichi's own store data says: a restock is planned, a restock is undecided, or sales have ended. Each brand family has its own section, never mixed: the <a href="{HOBO_TRACKER}">Hobonichi tracker</a> (the official store and independent shops){"".join(f', <a href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["name"])}</a> ({E(shop_names(k))})' for k in LIVE)}{f', and <a href="{INK_SLUG}/">limited-edition fountain pen inks</a> (Diamine, Sailor and Robert Oster, only at shops on each brand\'s own dealer list)' if INK_LIVE else ''}.{f' Separately, our <a href="{LAMY_SLUG}/">Lamy release calendar</a> lists Lamy&#x27;s special and limited edition pens, when each was first listed, and the authorized shops that sell them. It is not a tracker, and we don&#x27;t check stock on those links.' if LAMY_LIVE else ''} When a sold-out Hobonichi or dot grid listing becomes available again, it shows up in <a href="index.html#restocked">Recent restocks</a>. Restocks from all three trackers (Hobonichi, dot grid journals and limited-edition inks) also go out by email to the people who picked that tracker. Ink restocks show on the inks page.</p>
<p>We only show what the stores report. If a check fails, we say so instead of guessing.</p>
<p>Clip, the paper clip with the magnifying glass on our <a href="index.html">home page</a>, is the site's mascot.</p>
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
<p>Stationery Drop Watch LLC is run by Andrew Robinson and can be reached at {shown}. Questions, corrections, or a shop we should track are welcome.</p>
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
         title=f"Dot grid journal restock tracker: {dotgrid_checked_brand_names()}",
         desc=dotgrid_meta_desc(),
         og_image=OG_DOTGRID, og_alt=OG_DOTGRID_ALT,
         intro="Popular dot grid journals and limited editions sell out, and every brand only posts its own restocks. "
               f"We track a focused set of flagship dot grid notebooks from {dotgrid_checked_brand_names()}, size by size and color by color, plus Archer and Olive's dot grid refills. {dotgrid_where_checked()} "
               + (dotgrid_link_only_clause() + " " if dotgrid_link_only_clause() else "") +
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
        since_html = f' <span class="sub">since {time_tag(since)}</span>' if since and l["status"] != "unknown" else ""
        note = official_note(l)
        if note:
            since_html += f' <span class="sub official-note">{E(note)}</span>'
        rows.append(f"""<tr data-store="{E(l['store_id'])}" data-status="{E(l['status'])}" data-size="{E(listing_size(l))}" data-lang="{E(listing_language(l))}" data-country="{E(REGION.get(l['store_id'], ''))}"><td><a href="{E(l['url'])}" rel="noopener" target="_blank">{E(l['store'])}</a>{region_tag(l['store_id'])} <span class="sub">{E(l.get('title') or l['label'])}</span></td>
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
    if any(l["status"] == "link_only" for l in ls):
        status_opts += f'<option value="link_only">{LINK_LABEL}</option>'
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
    """Document title: the H1 ("<product> restock tracker") when it fits, so the title keeps the words
    people search for ("restock", and "2027" on the Hobonichi pages). A shorter fallback keeps both."""
    sec = g_sec(g)
    if g.get("seo_title"):
        return g["seo_title"]
    if len(g["h1"]) <= TITLE_LIMIT:
        return g["h1"]
    if sec == "dotgrid":
        return "Dot grid journal restock tracker"
    return f'Hobonichi {g["short"]} 2027 restock tracker'

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

# Search-title lead for each design family. "{name}" is the design's short name.
DESIGN_TITLE_PATTERNS = {
    "hobonichi-weeks-2027": "Hobonichi Weeks 2027 {name} restock tracker",
    "hobonichi-weeks-mega-2027": "Hobonichi Weeks Mega 2027 {name} restock tracker",
    "hobonichi-techo-2027-covers": "Hobonichi 2027 {name} cover restock tracker",
    "hobonichi-techo-2027-hon": "Hobonichi HON 2027 {name} restock tracker",
    "hobonichi-techo-2027-original-a6": "Hobonichi Techo 2027 {name} restock tracker",
    "hobonichi-techo-2027-cousin-a5": "Hobonichi Cousin 2027 {name} restock tracker",
    DOTGRID_SLUG: "{name} dot grid restock tracker",
}

def design_seo_title(d):
    """Search title that keeps "restock" (and "2027" on Hobonichi pages) within TITLE_LIMIT.
    Tries the full design name, then without an artist or brand prefix ("tanakadaisuke: "),
    then without the word "tracker", then the short family wording."""
    pat = DESIGN_TITLE_PATTERNS.get(d["parent"], "{name} restock tracker")
    name = d["name"]
    short = name
    if ": " in name:  # keep a leading size ("A5 Bow & Tie: …" -> "A5 …") so A5 and A6 pages stay distinct
        head, rest = name.split(": ", 1)
        size = re.match(r"(A\d|B\d)\b", head)
        short = (size.group(1) + " " if size else "") + rest
    tries = [pat.format(name=name), pat.format(name=short),
             pat.format(name=name).replace(" restock tracker", " restock"),
             pat.format(name=short).replace(" restock tracker", " restock")]
    if d["parent"] != DOTGRID_SLUG:  # drop the leading "Hobonichi " before giving up the family name
        tries += [t.replace("Hobonichi ", "", 1) for t in tries[:4]]
        tries.append(f'{short} 2027 restock')
    for t in tries:
        if len(t) <= TITLE_LIMIT:
            return t
    return tries[-1]

def design_is_link_only(d):
    """Every shop that lists this design is link-only, so the page makes no stock claim.
    These pages stay up and linked, but are noindex and left out of the sitemap."""
    return not design_listings(d) and bool(link_listings(d["match"]))

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
    link_sections = {}
    for l in link_listings(g["match"]):
        link_sections.setdefault(listing_group_id(l), []).append(l)
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
        mpl = None if dp else merged_parent_link(sl, here=g["slug"])
        if mpl:  # merged design (Nov 27, 2026): point at the page it folded into
            dp_link = f' · <a href="{mpl[0]}">{E(mpl[1])}</a>'
        md, md_to = merged_design_for(sl) if cid else (None, None)
        merged_note = (f'<p class="muted small">{E(design_about(md))}</p>'
                       if md and md_to == g["slug"] and not dp else "")
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
    <tbody>{status_rows(sl)}{link_status_rows(link_sections.get(cid, []))}</tbody>
  </table></div>
  {link_note(link_sections.get(cid, []))}
  {merged_note}
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
    card_filter = list_filter(ls + link_listings(g["match"]), g.get("search_hint") or "Shop or design")
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

# Nov 27, 2026 (owner, 2:02 AM ET; seo/thin-pages-plan-2026-11-27.md): single-shop design pages with fewer than
# 3 recorded restocks and no impressions in the owner's GSC export (Oct 25 - Nov 24) fold into their parent page.
# The listings stay as normal rows on every tracker; only the separate design URL goes (301 to the parent).
# Held back (GSC impressions): Apothecary Shelf, Storybook in Navy and the three Scribbles That Matter pages.
MERGED_DESIGN_TARGETS = {
    **{f"{DOTGRID_SLUG}/archer-and-olive-{s}": AO_SLUG for s in
       ("cozy-critters", "ice-castle", "songbird-beige", "stag", "storybook-olive", "winter-train")},
    "hobonichi-techo-2027-covers/puppet-sunsun-s-a5": "hobonichi-techo-2027-covers",
    "hobonichi-techo-2027-covers/puppet-sunsun-wa-a6": "hobonichi-techo-2027-covers",
}
MERGED_DESIGNS = [d for d in DESIGNS if f'{d["parent"]}/{d["slug"]}' in MERGED_DESIGN_TARGETS]
assert len(MERGED_DESIGNS) == len(MERGED_DESIGN_TARGETS), "a merged design slug no longer exists"
DESIGNS = [d for d in DESIGNS if d not in MERGED_DESIGNS]
for _d in MERGED_DESIGNS:
    _to = MERGED_DESIGN_TARGETS[f'{_d["parent"]}/{_d["slug"]}'] + "/"
    REDIRECTS[f'{_d["parent"]}/{_d["slug"]}'] = _to
    if _d["parent"] == DOTGRID_SLUG:  # the pre-Nov 21 URL goes straight to the parent too (no chain)
        REDIRECTS[f'{AO_SLUG}/{_d["slug"]}'] = _to

def merged_design_for(listings):
    """(design, parent slug) of a merged design that covers these listings, or (None, None)."""
    for d in MERGED_DESIGNS:
        if any(d["match"](l) for l in listings):
            return d, MERGED_DESIGN_TARGETS[f'{d["parent"]}/{d["slug"]}']
    return None, None

def merged_parent_link(listings, here=None):
    """(href, label) pointing a merged design's rows at the page it folded into; None on that page itself."""
    d, to = merged_design_for(listings)
    if not d or to == here:
        return None
    g = next(x for x in GROUPS if x["slug"] == to)
    return to + "/", f'{g["short"]} page'

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

# ---- Design-page enrichment (Nov 27, 2026; seo/thin-pages-plan-2026-11-27.md) ----
# Every sentence below is computed from stock.json / changes.json / REGION at build time. No hand-written facts,
# no predictions. A section is left out when its data is missing.
_STATUS_LOW = {"in_stock": "in stock", "preorder": "preorder", "coming_soon": "not yet on sale", "sold_out": "sold out"}

def _plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"

def _minutes(a, b):
    return round((dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds() / 60)

def design_events(ls):
    """Logged status changes for these listings, oldest first."""
    urls = {l["url"] for l in ls}
    return sorted((c for c in changes if c["url"] in urls), key=lambda c: c["at"])

def restock_sellout_pairs(evs):
    """(restock, sell-out) pairs: a restock and the next logged change at the same URL that took it out of stock."""
    pairs = []
    for i, c in enumerate(evs):
        if not is_restock_event(c):
            continue
        nxt = next((x for x in evs[i + 1:] if x["url"] == c["url"]), None)
        if nxt and nxt["from"] in BUYABLE and nxt["to"] in NOT_BUYABLE:
            pairs.append((c, nxt))
    return pairs

def design_format_key(d):
    """Same design in another format: drop the size or Weeks-cover marker from the slug."""
    k = re.sub(r"^(a5|a6)-", "", d["slug"])
    return re.sub(r"-(a5|a6|weeks-cover)$", "", k)

def design_series(d):
    """Artist or series exactly as the design name gives it ("tanakadaisuke: Starlight" -> "tanakadaisuke")."""
    name = re.sub(r"^A[56] ", "", d["name"])
    if ":" in name:
        return name.split(":", 1)[0].strip()
    for brand in ("Archer and Olive", "Leuchtturm1917", "Scribbles That Matter"):
        if name.startswith(brand):
            return brand
    return None

def related_designs(d):
    """(other formats, same artist/series): indexable design pages only, never this one."""
    pool = [x for x in DESIGNS if x is not d and not design_is_link_only(x) and design_listings(x)]
    fmt = [x for x in pool if design_format_key(x) == design_format_key(d)]
    ser = design_series(d)
    same = [x for x in pool if ser and x not in fmt and (design_series(x) or "").lower() == ser.lower()]
    return fmt, same, ser

def design_history_html(d, ls, parent):
    evs = design_events(ls)
    shop_of = {l["url"]: l["store"] for l in ls}  # today's shop name (older log rows can carry an earlier spelling)
    first = min((l for l in ls if l.get("first_seen")), key=lambda l: l["first_seen"], default=None)
    out = []
    if first:
        out.append(f'<p>We started tracking {E(d["name"])} on {time_tag(first["first_seen"])} at {E(first["store"])}.</p>')
    if evs:
        rs = [c for c in evs if is_restock_event(c)]
        so = [c for c in evs if c["from"] in BUYABLE and c["to"] in NOT_BUYABLE]
        other = len(evs) - len(rs) - len(so)
        shops_ = sorted({shop_of.get(c["url"], c["store"]) for c in evs})
        bits = [_plural(len(rs), "restock"), _plural(len(so), "sell-out")] + ([_plural(other, "other change")] if other else [])
        out.append(f'<p>Since then we\'ve recorded {_plural(len(evs), "status change")} at {E(names_and(shops_))}: {names_and(bits)}.</p>')
        pairs = restock_sellout_pairs(evs)
        if pairs:
            mins = sorted(_minutes(a["at"], b["at"]) for a, b in pairs)
            span = f"{mins[0]} minutes" if mins[0] == mins[-1] else f"{mins[0]} to {mins[-1]} minutes"
            lead = ("Each time we recorded it coming back, we recorded it sold out again" if len(pairs) == len(rs)
                    else f"For {len(pairs)} of the {_plural(len(rs), 'restock')}, we recorded it sold out again")
            out.append(f'<p>{lead} {span} later (we check {CHECK_FREQ}).</p>')
        per_shop = {}
        for l in ls:
            per_shop[l["store_id"]] = per_shop.get(l["store_id"], 0) + 1
        label = {l["url"]: (l.get("title") or l["label"]) for l in ls}
        who = lambda c: E(shop_of.get(c["url"], c["store"])) + (f' ({E(label.get(c["url"], c["label"]))})' if per_shop.get(c["store_id"], 0) > 1 else "")
        items = "".join(
            f'<li>{time_tag(c["at"])} · {who(c)}: {_STATUS_LOW.get(c["from"], c["from"])} → {_STATUS_LOW.get(c["to"], c["to"])}</li>'
            for c in reversed(evs[-12:]))
        more = f'<p class="muted small">The latest 12 of {len(evs)} changes.</p>' if len(evs) > 12 else ""
        out.append(f'<ul class="link-list">{items}</ul>{more}')
    elif first:
        out.append(f'<p>We haven\'t recorded a status change at any shop we check since then.</p>')
    # one comparison across the parent's design pages, from the same run
    sibs = [x for x in designs_of(parent["slug"]) if not design_is_link_only(x) and design_listings(x)]
    if len(sibs) > 1:
        buyable = lambda x: any(l["status"] in BUYABLE for l in design_listings(x))
        if any(l["status"] in BUYABLE for l in ls):
            n = sum(buyable(x) for x in sibs)
            out.append(f'<p class="muted small">At the last check, {n} of the {len(sibs)} designs with their own page under {E(parent["short"])} were in stock or on preorder at one or more shops, this one included.</p>')
        else:
            none_ = [x for x in sibs if not buyable(x)]
            if len(none_) == 1:
                out.append(f'<p class="muted small">At the last check, this was the only one of the {len(sibs)} designs with their own page under {E(parent["short"])} that no shop we could check had in stock or on preorder.</p>')
            else:
                others = names_and([x["name"] for x in none_ if x is not d])
                out.append(f'<p class="muted small">At the last check, this was one of {len(none_)} designs (of {len(sibs)} with their own page under {E(parent["short"])}) that no shop we could check had in stock or on preorder. The {"other is" if len(none_) == 2 else "others are"} {E(others)}.</p>')
    return f'<section class="card" id="history"><h2>Stock history</h2>{"".join(out)}</section>' if out else ""

def design_where_html(ls, lsl):
    by = {}
    for l in ls:
        by.setdefault(l["store_id"], []).append(l)
    rows = []
    for sid, xs in sorted(by.items(), key=lambda kv: (min(l["first_seen"] for l in kv[1] if l.get("first_seen")) if any(l.get("first_seen") for l in kv[1]) else "~", kv[1][0]["store"])):
        since = min((l["first_seen"] for l in xs if l.get("first_seen")), default=None)
        if len(xs) == 1:
            l = xs[0]
            if l["status"] == "unknown":
                cur = "Couldn't check this run"
            elif l.get("status_since") and l.get("status_since") == l.get("first_seen"):
                cur = f'{STATUS[l["status"]]} at every check since we started tracking it'
            elif l.get("status_since"):
                cur = f'{STATUS[l["status"]]} at every check since {time_tag(l["status_since"])}'
            else:
                cur = STATUS[l["status"]]
        else:
            cur = E(count_line(xs).capitalize())
        country = REGION_NAME.get(REGION.get(sid, ""), "")
        rows.append(f'<tr><td>{E(xs[0]["store"])}</td><td>{E(country)}</td><td>{time_tag(since) if since else ""}</td><td>{cur}</td></tr>')
    lo = sorted({l["store"] for l in lsl})
    lo_html = f'<p class="muted small">Also linked, stock not checked: {E(names_and(lo))}.</p>' if lo else ""
    return (f'<section class="card" id="where"><h2>Where we track it</h2><div class="table-wrap"><table class="stock">'
            f'<thead><tr><th>Shop</th><th>Country</th><th>Tracking since</th><th>Status</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>{lo_html}</section>')

def design_formats_html(ls):
    def tally(fn, missing):
        c = {}
        for l in ls:
            k = fn(l) or missing
            c[k] = c.get(k, 0) + 1
        return " · ".join(f"{E(k)} ({v})" for k, v in sorted(c.items(), key=lambda kv: (kv[0] == missing, -kv[1], kv[0])))
    rows = [("Type", tally(lambda l: l.get("type"), "not stated")),
            ("Size", tally(listing_size, "not stated")),
            ("Language named in the listing", tally(listing_language, "not named"))]
    lis = "".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in rows)
    return (f'<section class="card" id="formats"><h2>Formats and versions</h2>'
            f'<p class="muted small">From the {_plural(len(ls), "listing")} we track. Size and language come only from what each shop\'s own label or title says; each title is listed under Sources.</p>'
            f'<ul class="link-list">{lis}</ul></section>')

def design_related_html(d):
    fmt, same, ser = related_designs(d)
    def li(x):
        return f'<li><a href="{design_fname(x)}">{E(x["full"])}</a> <span class="muted small">· {E(count_line(design_listings(x)))}</span></li>'
    parts = []
    if fmt:
        parts.append(f'<h3>Same design, other formats</h3><ul class="link-list">{"".join(li(x) for x in fmt)}</ul>')
    if same:
        parts.append(f'<h3>More {E(ser)} designs we track</h3><ul class="link-list">{"".join(li(x) for x in same)}</ul>')
    return f'<section class="card" id="related"><h2>Related designs</h2>{"".join(parts)}<p class="muted small">Counts are from the same check as this page.</p></section>' if parts else ""

def design_extra_qa(d, ls):
    """Two FAQ answers from the change log. The second only when at least 2 restock/sell-out pairs exist."""
    evs = design_events(ls)
    buy = [l for l in ls if l["status"] in BUYABLE]
    run = fmt_et(stock["run_finished"])
    if buy:
        a = f"At the last check ({run}) it was in stock or on preorder at {names_and(sorted({l['store'] for l in buy}))}."
    else:
        out_ = [c for c in evs if c["from"] in BUYABLE]
        if out_:
            c = out_[-1]
            back = next((x for x in reversed(evs) if x["url"] == c["url"] and x["at"] < c["at"] and is_restock_event(x)), None)
            shop_now = next((l["store"] for l in ls if l["url"] == c["url"]), c["store"])
            a = (f"The last time we recorded it in stock or on preorder was at {shop_now}"
                 + (f", from {fmt_et(back['at'])}" if back else "")
                 + f" until {fmt_et(c['at'])}, when it was {_STATUS_LOW.get(c['to'], c['to'])}.")
        else:
            start = tracking_start(ls)
            a = f"We haven't recorded it in stock or on preorder at any shop we check since we started tracking it on {fmt_et(start)}."
    qa = [(f'When was {d["full"]} last in stock?', a)]
    pairs = restock_sellout_pairs(evs)
    if len(pairs) >= 2:
        mins = sorted(_minutes(x["at"], y["at"]) for x, y in pairs)
        qa.append((f'How fast does {d["full"]} sell out?',
                   f"The {len(pairs)} times we recorded it coming back and then selling out again, we recorded the sell-out {mins[0]} to {mins[-1]} minutes later. "
                   f"We check {CHECK_FREQ}, so a faster sell-out shows up at the next check."))
    return qa

def build_design(d, oe=None):
    parent = next(g for g in GROUPS if g["slug"] == d["parent"])
    ls = design_listings(d)
    lsl = link_listings(d["match"])
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
  {list_filter(ls + lsl, "Shop name")}
  {sold_everywhere_html(ls)}
  <div class="table-wrap"><table class="stock">
    <thead><tr><th>Shop</th><th>Status</th></tr></thead>
    <tbody>{status_rows(ls)}{link_status_rows(lsl)}</tbody>
  </table></div>
  {link_note(lsl)}
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
            if shops == 1:
                a1 = f"No. At the last check ({when}) {names(ls)} didn't have it in stock or on preorder."
            else:
                a1 = (f"Not at the shops we track. At the last check ({when}) none of the {of} had it in stock or on preorder." if chk > 1 else
                      f"Not at the shops we track. At the last check ({when}) the {'one shop we could check' if unk else 'one shop we track'} didn't have it in stock or on preorder.")
        elif shops == 1:
            avail = ("in stock" if any(l["status"] == "in_stock" for l in buy) else "on preorder")
            a1 = f"Yes, {avail} at {names(buy)} at the last check ({when}). Stock can change within minutes, so confirm on the shop's page."
        else:
            a1 = f"Yes, at {len({l['store_id'] for l in buy})} of {of} at the last check ({when}): {names(buy)}. Stock can change within minutes, so confirm on the shop's page."
        if unk:
            a1 += (f" We couldn't check {nshops(len(unk), 'listing')} at {names(unk)} this run, so we don't know {'its' if len(unk) == 1 else 'their'} status."
                   if shops == 1 else f" We couldn't check {names(unk)} this run, so we don't know their status.")
    a2 = (f"We track it at {shops} {'shop' if shops == 1 else 'shops'}: {names(ls)}. Each name in the table above opens that shop's own listing."
          if ls else "No shop we check lists it right now.")
    lo = sorted({l["store"] for l in lsl})
    if lo and ls:  # link-only rows are in the table and Store filter above, so the answer names them too
        one = len(lo) == 1
        who = lo[0] if one else ", ".join(lo[:-1]) + " and " + lo[-1]
        a2 += (f" We also link to {who} (link only, so check stock on the shop's page)." if one else
               f" We also link to {who} (links only, so check stock on each shop's page).")
    vers = sorted({(l.get("title") or l["label"]) for l in ls})
    a_v = (f"We track {len(ls)} {'listing' if len(ls) == 1 else 'listings'}. In {"the shop's" if shops == 1 else "each shop's"} own words: " + "; ".join(vers) + "." if ls else "None right now.")
    qa = [(f'Is {d["full"]} in stock?', a1),
          (f'Which sizes and versions of {d["full"]} do you track?', a_v),
          (f'Where can I buy {d["full"]}?', a2),
          *(design_extra_qa(d, ls) if ls else []),
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
    extra_links = UNCHECKED_LINKS.get(d["parent"] + "/" + d["slug"], []) + [
        dict(store=l["store"], url=l["url"], note="Link to the shop's own page. We don't check this shop's stock.") for l in sorted(lsl, key=lambda l: l["store"])]
    extra_html = ""
    if extra_links:
        items = "".join(
            f'<li><a href="{E(x["url"])}" rel="noopener" target="_blank">{E(x["store"])}</a> '
            f'<span class="muted small">{E(x["note"])}</span></li>' for x in extra_links)
        extra_html = f'<p class="muted small">Not checked</p><ul class="link-list">{items}</ul>'
    sources_html = f"""<section class="card" id="sources"><h2>Sources</h2>
  <p class="muted small">Statuses come from each shop's own public product page, read by our checker at the time shown. Each status links to the shop's own page, so you can confirm it there.</p>
  <ul class="link-list">{sources}</ul>{extra_html}</section>""" if ls or extra_links else ""
    sibs = "".join(f'<li><a href="{design_fname(x)}">{E(x["name"])}</a></li>' for x in designs_of(d["parent"]) if x is not d)
    others = (f'<li><a href="{parent["slug"]}/">All {E(parent["short"])} designs</a></li>' + sibs
              + (f'<li><a href="{HOBO_TRACKER}#tracker">Hobonichi tracker (every listing)</a></li>' if sec == "hobonichi" else f'<li><a href="{parent["slug"]}/#tracker">Every listing on the {E(parent["short"])} page</a></li>'))
    intro = (f'{E(design_about(d))} This page shows its stock at every shop we track, checked {CHECK_FREQ}. '
             f'For every design, see the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a>.')
    eyebrow_html = eyebrow(ey, nshops(shops), f"checked {CHECK_FREQ}")
    facts_html = hero_facts(ls)
    restock_card = f'<section class="card"><h2>Recent restocks</h2>{restock_html}</section>'
    enrich_html = (design_history_html(d, ls, parent) + design_where_html(ls, lsl) + design_formats_html(ls)
                   + design_related_html(d)) if ls else ""
    if not ls and lsl:
        # Every shop that lists this design is link-only (Notebook Therapy since Nov 23, 2026): no stock claim at all.
        lo_shops = names_and(sorted({l["store"] for l in lsl}))
        one = len({l["store_id"] for l in lsl}) == 1
        h1 = f'{d["full"]}: link only'
        eyebrow_html = eyebrow(ey, "link only", "stock not checked")
        intro = (f'{E(design_about(d))} We list it as a link only: we don\'t check its stock at {E(lo_shops)}, so no status is shown. '
                 f'Open the shop\'s page to see what it has. For the designs we do check, see the <a href="{parent["slug"]}/">{E(parent["short"])} restock page</a>.')
        facts_html = ""
        restock_card = ""
        enrich_html = ""
        table = (f'<section class="card group-sec" id="stock"><h2>Where to find it</h2>{list_filter(lsl, "Shop name")}<div class="table-wrap"><table class="stock">'
                 f'<thead><tr><th>Shop</th><th>Status</th></tr></thead><tbody>{link_status_rows(lsl)}</tbody></table></div>{link_note(lsl)}'
                 f'<p class="muted small card-empty" hidden>Nothing on this page matches those filters.</p></section>')
        lo_answer = (f"We don't check. {lo_shops} {'is' if one else 'are'} listed as {'a link only' if one else 'links only'}, so no status is shown. "
                     "Open the shop's page to see what it has.")
        qa = [(f'Is {d["full"]} in stock?', lo_answer),
              (f'Where can I buy {d["full"]}?', f"{lo_shops} {'sells' if one else 'sell'} it. The link above opens {'the shop' if one else 'each shop'}'s own page. We don't check {'its' if one else 'their'} stock.")]
        faq_html = '<section class="card faq" id="faq"><h2>Questions</h2>' + "".join(
            f'<details class="faq-item"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in qa) + "</section>"
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa]}
        sources_html = f'<section class="card" id="sources"><h2>Shop links</h2>{extra_html}</section>' if extra_html else ""
    body = f"""
<div class="product-page">
{crumbs(*hub_trail(parent), (parent["slug"] + "/", parent["short"]), (fname, d["name"]))}
<section class="hero hero-compact">
  {eyebrow_html}
  <h1>{E(h1)}</h1>
  <p class="lede">{intro}</p>
  {thanks}
  {facts_html}
  {signup_for(section=sec)}
</section>
<div class="layout">
  <div class="main-col">
    <div class="m-lead">{table}</div>
    {restock_card}
    {enrich_html}
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
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": h1.replace(" restock tracker", "").replace(": link only", "") + (": listings we track" if ls or not lsl else ": shop links (stock not checked)"),
             "numberOfItems": len(ls), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": f"{l.get('title') or l['label']} at {l['store']}", "url": l["url"]}
                 for i, l in enumerate(sorted(ls, key=lambda l: l["store"]))]}
    title = design_seo_title(d)
    desc = design_seo_desc(d, shops)
    if not ls and lsl:
        title = f'{d["name"]} · link only'
        desc = f"{d['name']}: we list it as a link only and don't check its stock. Open the shop's own page to see what it has."[:DESC_LIMIT]
    return fname, page(fname, title, desc, body, ld=(crumbs_ld(*hub_trail(parent), (parent["slug"] + "/", parent["short"]), (fname, d["name"])), items, faq_ld),
                       og_image=parent.get("og_image", OG_IMAGE), og_alt=parent.get("og_alt", OG_ALT), noindex=design_is_link_only(d))

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
    ("Can I use alerts for reselling?",
     "No. Stationery Drop Watch is for people buying for their own use. Our {terms} prohibit using the site, its alerts or its data for reselling, scalping or bot purchasing."),
]

FAQ_TRACKS = {  # one sentence per live section for "What do you track?"
    "dotgrid": "On a separate dot grid journals page, we track a focused set of flagship dot grid notebooks from {dg}, size by size and color by color, plus Archer and Olive's dot grid refills.{dg_lo}",
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
    n = len({p["store_id"] for p in stock["products"]} | ({r["store_id"] for r in LINK_ROWS} if COUNT_LINK_ONLY_IN_SHOP_TOTALS else set()))
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
    if LAMY_LIVE:
        pens_txt += " Our Lamy release calendar lists Lamy's special and limited edition pens and the authorized shops that sell them, without stock checks."
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
    qa = [(q, a.format(n=n, nh=N_HOBO, secs=secs, tracks=tracks.format(dg=dotgrid_checked_brand_names(), dg_lo=(" " + dotgrid_link_only_clause() if dotgrid_link_only_clause() else "")), shop=url_for("shop/"), unchecked=unchecked, terms="Terms of Use (" + url_for("terms/") + "#prohibited-uses)"),
           E(a).format(n=n, nh=N_HOBO, secs=E(secs), tracks=E(tracks.format(dg=dotgrid_checked_brand_names(), dg_lo=(" " + dotgrid_link_only_clause() if dotgrid_link_only_clause() else ""))), shop=f'<a href="shop/">{E(SHOP_NAME.lower())}</a>', unchecked=E(unchecked), terms='<a href="terms/#prohibited-uses">Terms of Use</a>')) for q, a in pairs]
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

STATIC_LASTMOD = {"hobonichi-2027/": "2026-11-27", "about/": "2026-11-22", "privacy/": "2026-11-22", "terms/": "2026-11-23", "transparency/": "2026-11-25", TPT_PAGE_PATH: TPT_PAGE_DATE, FOR_SHOPS_SLUG + "/": FOR_SHOPS_DATE}

def build_sitemap():
    home_mod = latest(*[p.get("status_since") for p in stock["products"]], *[c["at"] for c in changes], CONTENT_LASTMOD)
    urls = [(url_for("index.html"), home_mod), (url_for(HOBO_TRACKER), latest(*[p.get("status_since") for p in hobo_products()], *[c["at"] for c in changes], CONTENT_LASTMOD))]
    urls += [(url_for(g["slug"] + "/"), group_lastmod(g)) for g in GROUPS]
    urls += [(url_for(design_fname(d)), design_lastmod(d)) for d in DESIGNS if not design_is_link_only(d)]
    if INK_LIVE:
        urls.append((url_for(INK_SLUG + "/"), ink_lastmod()))
    if LAMY_LIVE:
        urls.append((url_for(LAMY_SLUG + "/"), lamy_lastmod()))
    urls += [(url_for(f), d) for f, d in STATIC_LASTMOD.items()]
    urls += [(url_for(slug + "/"), TAKEDOWN_DATE) for slug in (TN_SLUG,)]  # the indexed takedown notices
    hobo_mod = latest(*[p.get("status_since") for p in hobo_products()], GUIDES_LASTMOD)
    urls += [(url_for(WTB_SLUG + "/"), latest(hobo_mod, CONTENT_LASTMOD)), (url_for(VS_SLUG + "/"), latest(GUIDES_LASTMOD, CONTENT_LASTMOD, guide_modified(build_vs))), (url_for(JAN_APR_SLUG + "/"), latest(JAN_APR_MODIFIED, guide_modified(build_january_april))), (url_for(DG_GUIDE_SLUG + "/"), latest(*[p.get("status_since") for p in section_products("dotgrid")], DG_GUIDE_LASTMOD, CONTENT_LASTMOD, guide_modified(build_dotgrid_guide))), (url_for(GIFT_SLUG + "/"), latest(*[p.get("status_since") for k in GIFT_PICKS for p in gift_listings(k)], guide_modified(build_gift_guide))), (url_for("guides/"), latest(DG_GUIDE_LASTMOD, TAKEDOWN_DATE, CONTENT_LASTMOD)), (url_for("shop/"), shop_lastmod()), (url_for("follow/"), "2026-11-12"), (url_for("contact/"), "2026-11-20"), (url_for(SOLDOUT_SLUG + "/"), latest(*[p.get("status_since") for p in stock["products"]], CONTENT_LASTMOD))]
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

ROBOTS = f"""# Stationery Drop Watch is for personal shopping only.
# Using this site or its data for reselling, bulk buying,
# or automated purchasing is not allowed.
# See {BASE}terms/#prohibited-uses
User-agent: *
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
<p><a class="btn" href="{HOBO_TRACKER}">Go to the Hobonichi tracker</a> {" ".join([f'<a class="btn-ghost" href="{SECTIONS[k]["slug"]}/">{E(SECTIONS[k]["nav"])}</a>' for k in LIVE] + ([f'<a class="btn-ghost" href="{INK_SLUG}/">{E(INK_NAV)}</a>'] if INK_LIVE else []) + ([f'<a class="btn-ghost" href="{LAMY_SLUG}/">{E(LAMY_NAV)}</a>'] if LAMY_LIVE else []))}</p>
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
GIFT_PUBLISHED = "2026-11-20"  # PR #52 merged Fri Nov 20, 2026, 9:13 AM ET
DG_GUIDE_LASTMOD = "2026-11-20"  # STM Pro sizes, Leuchtturm formats, and TN wording (America/Detroit)
GUIDE_BLURBS = {WTB_SLUG + "/": "Which shops have each 2027 Original A6, Cousin A5, Weeks and Weeks Mega in stock right now, checked about every 30 minutes, plus tips for catching a restock.",
                VS_SLUG + "/": "Size, weight, daily vs weekly layout and pages for the three most popular Hobonichi books, from Hobonichi's own specs, and who each one suits.",
                JAN_APR_SLUG + "/": "Hobonichi's April-start (Spring) techo comes in fewer versions than the January-start edition and goes on sale on February 1.",
                "hobonichi-2027/": "When the 2027 planners launched, the October wave, and when restocks usually land, with sources.",
                DG_GUIDE_SLUG + "/": "Archer and Olive vs Leuchtturm1917 vs Scribbles That Matter vs Notebook Therapy: paper gsm, pages, size and features from each maker's own page, with live stock where we check it.",
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
                f'<li><a href="{design_fname(d)}">{E(d["full"])}</a> <span class="muted small">· {E(count_line(design_listings(d)) if design_listings(d) or not link_listings(d["match"]) else "link only, stock not checked")}</span></li>' for d in ds) + "</ul>")
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

def _shop_table(ls, links=()):
    rank = {s["id"]: i for i, s in enumerate(stores["stores"])}
    canon = {c["id"]: c["label"] for c in stores["canonical"]}
    order = {"in_stock": 0, "preorder": 1, "coming_soon": 2, "sold_out": 3, "unknown": 4, "link_only": 5}
    by = {}
    for l in list(ls) + list(links):
        by.setdefault(l["store_id"], []).append(l)
    rows = []
    for sid in sorted(by, key=lambda s: (min(order[l["status"]] for l in by[s]), rank.get(s, 99))):
        items = "".join(
            f'<li><a href="{E(l["url"])}" rel="noopener" target="_blank">{E(canon.get(l.get("canonical") or "") or l.get("title") or l["label"])}</a> '
            f'{status_badge(l["status"])}</li>'
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
  {_shop_table(ls, link_listings(g["match"]))}
  <p class="small"><a href="{g["slug"]}/">Full {E(g["short"])} restock page</a> <span class="muted">· every listing, when it last changed, and recent restocks</span></p>
  </div>
</details>''')
    unchecked = listed_unchecked() + listed_link_only()
    not_checked = "".join(f'<li><a href="{E(n["url"])}" rel="noopener" target="_blank">{E(n["name"])}</a> <span class="muted">· {E(n["reason"] or "")}</span></li>' for n in unchecked)
    if len(unchecked) == 1:
        unchecked_head, unchecked_blurb = "Shop we list but can't check", "Its site blocks automated checks, so we link to it without a status."
    else:
        unchecked_head, unchecked_blurb = "Shops we list but don't check", "We link to these without a status. Some sites block automated checks, and some shops are link only for now."
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
           "datePublished": GUIDES_LASTMOD, "dateModified": guide_modified(build_vs), "url": url_for(fname), "image": OG_IMAGE,
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
           "datePublished": JAN_APR_PUBLISHED, "dateModified": guide_modified(build_january_april), "url": url_for(fname), "image": OG_IMAGE,
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
    link_only_ids = {x["id"] for x in stores["stores"] if x.get("link_only")}
    def avail(store_id, canons):
        ls = col_ls(store_id)
        if store_id in link_only_ids:  # not checked: no stock claim, just where to find the listings
            return f'Link only: we don\'t check this shop\'s stock · <a href="{DOTGRID_SLUG}/#{jump[store_id]}">listings</a>'
        if not ls:
            return f'<a href="{DOTGRID_SLUG}/#{jump[store_id]}">Live stock</a>'
        buy = [l["label"] for l in ls if l["status"] in BUYABLE]
        names = f'<br><span class="muted small">In stock: {E("; ".join(buy))}</span>' if buy else ""
        return f'<strong>{len(buy)} of {len(ls)}</strong> versions we track · <a href="{DOTGRID_SLUG}/#{jump[store_id]}">live stock</a>{names}'
    if "notebooktherapy" in link_only_ids:
        nt_link = (f'<p><a href="{DOTGRID_SLUG}/#{jump["notebooktherapy"]}">Notebook Therapy on the tracker</a> '
                   f'<span class="muted small">(link only: we don\'t check its stock, so no status is shown)</span></p>')
    else:
        nt_link = f'<p><a href="{DOTGRID_SLUG}/#{jump["notebooktherapy"]}">Live Notebook Therapy stock</a></p>'
    checked_makers = [bare_shop_name(x["name"]) for x in DOTGRID_SHOPS if not x.get("link_only")]
    unchecked_makers = [bare_shop_name(x["name"]) for x in DOTGRID_SHOPS if x.get("link_only")]
    where_buy = (f'Our <a href="{DOTGRID_SLUG}/">dot grid journal tracker</a> checks '
                 + (f"each one at the maker's own shop {CHECK_FREQ}." if not unchecked_makers else
                    f"{names_and(checked_makers)} at each maker's own shop {CHECK_FREQ}. "
                    f"{names_and(unchecked_makers)} {'is' if len(unchecked_makers) == 1 else 'are'} listed as a link only: we don't check {'its' if len(unchecked_makers) == 1 else 'their'} stock."))
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
<p class="muted small">Stock in each column is what that maker's own shop said at our last check, {asof}. Each count covers every dot grid listing we track at that shop. Other shops that sell the same notebooks are on the <a href="{DOTGRID_SLUG}/">dot grid tracker</a>. {'Across the four makers' if not unchecked_makers else 'Across the ' + {1: 'one maker', 2: 'two makers', 3: 'three makers'}.get(len(checked_makers), f'{len(checked_makers)} makers') + ' we check'}: {E(dg_total)}. Across every shop: {E(dg_all)}.</p>

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
<p>Pick the Tsuki 160GSM if you want thick 160 GSM paper in a book you'll finish sooner. It's 135 × 195 mm with 128 pages, gilded edges, a 5 mm light grey dot grid, a back pocket with a sticker sheet and an elastic band {s("nt")}. The product page doesn't mention page numbers, an index or bookmarks. Notebook Therapy also releases limited-edition Tsuki designs, which we list too.</p>
{nt_link}

<h2>Where to buy</h2>
<p>All four sell direct, and sizes and colors sell out often. {where_buy} <a href="#alerts">Sign up above</a> for free restock emails for the trackers you pick. You can unsubscribe anytime. More guides are on the <a href="guides/">guides page</a>.</p>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources">{src_items}</ol>
<p class="muted small">Each maker sells other dot grid journals too. This guide covers the A5 versions above.</p>
{design_links_block("dotgrid")}
{related_block(fname)}
</article>"""
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title,
           "datePublished": "2026-11-04", "dateModified": guide_modified(build_dotgrid_guide), "url": url_for(fname), "image": OG_DOTGRID,
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
    "aostag": ("ao-stag", "pocket dot grid · ships now", AO_SLUG + "/#ao-stag", "Archer and Olive Stag, pocket size"),
    "lta5": ("lt-hardcover-a5", None, DOTGRID_SLUG + "/leuchtturm1917-hardcover-a5-dotted/", "Leuchtturm1917 Hardcover Medium (A5), dotted"),
    "lted2": ("lt-bullet-journal-ed2", None, DOTGRID_SLUG + "/leuchtturm1917-edition-2/", "Leuchtturm1917 Bullet Journal Edition 2"),
    "aonavy": ("ao-storybook-navy", "A5 ", DOTGRID_SLUG + "/archer-and-olive-storybook-navy/", "Archer and Olive Storybook in Navy, A5"),
    "aobeige": ("ao-songbird-beige", "B5 ", AO_SLUG + "/#ao-songbird-beige", "Archer and Olive Songbird in Beige, B5"),  # B5 since Nov 22, 2026: the A5 dot grid sold out
    # Winter 2026 designs: only the ships-now A5 dot grid option (the Feb preorder option is a separate listing).
    "aoice": ("ao-ice-castle", "A5 dot grid · ships now", AO_SLUG + "/#ao-ice-castle", "Archer and Olive Ice Castle, A5"),
    "aotrain": ("ao-winter-train", "A5 dot grid · ships now", AO_SLUG + "/#ao-winter-train", "Archer and Olive Winter Train, A5"),
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
                ("Our Habit & Mood Tracker Journal, A5 or 6x9 paperback",
                 AMAZON_LIST_PRICES.get("B0HSTYDQ8K") if AMAZON_LIST_PRICES.get("B0HSTYDQ8K") == AMAZON_LIST_PRICES.get("B0HQ5TLDK3") else None),
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
    src_items += f'<li id="src-stock">Stationery Drop Watch restock trackers (<a href="{HOBO_TRACKER}">Hobonichi</a>, <a href="{DOTGRID_SLUG}/">dot grid</a>), last check {asof}.</li>'
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
  <li><strong>Undated journals:</strong> {gift_own("B0HSTYDQ8K", "Habit & Mood Tracker Journal")} (A5, 168 pages; also available in {gift_own("B0HQ5TLDK3", "6 × 9 in")}, 166 pages) · {gift_own("B0HQ5X3C7D", "Reading Journal")} (7 × 10 in, 152 pages).</li>
</ul>

<section class="card faq" id="faq"><h2>Questions</h2>{faq_html}</section>

<h2>Sources</h2>
<ol class="sources two-col">{src_items}</ol>
{related_block(fname)}
</article>"""
    upd = guide_modified(build_gift_guide)
    art = {"@context": "https://schema.org", "@type": "Article", "headline": title,
           "datePublished": GIFT_PUBLISHED, "dateModified": upd, "url": url_for(fname), "image": OG_IMAGE,
           "author": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE},
           "publisher": {"@type": "Organization", "name": "Stationery Drop Watch", "url": BASE, "logo": {"@type": "ImageObject", "url": BASE + "assets/brand/icon-512.png"}}}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    doc = page(fname, title + TITLE_SUFFIX, desc, body,
               ld=(crumbs_ld(("guides/", "Guides"), (fname, "Holiday gift guide")), art, faq_ld), og_type="article")
    check_none_claim(fname, doc)
    return fname, doc


LAMY_SEE_ALSO_TAIL = "Lamy's special and limited edition pens, when each was first listed, and the authorized shops that sell them."


def lamy_see_also():
    """Guides index pointer to the Lamy release calendar. A line, not a guide card: GUIDES and the guide count stay as they are."""
    if not LAMY_LIVE:
        return ""
    return f'<p class="small section-switch lamy-see-also">See also: <a href="{LAMY_SLUG}/">Lamy release calendar</a>, {E(LAMY_SEE_ALSO_TAIL)}</p>'


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
{lamy_see_also()}
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
    # Listed 2026-11-22. Same card as the other Etsy tip-ins: regular price and the shared
    # sale note. Fit wording is from the listing description (FITS line).
    dict(id="spin-lift-unfold", kind="insert", sale_confirmed=True, price="$7.99",
         title="Spin, Lift & Unfold Interactive Tip-Ins",
         img="assets/shop/spin-lift-unfold.webp", img_class="sheet", img_w=1800, img_h=1350,
         url="https://www.etsy.com/listing/4623478927/interactive-planner-tip-ins-printable",
         alt=("Spin, Lift & Unfold: five interactive tip-in sheets in a row, a Side-Quest Roulette card, "
              "a Weather & Light flap card, a gatefold, an Overheard & Ephemera specimen card and a Future-Self Accordion sleeve. "
              "The header reads \"five interactive tip-ins · 85 × 175 mm · fits 94 × 188 mm weekly planners\"."),
         sub="Printable interactive tip-ins · personal use · instant download from Etsy",
         hub_sub="Printable tip-ins",
         blurb=("Five interactive tip-ins that move: spin a wheel, lift flaps, open a gatefold and pull out notes to your future self. "
                "Each piece is 85 × 175 mm, including a 4 mm hinge strip, and fits 94 × 188 mm weekly planners. "
                "A digital download for personal use."),
         details=["Fits Hobonichi Weeks and Hobonichi Weeks Mega, and other narrow weekly planners with a cover of about 94 × 188 mm",
                  "4 PDFs: US Letter and A4, each in color and grayscale. 10 pages in each PDF: print and cut guide, 7 printable sheets, assembly steps and an about page. A print guide (README) is in the download",
                  "Full-length cut lines, dashed score lines, hatched glue zones and a 50 mm scale bar on every sheet. Print at 100% / actual size and check that each section of the scale bar measures 10 mm",
                  "You will also need scissors or a trimmer, a craft knife and metal ruler, a scoring tool, glue or double-sided tape, washi tape, and one small flat paper brad or a knotted thread for the wheel",
                  "Personal use only: don't share, resell, or redistribute the files or printed copies",
                  "Digital download only. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Side-Quest Roulette", "Sensory Time Capsule", "What I Changed My Mind About",
                    "Overheard & Ephemera", "Future-Self Accordion"],
         templates_label="5 interactive tip-ins",
         inside="spin-lift-unfold"),
    dict(id="a5-cozy", kind="insert", sale_confirmed=True, price="$6.99",
         title="A5 Cozy Planner Inserts",
         img="assets/shop/a5-cozy-planner-inserts.webp", img_class="sheet", img_w=1800, img_h=1350,
         url="https://www.etsy.com/listing/4623487808/a5-planner-inserts-printable-cozy",
         alt=("A5 Cozy Planner Insert Set: three fanned A5 pages with soft watercolor-style art, a capybara at a cafe table, "
              "a sleeping cat by a bookshelf and a bunny with happy mail. "
              "The header reads \"printable · fits 148 × 210 mm (A5) · color + grayscale\"."),
         sub="Printable A5 planner pages · personal use · instant download from Etsy",
         hub_sub="Printable inserts",
         blurb=("A cozy set of A5 planner pages with soft, original watercolor-style art: a capybara cafe, a sleeping cat by a bookshelf, "
                "a pressed sakura and ginkgo bouquet and a bunny with happy mail. Print the pages you need, trim them and add them "
                "to your planner, binder or notebook. A digital download for personal use."),
         details=["Fits Hobonichi Techo Cousin (A5) and other A5 planners. Each page trims to 148 × 210 mm (5.83 × 8.27 in). Planner sizes vary, so please measure yours or test-print one page on plain paper first",
                  "4 print PDFs, 10 sheets each: US Letter and A4, in color and grayscale. A short README with printing steps is in the download",
                  "A 7 mm hinge strip on the binding edge is marked with a dashed line, for washi tape, glue or binder holes. No punch guide is printed",
                  "Print at 100% / actual size with \"Fit to page\" and \"Shrink\" turned off. Each sheet has a 50 mm scale bar. Thin cut lines run edge to edge, no bleed",
                  "Personal use only: don't share, resell, or redistribute the files or printed copies",
                  "Digital download only. Returns and exchanges are not accepted. Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi."],
         templates=["Kissaten Capybara Cafe dashboard", "Cozy Neko Bookshelf dashboard", "Botanical reset dashboard",
                    "Little Notes & Happy Mail dashboard", "Grid, dot grid & lines notes page", "Year in Pixels",
                    "Weekly spread, left page", "Weekly spread, right page"],
         templates_label="8 A5 pages",
         inside="a5-cozy"),
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
# B0HSTYDQ8K (Habit & Mood Tracker Journal, A5 paperback) was $14.99 in the buy box on its Amazon page
# on 2026-11-25 (about 10:55 AM ET), the same as the 6x9 edition it replaces on /shop.
AMAZON_LIST_PRICES = {"B0HPBDNS7F": "$19.99", "B0HQ5TLDK3": "$14.99", "B0HQ5X3C7D": "$16.99",
                      "B0HP9PXSR1": "$14.99", "B0HRTLMZ1M": "$14.99", "B0HRTTCH4D": "$14.99",
                      "B0HQW8273V": "$19.99", "B0HSTYDQ8K": "$14.99"}
SHOP_LABELS = {"B0HRTLMZ1M": "2027 Planner, Blush", "B0HSTYDQ8K": "Habit & Mood Tracker Journal", "B0HQ5X3C7D": "Reading Journal",
               "B0HRTTCH4D": "2027 Planner for Men", "B0HQW8273V": "Level Up! My 2027 Planner"}
SHOP_ORDER = ("B0HRTLMZ1M", "B0HSTYDQ8K", "B0HQ5X3C7D", "B0HRTTCH4D", "B0HQW8273V")
# Optional note under the detail bullets. The 8.5x11 planners and the 6x9 Habit & Mood Tracker
# remain linked notes on the A5 cards, not featured cards of their own. Link text matches the
# owner-approved phrasing ("Also available in 6x9" is the owner's wording, Nov 25).
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
    "B0HSTYDQ8K": {
        "before": "Also available in ",
        "link_text": "6x9 paperback",
        "url": "https://www.amazon.com/dp/B0HQ5TLDK3",
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
    "B0HSTYDQ8K": [("habit-and-mood-tracker-spread-p6-7", "Habit tracker and mood tracker, pages 6-7"),
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
    "spin-lift-unfold": {"class": " samples inserts", "note": "Sheets from the print file (US Letter, color), not a photograph of a printed copy.", "items": [
        _sample("/assets/shop/inside/spin-roulette-color.webp",
                "Spin, Lift & Unfold print file, sheet 1 of 7: No. 01 Side-Quest Roulette, the card with a cut-out window and quest log, and the printed quest wheel and blank wheel.",
                "No. 01 Side-Quest Roulette. Sample of a color sheet.", 1000, 964),
        _sample("/assets/shop/inside/spin-time-capsule-color.webp",
                "Spin, Lift & Unfold print file, sheet 2 of 7: No. 02 Sensory Time Capsule, three lift-up flaps (Weather & Light, Soundtrack, Scent & Texture) and the base card for Week in Review, Small Win or Surprise, and Carry It Forward.",
                "No. 02 Sensory Time Capsule. Sample of a color sheet.", 1000, 964),
        _sample("/assets/shop/inside/spin-gatefold-color.webp",
                "Spin, Lift & Unfold print file, sheet 3 of 7: No. 03 What I Changed My Mind About, the gatefold with Used to Think, The Upgraded Rule and The Plot Twist.",
                "No. 03 What I Changed My Mind About, the gatefold. Sample of a color sheet.", 1000, 964),
    ]},
    "a5-cozy": {"class": " samples", "note": "Pages from the print file (US Letter, color), not photographs of a printed copy.", "items": [
        _sample("/assets/shop/inside/a5-cozy-capybara-color.webp",
                "A5 Cozy Planner Inserts print file: the Kissaten Capybara Cafe dashboard, Slow Mornings & Sweet Treats, with a capybara illustration and Currently savoring lines for sipping, reading, listening to and looking forward to.",
                "Kissaten Capybara Cafe dashboard. Sample of a color page.", 700, 994),
        _sample("/assets/shop/inside/a5-cozy-year-in-pixels-color.webp",
                "A5 Cozy Planner Inserts print file: the Year in Pixels page, 12 months by 31 days, with a color key.",
                "Year in Pixels. Sample of a color page.", 700, 994),
        _sample("/assets/shop/inside/a5-cozy-weekly-left-color.webp",
                "A5 Cozy Planner Inserts print file: the Weekly Rhythm page, with weekly dinners and prep, morning anchors, evening save-point and Sunday reset ritual.",
                "Weekly spread, left page. Sample of a color page.", 700, 994),
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
    if PRINT_DROP_URL:
        return PRINT_DROP_LASTMOD  # Nov 26: The Print Drop card
    if any(e.get("id") in {"spin-lift-unfold", "a5-cozy"} and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-22"
    # Shop facts changed 2026-11-18 (Happy Mail & Washi Club and Seasonal Reset Dashboards).
    if any(e.get("id") in {"happy-mail", "seasonal-dashboards"} and etsy_listing_url(e) for e in SHOP_ETSY):
        return "2026-11-18"
    # Shop facts changed 2026-11-17 (Teachers Pay Teachers section is two collection cards).
    if SHOP_TPT:
        return "2026-11-23"  # Nov 23: link to the Teachers Pay Teachers page
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

# The Print Drop: the owner's sister site, a free beta planner page studio.
# Every phrase below comes from https://theprintdrop.com/ or its beta studio,
# read Nov 26, 2026. No prices, Pro features or monthly-drop promises.
PRINT_DROP_URL = "https://theprintdrop.com/"
PRINT_DROP_ICON = "/assets/brand/the-print-drop-icon.svg"
PRINT_DROP_LASTMOD = "2026-11-26"
PRINT_DROP_COPY = {
    "eyebrow": "New from us · Free beta",
    "title": "The Print Drop",
    "body": ("A little studio for planner pages you make yourself and print at home. "
             "Pick your size and a theme, add stickers, washi tape and templates, "
             "then download a print-ready PDF."),
    "note": "The free studio is open in beta. A Stationery Drop Watch creation.",
    "button": "Try the free beta",
}

def print_drop_card(heading="h2"):
    """A plain card pointing visitors to The Print Drop. One link target, no tracking."""
    c = PRINT_DROP_COPY
    return f"""<aside class="card print-drop-card" id="the-print-drop" aria-labelledby="print-drop-h">
  <a class="print-drop-thumb" href="{PRINT_DROP_URL}" rel="noopener" target="_blank" tabindex="-1" aria-hidden="true">
    <img src="{PRINT_DROP_ICON}" alt="" width="120" height="120" loading="lazy" decoding="async">
  </a>
  <div class="print-drop-body">
    <p class="eyebrow">{E(c['eyebrow'])}</p>
    <{heading} id="print-drop-h">{E(c['title'])}</{heading}>
    <p>{E(c['body'])}</p>
    <p class="muted small">{E(c['note'])}</p>
    <a class="btn" href="{PRINT_DROP_URL}" rel="noopener" target="_blank">{E(c['button'])}</a>
  </div>
</aside>"""

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
{print_drop_card()}
<h2>Printed planners and journals on Amazon</h2>
<ul class="shop-list">{amz}</ul>
<h2>Printable PDFs on Etsy</h2>
{etsy_intro}<ul class="shop-list">{etsy}</ul>
<h2 id="classroom-printables">Classroom printables on Teachers Pay Teachers</h2>
<p class="muted">{E(tpt_intro)}</p>
<ul class="shop-list">{tpt}</ul>
<p class="tpt-all"><a href="{TPT_PAGE_PATH}">See all our Teachers Pay Teachers resources</a></p>
{signup("shop")}
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
<p class="muted small">"Sold out" is exactly what each shop's public product data said. "Not yet on sale" means the shop has a preview page up but isn't taking orders. Always confirm on the shop's page before you plan around it.</p>
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
INK_FAQ_TRACK = ("On a separate limited inks page, we track limited-edition fountain pen inks from Diamine, Sailor and Robert Oster, "
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

INK_CONTENT_LASTMOD = "2026-11-27"

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
  <p class="muted small hero-check">{last}{len(ls) - s["unknown"]} of {len(ls)} listings checked successfully · {shops_checked_phrase(tracked, checked_shops)}.</p>'''

def ink_checked_line():
    return f'checked {time_tag(INK_STOCK["run_finished"])}' if INK_STOCK.get("run_finished") else ""

def ink_color_table(ink, rows):
    """One row per color, one column per shop: for single bottles sold color by color."""
    # A shop gets a column once it has a checked row, so a listing added since the last check
    # never shows as "Not listed" before its first check.
    have = {r["store_id"] for r in rows}
    shop_ids = []
    for l in ink["listings"]:
        if l["store_id"] not in shop_ids and l["store_id"] in have:
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

def ink_search_words(ink, rows):
    """Words the ink page's ?q= filter matches (app.js): the same name, kind, note, brand, colors and shops the homepage
    search index uses for this ink, so a search that found the ink on the homepage also finds it on this page."""
    brand = (INK_CFG.get("brands", {}).get(ink.get("brand")) or {}).get("name") or ""
    colors = sorted({r.get("color") or "" for r in rows if r.get("color")})
    shops = sorted({r.get("store") or "" for r in rows})
    words = " ".join([_search_public(ink.get("name") or ""), _search_public(ink.get("kind") or ""), _search_public(ink.get("note") or ""), brand, *colors, *shops])
    return " ".join(w for w in _search_fold(words).split() if not _SEARCH_BANNED.search(w))


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
    sids = " ".join(dict.fromkeys(r["store_id"] for r in rows))
    return f"""<details class="card group-fold" id="ink-{E(ink['id'])}" data-stores="{E(sids)}" data-q="{E(ink_search_words(ink, rows))}">
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
    <p id="ink-store-note" class="muted small" hidden></p>
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

# --- Lamy special and limited edition release calendar ------------------------------------------------
def lamy_split(pens, today, latest_max=None, older_max=None):
    """(upcoming, latest, older). A pen is released on its official date, or, when Lamy gave none, on the day the first
    of our shops listed it. Everything else is upcoming (dated first, then TBA). Latest holds the newest latest_max;
    Older holds up to older_max more; anything past that is dropped from the page."""
    latest_max = LAMY_LATEST_MAX if latest_max is None else latest_max
    older_max = LAMY_OLDER_MAX if older_max is None else older_max
    def rel(p):
        if p.get("official_date"):
            return p["official_date"] if dt.date.fromisoformat(p["official_date"]) <= today else None
        if p.get("first_listed") and dt.date.fromisoformat(p["first_listed"]) <= today:
            return p["first_listed"]
        return None
    released = [p for p in pens if rel(p)]
    upcoming = [p for p in pens if not rel(p)]
    released.sort(key=lambda p: (rel(p), p["name"].lower()), reverse=True)
    upcoming.sort(key=lambda p: (p.get("official_date") is None, p.get("official_date") or "", p["name"].lower()))
    return upcoming, released[:latest_max], released[latest_max:latest_max + older_max]

def lamy_today():
    return dt.datetime.now(ET).date()

def lamy_status_index():
    """URL -> status, only from rows the existing checkers already publish. Link-only shops never get a status."""
    idx = {}
    for r in stock["products"] + INK_ROWS:
        if r.get("store_id") in LINK_ONLY or r.get("status") not in STATUS:
            continue
        idx[r["url"]] = r["status"]
    return idx

def lamy_shop_name(sid):
    return next((s["name"] for s in stores["stores"] if s["id"] == sid), sid)

def lamy_date_block(p, upcoming):
    if upcoming:
        if p.get("official_date"):
            d = dt.date.fromisoformat(p["official_date"])
            return (f'<div class="lamy-when"><span class="lbl">Release date</span><span class="d">{d.strftime("%b")} {d.day}</span>'
                    f'<span class="y">{d.year}</span></div>')
        return '<div class="lamy-when tba"><span class="lbl">Release date</span><span class="d">TBA</span><span class="y">not announced</span></div>'
    if p.get("official_date"):
        d, lbl, tip = dt.date.fromisoformat(p["official_date"]), "Released", "Lamy's release date"
    else:
        d, lbl, tip = dt.date.fromisoformat(p["first_listed"]), "First listed", f"First day one of these shops listed it ({lamy_shop_name(p['first_listed_store'])}). Not an official Lamy date."
    return (f'<div class="lamy-when" title="{E(tip)}"><span class="lbl">{lbl}</span><span class="d">{d.strftime("%b")} {d.day}</span>'
            f'<span class="y">{d.year}</span></div>')

def lamy_card(p, statuses, upcoming=False):
    ls = sorted(p.get("listings", []), key=lambda l: lamy_shop_name(l["store_id"]).lower())
    known = [(l, statuses.get(l["url"])) for l in ls]
    n_in = sum(st == "in_stock" for _, st in known)
    any_known = any(st for _, st in known)
    tags = f'<span class="lamy-tag">{E(p["line"])}</span><span class="lamy-tag{" lim" if "imited" in p["kind"] else ""}">{E(p["kind"])}</span>'
    if p.get("qty"):
        tags += f'<span class="lamy-tag lim">{E(p["qty"])}</span>'
    items = []
    for l, st in known:
        sid = l["store_id"]
        badge = f' <small>{E(STATUS[st].lower())}</small>' if st else ""
        out = " out" if st == "sold_out" else ""
        items.append(f'<li data-store="{E(sid)}" data-status="{E(st or "")}"><a class="lamy-shop{out}" href="{E(l["url"])}" rel="noopener" target="_blank">'
                     f'{E(lamy_shop_name(sid))}{badge}</a>{region_tag(sid)}</li>')
    summary = f'<span class="sl-t">Sold at {nshops(len(ls))}</span>' + (f'<span class="sl-s"> · {n_in} in stock</span>' if any_known else "")
    shops_html = (f'<details class="lamy-shops"><summary>{summary}</summary>'
                  f'<ul class="lamy-shoplist" aria-label="Shops selling {E(p["name"])}">{"".join(items)}</ul></details>') if ls else '<span class="sl-s muted small">No shop has listed it yet</span>'
    us = (f'<a class="lamy-shop maker" href="{E(p["lamy_us_url"])}" rel="noopener" target="_blank">Lamy US store <small>maker, link only</small></a>'
          if p.get("lamy_us_url") else "")
    src = ('<span class="lamy-src">Source: ' + ", ".join(f'<a href="{E(u)}" rel="noopener" target="_blank">{E(t)}</a>' for t, u in p.get("sources", [])) + "</span>")
    hay = " ".join([p["name"], p["line"], p["kind"], p.get("qty", ""), p.get("desc", "")] + [lamy_shop_name(l["store_id"]) for l in ls]
                   + (["Lamy US store"] if p.get("lamy_us_url") else [])).lower()
    instock_ids = " ".join(l["store_id"] for l, st in known if st == "in_stock")
    return f"""<article class="lamy-entry" id="pen-{E(p['id'])}" data-line="{E(p['line'])}" data-shops="{E(' '.join(l['store_id'] for l in ls))}" data-instock="{E(instock_ids)}" data-q="{E(hay)}">
  {lamy_date_block(p, upcoming)}<div class="lamy-body"><div class="lamy-titlerow"><h3>{E(p['name'])}</h3><span class="lamy-tags">{tags}</span></div>
  <p class="lamy-desc">{E(p.get('desc', ''))}</p>
  <div class="lamy-rowline">{shops_html}{us}{src}</div></div>
</article>"""

LAMY_INTRO = ("Lamy's special and limited edition pens, newest first, with the date each one came out and the authorized shops "
              "that sell it. Open a shop to go straight to that pen on the shop's own site.")

def lamy_lastmod():
    return latest(LAMY_CFG.get("verified"), *[p.get("first_listed") for p in LAMY_CFG["pens"]], *[p.get("official_date") for p in LAMY_CFG["pens"]])

def build_lamy(today=None):
    fname = LAMY_SLUG + "/"
    today = today or lamy_today()
    pens = LAMY_CFG["pens"]
    upcoming, newest, older = lamy_split(pens, today)
    statuses = lamy_status_index()
    shown = upcoming + newest + older
    any_status = any(statuses.get(l["url"]) for p in shown for l in p.get("listings", []))
    lines = sorted({p["line"] for p in shown}, key=str.lower)
    shop_ids = sorted({l["store_id"] for p in shown for l in p.get("listings", [])}, key=lambda s: lamy_shop_name(s).lower())
    shop_opts = "".join(f'<option value="{E(s)}">{E(lamy_shop_name(s))}</option>' for s in shop_ids)
    if any(p.get("lamy_us_url") for p in shown):
        shop_opts += '<option value="lamy-us">Lamy US store</option>'
    line_opts = "".join(f'<option value="{E(l)}">{E(l)}</option>' for l in lines)
    instock = ('<label class="lamy-chk"><input type="checkbox" id="lamy-instock"> In stock only</label>' if any_status else "")
    reviewed = dt.date.fromisoformat(LAMY_CFG.get("verified") or today.isoformat())
    reviewed_txt = f'{reviewed.strftime("%b")} {reviewed.day}, {reviewed.year}'
    up_html = ("".join(lamy_card(p, statuses, upcoming=True) for p in upcoming) if upcoming else
               f'<div class="empty lamy-empty-up"><p><strong>No upcoming Lamy special or limited editions are confirmed right now.</strong></p>'
               f'<p>A pen shows up here only once Lamy or one of these shops has published it. If there is no date yet, it says TBA. Last reviewed {reviewed_txt}.</p></div>')
    rel_html = "".join(lamy_card(p, statuses) for p in newest) or '<div class="empty"><p>No releases yet.</p></div>'
    older_n = (f"{len(older)} older, up to {LAMY_OLDER_MAX}" if older else f"None yet. When release {LAMY_LATEST_MAX + 1} arrives, the oldest moves here.")
    older_html = "".join(lamy_card(p, statuses) for p in older) or '<div class="empty"><p>Nothing here yet.</p></div>'
    year = today.year
    n_year = sum(1 for p in newest + older if (p.get("official_date") or p["first_listed"]).startswith(str(year)))
    n_lim = sum(1 for p in shown if p.get("qty"))
    shops = LAMY_CFG["shops"]
    linked = names_and([lamy_shop_name(s) for s in sorted(shops, key=lambda s: lamy_shop_name(s).lower())])
    stock_note = ("Stock shows only where our regular checker already covers that exact listing."
                  if any_status else "We don't check stock for this calendar, so there's no in-stock label here. Confirm on the shop's page before you plan around it.")
    body = f"""
<div class="product-page" id="lamy-cal">
{crumbs((fname, LAMY_NAV))}
<section class="hero">
  {eyebrow("Lamy special and limited editions", "release calendar", f"last reviewed {reviewed_txt}")}
  <h1>Lamy special and limited edition release calendar</h1>
  <p class="lede">{E(LAMY_INTRO)}</p>
  <div class="lamy-stats">
    <div class="s-up"><b>{len(upcoming)}</b><span>upcoming, confirmed</span></div>
    <div class="s-rel"><b>{n_year}</b><span>released in {year}</span></div>
    <div class="s-shop"><b>{len(shop_ids)}</b><span>authorized shops linked</span></div>
    <div><b>{n_lim}</b><span>limited-quantity editions</span></div>
  </div>
  {also_tracked(fname)}
</section>

<section class="card lamy-panel lamy-filter-panel" id="lamy-filters" aria-label="Search and filter" hidden>
  <form class="lamy-filters" role="search" onsubmit="return false">
    <label class="f-q">Search pens<input id="lamy-q" type="search" placeholder="Try pine, safari, bog oak or Goulet" autocomplete="off" spellcheck="false"></label>
    <label>Line<select id="lamy-line"><option value="">All lines</option>{line_opts}</select></label>
    <label>Shop<select id="lamy-shop"><option value="">All shops</option>{shop_opts}</select></label>
    {instock}
  </form>
  <p class="lamy-count muted small" id="lamy-count" role="status" aria-live="polite"></p>
</section>

<section class="card lamy-panel" id="upcoming" aria-labelledby="lamy-up-h">
  <div class="lamy-sec-h"><h2 id="lamy-up-h">Upcoming releases</h2><span class="small muted">Confirmed by Lamy or a shop page</span></div>
  <div class="lamy-list" id="lamy-up-list">{up_html}</div>
  <div class="empty lamy-nomatch" hidden><p>No upcoming releases match.</p></div>
</section>

<section class="card lamy-panel" id="released" aria-labelledby="lamy-rel-h">
  <div class="lamy-sec-h"><h2 id="lamy-rel-h">Latest releases</h2><span class="small muted">The {LAMY_LATEST_MAX} newest, newest first</span></div>
  <div class="lamy-list" id="lamy-rel-list">{rel_html}</div>
  <div class="empty lamy-nomatch" hidden><p>No latest releases match. Try fewer words or clear a filter.</p></div>
  <details class="lamy-older" id="lamy-older"><summary><span class="sum-t">Older releases</span> <span class="sum-n" id="lamy-older-n">{E(older_n)}</span></summary>
    <div class="lamy-list" id="lamy-older-list">{older_html}</div>
    <div class="empty lamy-nomatch" hidden><p>No older releases match.</p></div>
  </details>
</section>

<section class="card"><h2>How this calendar works</h2>
  <p>We link only to shops that are authorized Lamy retailers: {E(linked)}. Lamy's own US store is linked on the pens it sells; it's the maker's store and we never check it. Other shops may sell these pens too.</p>
  <p>"First listed" is the first day one of these shops put the pen up for sale. It is not an official Lamy date. When Lamy publishes a release date, we show that date instead. Upcoming pens move into Latest releases on their release date, or on the day the first shop lists them.</p>
  <p>{E(stock_note)} Each pen links to where its details come from.</p>
  {region_legend(shop_ids)}
</section>
</div>"""
    items = {"@context": "https://schema.org", "@type": "ItemList", "name": "Lamy special and limited edition releases",
             "numberOfItems": len(shown), "itemListElement": [
                 {"@type": "ListItem", "position": i + 1, "name": p["name"], "url": url_for(fname) + "#pen-" + p["id"]}
                 for i, p in enumerate(shown)]}
    desc = ("Lamy special and limited edition pens: new safari, AL-star, studio, scala and LAMY 2000 editions, "
            "when each came out, and authorized shops that sell them.")
    return fname, page(fname, "Lamy special and limited edition release calendar", desc, body,
                       ld=(crumbs_ld((fname, LAMY_NAV)), items))

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

# Public site/data/stock.json: the checker's data/stock.json minus fields no page or reader needs.
# Kept: everything the drop-alert routine reads from the LIVE file (status, status_since, checked_at, url,
# label, type, store_id, store, canonical, title, first_seen, price fields, official_note, and "method",
# which the alert gate uses to spot a variant row whose URL lost its ?variant= id). Dropped: the checker's
# per-row error text and its variant counts. The full file stays in data/ for the build, tests and checker.
PUBLIC_STOCK_DROP = ("error", "available_variants", "total_variants")

def public_stock(raw):
    out = {k: v for k, v in raw.items() if k != "products"}
    out["products"] = [{k: v for k, v in row.items() if k not in PUBLIC_STOCK_DROP} for row in raw.get("products") or []]
    return out

def publish_stock_data():
    raw = json.loads((ROOT / "data/stock.json").read_text())
    (SITE / "data/stock.json").write_text(json.dumps(public_stock(raw), indent=1, ensure_ascii=False) + "\n")


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


_SEARCH_TRACKERS = (
    ("h", "Hobonichi", "/" + HOBO_TRACKER),
    ("d", "Dot grid", "/" + DOTGRID_SLUG + "/"),
    ("i", "Limited inks", "/" + INK_SLUG + "/"),
)
_SEARCH_WORD = re.compile(r"[a-z0-9]+")
_SEARCH_STOP = {"a", "an", "the", "and", "of", "for", "to", "in", "on", "with", "or"}
_SEARCH_BANNED = re.compile(r"midori|designphil|travell?er'?s\s+company", re.I)
_SEARCH_BULLET = re.compile(r"\bbullet\s+journals?\b", re.I)


def _search_public(text):
    """Search copy says dot grid. A maker's own 'Bullet Journal' name is not repeated here."""
    text = _SEARCH_BULLET.sub("dot grid", text or "")
    return re.sub(r"\s{2,}", " ", text).strip()


def _search_fold(text):
    import unicodedata
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _search_extra(name, blobs):
    have = set(_SEARCH_WORD.findall(_search_fold(name)))
    out, seen = [], set()
    for blob in blobs:
        for word in _SEARCH_WORD.findall(_search_fold(blob or "")):
            if len(word) < 2 or word in have or word in seen or word in _SEARCH_STOP:
                continue
            seen.add(word)
            out.append(word)
    return " ".join(out)


def _search_summary(checked):
    """Same sentence as the product page. No checked rows means the listing is link-only."""
    if not checked:
        return "Link only, we don't check stock"
    return count_line(checked).capitalize()


def _search_group(sample):
    for g in GROUPS:
        if g.get("aux"):
            continue
        if g["match"](sample):
            return g
    return None


def lamy_search_item():
    """One homepage search entry for the Lamy release calendar. Pen names, lines and editions are in
    its search words, so 'lamy', 'bog oak' or 'pine' find it. No shops and no stock line: we don't check those links."""
    pens = [p for p in LAMY_CFG.get("pens", []) if not _SEARCH_BANNED.search(p.get("name") or "")]
    if not LAMY_LIVE or not pens:
        return None
    n = len(pens)
    name = "Lamy release calendar"
    blobs = ["Lamy releases", "special limited edition pen pens fountain"]
    for p in pens:
        blobs.extend((p.get("name") or "", p.get("line") or "", p.get("kind") or ""))
    extra = _search_extra(name, blobs)
    extra = " ".join(w for w in extra.split() if w != "bullet" and not _SEARCH_BANNED.search(w))
    item = {"id": "lamy-release-calendar", "n": name, "t": "p",
            "s": f"{n} special and limited edition {'pen' if n == 1 else 'pens'}, no stock checks",
            "u": "/" + LAMY_SLUG + "/", "sh": []}
    if extra:
        item["q"] = extra
    return item


def lamy_pen_search_items():
    """One homepage search entry per pen shown on the Lamy release calendar, linking to that pen's card (#pen-<id>).
    Same pens the page shows (lamy_split). The line under the name is the pen's kind and its date, as on its card."""
    if not LAMY_LIVE:
        return []
    upcoming, newest, older = lamy_split(LAMY_CFG.get("pens", []), lamy_today())
    items = []
    for p in upcoming + newest + older:
        name = _search_public(p.get("name") or "")
        if not name or _SEARCH_BANNED.search(name):
            continue
        if p in upcoming:
            when = ("Release date " + _search_date(p["official_date"])) if p.get("official_date") else "Release date TBA"
        elif p.get("official_date"):
            when = "Released " + _search_date(p["official_date"])
        else:
            when = "First listed " + _search_date(p["first_listed"])
        bits = [x for x in (p.get("kind"), p.get("qty")) if x]
        item = {"id": "lamy-" + p["id"], "n": name, "t": "p", "s": " · ".join(bits + [when]),
                "u": f"/{LAMY_SLUG}/#pen-{p['id']}", "sh": []}
        extra = _search_extra(name, ["Lamy releases", "special limited edition pen pens fountain", p.get("line") or "",
                                     p.get("kind") or "", p.get("qty") or ""])
        extra = " ".join(w for w in extra.split() if w != "bullet" and not _SEARCH_BANNED.search(w))
        if extra:
            item["q"] = extra
        items.append(item)
    return items


def _search_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def guide_search_items():
    """One homepage search entry per guide in GUIDES, with its /guides/ blurb as the line under the name."""
    items = []
    for h, t in GUIDES:
        name = _search_public(t)
        blurb = _search_public(GUIDE_BLURBS.get(h, ""))
        if _SEARCH_BANNED.search(name) or _SEARCH_BANNED.search(blurb):
            continue
        item = {"id": "guide-" + h.strip("/"), "n": name, "t": "g", "s": blurb, "u": "/" + h, "sh": []}
        extra = _search_extra(name, ["guide guides", blurb])
        extra = " ".join(w for w in extra.split() if w != "bullet" and not _SEARCH_BANNED.search(w))
        if extra:
            item["q"] = extra
        items.append(item)
    return items


def _search_anchor(cid):
    return re.sub(r"[^A-Za-z0-9]+", "-", cid).strip("-") or "other"


def search_index():
    """Static homepage index: one record per active canonical item and each live ink.

    Counts use count_line on the listings the destination page shows. Link-only shops are
    searchable and are never included in an in-stock or checked total."""
    from urllib.parse import quote
    names = {s["id"]: s["name"] for s in stores["stores"]}
    canon = {c["id"]: c for c in stores["canonical"]}
    design_by = {design_fname(d): d for d in DESIGNS}
    track = {key: (label, url) for key, label, url in _SEARCH_TRACKERS}

    checked_by = {"h": {}, "d": {}, "i": {}}
    link_by = {"h": {}, "d": {}}

    def stash(bucket, row, link=False):
        dest = link_by if link else checked_by
        dest[bucket].setdefault(row["store_id"], []).append(row)

    for row in stock["products"]:
        stash("d" if section_of(row) == "dotgrid" else "h", row)
    for row in LINK_ROWS:
        stash("d" if section_of(row) == "dotgrid" else "h", row, link=True)
    for row in INK_ROWS:
        stash("i", row)

    shop_ids = [s["id"] for s in stores["stores"]
                if any(s["id"] in checked_by[key] or s["id"] in link_by.get(key, {}) for key in ("h", "d", "i"))]
    shop_at = {sid: i for i, sid in enumerate(shop_ids)}
    shops = []
    for sid in shop_ids:
        pages = []
        for key in ("h", "d", "i"):
            rows = checked_by[key].get(sid, [])
            links = link_by.get(key, {}).get(sid, [])
            if not rows and not links:
                continue
            _, base = track[key]
            pages.append({"t": key, "u": f"{base}?store={quote(sid)}", "s": _search_summary(rows), "c": len(rows)})
        shops.append({"i": sid, "n": names.get(sid, sid), "p": pages})

    by_canon = {}
    for row in stock["products"]:
        cid = row.get("canonical")
        if cid:
            by_canon.setdefault(cid, {"checked": [], "link": []})["checked"].append(row)
    for row in LINK_ROWS:
        cid = row.get("canonical")
        if cid:
            by_canon.setdefault(cid, {"checked": [], "link": []})["link"].append(row)
    order = [c["id"] for c in stores["canonical"] if c["id"] in by_canon]
    order += [cid for cid in by_canon if cid not in order]

    def shop_refs(rows):
        refs, seen = [], set()
        for row in rows:
            sid = row["store_id"]
            if sid in shop_at and sid not in seen:
                seen.add(sid)
                refs.append(shop_at[sid])
        return refs

    items = []
    for cid in order:
        bucket = by_canon[cid]
        checked, links = bucket["checked"], bucket["link"]
        sample = (checked or links)[0]
        label = canon.get(cid, {}).get("label") or sample.get("label") or cid
        if _SEARCH_BANNED.search(label) or _SEARCH_BANNED.search(cid):
            continue
        group = _search_group(sample)
        fname = design_page_for(checked or links)
        design = design_by.get(fname) if fname else None
        if design:
            page_rows = design_listings(design)
            # The design page's stock line counts every checked listing on that page, including a
            # sibling canonical that shares the page. Link-only pages have no checked total.
            summary = count_line(page_rows).capitalize() if page_rows else "Link only, we don't check stock"
            url = "/" + design_fname(design)
        elif group:
            summary = _search_summary(checked)
            url = f"/{group['slug']}/#{_search_anchor(cid)}"
        else:
            key = "d" if section_of(sample) == "dotgrid" else "h"
            summary = _search_summary(checked)
            url = f"{track[key][1]}?product={quote(cid)}#tracker"
        if design:
            name = design["name"]
            short = (group or {}).get("short") or ""
            if group and g_sec(group) == "hobonichi" and short and short.lower() not in _search_public(name).lower():
                name = f"{short} · {name}"
        else:
            name = label
        name = _search_public(name)
        if _SEARCH_BANNED.search(name) or _SEARCH_BANNED.search(url):
            continue
        blobs = [_search_public(label), sample.get("type") or ""]
        if design:
            blobs.append(design.get("full") or "")
        if group:
            blobs.extend((group.get("short") or "", group.get("product") or ""))
        blobs.extend(listing_size(p) for p in checked + links)
        blobs.extend(listing_language(p) for p in checked + links)
        blobs.extend(sorted({(p.get("label") or "") for p in checked + links}))
        extra = _search_extra(name, blobs)
        extra = " ".join(w for w in extra.split() if w != "bullet" and not _SEARCH_BANNED.search(w))
        item = {"id": cid, "n": name, "t": "d" if section_of(sample) == "dotgrid" else "h",
                "s": summary, "u": url, "sh": shop_refs(checked + links)}
        if extra:
            item["q"] = extra
        items.append(item)

    if INK_LIVE:
        brands = {key: info.get("name") or "" for key, info in INK_CFG.get("brands", {}).items()}
        for ink in INK_CFG["inks"]:
            if ink["id"] in INK_RETIRED:
                continue
            rows = [r for r in INK_ROWS if r["ink_id"] == ink["id"]]
            if not rows or _SEARCH_BANNED.search(ink.get("name") or ""):
                continue
            colors = sorted({r.get("color") or "" for r in rows if r.get("color")})
            extra = _search_extra(ink["name"], [_search_public(ink.get("kind") or ""), _search_public(ink.get("note") or ""),
                                                brands.get(ink.get("brand"), ""), *colors])
            extra = " ".join(w for w in extra.split() if w != "bullet" and not _SEARCH_BANNED.search(w))
            item = {"id": ink["id"], "n": _search_public(ink["name"]), "t": "i", "s": count_line(rows).capitalize(),
                    "u": f"/{INK_SLUG}/#ink-{ink['id']}", "sh": shop_refs(rows)}
            if extra:
                item["q"] = extra
            items.append(item)

    trackers = {key: {"l": track[key][0], "u": track[key][1]} for key in
                [key for key, _, _ in _SEARCH_TRACKERS if key != "i" or INK_LIVE]}
    lamy = lamy_search_item()
    if lamy:
        # Not a tracker: "p" only gives the result its tag ("Lamy releases") and the Enter-key page.
        trackers["p"] = {"l": LAMY_NAV, "u": "/" + LAMY_SLUG + "/"}
        items.append(lamy)
        items.extend(lamy_pen_search_items())
    guides = guide_search_items()
    if guides:
        # Not a tracker either: "g" gives guide results their tag ("Guides").
        trackers["g"] = {"l": "Guides", "u": "/guides/"}
        items.extend(guides)
    for item in items:
        item["u"] = safe_href(item["u"], "search item " + str(item.get("id")))
    for shop in shops:
        for page in shop.get("p", []):
            page["u"] = safe_href(page["u"], "search shop " + str(shop.get("i")))
    for tr in trackers.values():
        tr["u"] = safe_href(tr["u"], "search tracker")
    return {
        "trackers": trackers,
        "shops": shops,
        "items": items,
    }


def main():
    if shop_preview() and SITE.resolve() == (ROOT / "site").resolve():
        raise SystemExit("Refusing to write a shop preview into site/. Set DROPWATCH_SITE_OUT to another directory.")
    if OG_SHOPS is not None and OG_SHOPS != N_STORES:
        print(f"WARNING: og-image.png says {OG_SHOPS} shops but we check {N_STORES}; re-run scripts/brand/make_og.py")
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    publish_stock_data()
    (SITE / "data" / "search-index.json").write_text(
        json.dumps(search_index(), ensure_ascii=False, separators=(",", ":")) + "\n")
    # Published feed: same filtering as the pages (takedowns, link-only shops), never the raw file.
    (SITE / "data/changes.json").write_text(json.dumps(changes, indent=1, ensure_ascii=False))
    publish_ink_data()
    (SITE / "index.html").write_text(build_index())
    (SITE / HOBO_TRACKER).mkdir(parents=True, exist_ok=True)
    (SITE / HOBO_TRACKER / "index.html").write_text(build_hobo_tracker())
    tdir = SITE / TRACKER_DATA_DIR
    tdir.mkdir(parents=True, exist_ok=True)
    for old in tdir.glob("*.json"):  # only the files the pages built this run point at
        if f"{TRACKER_DATA_DIR}/{old.name}" not in TRACKER_DATA_FILES:
            old.unlink()
    for rel, text in TRACKER_DATA_FILES.items():
        (SITE / rel).write_text(text)
    for fname, doc in (("hobonichi-2027/", build_hobonichi()), ("about/", build_about()), ("privacy/", build_privacy()), ("terms/", build_terms()), ("transparency/", build_transparency())):
        (SITE / fname).mkdir(parents=True, exist_ok=True)
        (SITE / fname / "index.html").write_text(doc)
    _fs_fname, _fs_doc = build_for_shops()
    (SITE / _fs_fname).mkdir(parents=True, exist_ok=True)
    (SITE / _fs_fname / "index.html").write_text(_fs_doc)
    _tpt_fname, _tpt_doc = build_tpt_page()
    (SITE / _tpt_fname).mkdir(parents=True, exist_ok=True)
    (SITE / _tpt_fname / "index.html").write_text(_tpt_doc)
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
    if LAMY_LIVE:
        fname, doc = build_lamy()
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
    for gone in GONE_PATHS:  # no file is left behind for a 410 path (the middleware answers before assets)
        shutil.rmtree(SITE / gone, ignore_errors=True)
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
