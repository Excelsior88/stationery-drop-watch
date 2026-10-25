# Stationery Drop Watch (v1, local)

    python3 scripts/checker.py      # polite stock check -> data/stock.json, data/changes.json
    python3 scripts/build_site.py   # renders site/ from stores.json + data/ + content/
    cd site && python3 -m http.server 8000

- `stores.json`: tracked retailers and product URLs (built by build_stores.py).
- `content/editor_picks.json`: the "From the editor" house ad. Add another object to `books` to show a second book.
- TODOs: grep for `TODO` / `data-todo` (newsletter form action, affiliate links, sponsor contact, Associates tag, checker contact email in User-Agent).
- The checker only reports what stores return. Failed checks show as "Couldn't check" and are never guessed.

## Hosting (GitHub Pages)

`.github/workflows/check-and-deploy.yml` runs hourly (and on demand): checker -> build -> commit `data/` only when a status changed -> deploy `site/` to Pages.
All site links are relative, so it works under `https://<user>.github.io/stationery-drop-watch/`.
First-time publish: `gh auth login`, then `scripts/publish.sh`.
