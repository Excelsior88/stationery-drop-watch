"""Recent restocks must show the latest check, not the status at the moment of the restock."""
import datetime as dt
import html
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402


def feed_items(doc, section_id="restocked"):
    start = doc.find(f'id="{section_id}"')
    chunk = doc[start:] if start >= 0 else doc
    stop = chunk.find("</section>")
    if stop >= 0:
        chunk = chunk[:stop]
    return re.findall(r'<li class="feed-item\b.*?</li>', chunk, re.S)


def badge(li):
    badges = re.findall(r'class="badge (\w+)">([^<]*)', li)
    return [(cls, html.unescape(label)) for cls, label in badges]


class RestockFeedTests(unittest.TestCase):
    def test_row_uses_latest_check_not_the_event_status(self):
        at = "2026-11-06T23:18:18+00:00"
        event = {"url": "https://shop.example/card-black", "label": "Card Size 20th Anniversary Set",
                 "store": "Traveler's Company USA (official)", "at": at, "from": "sold_out", "to": "in_stock"}
        products = site.stock["products"]
        try:
            site.stock["products"] = [{"url": event["url"], "status": "sold_out"}]
            sold = site.restock_feed_item(event)
            site.stock["products"] = [{"url": event["url"], "status": "in_stock"}]
            still = site.restock_feed_item(event)
            site.stock["products"] = [{"url": event["url"], "status": "unknown"}]
            failed = site.restock_feed_item(event)
            site.stock["products"] = []
            missing = site.restock_feed_item(event)
            site.stock["products"] = [{"url": event["url"], "status": "in_stock"},
                                      {"url": event["url"], "status": "sold_out"}]
            conflict = site.restock_feed_item(event)
            site.stock["products"] = [{"url": event["url"], "status": "preorder"}]
            event_to_in_stock = dict(event, to="in_stock")
            preorder = site.restock_feed_item(event_to_in_stock)
        finally:
            site.stock["products"] = products

        self.assertEqual(badge(sold), [("sold_out", "Sold out")])
        self.assertEqual(badge(still), [("in_stock", "In stock")])
        self.assertEqual(badge(failed), [("unknown", "Couldn't check")])
        self.assertEqual(badge(missing), [("unknown", "No current check")])
        self.assertEqual(badge(conflict), [("unknown", "No current check")])
        self.assertEqual(badge(preorder), [("preorder", "Preorder")])
        for li in (sold, failed, missing, conflict, preorder):
            self.assertNotIn("in_stock", li)
            self.assertNotIn("In stock", li)
            self.assertIn(f'datetime="{at}"', li)
            self.assertIn("Nov 6, 6:18 PM ET", li)
            self.assertIn('href="https://shop.example/card-black"', li)
            self.assertIn("Traveler&#x27;s Company USA (official)", li)
            self.assertIn("restocked", li)
            self.assertIn(">now <", li)

    def test_homepage_keeps_history_and_drops_stale_in_stock_claims(self):
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        def at(delta):
            return (now + delta).isoformat()
        sold_at, again_at = at(dt.timedelta(hours=5)), at(dt.timedelta(hours=1))
        still_at, failed_at, pre_at = at(dt.timedelta(hours=4)), at(dt.timedelta(hours=3)), at(dt.timedelta(hours=2))
        old_at, missing_at = at(dt.timedelta(days=-20)), at(dt.timedelta(hours=6))
        rows = [
            ("https://example.test/sold", "sold_out", "Sold Later"),
            ("https://example.test/still", "in_stock", "Still Here"),
            ("https://example.test/failed", "unknown", "Check Failed"),
            ("https://example.test/preorder", "preorder", "Opened As Preorder"),
            ("https://example.test/old", "sold_out", "Too Old"),
        ]
        products = [{"url": url, "status": status, "section": "travelers", "store_id": "fixture",
                     "store": "Fixture", "label": label, "type": "Notebook"} for url, status, label in rows]
        events = [
            {"url": "https://example.test/sold", "to": "in_stock", "from": "sold_out", "at": sold_at,
             "label": "Sold Later", "store": "Traveler's Company USA (official)"},
            {"url": "https://example.test/sold", "to": "in_stock", "from": "sold_out", "at": again_at,
             "label": "Sold Later", "store": "Traveler's Company USA (official)"},
            {"url": "https://example.test/still", "to": "in_stock", "from": "sold_out", "at": still_at,
             "label": "Still Here", "store": "Simple Paper"},
            {"url": "https://example.test/failed", "to": "in_stock", "from": "coming_soon", "at": failed_at,
             "label": "Check Failed", "store": "Omoi Zakka Shop"},
            {"url": "https://example.test/preorder", "to": "in_stock", "from": "sold_out", "at": pre_at,
             "label": "Opened As Preorder", "store": "Atlas Stationers"},
            {"url": "https://example.test/old", "to": "in_stock", "from": "sold_out", "at": old_at,
             "label": "Too Old", "store": "Old Shop"},
            {"url": "https://example.test/missing", "to": "in_stock", "from": "sold_out", "at": missing_at,
             "label": "Gone Listing", "store": "Nowhere"},
        ]
        orig_products, orig_changes = site.stock["products"], site.changes
        try:
            site.stock["products"] = list(orig_products) + products
            site.changes = list(orig_changes) + events
            doc = site.build_index()
        finally:
            site.stock["products"] = orig_products
            site.changes = orig_changes

        items = feed_items(doc)
        def item_for(url):
            hits = [li for li in items if url in li]
            self.assertEqual(len(hits), 1, url)
            return hits[0]
        sold = item_for("https://example.test/sold")
        still = item_for("https://example.test/still")
        failed = item_for("https://example.test/failed")
        preorder = item_for("https://example.test/preorder")
        self.assertNotIn("https://example.test/old", doc)
        self.assertNotIn("Gone Listing", doc)
        self.assertNotIn("https://example.test/missing", doc)
        self.assertIn(sold_at, sold)
        self.assertIn(again_at, sold)
        self.assertLess(sold.find(sold_at), sold.find(again_at))
        self.assertIn("<details", sold)
        self.assertNotIn("<details open", sold)
        self.assertEqual(badge(sold), [("sold_out", "Sold out")])
        self.assertEqual(badge(still), [("in_stock", "In stock")])
        self.assertEqual(badge(failed), [("unknown", "Couldn't check")])
        self.assertEqual(badge(preorder), [("preorder", "Preorder")])
        for li in (sold, failed, preorder):
            self.assertNotIn('data-now="in_stock"', li)
            self.assertNotIn(">In stock<", li)
        self.assertIn('data-now="in_stock"', still)
        self.assertIn('href="https://example.test/sold"', sold)
        self.assertIn("Traveler&#x27;s Company USA (official)", sold)
        self.assertIn('href="/travelers-company-limited-edition/"', sold)
        self.assertIn("restocked", sold)
        self.assertLess(doc.find("https://example.test/sold"), doc.find("https://example.test/still"))
        self.assertLess(doc.find("https://example.test/still"), doc.find("https://example.test/failed"))
        self.assertLess(doc.find("https://example.test/failed"), doc.find("https://example.test/preorder"))
        self.assertIn("Every tracker, newest first. Last 14 days.", doc)
        self.assertIn(site.RESTOCK_NOW_NOTE, doc)
        self.assertIn('class="restock-all" checked', doc)
        self.assertIn('class="restock-in"', doc)
        self.assertIn("None of these are in stock now.", doc)

    def test_homepage_keeps_newest_twelve_in_the_last_14_days(self):
        base = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) + dt.timedelta(days=2)
        products, events = [], []
        for i in range(13):
            url = f"https://example.test/limit-{i}"
            products.append({"url": url, "status": "sold_out", "section": "hobonichi", "store_id": "fixture",
                             "store": "Fixture", "label": f"Limit {i}", "type": "Book"})
            events.append({"url": url, "to": "in_stock", "from": "sold_out",
                           "at": (base - dt.timedelta(minutes=i)).isoformat(),
                           "label": f"Limit {i}", "store": "Fixture"})
        orig_products, orig_changes = site.stock["products"], site.changes
        try:
            site.stock["products"] = list(orig_products) + products
            site.changes = list(orig_changes) + events
            doc = site.build_index()
        finally:
            site.stock["products"] = orig_products
            site.changes = orig_changes
        items = feed_items(doc)
        self.assertEqual(len(items), 12)
        shown = [re.search(r'datetime="([^"]+)"', li).group(1) for li in items]
        self.assertEqual(shown, sorted(shown, reverse=True))
        self.assertIn("https://example.test/limit-0", items[0])
        self.assertNotIn("https://example.test/limit-12", "".join(items))
        self.assertEqual(badge(items[0]), [("sold_out", "Sold out")])

    def test_same_listing_groups_and_different_listings_stay_apart(self):
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        def at(hours):
            return (now + dt.timedelta(hours=hours)).isoformat()
        newer, older = at(3), at(1)
        events = [
            {"url": "https://example.test/black", "to": "in_stock", "from": "sold_out", "at": newer,
             "label": "Regular Black", "store": "Shop A"},
            {"url": "https://example.test/black", "to": "in_stock", "from": "sold_out", "at": older,
             "label": "Regular Black", "store": "Shop A"},
            {"url": "https://example.test/black-other", "to": "in_stock", "from": "sold_out", "at": at(2),
             "label": "Regular Black", "store": "Shop B"},
        ]
        products = [
            {"url": "https://example.test/black", "status": "sold_out"},
            {"url": "https://example.test/black-other", "status": "in_stock"},
        ]
        orig = site.stock["products"]
        try:
            site.stock["products"] = products
            doc = site.restock_feed(events, feed_id="split")
        finally:
            site.stock["products"] = orig
        items = feed_items(doc)
        self.assertEqual(len(items), 2)
        self.assertIn(newer, items[0])
        self.assertIn(older, items[0])
        self.assertIn("Earlier restock (1)", items[0])
        self.assertIn('href="https://example.test/black"', items[0])
        self.assertIn("Shop A", items[0])
        self.assertNotIn("Shop B", items[0])
        self.assertIn('data-now="sold_out"', items[0])
        self.assertIn('href="https://example.test/black-other"', items[1])
        self.assertIn("Shop B", items[1])
        self.assertIn('data-now="in_stock"', items[1])
        self.assertNotIn("<details", items[1])

    def test_in_stock_view_excludes_unknown_preorder_and_sold_out(self):
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        events = [{"url": f"https://example.test/{st}", "to": "in_stock", "from": "sold_out", "at": now,
                   "label": st, "store": "Shop"} for st in ("in_stock", "preorder", "sold_out", "unknown")]
        products = [{"url": e["url"], "status": e["label"]} for e in events]
        orig = site.stock["products"]
        try:
            site.stock["products"] = products
            doc = site.restock_feed(events, feed_id="filter")
        finally:
            site.stock["products"] = orig
        self.assertEqual(doc.count('data-now="in_stock"'), 1)
        for st in ("preorder", "sold_out", "unknown"):
            self.assertIn(f'data-now="{st}"', doc)
            self.assertNotIn(f'data-now="{st}" data-now="in_stock"', doc)
        self.assertIn("None of these are in stock now.", doc)
        self.assertIn('class="time-instant"', doc)
        self.assertIn(f'datetime="{now}"', doc)

    def test_filter_controls_stay_hidden_without_has_support(self):
        css = (ROOT / "site/assets/style.css").read_text()
        hidden = css.find(".feed-controls{display:none}")
        guard = css.find("@supports selector(:has(*))")
        rule = css.find('.restocks:has(.restock-in:checked) .feed-item:not([data-now="in_stock"]){display:none}')
        empty = css.find('.restocks:has(.restock-in:checked):not(:has(.feed-item[data-now="in_stock"])) .feed-empty{display:block}')
        end = css.find("\n}", guard)
        self.assertGreater(hidden, 0)
        self.assertLess(hidden, guard)
        self.assertLess(guard, rule)
        self.assertLess(rule, empty)
        self.assertLess(empty, end)

    def test_tracker_pages_use_the_same_current_status(self):
        oe = site.amazon_main(site.stock["products"])
        docs = [("index", site.build_index()), ("hobo", site.build_hobo_tracker())]
        for g in site.GROUPS:
            fname, doc = site.build_group(g, oe)
            site.check_none_claim(fname, doc)
            docs.append((fname, doc))
        for d in site.DESIGNS:
            fname, doc = site.build_design(d, oe)
            site.check_none_claim(fname, doc)
            site.check_amz_doc(fname, doc)
            docs.append((fname, doc))
        by_url = {}
        for p in site.stock["products"]:
            by_url.setdefault(p["url"], set()).add(p.get("status"))
        seen = 0
        for name, doc in docs:
            for li in re.findall(r'<li class="feed-item"[^>]*>(.*?)</li>', doc, re.S):
                seen += 1
                href = html.unescape(re.search(r'href="([^"]+)"', li).group(1))
                badges = badge(li)
                self.assertEqual(len(badges), 1, name)
                st, label = badges[0]
                statuses = by_url.get(href)
                if not statuses or len(statuses) != 1 or next(iter(statuses)) not in site.STATUS:
                    self.assertEqual((st, label), ("unknown", "No current check"), name)
                else:
                    cur = next(iter(statuses))
                    self.assertEqual((st, label), (cur, site.STATUS[cur]), f"{name} {href}")
                self.assertIn("restocked", li)
                self.assertRegex(li, r'datetime="20\d\d-')
                if st != "in_stock":
                    self.assertNotIn("in_stock", li)
                    self.assertNotIn("In stock", li)
        self.assertGreater(seen, 0)


class RestockViewBrowserTests(unittest.TestCase):
    """Synthetic listings only. Not shop data and not the live site."""

    def test_chrome_toggles_filters_keyboard_and_time_zones(self):
        chrome = "/usr/local/bin/google-chrome"
        if not Path(chrome).exists() or not Path("/tmp/qa-browser/node_modules/puppeteer-core").exists():
            self.skipTest("Chrome or puppeteer-core is not available")
        out = Path("/tmp/qa-feed")
        if out.exists():
            shutil.rmtree(out)
        (out / "assets").mkdir(parents=True)
        shutil.copy(ROOT / "site/assets/style.css", out / "assets/style.css")
        shutil.copy(ROOT / "site/assets/local-time.js", out / "assets/local-time.js")
        newer, older = "2026-11-08T08:44:43+00:00", "2026-11-06T23:18:18+00:00"
        def event(url, label, when):
            return {"url": url, "label": label, "store": "Fixture", "at": when,
                    "to": "in_stock", "from": "sold_out"}
        mixed_events = [
            event("https://example.test/sold", "Fixture sold out", newer),
            event("https://example.test/sold", "Fixture sold out", older),
            event("https://example.test/stocked", "Fixture in stock", newer),
        ]
        empty_events = [
            event("https://example.test/sold", "Fixture sold out", newer),
            event("https://example.test/preorder", "Fixture preorder", newer),
            event("https://example.test/unknown", "Fixture unchecked", newer),
            event("https://example.test/missing", "Fixture missing check", newer),
        ]
        products = [
            {"url": "https://example.test/sold", "status": "sold_out"},
            {"url": "https://example.test/stocked", "status": "in_stock"},
            {"url": "https://example.test/preorder", "status": "preorder"},
            {"url": "https://example.test/unknown", "status": "unknown"},
        ]
        orig = site.stock["products"]
        try:
            site.stock["products"] = products
            mixed = site.RESTOCK_NOW_NOTE + site.restock_feed(mixed_events, feed_id="mixed")
            empty = site.RESTOCK_NOW_NOTE + site.restock_feed(empty_events, feed_id="empty")
        finally:
            site.stock["products"] = orig

        def wrap(body):
            return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<link rel="stylesheet" href="/assets/style.css"></head><body>
<main class="wrap"><section id="restocked"><h2>Synthetic fixture, not a shop</h2>{body}</section></main>
<script src="/assets/local-time.js"></script>
<script>DropWatchTime.showLocalTimes(document)</script>
</body></html>"""
        (out / "mixed.html").write_text(wrap(mixed))
        (out / "empty.html").write_text(wrap(empty))
        env = os.environ.copy()
        env["NODE_PATH"] = "/tmp/qa-browser/node_modules"
        env["FIXTURE_ORIGIN"] = "http://127.0.0.1:8770"
        server = subprocess.Popen([sys.executable, "-m", "http.server", "8770", "--bind", "127.0.0.1"],
                                  cwd=out, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.4)
        try:
            run = subprocess.run(["node", str(ROOT / "tests/restock_view_browser.mjs")],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
        finally:
            server.kill()
            server.wait(timeout=5)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("browser restock view ok", run.stdout)


if __name__ == "__main__":
    unittest.main()
