# Stationery Drop Watch (v1, local)

Live at https://stationerydropwatch.com/. A restock tracker, checked about every 30 minutes, with separate sections:

- **Hobonichi Techo 2027** (home page, plus per-product pages): Original A6, Cousin A5, Weeks, Weeks Mega and covers at the Hobonichi shops in `stores.json`.
- **Dot grid journaling** (`/dot-grid-journal-restock-tracker/`): Archer and Olive, Leuchtturm1917 US, Scribbles That Matter and Notebook Therapy (Tsuki), size by size and color by color, plus Archer and Olive's dot grid refills. The tracker moved here on Nov 21, 2026. The old URL, `/archer-and-olive-dot-grid-journal/`, is now an Archer and Olive page that links to the tracker, and the old design pages under it 301 to the new ones. `/archer-and-olive-bullet-journal/` 301s to the Archer and Olive page. This page also shows the owner's own 2027 Planner as a gift pick, with a plain Amazon link.

- **Traveler's Company and MIDORI: removed Nov 19, 2026.** TRAVELER'S COMPANY USA asked us to remove both brands, and the owner approved. `/travelers-company-limited-edition/`, `/midori-md-limited-edition/` and the old Traveler's size guide URL now show the owner-approved notice (`TAKEDOWN_NOTICE` in `build_site.py`; do not edit its wording without the owner). The old item pages redirect to their brand's notice. Neither brand is checked, alerted, emailed or shown anywhere else.
- A new section is added in `SECTIONS` (`build_site.py`); until it has listings it shows only in the home page's "Coming to the tracker" box, which disappears when every section is live.

- **Limited-edition fountain pen ink** (`/limited-edition-fountain-pen-ink/`): limited, seasonal and shop-exclusive inks from Diamine and Sailor (Robert Oster is watched for new finds), only at shops on each brand's own dealer list (`inks.json` "brands"; see `research/inks-2026-11-21.md` in the owner's working copy). Every ink shop is already a shop in `stores.json`, so the site-wide shop count (distinct shop ids across `data/stock.json` and the public ink rows) only changes if a new shop is added. Pelikan, Colorverse, Lamy and Montblanc are left out until a dealer list verifies them. Milligram and every Designphil brand are never tracked.

Pens and other paper are not tracked.

### Ink tracker (`scripts/ink_tracker.py`)

    python3 scripts/ink_tracker.py check      # every checker run (check-and-deploy.yml): data/inks/stock.json, changes.json, retired.json
    python3 scripts/ink_tracker.py discover   # daily (ink-discovery.yml): data/inks/discovery.json, pending.json, new_finds.json
    python3 scripts/ink_tracker.py approve <find_id> --ink <ink_id> [--name "..."] [--color "..."]

- Statuses use the same polite fetcher and rules as `checker.py`. An unavailable product in the shop's own coming-soon collection (`inks.json` "coming_soon_collections") is "Not yet on sale", not sold out; available products in a pre-order collection are "Preorder". If that collection can't be read, the row is "Couldn't check".
- Ink changes go to `data/inks/changes.json`. `new_in_stock.py` (the drop-alert webhook) reads it too and adds new flips to in_stock to the ping with `tracker: "inks"` and `section: "inks"`, so the alert routine can email the Limited-edition inks list. A listing's first check never counts as a change, and hidden (pending) rows never alert.
- Discovery reads each verified shop's public `/products.json`. A shop's first scan is a baseline (remembered, not reported) apart from coming-soon or preorder items. After that, each new limited ink match becomes a pending find: it is checked from the next run, carries `"hidden": true`, and never renders. `data/inks/new_finds.json` lists that run's finds and a plain-text `note`; the note is empty on days with no finds. Nothing is sent from here.
- Owner approval: `approve` moves a find into `inks.json`; it shows on the page after the next check.
- Retirement: an ink whose every listing has been sold out for 60 days is moved to `data/inks/retired.json`, stops being checked, and is listed under "No longer tracked".

    python3 scripts/checker.py      # polite stock check -> data/stock.json, data/changes.json
    python3 scripts/build_site.py   # renders site/ from stores.json + data/ + content/
    cd site && python3 -m http.server 8000

- `stores.json`: tracked retailers and product URLs (first built by build_stores.py, now edited by hand). A product with a Leuchtturm1917, Archer and Olive, Scribbles That Matter or Notebook Therapy canonical (or a store with a `"brand"`) is dot grid; the rest are Hobonichi. The checker copies `section` into `data/stock.json` and `data/changes.json`, so alerts can link the right page. A section page is built only once it has listings.
- Link-only shops: a store with `"link_only": true` (Blesket, Milligram, Kinokuniya USA and Kinokuniya Singapore, until each gives written permission) is never requested. The checker skips it and a network guard (`GuardedSession`) refuses any request to its host, ink discovery skips it, and `new_in_stock.py` and `build_site.py` drop its rows and events. Its listings render as plain links with a neutral "Link only" label. To turn a shop back on, delete its `link_only` and `link_only_reason` lines in `stores.json`. `COUNT_LINK_ONLY_IN_SHOP_TOTALS` in `scripts/build_site.py` decides whether link-only shops are included in the "N shops" copy. Since Nov 23, 2026 it is False: "27 shops" means 27 shops the checker actually requests. Hunter Paper Co (UK), Zakka Joy, ColorSwatch and Greenstar Paperie (US) were added on Hobonichi only that day; all four are on Hobonichi's official 2027 retailer list.
- `content/editor_picks.json`: the "From the editor" house ad. Add another object to `books` to show a second book.
- TODOs: grep for `TODO` / `data-todo` (newsletter form action).
- The checker only reports what stores return. Failed checks show as "Couldn't check" and are never guessed.
- Restock times and last-check times are stored as ISO timestamps and rendered as Eastern Time. `site/assets/local-time.js` rewrites `time.time-instant` into the visitor's time zone and names that zone. If the browser cannot, the Eastern Time label stays. Guide dates and the 2027 calendar dates are not rewritten.

## SEO

- Prices: for Shopify listings the checker also stores `price_cents` (integer cents, from the same `.js` product data; `price_max_cents` too when the product's variants are priced differently) with `currency: "USD"`, but only when the shop's public `/meta.json` says it sells in USD. Other shops, Hobonichi's own store and failed `/meta.json` reads get no price fields. Only the holiday gift guide shows them: the lowest single price among shops with the pick in stock or on preorder, rebuilt every run, with "See price at the shop" / "Couldn't check" when there is none.
- `build_site.py` also writes one restock page per product group (`GROUPS`): `site/<slug>/index.html`, e.g. `hobonichi-weeks-2027/`. Statuses are exactly what `data/stock.json` says.
- Every page gets a canonical URL, Open Graph/Twitter tags with a share image and alt text (`assets/brand/og-image.png` as the site-wide default, covering all three trackers with Clip, and `assets/brand/og-dotgrid.png` for the dot grid page, both made by `scripts/brand/make_og.py`) and JSON-LD (WebSite + FAQPage on home, BreadcrumbList + ItemList of tracked listings on product pages). No Product markup: we have no prices or ratings to put in it. The default card (`og-image.png`) prints "We check N shops for you" with the site-wide total at the time it was made; `make_og.py` records N in `og-image.json`, the alt text repeats it, and the build prints a warning when it no longer matches `N_STORES` (re-run `make_og.py`). Hobonichi-only totals in page copy come from `N_SEC["hobonichi"]`. The site-wide total (`N_STORES`) is the number of distinct `store_id` values in `data/stock.json`, not the sum of the section counts. The home eyebrow counts restock trackers only (`NAV_TRACKERS`); the 2027 calendar, guides, and shop stay in the rest of the nav.
- `site/sitemap.xml` (lastmod = last status change on that page, or `CONTENT_LASTMOD` if the copy changed more recently; redirects are left out) and `site/robots.txt` are regenerated on every build, so the scheduled workflow keeps them current.
- The site is served at the root of the custom domain https://stationerydropwatch.com/, so `robots.txt` (which points at `/sitemap.xml`) is read by crawlers.

## Hosting (GitHub Pages)

`.github/workflows/check-and-deploy.yml` runs about every 30 minutes (cron `17,47 * * * *`, plus on push and on demand): checker -> build -> commit `data/` only when a status changed -> deploy `site/` to Pages.
Custom domain: `stationerydropwatch.com` (set in the repo's Pages settings; `build_site.py` also writes `site/CNAME`). Local links are root-relative (`/assets/...`), so the site must be served from a domain root. The old `https://excelsior88.github.io/stationery-drop-watch/` URL redirects to the domain.
First-time publish: `gh auth login`, then `scripts/publish.sh`.
