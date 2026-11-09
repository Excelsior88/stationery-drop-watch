# Starlight Weeks, 2026-11-09

Published. Merge `757f5844c61c44c9dfe502a50d73197aa9d29f0d` of reviewed head `9a699c08085d444f89f620f85d4486f8879e008d`. There were no pull-request checks. Checker [42550285198](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42550285198) ran `2026-11-09T02:19:33+00:00` to `2026-11-09T02:20:35+00:00`, found 0 new in-stock flips, and committed the seven new rows as `f62117c2ce3d9d9ed5dc8b792c18b979de7b09e3` because they were not timestamp-only. Artifact `github-pages` `13644789101`, digest `sha256:a15c394048bbe32a81b1df2f8bba87f39950b232d1cb11dbd376b2155fa0b6e5`. Cloudflare [42550603906](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42550603906) deployed that artifact to https://f38f00f1.stationery-drop-watch.pages.dev. Public page: https://stationerydropwatch.com/hobonichi-weeks-2027/starlight/

## Product

Hobonichi's lineup page is https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_tdaisuke/

The feed key is `wb27_tdaisuke`. The English title is "tanakadaisuke: Starlight" and the type line is "Weeks Hardcover Book / Weekly Horizontal / ENG or JPN edition / Jan start / Mon start". Size on that page is 188 × 94 × 11 mm. It is the same "Weeks Hardcover Book" wording as Midnight Blue, not the "Weeks Softcover Book" wording used for Smooth and White Line. It is not a Weeks Mega.

The official item has two sales keys, `d27_9_wb27_tdaisuke_m` and `d27_9_wb27_tdaisuke_me`, for the Japanese and English books on one page. On 2026-11-09 both were `soldout: 1`, and the lineup message was "Restock Coming". The existing checker reports sold out when that flag is set. It does not turn the restock message into a restock event.

Some shops call this book a light hardcover. Pen Boutique uses that phrase for this book and also for Midnight Blue, which this site already tracks as a Weeks book. The tracked identity is Hobonichi's hardcover Weeks book, JAN `4580812709897` where the shop publishes that code.

## Listings added

| Shop | URL | How it was matched |
| --- | --- | --- |
| Hobonichi Online Store | https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_tdaisuke/ | Official page and `items.json` key |
| The Paper Mouse | https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-tanakadaisuke-starlight-english | Title says 2027 Weeks, Starlight, English. SKU `4580812709897` |
| Atlas Stationers | https://www.atlasstationers.com/products/hobonichi-techo-weeks-tanakadaisuke-starlight | Title and description say English Weeks. SKU `4580812709897` |
| Wonder Pens | https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-tanakadaisuke-starlight | Preview page titled English Weeks. SKU `4580812709897`. The preview word makes the checker say not yet on sale |
| Pen Boutique | https://www.penboutique.com/products/hobonichi-2027-light-hard-cover-english-book-tanakadaisuke-starlight-tall-slim-weeks-january-start | Title says English, Weeks, January start. SKU `4580812709897` |
| Yoseka Stationery | https://yosekastationery.com/products/hobonichi-techo-weeks-2027-tanakadaisuke-starlight | Title says Weeks 2027 Starlight. A search for the JAN returns this product |
| Jenni Bick | https://www.jennibick.com/products/hobonichi-techo-weeks-2027-tanakadaisuke-starlight | Title says Weeks 2027 Starlight. SKU `HT-4580812709897` |

The public design sentence says Hobonichi's own listing includes the English and Japanese books, and the other shops on the page sell the English book. No separate Japanese-book URL turned up at those shops. Baum-kuchen, Bobo Design Studio, Laywine's, and Omoi Zakka Shop did not return this book. Kinokuniya's results for the name were unrelated books. JetPens is not checked automatically, and Nanami Paper disallows the checker, so they were not added.

A first check of a new URL has no previous status, so it is not written to the restock log.

## Surfaces

Checked on the public site after the deploy above. Stock `run_finished` `2026-11-09T02:20:35+00:00`.

| Surface | Status | Source | Next |
| --- | --- | --- | --- |
| Seven Starlight listings | Corrected | Live `stock.json` matches the seven URLs. Wonder Pens is not yet on sale. The other six are sold out. `changes.json` has no event for these URLs. | None |
| `/hobonichi-weeks-2027/starlight/` | Corrected | Same seven rows and statuses. Official listing is English and Japanese. The other shops are the English book. Hardcover, 2027, January start, Monday start. | None |
| Weeks page and Hobonichi tracker | Corrected | Both list the seven URLs. Product filter and search return 7 of 7. Design link is present. Weeks is 42 listings at 11 shops. | None |
| Sitemap and canonical | Corrected | Sitemap and the page canonical use `/hobonichi-weeks-2027/starlight`. | None |
| Times | Already consistent | With JavaScript, the check time shows in the visitor zone. With JavaScript off, the same instants stay Eastern Time. | None |
| FAQ and guides | Already consistent | They do not name this design or a closed Weeks list that would now be wrong. | None |
| Social bios and banners | Unverified | This approval did not include profile edits. No checked page says a bio states this product. | None unless a bio is later found naming a fixed Weeks list |
| A separate Japanese shop URL | Unverified | Not found at the tracked shops. The official page already covers both languages. | Do not add a URL that is only a name match |
