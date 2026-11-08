# Visitor-local times, and two image files, 8 Nov 2026

This is a follow-up to the copy release in `docs/consistency-2026-11-08.md`. That release stays as recorded. This change is not merged and not deployed.

## Timestamps

Restock times and last-check times were one Eastern Time label, for example `Nov 8, 3:14 AM ET`, with the stored instant in `<time datetime="...">`. The checker still writes those instants. Nothing here changes stock, history, the cron, or `CONTENT_LASTMOD`.

`time.time-instant` is the set that may be rewritten. `site/assets/local-time.js` reads the `datetime` value and replaces the visible text with the same instant in the browser's time zone, including a short zone name (`EST`, `EDT`, `GMT`, `GMT+9`, and the equivalent for other zones). The `datetime` attribute stays the stored ISO timestamp. Sorting and stock badges are untouched.

Without JavaScript, or if the zone or the timestamp cannot be read, the visible text stays the Eastern Time label. That label does not say it is the visitor's zone. The "How often do you check the shops?" answer says the same thing. Guide update lines (`updated Nov 4, 2026` and `updated Nov 5, 2026`) and the 2027 calendar (`Aug 25, 2026`, `Aug 31, 2026 · 10 PM ET`, `Sep 30 – Oct 1, 2026`, and the other calendar lines) are not `time-instant` elements, so they are not moved onto another date.

Status "since" on a listing row was a date clipped from the instant (`since Nov 3`). It is now the full instant, so a time near midnight is the visitor's date rather than a clipped Eastern date. Design-page and where-to-buy FAQ text that names the last check uses the same element in the page. The FAQ structured data keeps the Eastern Time sentence, because that text is for crawlers and is not a visitor's zone.

The visible "updated" dates on the comparison guides stay 4 Nov 2026 and 5 Nov 2026. `data/guide_dates.json` keeps those dates. Only the template hashes for `build_vs` and `build_dotgrid_guide` changed, because those templates now emit `time-instant` for the stock check time.

## X header file

`site/assets/brand/x-header-1500x500.png` is 1500×500, sha256 `670c3cb4fdc101d00157ffb22a9edb3ae08de462401057b09ad09411cfa9498c`. The pixels still read "checked hourly across 13 shops." `scripts/brand/make_x_header.py` would write a different line ("every 30 minutes across 20 shops") if someone ran it. That line is not the current distinct shop count either. `scripts/brand/x_header_preview.py` only opens the PNG to draw a preview. No HTML page, stylesheet, or sitemap entry points at the file. It is still inside `site/assets/brand/`, so a site deploy publishes the URL. A public file is not evidence of the current X profile banner. This pass did not open an X account, replace the file, or regenerate it.

Next step, if wanted later: ask the owner whether the live profile banner should be replaced, and only then regenerate from a derived shop count and the real check cadence. Do not delete the file until that is decided.

## MIDORI card

`site/assets/brand/og-midori.png` is 1200×630 RGB, sha256 `a5a6729f132d02d518c2b2b069d4349657320b2251afdea0c7e6f62bdbcb838e`. The generator is `scripts/brand/make_og.py`. The page template sets `og:image` and `twitter:image` to `https://stationerydropwatch.com/assets/brand/og-midori.png` with width 1200 and height 630, on the MIDORI tracker and its design pages. The current alt is "Stationery Drop Watch: MIDORI MD seasonal release tracker, checked about every 30 minutes." The current artwork's middle line says "MD notebooks, diaries and limited covers (now MD PRODUCT)."

On 8 Nov 2026 at 3:30 AM EST the owner approved replacement artwork with this exact copy: "MIDORI restock tracker", "Diaries, diary stickers & paper", the existing Stationery Drop Watch logo, and `stationerydropwatch.com`, at 1200×630. That wording matches the live tracker, which lists the 2027 MD diaries, the 2027 diary stickers, and the MD PAPER Block. It does not match a claim of limited covers. The clean master was not attached to this run. The review preview is not a substitute, because it carries a review footer. `og-midori.png` and its alt are unchanged until that clean file is here. The X header file was not changed.
