# Weeks Colors and V&A, 2026-11-09

Not published. The catalog change is in this branch. `data/stock.json` in the repository is unchanged, so the live site still shows the old one-shop rows until a checker run after release.

A local checker run finished `2026-11-09T02:52:39+00:00`. It classified every new row. It wrote no restock for a new URL, and the four original URLs kept their `first_seen` and `status_since`. That run is not committed.

These are four separate regular Hobonichi Weeks 2027 hardcover books, January start, Monday start. Official type line for each: "Weeks Hardcover Book / Weekly Horizontal / ENG or JPN edition / Jan start / Mon start". They are not Weeks Mega. Mega keys `wb27_m_colorspsapphire` and `wb27_m_colorssglass` exist and were not added. No Weeks Mega key uses the V&A names.

The official page for each design is one listing with two sales keys, Japanese (`_m`) and English (`_me`). A shop page was added only when its own title names that design, says Weeks, and does not say Mega. Retailer pages that publish a code use JAN `4580812709712` Pink Sapphire, `4580812709743` Sea Glass, `4580812709880` Welcome to the V&A, and `4580812709873` Leicester. Yoseka's SKU is a cart fragment ending in those four digits, and a search for the full JAN returns that product. Bobo's two existing pages publish no SKU; the title is the match.

## Before and after

| Design | Before | After |
| --- | --- | --- |
| Colors: Pink Sapphire | Atlas Stationers only | 9 shops |
| Colors: Sea Glass | Atlas Stationers only | 9 shops |
| V&A: Welcome to the V&A | Bobo Design Studio only | 10 shops |
| V&A: Leicester | Bobo Design Studio only | 10 shops |

The four original URLs are unchanged. Their `first_seen` and `status_since` stay with those URLs. A first check of a new URL is not a restock.

Local check at `2026-11-09T02:52:39+00:00`, from each shop's own product data:

| Design | In stock | Not yet on sale | Sold out |
| --- | --- | --- | --- |
| Pink Sapphire | Official, Paper Mouse, Yoseka, Baum-kuchen variant | Wonder Pens | Atlas, Jenni Bick, Kinokuniya USA, Pen Boutique |
| Sea Glass | Official, Kinokuniya USA, Baum-kuchen variant | Wonder Pens | Atlas, Paper Mouse, Yoseka, Jenni Bick, Pen Boutique |
| Welcome to the V&A | Baum-kuchen variant | Wonder Pens | Official, Atlas, Bobo, Paper Mouse, Pen Boutique, Yoseka, Jenni Bick, Kinokuniya USA |
| Leicester | Official | Wonder Pens | Atlas, Bobo, Baum-kuchen variant, Paper Mouse, Pen Boutique, Yoseka, Jenni Bick, Kinokuniya USA |

Atlas Pink Sapphire was already sold out, and its `status_since` stayed `2026-11-06T23:17:52+00:00`. The other three original rows stayed sold out since `2026-10-25`. None of the 34 new URLs were added to `changes.json`.

## Listings

Official feed read 2026-11-09. Both language keys were not sold out for Pink Sapphire, Sea Glass, and Leicester. Both language keys were sold out for Welcome to the V&A.

| Shop | Pink Sapphire | Sea Glass | Welcome to the V&A | Leicester |
| --- | --- | --- | --- | --- |
| Hobonichi | [wb27_colorspsapphire](https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorspsapphire/) | [wb27_colorssglass](https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorssglass/) | [wb27_vawelcome](https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_vawelcome/) | [wb27_valeicester](https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_valeicester/) |
| The Paper Mouse | [English](https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-colors-pink-sapphire-english) | [English](https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-colors-sea-glass-english) | [English](https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-v-a-series-welcome-to-the-v-a-english) | [English](https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-v-a-series-leicester-english) |
| Atlas Stationers | [existing](https://www.atlasstationers.com/products/hobonichi-techo-weeks-colors-pink-sapphire) | [existing](https://www.atlasstationers.com/products/hobonichi-techo-weeks-colors-sea-glass) | [new](https://www.atlasstationers.com/products/hobonichi-techo-weeks-v-a-series-welcome-to-the-v-a) | [new](https://www.atlasstationers.com/products/hobonichi-techo-weeks-v-a-series-leicester) |
| Bobo Design Studio | not listed | not listed | [existing](https://bobodesignstudio.com/products/hobonichi-techo-2027-weeks-v-a-series-welcome-to-the-v-a) | [existing](https://bobodesignstudio.com/products/hobonichi-techo-2027-weeks-v-a-series-leicester) |
| Baum-kuchen | [variant 43546059636803](https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43546059636803) | [variant 43545928269891](https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43545928269891) | [variant 43546082246723](https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43546082246723) | [variant 43546076676163](https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43546076676163) |
| Wonder Pens | [English preview](https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-colors-pink-sapphire) | [English preview](https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-colors-sea-glass) | [English preview](https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-v-a-series-welcome-to-the-v-a) | [English preview](https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-v-a-series-leicester) |
| Pen Boutique | [English, January start](https://www.penboutique.com/products/hobonichi-2027-weeks-colors-pink-sapphire-english-january-start) | [English, January start](https://www.penboutique.com/products/hobonichi-2027-weeks-colors-sea-glass-english-january-start) | [English, January start](https://www.penboutique.com/products/hobonichi-weeks-2027-va-series-welcome-to-the-va) | [English, January start](https://www.penboutique.com/products/hobonichi-techo-2027-weeks-va-leicester) |
| Yoseka Stationery | [Weeks 2027](https://yosekastationery.com/products/hobonichi-techo-weeks-2027-colors-pink-sapphire) | [Weeks 2027](https://yosekastationery.com/products/hobonichi-techo-weeks-2027-colors-sea-glass) | [Weeks 2027](https://yosekastationery.com/products/hobonichi-techo-weeks-2027-v-a-series-welcome-to-the-v-a) | [Weeks 2027](https://yosekastationery.com/products/hobonichi-techo-weeks-2027-v-a-series-leicester) |
| Jenni Bick | [Weeks 2027](https://www.jennibick.com/products/hobonichi-techo-weeks-2027-colors-pink-sapphire) | [Weeks 2027](https://www.jennibick.com/products/hobonichi-techo-weeks-2027-colors-sea-glass) | [Weeks 2027](https://www.jennibick.com/products/hobonichi-techo-weeks-2027-v-a-series-welcome-to-the-v-a) | [Weeks 2027](https://www.jennibick.com/products/hobonichi-techo-weeks-2027-v-a-series-leicester) |
| Kinokuniya USA | [Weeks ENG](https://usa.kinokuniya.com/products/4580812709712) | [Weeks ENG](https://usa.kinokuniya.com/products/4580812709743) | [Weeks ENG](https://usa.kinokuniya.com/products/4580812709880) | [Weeks ENG](https://usa.kinokuniya.com/products/4580812709873) |

Baum-kuchen sells these on one English Weeks product with a variant per design. The checker follows `variant_id`, so one design being available does not mark the others available. The older mixed row, with no canonical id, stays as its own listing and is not one of these four designs.

Wonder Pens titles begin with PREVIEW, which the checker reports as not yet on sale. Jenni Bick's regular Weeks handle is the one without the Mega `-1` suffix. Kinokuniya USA's handle is the JAN. The product title says Weeks ENG, not MEGA. Sea Glass Mega at Kinokuniya is a different product, `4580812710084`, and was not added.

## Not added

Laywine's, Omoi Zakka Shop, and Kinokuniya Singapore returned no product for these four names or JANs. Kinokuniya Singapore's four JAN URLs answered 404. Bobo Design Studio lists the two V&A books and does not list Pink Sapphire or Sea Glass. No separate Japanese-book URL turned up at the retailers; the official page already covers both languages. JetPens and Nanami Paper are link-only shops, so they were not added.

The verified Pink Sapphire Amazon ASIN `B0H6P9F2S9` now follows the canonical product, the same way the other Weeks designs do. The original Atlas URL mapping is still in the listings file. Sea Glass, Welcome to the V&A, and Leicester have no verified ASIN, so they keep the Hobonichi brand link.
