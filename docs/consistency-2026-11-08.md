# Consistency pass, 8 Nov 2026

This record is the investigation and the generator change. It is not a claim that production has been updated. Nothing here was merged or deployed. Public pages keep the previous copy until an approved checker run on `main` publishes a fresh site artifact.

Checked live on 8 Nov 2026 against https://stationerydropwatch.com/ and `data/stock.json` there (`run_finished` `2026-11-08T07:48:42+00:00`, 168 products, 23 distinct `store_id`s). The repository snapshot at that time was the 7 Nov checker commit (`data/stock.json` `run_finished` `2026-11-07T18:18:39+00:00`). Shop membership matched. Status rows did not, so this change does not rebuild `site/` from the repository snapshot.

## Shop count

`N_STORES` is the number of distinct `store_id` values on `stock["products"]`. It is not the sum of the section counts. A shop that sells more than one brand is one shop in the total. The FAQ already says that.

On the live file above, and on the 7 Nov snapshot, that split was:

| Scope | Distinct shops | How it is counted |
| --- | --- | --- |
| All trackers | 23 | `N_STORES` |
| Hobonichi | 13 | listings `section_of()` classifies as hobonichi |
| Dot grid | 4 | Archer and Olive, Leuchtturm1917, Scribbles That Matter, Notebook Therapy |
| Traveler's Company | 9 | listings with section `travelers` |
| MIDORI MD | 9 | listings with section `midori` |

13 + 4 + 9 + 9 is 35 because some shops are in more than one section. JetPens and Nanami Paper are named as not checked. They are not part of the 23. None of these numbers are hardcoded. The next checker build fills them from that run's `data/stock.json`.

## 1. Share-image alt said "13 shops"

Live homepage `og:image:alt` and `twitter:image:alt` were:

> Stationery Drop Watch: Hobonichi Techo 2027 restock tracker, books, Weeks and covers checked about every 30 minutes across 13 shops

The same homepage `og:description` said "at 23 shops". The alt is the default for every page that uses `og-image.png` (the hub, Hobonichi pages, guides, about, the shop, follow, privacy). Thirteen is only the Hobonichi section.

The image itself does not say 13. `https://stationerydropwatch.com/assets/brand/og-image.png` matches `site/assets/brand/og-image.png` (`sha256` `c5b67c5f3f33837892394180fb497a3b667311925f3432b61c610fafe759626e`). The card reads: "Hobonichi Techo 2027 restock tracker. Books, Weeks & covers · checked about every 30 minutes."

The alt is now that sentence, without a shop count. Putting 23 into the alt would describe a number that is not on the card and would be wrong on Hobonichi pages that share the file. Hobonichi sentences that mean the Hobonichi section still use the derived Hobonichi count (`at {N_HOBO} shops`, the FAQ line "Hobonichi: {N_HOBO} shops", the where-to-buy line, the hub card).

`og-dotgrid.png` already matched its count-free alt and names all four makers. It was left as-is.

`og-travelers.png` (same bytes live and in the repo, `sha256` `3e023a1dbac8c88c1182f6526c956b02ce1dea2627c15b363677f0179ae1d848`) reads: "Traveler's Notebook restock tracker. Regular size colors · 2027 diary accessories · limited editions. Official and independent shops · checked about every 30 minutes." The alt said only "Traveler's Notebook and limited edition tracker". It now follows the card, on the tracker and on the size guide, which uses the same image. The guide article was not rewritten. Its visible updated date stays 5 Nov 2026. `data/guide_dates.json` keeps that date and stores the new template hash so the alt edit is not stamped as a new guide revision.

WebSite JSON-LD on the homepage did not say "13 shops". It still does not. It now says "Traveler's Notebook regular colors and limited editions" where it used to say "Traveler's Company notebooks and limited editions".

## 2. Slugs are narrower than the pages. The URLs stay.

These published URLs were not renamed:

- `/archer-and-olive-dot-grid-journal/`
- `/travelers-company-limited-edition/`
- `/archer-and-olive-bullet-journal/` still redirects, noindex, to the dot grid page
- `/travelers-notebook-regular-size/` still redirects to `/travelers-company-limited-edition/#tracker`

Renaming either tracker URL would need a planned redirect. This pass does not do that.

Dot grid listings on the live check are the four makers above, size by size and color by color, plus two Archer and Olive dot grid refills (A5 soft cover refill and A5 notepad refill). The nav, breadcrumb, and H1 already said "Dot grid journals" / "Dot grid journal restock tracker". The title already named all four makers. The lede now names the four makers and those refills, so the page does not read as Archer and Olive only. Leuchtturm1917 Bullet Journal Edition 2, and Tsuki labels that use the maker's "Bullet Journal" name, stay. Those are the product names. Our headings say "dot grid".

Traveler's listings on the live check are the five Regular colors (Black 13714006, Brown 13715006, Blue 15239006, Camel 15193006, Olive 15342006), ROAD TRIP Brown, the Card Size 20th Anniversary Set in Black, the 20th Anniversary Customization Set, and the 2027 sticker set, clear folder, and plastic sheet. There is no Passport listing and no refill listing. The size guide already says Passport is not tracked and that refills are checked at the shops. The hub card said "Traveler's notebooks, refills and limited editions." That refill claim did not match the listings. The H1 was "Traveler's Company notebook and limited edition restock tracker" while the title already said "regular colors and limited editions".

The H1 is now "Traveler's Notebook restock tracker: regular colors and limited editions". The hub card is "Regular size colors, plus limited editions: 2027 diary accessories, anniversary sets and shop exclusives." The footer link is "Regular colors and limited editions". Breadcrumb and nav stay "Traveler's Company".

## 3. The hero said "4 restock trackers"

Four is the number of restock trackers: Hobonichi plus each section that has listings. The nav also has the 2027 calendar, Guides, Planners and journals, Follow us, and About. Those are not trackers, and they are not added to the four.

The eyebrow is now `len(NAV_TRACKERS)`, which is 4 with the current sections, not a fixed numeral and not `len(NAV)`. Under the lede, the hero says: "Also on the site, separate from the trackers: 2027 calendar · Guides · Planners and journals." Follow us and About stay in the nav. No CSS was changed. The hero remains full width.

## Artwork left unchanged, on purpose

`og-midori.png` reads "MD notebooks, diaries and limited covers (now MD PRODUCT)". Live MIDORI listings are the MD Notebook Diary 2027 A5, the 1 Day 1 Page 2027 A5 diary, the 2027 diary stickers (Large), and the MD PAPER Block 200×200 online-store limited. There is no separate plain notebook and no cover in the listings. The page already says plain MD notebooks are not tracked. The alt does not repeat "limited covers". The file was not redrawn. A new card would be new social imagery and was out of scope.

`site/assets/brand/x-header-1500x500.png` matches the file on the live site (`sha256` `670c3cb4fdc101d00157ffb22a9edb3ae08de462401057b09ad09411cfa9498c`). It reads: "Hobonichi Techo 2027 planners & covers, checked hourly across 13 shops." Checks run about every 30 minutes, and 13 is only the Hobonichi section. `scripts/brand/make_x_header.py` contains a different line that was never rendered into this PNG: "Hobonichi, dot grid journals & more, checked every 30 minutes across 20 shops." Twenty is not the distinct shop count either. The PNG was not regenerated, and no X profile, bio, banner, or post was changed. Replacing the live header needs a separate approval.

## Already consistent, so left alone

- FAQ "Which shops do you check?" gives the distinct total, then each section, and says overlapping shops are counted once.
- The Hobonichi tracker description uses the Hobonichi shop count, not the all-tracker total.
- Dot grid and MIDORI image alts were already count-free.
- Nav labels were already "Dot grid journals" and "Traveler's Company".
- Stock checks, "Couldn't check", referral links, product listings, release history, and the fresh-artifact deploy guard were not modified. Commit `6becc7b1039fe9d74a22407e2f4d46277045da16` is untouched.

## Checks

`python3 -m unittest tests.test_copy_consistency tests.test_restock_feed tests.test_require_fresh_pages_artifact` — 21 tests, OK.

A build with `DROPWATCH_SITE_OUT` set to a temp directory (not `site/`) wrote no page whose image alt contained "across 13 shops" or "limited edition tracker".

Local screenshots of that temp build show the new hero line, the dot grid lede, and the Traveler's H1. Their "last check" and in-stock counts are the 7 Nov repository snapshot, not the live 8 Nov check.

## Next action

After approval, merge to `main` and let the existing checker workflow rebuild from a fresh stock check and deploy that artifact. Do not deploy the checked-in `site/` directory. Then re-fetch the live homepage alt and hero, and the H1s at `/archer-and-olive-dot-grid-journal/` and `/travelers-company-limited-edition/`. Do not describe this as live before that check. Do not replace the X header or the MIDORI card in that release unless someone approves those images separately.
