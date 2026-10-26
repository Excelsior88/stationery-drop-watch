# Stationery Drop Watch (v1, local)

    python3 scripts/checker.py      # polite stock check -> data/stock.json, data/changes.json
    python3 scripts/build_site.py   # renders site/ from stores.json + data/ + content/
    cd site && python3 -m http.server 8000

- `stores.json`: tracked retailers and product URLs (built by build_stores.py).
- `content/editor_picks.json`: the "From the editor" house ad. Add another object to `books` to show a second book.
- TODOs: grep for `TODO` / `data-todo` (newsletter form action, affiliate links, Associates tag).
- The checker only reports what stores return. Failed checks show as "Couldn't check" and are never guessed.

## SEO

- `build_site.py` also writes one restock page per product group (`GROUPS`): `site/<slug>/index.html`, e.g. `hobonichi-weeks-2027/`. Statuses are exactly what `data/stock.json` says.
- Every page gets a canonical URL, Open Graph/Twitter tags (`assets/brand/og-image.png`, made by `scripts/brand/make_og.py`) and JSON-LD (WebSite + FAQPage on home, BreadcrumbList + ItemList on product pages). No Product markup: we have no prices or ratings to put in it.
- `site/sitemap.xml` (lastmod = last status change on that page) and `site/robots.txt` are regenerated on every build, so the hourly workflow keeps them current.
- GitHub Pages serves this as a project site, so crawlers won't read `/stationery-drop-watch/robots.txt` (robots.txt only counts at the host root). Submit the sitemap in Google Search Console instead.

## Hosting (GitHub Pages)

`.github/workflows/check-and-deploy.yml` runs hourly (and on demand): checker -> build -> commit `data/` only when a status changed -> deploy `site/` to Pages.
All site links are relative, so it works under `https://<user>.github.io/stationery-drop-watch/`.
First-time publish: `gh auth login`, then `scripts/publish.sh`.
