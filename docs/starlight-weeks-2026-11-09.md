# Starlight Weeks, 2026-11-09

Not merged and not on the public site. The catalog change is in `stores.json`. The checker writes stock on its next run. This note does not add a status or a restock.

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

No separate Japanese-book URL turned up at these shops. Baum-kuchen, Bobo Design Studio, Laywine's, and Omoi Zakka Shop did not return this book. Kinokuniya's results for the name were unrelated books. JetPens is not checked automatically, and Nanami Paper disallows the checker, so they were not added.

A first check of a new URL has no previous status, so it is not written to the restock log.

## Surfaces

| Surface | Status | Next |
| --- | --- | --- |
| Weeks tracker and `/hobonichi-weeks-2027/starlight/` | Implemented in the catalog and design list. Not on the public site until the checker runs | Review, then merge |
| Live stock before this change | Already consistent. No Starlight canonical in the 2026-11-09T02:00:37Z public stock | None |
| FAQ, guides, social bios | Already consistent. They do not name this design | None |
| Delivered shop copies versus the official book | Unverified beyond the titles, type line, and JAN above | Do not add a shop that only shares the word Starlight |
