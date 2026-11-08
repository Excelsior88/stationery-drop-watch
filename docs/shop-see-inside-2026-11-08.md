# Shop see-inside, 2026-11-08

Published. Merge `5f10a1fc95047ef392a4cefb72470dc8cda9c42b` of approved head `b4e78fda15d5703feac34e564519b7f6c3e33058`. Checker run [42518952830](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42518952830) finished stock at `2026-11-08T20:13:54+00:00` and did not commit, because there were no status changes. Artifact `github-pages` `13632139522`, digest `sha256:d96651dd377cf7e4d4cdc5158513335806e9ee2e2cc729219a5de77e2e0e982b`. Cloudflare [42519090790](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42519090790) deployed that artifact to https://ac54660d.stationery-drop-watch.pages.dev. Public shop: https://stationerydropwatch.com/shop/

## What changed

The shop adds the Level Up paperback (`https://www.amazon.com/dp/B0HQW8273V`) beside the existing books. Its link is the plain owner product URL, the same pattern as the other books on this page, with no Associates tag. The snapshot price and stock state are not printed. The card says to check the price on Amazon.

The Level Up Etsy card no longer says "Print edition coming soon." It keeps `https://www.etsy.com/listing/4610143237` and the shared $6.99 launch note through Nov 30. The card image is the printable PDF front, not the older composite of a cover plus loose pages.

See inside stays a closed `<details>` control. Level Up digital and Level Up print each show three different pages: January calendar, Week 2 plan, and Week 2 save point. Soft Days shows the weekly plan, habit tracker, and pen-and-ink swatches from the insert files. The supplied Soft Days marketing tile is not used as an interior and is not on the site. The existing Soft Days product image stays.

A phone stacks the new Level Up samples instead of squeezing two pages side by side. Soft Days inserts are one column at every width. Each sample links to the same file at its full pixel size.

## Fit claim

The live card said the inserts were tested in a Hobonichi Weeks Mega. The 2026-11-08 file note for these inserts says the 85 × 175 mm cut was not physically tested. The tested-fit sentence is removed. The card now says physical fit in a planner has not been tested, and that this is not a Hobonichi product. No Traveler's notebook fit sentence was added. The Pen & Ink Swatches sample is labeled as one Soft Days insert, not a separate product.

## Asset provenance

WebP SHA-256 values below were calculated for this handoff. They are not an older independent record. Marquee's read-only audit found each file byte-identical to the handoff zip, and the eight source PDFs matched the manifest hashes and page geometry. The files were copied unchanged.

| File | Pixels | Bytes | SHA-256 |
| --- | --- | --- | --- |
| levelup-etsy-cover.webp | 812×1050 | 40890 | `58996cadc76a15323a3d6c2349e460d6225f39b294897a0403164fc1eb626a37` |
| levelup-etsy-p009.webp | 812×1050 | 19914 | `bbe894f9b82b95c0ecb942377300786924cc56a2d731662c99683fc73947c558` |
| levelup-etsy-p012.webp | 812×1050 | 20238 | `8c13a3528f274ba3a322bbf38cef3b7d8274a873b0ca90abf7032127c892697f` |
| levelup-etsy-p013.webp | 812×1050 | 38106 | `28dfa6dcd72da00a91ac03c2902c908dd9dc59a490f7068c66227d239ed9303b` |
| levelup-print-front.webp | 812×1051 | 40370 | `4f6624098922b692673f1ceafdedf2e58186058d19a41c734cba8543a26fc28a` |
| levelup-print-p009.webp | 812×1050 | 19962 | `057c7e3ea5333d49e06dab724d8eaa01c26113a91884e878f5d8df573f7d827e` |
| levelup-print-p012.webp | 812×1050 | 19988 | `500ddeef0d156812fc77d7a98fbe6e911efa06d7a0b58a97f923947d84b30da0` |
| levelup-print-p013.webp | 812×1050 | 37206 | `f9cc8eeaaa34c8bd13ec9937c8c0e95307a4127f74c693b835684560fc8132f0` |
| softdays-weekly-color.webp | 511×1051 | 7318 | `b8cbcd75471432adf2e31c1f2d58865f6d1f4ff961b84844abd26cc669b5182f` |
| softdays-habit-gray.webp | 511×1051 | 27560 | `3619d2a802c9e9d7c9c2e2fa0faa487cc83f06622f0eb82c22c507292d1a581d` |
| softdays-swatches-color.webp | 511×1051 | 7880 | `9c7cd6d92eefd21ffd1054ef63dfb6f3e11a2ac94bf73a5fb53bc4d19bf18ff8` |

Cover alt text on the page is "Front cover of the Level Up! 2027 printable planner" and "Front cover of the Level Up! 2027 paperback planner." The handoff manifest called those covers interior or insert art. That wording is not used.

The closed paperback card states each buyer fact once: paperback, ages 7 to 11, 168 pages, 8.5 × 11 in, full color, January to December 2027, Monday start, and the Reading Quest Log, Trophy Room, and Coin Bank. Inside the closed See inside control, one line says the samples are from the print-ready file, not photographs of a printed copy. Public Amazon details agree with that file. They do not prove the file Amazon delivers is the same bytes.

## Changed-fact inventory

Checked on the public site after the deploy above.

| Surface | Status | Source | Next |
| --- | --- | --- | --- |
| `/shop` Level Up PDF | Corrected | Live card. Coming-soon line is gone. Listing `4610143237` and the $6.99 launch note remain. Cover alt is the printable front. | None |
| `/shop` Level Up paperback | Corrected | Live card. Plain `/dp/B0HQW8273V`, no price and no stock claim. Specs once. Print-file sentence is inside See inside. | None |
| `/shop` Soft Days | Corrected | Live card. Three insert files. Fit sentence says it has not been tested. Listing `4611293526` remains. | None |
| Existing six preview groups | Already consistent | The four Amazon spreads and two adult PDF sets still use the same jpg paths. | None |
| Shop FAQ and offer schema | Already consistent | `/shop` has no FAQ and no product offer schema. | None |
| Homepage product row | Corrected | Nine items, both Level Up editions, row scrolls, page does not. | None |
| Homepage and tracker FAQ | Already consistent | Tracker FAQ still says printed books are on Amazon and PDFs and tip-ins are on Etsy. No coming-soon or fit claim. | None |
| About | Already consistent | No Level Up sentence. | None |
| Guides, calendar, local time, MIDORI, grouped restocks, deploy guard | Already consistent | Guide dates unchanged. MIDORI hash matches. Homepage restocks are still grouped. This deploy used the fresh-artifact guard. | None |
| Delivered paperback bytes | Unverified | Public specs agree with the print-ready file. The live note does not claim the delivered file matches. | Do not claim a byte match |
| Insert fit | Unverified | The live sentence says physical fit has not been tested. | Leave that sentence |
| Social bios and banners | Unverified | This approval did not include profile edits. No checked page says a bio states these product facts. | None unless a bio is later found stating the old coming-soon line |
