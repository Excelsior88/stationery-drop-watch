# Shop see-inside, 2026-11-08

Candidate only. Not merged and not published.

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

Print page samples are labeled as the local print master, not photographs of a physical copy. Public Amazon details (168 pages, 8.5 × 11 in, full color, paperback, publication 8 Nov 2026) agree with that master. They do not prove the file Amazon delivers is the same bytes.

## Changed-fact inventory

| Surface | Status | Note | Next |
| --- | --- | --- | --- |
| `/shop` Level Up Etsy card | Corrected | Coming-soon line removed. PDF front and three PDF pages added. Listing URL and sale note kept. | Owner review |
| `/shop` Level Up paperback | Corrected | New card. Plain `/dp/B0HQW8273V` link. No hardcoded price or availability. | Owner review |
| `/shop` Soft Days | Corrected | Weeks Mega fit claim removed. Three insert samples added. Existing tile kept. | Owner review |
| `/shop` four Amazon and two adult PDF previews | Already consistent | Same jpg paths and captions. No larger-view link added. | None |
| `/shop` FAQ and product offer schema | Already consistent | This page has no FAQ and no product offer schema, so no price was added there. | None |
| Homepage product row | Corrected | Paperback and printable covers both show. No coming-soon line. Nine items scroll on a phone. | Owner review |
| Homepage FAQ | Already consistent | Sells printed books and PDFs. No Level Up fit or coming-soon sentence. | None |
| Guides, calendar, local time, MIDORI, grouped restocks, deploy guard | Already consistent | Not edited. | None |
| Physical book equals the print master | Unverified | Public specs agree. File bytes were not compared with a delivered copy. | Do not claim a photo or a byte match |
| Physical insert fit | Unverified | Source says it was not tested. | Leave the qualified sentence |
| Soft Days marketing tile | Not used | Supplied, and not an interior. Existing tile already works. | None |
| Merge and deploy | Approval blocked | This note is the review candidate. | Wait for the owner |
