# Stationery Drop Watch (v1, local)

Live at https://stationerydropwatch.com/. A restock tracker, checked about every 30 minutes, with separate sections:

- **Hobonichi Techo 2027** (home page, plus per-product pages): Original A6, Cousin A5, Weeks, Weeks Mega and covers at the Hobonichi shops in `stores.json`. Sold-out items link to the same item on Amazon (Associates tag, `rel="sponsored"`).
- **Dot grid journaling** (`/archer-and-olive-dot-grid-journal/`): Archer and Olive, Leuchtturm1917 US, Scribbles That Matter and Notebook Therapy (Tsuki), size by size and color by color. The old `/archer-and-olive-bullet-journal/` URL is a noindex redirect. This page also shows the owner's own 2027 Planner as a gift pick, with a plain Amazon link (no tag, not sponsored).

- **Traveler's Company limited editions** (`/travelers-company-limited-edition/`): yearly diary accessories (sticker set, clear folder, plastic sheet), 20th anniversary sets and shop exclusives at the official Traveler's Company USA shop and independent shops. Sold-out items fall back to an Amazon brand search with the Associates tag.
- **MIDORI MD seasonal releases** (`/midori-md-limited-edition/`; MIDORI sells MD as "MD PRODUCT" in 2026): the dated 2027 MD diaries, 2027 diary stickers and online store limited editions at the official MD PRODUCT USA store and independent shops. Sold-out items fall back to an Amazon MD search with the Associates tag.
- A new section is added in `SECTIONS` (`build_site.py`); until it has listings it shows only in the home page's "Coming to the tracker" box, which disappears when every section is live.

Pens, inks and other paper are not tracked.

    python3 scripts/checker.py      # polite stock check -> data/stock.json, data/changes.json
    python3 scripts/build_site.py   # renders site/ from stores.json + data/ + content/
    cd site && python3 -m http.server 8000

- `stores.json`: tracked retailers and product URLs (first built by build_stores.py, now edited by hand). A product or store with `"section": "travelers"` or `"midori"` belongs to that section (`SECTIONS` in `build_site.py`); otherwise Hobonichi shops are Hobonichi and the rest are dot grid. The checker copies `section` into `data/stock.json` and `data/changes.json`, so alerts can link the right page. A section page is built only once it has listings.
- `content/editor_picks.json`: the "From the editor" house ad. Add another object to `books` to show a second book.
- TODOs: grep for `TODO` / `data-todo` (newsletter form action, affiliate links, Associates tag).
- The checker only reports what stores return. Failed checks show as "Couldn't check" and are never guessed.

## SEO

- `build_site.py` also writes one restock page per product group (`GROUPS`): `site/<slug>/index.html`, e.g. `hobonichi-weeks-2027/`. Statuses are exactly what `data/stock.json` says.
- Every page gets a canonical URL, Open Graph/Twitter tags with a share image and alt text (`assets/brand/og-image.png` for the Hobonichi side, `assets/brand/og-dotgrid.png` for the dot grid page, `og-travelers.png` and `og-midori.png` for the newer sections; all made by `scripts/brand/make_og.py`) and JSON-LD (WebSite + FAQPage on home, BreadcrumbList + ItemList of tracked listings on product pages). No Product markup: we have no prices or ratings to put in it.
- `site/sitemap.xml` (lastmod = last status change on that page, or `CONTENT_LASTMOD` if the copy changed more recently; redirects are left out) and `site/robots.txt` are regenerated on every build, so the scheduled workflow keeps them current.
- The site is served at the root of the custom domain https://stationerydropwatch.com/, so `robots.txt` (which points at `/sitemap.xml`) is read by crawlers.

## Hosting (GitHub Pages)

`.github/workflows/check-and-deploy.yml` runs about every 30 minutes (cron `17,47 * * * *`, plus on push and on demand): checker -> build -> commit `data/` only when a status changed -> deploy `site/` to Pages.
Custom domain: `stationerydropwatch.com` (set in the repo's Pages settings; `build_site.py` also writes `site/CNAME`). Local links are root-relative (`/assets/...`), so the site must be served from a domain root. The old `https://excelsior88.github.io/stationery-drop-watch/` URL redirects to the domain.
First-time publish: `gh auth login`, then `scripts/publish.sh`.
