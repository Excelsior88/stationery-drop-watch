# Grouped recent restocks, 8 Nov 2026

Not merged and not deployed. The 13-versus-23 preview question was left as already answered: the live homepage social tags do not say 13.

## What the list does

A restock row is one listing URL. The same product at another shop, or another variant or edition, stays its own row. The row shows the newest return in the set and the current status from the stock check, not the status stored on the old event. Preorder, sold out, couldn't-check, and a missing check are not "in stock."

Earlier returns of that same listing sit in a closed "Earlier restocks" disclosure. All and In stock now are two radio buttons. All is the default. In stock now hides the other rows and, if none remain, says "None of these are in stock now." Choosing All brings them back. The radios work without JavaScript. Times stay ISO in `datetime` and Eastern Time in the text until the existing local-time script renames the zone.

On the homepage and the Hobonichi tracker the set is the last 14 days, then the 12 listings with the newest return. On a product or design page the set is still the 10 newest events, grouped after that.

## Preview

Screenshots `feed-desktop-all.png`, `feed-mobile-all.png`, `feed-desktop-instock.png`, `feed-mobile-instock.png`, `feed-desktop-history.png`, and `feed-mobile-history.png` are a local build from repository stock `run_finished` `2026-11-08T17:48:38+00:00`, not the live site. Those six pages did not load `local-time.js`, so the Eastern Time text is the no-JavaScript fallback, not a local-zone check.

The All / In stock radios are hidden unless the browser supports `:has`. Without that selector the list stays the full All view, and there is no control that does nothing. Chrome, which supports `:has`, was driven through All, In stock now, and back, including a fixture whose rows are only sold out, preorder, couldn't check, and a missing check.
