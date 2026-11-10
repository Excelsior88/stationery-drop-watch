# Rest-of-site accuracy audit, 2026-11-09

## Live health check, 2026-11-08 11:19 PM EST

Read only. Not committed. Public stock finished `2026-11-09T04:02:01+00:00` (11:02 PM EST). 253 products: 124 in stock, 15 not yet on sale, 109 sold out, 5 unknown. `changes.json` still 37 events, newest `2026-11-08T17:48:00+00:00`. The 44 rows first seen at the PR 12 checker (`03:55`/`03:56`) have no change events. The five Omoi URLs are still unknown with October 25 timestamps and HTTP 404. JetPens product `pd/54089` returned 403 again. Nanami `robots.txt` still disallows all crawls.

Browser checks on the live site, America/Detroit: home navigation, product/status/search/type/store filters, restock All and In-stock, expand, reset to 11 rows, Floral Remedy at 390px with no horizontal overflow, JetPens link without a status badge, no-JS time `Nov 8, 11:02 PM ET`. No page errors. Newsletter form action is `https://buttondown.com/api/emails/embed-subscribe/dropwatch` method POST. It was not submitted.

Weeks page "Other designs" shows Baum-kuchen `[Hobonichi 2027] Weeks (English)` in stock, while the Leicester variant on the same product is sold out. Official feed still has `wb27_colorscyellow` and `oc27_kitagishi` with `soldout` 0, and neither URL is in the tracker. `wb27_m_colorsmblue` is in the tracker and in stock.

Calendar and the Techo-versus-Cousin guide were opened. Their dates were not re-proved against Hobonichi's shopping guide.

Read only. Not committed on purpose. Public snapshot `stock.json` `run_started` `2026-11-09T03:18:26+00:00`, `run_finished` `2026-11-09T03:19:38+00:00`, 209 products. Summary: 113 in stock, 0 preorder, 11 not yet on sale, 80 sold out, 5 unknown. `changes.json` has 37 events; the newest is `2026-11-08T17:48:00+00:00`. This audit did not start a checker run. Statuses below are that snapshot unless a line says it was re-read from the shop.

The four PR 11 designs were not re-audited. Live counts at this snapshot were still Pink Sapphire 9, Sea Glass 9, Welcome to the V&A 10, Leicester 10.

## Five Omoi rows

Re-requested each `.js` URL during this audit. All five returned HTTP 404. The snapshot error on each is `HTTP 404 on .js, HTTP 404 on page, no availability markup`. `first_seen` equals `status_since`, so they have been unknown since they were first recorded.

| Product | URL | Canonical | First recorded |
| --- | --- | --- | --- |
| Weeks Mega Midnight Blue | https://omoionline.com/products/hobonichi-techo-2027-weeks-mega-colors-planner-midnight-blue | `weeks-mega-midnight-blue` | `2026-10-25T21:41:06+00:00` |
| HON A5 Slash Navy | https://omoionline.com/products/hobonichi-techo-2027-hon-a5-slash-planner-navy | none | `2026-10-25T21:41:08+00:00` |
| HON A6 Slash Navy | https://omoionline.com/products/hobonichi-techo-2027-hon-a6-slash-planner-navy | none | `2026-10-25T21:41:11+00:00` |
| Weeks Shirt Fabric Graph Plaid | https://omoionline.com/products/hobonichi-techo-2027-weeks-shirt-fabric-planner-graph-plaid | none | `2026-10-25T21:41:13+00:00` |
| Weeks Paper Series Jade | https://omoionline.com/products/hobonichi-techo-2027-weeks-paper-series-planner-jade | none | `2026-10-25T21:41:16+00:00` |

Mega Midnight Blue is still tracked at seven other shops. The HON, Jade, and Graph Plaid rows are the only listings for those designs. Their public pages say the status is unknown. Checked at `2026-11-09T03:19:06+00:00` through `2026-11-09T03:19:27+00:00`.

## Omoi replacement search, same day

No catalog or code change. Each old HTML path returns HTTP 404 with no redirect. The published product sitemaps, 1,663 URLs, contain no Hobonichi, Techo, Weeks, or Slash handle. `title:Hobonichi`, `vendor:Hobonichi`, and `tag:hobonichi` on the storefront product query return nothing, as do the exact phrases Graph Plaid, Paper Series, Slash, and Weeks MEGA. https://omoionline.com/collections/hobonichi says there are no products in that collection, and its `products.json` is empty. The two MIDORI diary URLs already tracked at Omoi are still in the sitemap, so the shop catalog itself is publishing. No exact live replacement URL was found for any of the five. The rows stay "Couldn't check."

## Official listings for products we already track

`items.json` read during this audit. These keys are the regular or Mega book we already track, and none is in the 1101 rows.

| Already tracked | Official key | Feed `soldout` at this read | Official URL not in the catalog |
| --- | --- | --- | --- |
| Weeks Canaria Yellow | `wb27_colorscyellow` | 0 | https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorscyellow/ |
| Weeks Mega Midnight Blue | `wb27_m_colorsmblue` | 0 | https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_m_colorsmblue/ |
| A6 cover White Cat House | `oc27_kitagishi` | 0 | https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_kitagishi/ |

White Cat House is otherwise only https://usa.kinokuniya.com/products/4580812708791, in stock at the snapshot. Canaria Yellow's public page is 4 of 7 at the seven retailers, with no official row. Mega Midnight Blue's page is 3 of 7 checked, plus the Omoi unknown.

## Baum-kuchen mixed pages

Re-read both product `.js` files during this audit.

https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english is `available: true`. Named options include Midnight Blue, Canaria Yellow, Moomin: At the Table, and White Cat Wallpaper, all available, plus the four designs added in PR 11. Leicester on that page is not available.

https://www.baum-kuchen.net/products/hobonichi-2027-weeks-mega-english is `available: true`. Named options include Midnight Blue and Candy Dream, both available.

The catalog has separate variant rows only for the four PR 11 designs. The older mixed rows remain, with no canonical id, and the snapshot marks both in stock. The public Weeks page therefore shows Baum's whole English Weeks page as in stock and, separately, the Leicester variant as sold out.

Variant ids confirmed on the `.js` files, not yet catalog rows: Midnight Blue `43546058817603`, Canaria Yellow `43545982435395`, Moomin `43546062159939`, White Cat Wallpaper `43733001928771`, Mega Midnight Blue `43546097451075`, Mega Candy Dream `67668417904707`.

## Page counts against this snapshot

Checked text on the public pages. Last-check fallback is `Nov 8, 10:19 PM ET` for `2026-11-09T03:19:38+00:00`.

| Page | Public sentence | Snapshot |
| --- | --- | --- |
| Weeks | 30 of 74 checked, 8 of 11 shops, 2 unknown | 76 Weeks rows, 2 unknown, 30 buyable, 8 of 11 shops |
| Weeks Mega | 7 of 13 checked, 6 of 9 shops, 1 unknown | 14 rows, 1 unknown, 7 buyable, 6 of 9 shops |
| Original A6 | 15 of 17, 9 of 10 shops | Wonder is the shop with no buyable A6 row |
| Cousin | 8 of 8 at 8 of 8 | matches |
| A6 covers | 4 of 4 at 3 of 3 | matches |
| Dot grid | 13 of 24 at 4 of 4 | matches |
| Traveler's | 18 of 45 at 7 of 9 | matches |
| MIDORI | 18 of 19 at 9 of 9 | matches |

Homepage restock feed: 11 rows, each badge matched the current status of that URL. Eyebrows: 4 trackers, 23 shops, 13 Hobonichi. About says the script visits 23 stores. Shop and follow footers use the same 13 / 4 / 9 / 9 split. JetPens and Nanami remain the two not-checked shops. Shop page does not say "Print edition coming soon."

Sitemap contains the Pink Sapphire, Sea Glass, and V&A design URLs.

## Repair status after the exact-variant PR, 2026-11-08 11:40 PM EST

Recorded while cursor/baum-exact-and-official-78a4 was open and not merged.

Corrected in that branch: Baum Weeks and Mega combined rows replaced by exact variant URLs; checker returns unknown when named variants disagree; official wb27_colorscyellow and oc27_kitagishi added; February calendar line cites Paper Mouse only; calendar sitemap lastmod is 2026-11-08.

Already consistent: Aug 25 previews, Aug 31 10 PM ET / 9 PM CT, Oct 1 and Oct 15, restock-email scope, Techo vs Cousin vs Weeks English specs, Omoi product objects, signup form action, Level Up Amazon dp/B0HQW8273V title, live /hobonichi-2027 /about /privacy.

Unverified: Etsy listing bodies (403 here), newsletter delivery, webhook delivery. No mail was sent and no order was placed.

Awaiting approval: merge and deploy. The live site still shows the combined Baum rows until then.

## Guard blast radius and signup evidence, 2026-11-09

Non-Baum whole-product rows in stock run 2026-11-09T03:56:46Z: 174 classified with one variant, 5 Omoi already unknown. None would newly become unknown. Mixed named products that already have a variant id stay on that id. Guard not weakened. No catalog widening.

Historical signup delivery, from the parent reading dropwatch Gmail, with no address or token recorded: Buttondown confirmation Nov 2, 1:42 AM EST; new-subscriber notice Nov 8, 12:06 AM EST via stationerydropwatch.com. Not a current restock or webhook proof. Etsy body still 403, not treated as a broken route. Amazon Level Up route already verified. No mail sent.
