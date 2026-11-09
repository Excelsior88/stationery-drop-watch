# Exact Baum variants and two official listings, 2026-11-09

Not published. This branch is waiting for an explicit merge approval. No checker run and no Cloudflare deploy have been started from it.

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

Read from `https://www.1101.com/store/techo/2027/items.json` on 2026-11-09, and from the product pages. Canaria Yellow is category `weeks`, a Weeks hardcover, weekly horizontal, English or Japanese, January start, Monday start. Size on that page: 188 × 94 × 10 mm, about 134 g. The Japanese sale `d27_9_wb27_colorscyellow_m` was not sold out. The English sale `d27_9_wb27_colorscyellow_me` was sold out. The existing bilingual rule reports the official row in stock when either language is live. White Cat House is category `cover_original`, an A6 Original cover, one sale `d27_1_oc27_kitagishi_c`, not sold out. It is not the Weeks White Cat Wallpaper book.

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

## Checks

`python3 -m unittest discover -s tests` : 59 tests, OK. That includes a mixed available/sold-out product returning `unknown`, each variant keeping its own status, an existing Leicester URL keeping `first_seen` and `status_since`, and a new Midnight Blue URL adding no `changes.json` event. `node tests/local-time.test.js` passed.

A local preview overlaid the verified statuses onto a copy of `data/stock.json`, built with `DROPWATCH_SITE_OUT`, and restored the repo stock file. The preview showed Leicester at Baum sold out, Sheep and Mega Sheep sold out on their own cards, Mega Midnight Blue at Baum in stock, official Canaria Yellow and White Cat House in stock, and no combined Weeks or Mega URL. Those overlay rows are not committed.

Browser checks on that preview: dot grid search "Apothecary" 15 cards to 1; Traveler's search "Olive" 11 to 1; MIDORI search "1 Day 1 Page" 4 to 1; a MIDORI hash chip landed on `#md-diary-2027-a5`; mobile overflow was 0 on those three pages and on the Weeks, Canaria, White Cat House, and Mega pages. The Hobonichi tracker product filter for Sheep showed 1 of 1, and the status filter kept it sold out. Signup forms render `POST` to `https://buttondown.com/api/emails/embed-subscribe/dropwatch`. None were submitted.

`https://www.amazon.com/dp/B0HQW8273V` opened as "Level Up! My 2027 Planner: For Kids Ages 7-11, January - December". No add-to-cart, payment, or account step was used. The shop's own Amazon links are plain `/dp/` URLs. Hobonichi search links on the family pages carry `tag=excelsior88-20`. Etsy listing `4610143237` returned HTTP 403 to this browser, so the listing page itself was not read. The href is that listing URL. Live `https://stationerydropwatch.com/hobonichi-2027`, `/about`, and `/privacy` returned 200. Extensionless paths 404 on the local static server; Pages serves them.

Email delivery was not tested. The drop-alert webhook URL and key are repository secrets, not in this repo, and this branch does not ping them. JetPens and Nanami stay link-only.

## Status

| Item | State |
| --- | --- |
| Baum Weeks and Mega each design has its own status | Corrected in this PR. Live site still shows the combined rows until merge and the next checker. |
| Official Canaria Yellow and A6 White Cat House | Corrected in the catalog. Not on the live site until that checker run. |
| February calendar citation | Corrected. |
| August 25, August 31 launch times, October 1, October 15, restock-email scope, comparison specs | Already consistent with the sources above. |
| Omoi URLs and history | Untouched. Still unknown. |
| Etsy listing page content, newsletter delivery, webhook delivery | Unverified. Not treated as a bug. |
| Merge and deploy | Awaiting approval. |
