# Exact Baum variants and two official listings, 2026-11-09

Published. The owner approved head `92ed6c22745ff66c2f2ed72b3793eeba783b5276` at Nov 8, 11:48 PM EST. Merge commit `22f911d59d392648abea5313016ad2a06695ef1b` at `2026-11-09T04:50:02Z`. There were no pull-request check runs on that head. Checker [42563944987](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42563944987) ran from that merge and committed `94ad748dd17388edb49a18775fd3b24bd2ea95d4`. Its drop-alert webhook step was skipped. Cloudflare [42564119022](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42564119022) deployed artifact `13650990354`, digest `sha256:bbd36322045222ab0505c091b726f9ee1a8fe715ce1f5756b99a67869e0c025c`, from checker `42563944987`, to https://e96a24b8.stationery-drop-watch.pages.dev and https://stationerydropwatch.com/. Public stock `run_finished` is `2026-11-09T04:51:45+00:00`. 267 products. `changes.json` is still 37 events, newest `2026-11-08T17:48:00+00:00`. No restock event was added for a new variant or the two official URLs.

The two combined Baum URLs are gone. All 11 Weeks variant links and all 7 Mega variant links are on the family pages. Pink Sapphire `43546059636803`, Sea Glass `43545928269891`, Welcome `43546082246723`, and Leicester `43546076676163` kept their earlier `first_seen` and `status_since`. Leicester at Baum is sold out. Sheep `43546089291843` and Mega Sheep `43546097647683` are sold out on their own cards. The other 14 new variant rows and the two official rows are first observations. Official Canaria Yellow is in stock because the Japanese sale was live; the English sale was sold out, and the page says the listing includes both languages. Official White Cat House, the A6 cover, is in stock beside Kinokuniya. The other 247 URLs that were already checked kept the same status and `first_seen`. The five Omoi URLs are still unknown, with their October 25 times. Weeks reads 38 of 106 checked listings in stock or on preorder at 8 of 11 shops, with 2 unchecked. Mega reads 13 of 20 checked at 6 of 9 shops, with 1 unchecked. Canaria Yellow reads 6 of 9. The home line is 262 of 267 listings checked, 5 unchecked.

Historical signup evidence stays historical: a Buttondown confirmation read in the site Gmail for Nov 2, 1:42 AM EST, and a new-subscriber notice for Nov 8, 12:06 AM EST via stationerydropwatch.com. No address or confirmation token is stored. Current restock email, webhook delivery, payment, and the Etsy listing body remain unverified. Etsy returned 403 and is not shown to be a broken link.

## What changed

Baum-kuchen sells the 2027 English Weeks designs on one Shopify product, and the Weeks Mega designs on another. The checker treated a product as in stock when any variant was available, and the catalog tracked those two products as single rows. A sold-out design on the same page was shown as in stock.

The two combined URLs are no longer catalog rows:

- `https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english`
- `https://www.baum-kuchen.net/products/hobonichi-2027-weeks-mega-english`

Each named option is now its own `?variant=` row. The four Weeks variant URLs already in the catalog are unchanged, including Leicester `43546076676163`. A new URL does not inherit the combined row's `first_seen` or `status_since`. `data/changes.json` has no events for the combined URLs, and this change does not write any. `data/stock.json` is not in this commit. The next checker run drops URLs that are no longer in the catalog and records a new URL as a first observation, not a restock.

If a Shopify product is still catalogued without a `variant_id` and its named options disagree, `classify_shopify` now returns `unknown` and the check records `named variants do not share one availability`. A single variant, a `Default Title`, and a variant titled `-` are unchanged. Baum's Original, Cousin, and Planner Book A6 products are one variant titled `-`.

Official listings added on the existing pages:

- Weeks Canaria Yellow, `wb27_colorscyellow`, https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorscyellow/
- A6 cover White Cat House, `oc27_kitagishi`, https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_kitagishi/

Read from `https://www.1101.com/store/techo/2027/items.json` on 2026-11-09, and from the product pages. Canaria Yellow is category `weeks`, a Weeks hardcover, weekly horizontal, English or Japanese, January start, Monday start. Size on that page: 188 × 94 × 10 mm, about 134 g. The Japanese sale `d27_9_wb27_colorscyellow_m` was not sold out. The English sale `d27_9_wb27_colorscyellow_me` was sold out. The page says the official listing includes both languages. That sentence is the product identity. It does not mean the English book is in stock. The checker's existing rule marks the official row in stock when either language sale is live, so this row follows the Japanese sale. White Cat House is category `cover_original`, an A6 Original cover, one sale `d27_1_oc27_kitagishi_c`, not sold out. It is not the Weeks White Cat Wallpaper book.

Omoi product objects are unchanged.

## Baum options on 2026-11-09

Weeks product, 11 named options. Available unless marked sold out.

| Variant | Canonical | Available |
| --- | --- | --- |
| 43545928269891 Sea Glass | weeks-sea-glass | yes, already tracked |
| 43545982435395 Canaria Yellow | weeks-canaria-yellow | yes |
| 43546058817603 Midnight Blue | weeks-midnight-blue | yes |
| 43546059636803 Pink Sapphire | weeks-pink-sapphire | yes, already tracked |
| 43546062159939 Moomin: At the Table | weeks-moomin-table | yes |
| 43546068385859 Moomin: A Day in the Life of Snufkin | weeks-moomin-snufkin | yes |
| 43733001928771 White Cat Wallpaper | weeks-white-cat | yes |
| 43546076676163 Leicester | weeks-va-leicester | sold out, already tracked |
| 43546082246723 Welcome to the V&A | weeks-va-welcome | yes, already tracked |
| 43546089291843 Sheep Sheep Sheep | weeks-sheep | sold out |
| 43546093191235 Leather: Forest Green | weeks-leather-forest | sold out |

Mega product, 7 named options.

| Variant | Canonical | Available |
| --- | --- | --- |
| 43546097352771 Sea Glass | weeks-mega-sea-glass | yes |
| 43546097385539 Canaria Yellow | weeks-mega-canaria-yellow | yes |
| 43546097418307 Poppy Red | weeks-mega-poppy-red | yes |
| 43546097451075 Midnight Blue | weeks-mega-midnight-blue | yes |
| 43546097483843 Pink Sapphire | weeks-mega-pink-sapphire | yes |
| 43546097647683 Sheep Sheep Sheep | weeks-mega-sheep | sold out |
| 67668417904707 Candy Dream | weeks-mega-candy-dream | yes |

Design pages were not added for Snufkin, Sheep, Forest Green, or the Mega colors that did not already have one. Those rows sit on the Weeks or Weeks Mega family page under their own canonical. Canaria Yellow, Midnight Blue, Moomin, White Cat Wallpaper, Mega Midnight Blue, and Mega Candy Dream use the design pages that already exist.

## Calendar and comparison

Paper Mouse's Hobonichi FAQ, read 2026-11-09, says previews start August 25 and that new items appear out of stock until the August 31 launch. That calendar line stays. The same page says the online launch is 10pm ET on August 31, which is 11am September 1 in Japan, and that there is a second release in February for planners that start on April 1. Atlas says the launch is 9:00 PM Central on Monday, August 31, 2026, and that the first restock was expected in early October. Hobonichi's shopping guide says some products begin sales on October 1 and that restock emails cover the Techo and the Drawer Pouch only, and are not a guarantee. It does not give a February or April date.

The February calendar line had cited Hobonichi for that date. It now cites Paper Mouse only and uses Paper Mouse's wording. The sitemap `lastmod` for the calendar moves from 2026-11-03 to 2026-11-08, the day that template change is recorded in `data/guide_dates.json`. No Spring 2027 detail beyond that sentence was added.

The Techo vs Cousin vs Weeks table still matches the cited English product pages: Original 148 × 105 × 15 mm, about 195 g, 464 pages; Cousin 210 × 148 × 18 mm, about 445 g, 544 pages; Weeks Colors Midnight Blue 188 × 94 × 10 mm, about 134 g, 240 pages, 75 English memo pages; Mega Candy Dream 384 pages and 219 English memo pages. The Japanese editions of those Weeks and Mega books list 71 and 215 memo pages. The table is labeled as the English January-start books. No comparison copy was changed.

## Guard blast radius

`named_variants_disagree` runs only for a Shopify row with no `variant_id`. A row with a variant id still uses `classify_shopify_variant`. Names `Default Title` and `-` are not named options. One named option, or several named options that are all available or all unavailable, keeps the old status. Mixed named options on a whole-product row become unknown. The guard was not weakened.

Public stock `run_finished` `2026-11-09T03:56:46+00:00`. Every non-Baum Shopify whole-product row in that file is one variant or already unknown. 174 classified rows are `total_variants` 1 (73 in stock, 86 sold out, 15 not yet on sale). The five Omoi whole rows are already unknown, with no variant counts, because the fetch failed. None of those 179 rows is a partial-availability product, so none would newly become unknown.

Live `.js` on 2026-11-09, passed through `classify_shopify`: Paper Mouse Original A6 is one `Default Title` and stays in stock; the 2027 sticker set is one `Default Title` and stays sold out; Wonder Pens Midnight Blue is one `Default Title` on a PREVIEW title and stays not yet on sale; Baum's Original A6 is one variant titled `-` and stays in stock.

These catalog rows already store a variant id, so the guard does not read them. Their parent products do mix availability, and the exact ids in the catalog stay on their own status. Other options on those products are not tracked. Scope was not widened.

| Product | Tracked variant ids | Last status of those ids |
| --- | --- | --- |
| Tokyo Pen Shop Traveler's notebook | 42876827304148, 42876827402452, 42876827369684, 42876827336916, 43664241295572 | Blue in stock; Black, Brown, Camel, Olive sold out |
| Love Notebooks Traveler's notebook | 51593658335546, 51593658401082, 51593658433850, 51593658368314, 52467629588794 | Blue in stock; the other four sold out |
| Archer and Olive Storybook in Navy | 48885118566555 A5, 48885118501019 B5 | both in stock |
| Archer and Olive Songbird in Blue | 47128956928155 A5 dot grid, 47128956862619 B5 dot grid | A5 sold out, B5 in stock. The live product has 13 named options, 8 available. The other 11 ids are not tracked. Classifying the whole product would be unknown. |
| Leuchtturm1917 hardcover Medium dotted | 48072862597365 Black, 48072862990581 Navy, 48072863842549 Sage | Sage in stock; Black and Navy sold out |
| Leuchtturm1917 Bullet Journal Edition 2 | 48072859189493 Black, 48501811151093 Purple26 | Black in stock; Purple26 sold out |
| Scribbles That Matter Dotted Journal Pro | 42136311300272, 42136311955632, 42136311070896 | both Charcoal sizes in stock; Bottle Green sold out |
| Notebook Therapy Tsuki 160GSM | 30591991545971 Pink Sakura, 30591988203635 Mint Matcha | Mint in stock; Pink sold out |

The two combined Baum URLs are still in that stock file, at 8 of 11 and 6 of 7, because this PR does not commit stock. They are no longer catalog rows. The next checker drops them instead of turning them into a fresh unknown event.

## Checks

`python3 -m unittest discover -s tests` was 59 tests, OK, before this follow-up. The follow-up reran `tests.test_baum_exact_variants` only. That file covers a mixed available/sold-out product returning `unknown`, each variant keeping its own status, an existing Leicester URL keeping `first_seen` and `status_since`, a new Midnight Blue URL adding no `changes.json` event, the single-variant and same-availability shapes, and the current stock file having no non-Baum whole row the guard would flip. `node tests/local-time.test.js` passed in the earlier run and was not repeated.

A local preview overlaid the verified statuses onto a copy of `data/stock.json`, built with `DROPWATCH_SITE_OUT`, and restored the repo stock file. The preview showed Leicester at Baum sold out, Sheep and Mega Sheep sold out on their own cards, Mega Midnight Blue at Baum in stock, official Canaria Yellow and White Cat House in stock, and no combined Weeks or Mega URL. Those overlay rows are not committed.

Browser checks on that preview: dot grid search "Apothecary" 15 cards to 1; Traveler's search "Olive" 11 to 1; MIDORI search "1 Day 1 Page" 4 to 1; a MIDORI hash chip landed on `#md-diary-2027-a5`; mobile overflow was 0 on those three pages and on the Weeks, Canaria, White Cat House, and Mega pages. The Hobonichi tracker product filter for Sheep showed 1 of 1, and the status filter kept it sold out. Signup forms render `POST` to `https://buttondown.com/api/emails/embed-subscribe/dropwatch`. None were submitted.

`https://www.amazon.com/dp/B0HQW8273V` opened as "Level Up! My 2027 Planner: For Kids Ages 7-11, January - December". No add-to-cart, payment, or account step was used. The shop's own Amazon links are plain `/dp/` URLs. Hobonichi search links on the family pages carry `tag=excelsior88-20`. Etsy listing `4610143237` returned HTTP 403 to this browser, so the listing page itself was not read. The href is that listing URL. Live `https://stationerydropwatch.com/hobonichi-2027`, `/about`, and `/privacy` returned 200. Extensionless paths 404 on the local static server; Pages serves them.

Signup forms on the built pages post to `https://buttondown.com/api/emails/embed-subscribe/dropwatch`. No form was submitted from this work, no test email was sent, and the drop-alert webhook was not pinged. Provider settings were not changed. The parent read the site's dropwatch Gmail and found a delivered Buttondown confirmation from Nov 2, 1:42 AM EST, and a new-subscriber notification from Nov 8, 12:06 AM EST that says the subscription came via stationerydropwatch.com. That is historical signup delivery. It is not a current end-to-end restock or webhook delivery. The subscriber address and any confirmation token are not recorded here. Amazon `B0HQW8273V` opened on the Level Up book. Etsy listing `4610143237` returned HTTP 403, so the listing body is unverified and not shown to be broken. Payment, account, and a full current delivery check stay unverified. JetPens and Nanami stay link-only.

## Status

| Item | State |
| --- | --- |
| Baum Weeks and Mega each design has its own status | Corrected in this PR. Live site still shows the combined rows until merge and the next checker. |
| Official Canaria Yellow and A6 White Cat House | Corrected in the catalog. Not on the live site until that checker run. Canaria's official in-stock result follows the Japanese sale. The English sale was sold out. |
| February calendar citation | Corrected. |
| August 25, August 31 launch times, October 1, October 15, restock-email scope, comparison specs | Already consistent with the sources above. |
| Omoi URLs and history | Untouched. Still unknown. |
| Non-Baum whole-product rows under the new guard | No row in the 2026-11-09T03:56:46Z stock would newly become unknown. Mixed products that already have a variant id stay on that id. |
| Historical signup delivery | Verified from the site Gmail: Buttondown confirmation Nov 2, 1:42 AM EST, and a new-subscriber notice Nov 8, 12:06 AM EST via stationerydropwatch.com. |
| Current restock email, webhook, payment, and the Etsy listing body | Unverified. Etsy returned 403. Not treated as a broken route. |
| Merge and deploy | Published. Merge `22f911d`, checker `42563944987`, stock `94ad748`, Cloudflare `42564119022`. |
