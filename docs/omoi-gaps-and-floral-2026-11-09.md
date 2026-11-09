# Omoi gaps and Floral Remedy, 2026-11-09

Published. Merge of reviewed head `bdccd747ccb2111a24d7f84bc8923ec097782eb9` at `2026-11-09T03:55:08Z`. There were no pull-request checks on that commit. Checker [42558947060](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42558947060) ran `2026-11-09T03:55:20+00:00` to `2026-11-09T03:56:46+00:00` and committed `7da3220d332ce2f843e90589efe8834099a9f06b`. It did not add a restock event for any new URL. `changes.json` stayed at 37 events, newest `2026-11-08T17:48:00+00:00`. Cloudflare [42559118666](https://github.com/Excelsior88/stationery-drop-watch/actions/runs/42559118666) deployed artifact `13648726736`, digest `sha256:008686c6c4b8f999c6f1d06fb9f29470d4431f12b727d1dfa429932ee44d628e`, from that checker run, to https://40c293af.stationery-drop-watch.pages.dev. Public stock matches that run.

The five Omoi URLs are unchanged. They are still unknown, HTTP 404, with their October 25 `first_seen` and `status_since`.

## Identity

Official `items.json` read 2026-11-09.

| Design | Key | What it is |
| --- | --- | --- |
| HON A5 Slash (Navy) | `cb27_hon_slashnv` | HON, A5, daily, English or Japanese, January start, Monday start. Japanese sale was live; English sale was sold out. |
| HON A6 Slash (Navy) | `ob27_hon_slashnv` | HON, A6, daily, English or Japanese, January start, Monday start. Japanese sale was live; English sale was sold out. |
| Shirt Fabric: Graph Plaid | `wb27_shirtfplaid` | Regular Weeks hardcover, English or Japanese, January start, Monday start. Both language sales were live. Not Brownie Plaid and not a cover. |
| Paper Series: Frosty Jade | `wb27_paperfjade` | Regular Weeks hardcover. English title Frosty Jade, Japanese ひすい. English sale was sold out; Japanese sale was live. Bobo titles the same item code "Jade". |
| Liberty Fabrics: Floral Remedy | `wb27_libertyfloral` | Regular Weeks hardcover, English or Japanese, January start, Monday start. Both language sales were live. Not the Michelle or Sasha Kiora covers. |
| Weeks Mega Midnight Blue | `wb27_m_colorsmblue` | Weeks Mega hardcover. Both language sales were live. Added only at Hobonichi; the other seven shop URLs were already tracked. |

Jenni Bick's A6 Slash page is titled Japanese, while a search for the English JAN `4580812710268` returns that same page. It was not added.

Pen Boutique's Japanese A6 listing is JAN `4580812710152`, a different code from the English JAN `4580812710268`. Both are on the A6 page. The English shops use `4580812710268`.

JetPens `https://www.jetpens.com/Hobonichi-Techo-Weeks-English-Liberty-Fabrics-Floral-Remedy-2027-Jan-Start/pd/54089` returned HTTP 403 to the checker's normal request and to a browser user agent. The tracking parameter was removed. The owner's sold-out observation is not stored as a status. The design page links JetPens as not checked. A public copy of that page gives the model number `HOBONICHI 4580812709934`, language English, hardcover, January start, Monday start. That is the same English Weeks JAN as Kinokuniya, Pen Boutique, Atlas, Paper Mouse, Wonder Pens, Yoseka, and Jenni Bick.

Hobonichi's Floral Remedy page uses the word "Normal" once, next to "Available," as the sale label for this book. The same page then specifies two language editions of that one Weeks hardcover: English / January start and Japanese / January start. The 2027 feed has no second Floral Remedy key, no Floral Remedy Mega, and no Floral Remedy cover. The Liberty covers on that page are Michelle and Sasha Kiora, different designs. No tracked shop returned a Floral Remedy listing with a different JAN. A separate "normal" product was not added.

Wonder Pens titles that begin with PREVIEW and are unavailable are "Not yet on sale." The A6 Slash preview page's product data said the variant was available, so the existing checker reports that row in stock.
