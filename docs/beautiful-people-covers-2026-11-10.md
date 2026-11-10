# Beautiful People 2027 covers

Two 2027 covers, current year only. Nothing from 2026 was added.

- A6 Original, beautiful people: Nothing to Hide (Green), JAN 4580812708883, official key `oc27_bpeople`.
- A5 Cousin, beautiful people: Nothing to Hide (Pink), JAN 4580812709163, official key `cc27_bpeople`.

Other covers use one English official URL plus the feed key. The Japanese pages are the same covers, so they are not a second row.

Checked with the existing checker, then written as a first observation. `data/changes.json` was not given a new event, and no webhook was sent.

The official feed read during this check had `soldout: 1` on both cover sales. An earlier page read the same evening had said Available. The tracker follows `items.json`, which is what the checker reads.

Wonder Pens titles still say PREVIEW and the variants are not available, so the checker reports not yet on sale. Every other checked shop reported sold out.

The Paper Mouse A5 URL without `-1` returned 404. The listing that exists ends in `-1`, and its barcode is the A5 JAN.

Buchan's and The Journal Shop answered `.js` for both sizes, with the matching JAN.

M.Lovewell lists the A6 cover by that title. Its barcode field is not the JAN. No A5 listing was found.

Loft's pages include the JAN and say 在庫切れ, but they do not publish schema.org availability and the checker has no Loft reader. Loft is not in the catalog.

JetPens is a link only, same as its other Hobonichi links. It is not a stock status.
