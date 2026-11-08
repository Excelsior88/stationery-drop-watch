"""Recent restocks must show the latest check, not the status at the moment of the restock."""
import datetime as dt
import html
import re
import sys
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
    return re.findall(r'<li class="feed-item">(.*?)</li>', chunk, re.S)


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
        by_when = {}
        for li in items:
            m = re.search(r'datetime="([^"]+)"', li)
            self.assertIsNotNone(m)
            by_when.setdefault(m.group(1), li)
        self.assertIn(sold_at, by_when)
        self.assertIn(again_at, by_when)
        self.assertNotIn(old_at, by_when)
        self.assertNotIn("Gone Listing", doc)
        self.assertNotIn("https://example.test/missing", doc)
        sold, still, failed, preorder = by_when[sold_at], by_when[still_at], by_when[failed_at], by_when[pre_at]
        self.assertEqual(badge(sold), [("sold_out", "Sold out")])
        self.assertEqual(badge(still), [("in_stock", "In stock")])
        self.assertEqual(badge(failed), [("unknown", "Couldn't check")])
        self.assertEqual(badge(preorder), [("preorder", "Preorder")])
        for li in (sold, failed, preorder):
            self.assertNotIn("in_stock", li)
            self.assertNotIn("In stock", li)
        self.assertIn('href="https://example.test/sold"', sold)
        self.assertIn("Traveler&#x27;s Company USA (official)", sold)
        self.assertIn('href="/travelers-company-limited-edition/"', sold)
        self.assertIn("restocked", sold)
        self.assertLess(doc.find(sold_at), doc.find(still_at))
        self.assertLess(doc.find(still_at), doc.find(failed_at))
        self.assertLess(doc.find(failed_at), doc.find(pre_at))
        self.assertLess(doc.find(pre_at), doc.find(again_at))
        self.assertIn("Every tracker, newest first. Last 14 days.", doc)
        self.assertIn(site.RESTOCK_NOW_NOTE, doc)

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
            for li in re.findall(r'<li class="feed-item">(.*?)</li>', doc, re.S):
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


if __name__ == "__main__":
    unittest.main()
