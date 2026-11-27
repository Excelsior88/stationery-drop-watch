"""Brand-protection and checker politeness fixes, Nov 20, 2026.

Fetch dedupe, robots.txt longest-match, the contact address, www to apex
history, Pen Boutique HON labels, and Laywine's Planner A6 mapping.
"""
import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import scripts.checker as checker
import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import baseline  # noqa: E402
UA = checker.UA
OLD = "2026-10-25T21:40:49+00:00"
LAY = "https://laywines.com/products/hobonichi-a6-planner-english-book-2027"
PEN = {
    "https://www.penboutique.com/products/hobonichi-hon-a6-2027-english-slash-navy":
        "HON A6 · Slash (Navy) (English)",
    "https://www.penboutique.com/products/hobonichi-hon-light-hardcover-japanese-book-slash-navy-a6-january-start":
        "HON A6 · Slash (Navy) (Japanese)",
    "https://www.penboutique.com/products/hobonichi-hon-a6-2027-bow-tie-sheep-sheep-sheep":
        "HON A6 · Bow & Tie: Sheep Sheep Sheep (English)",
    "https://www.penboutique.com/products/hobonichi-hon-light-hardcover-japanese-book-bow-tie-sheep-sheep-sheep-a6-january-start":
        "HON A6 · Bow & Tie: Sheep Sheep Sheep (Japanese)",
}
NOTE = (
    "Stationery Drop Watch is an independent site. "
    "It is not affiliated with or endorsed by any brand or shop we track. "
    "Brands or shops can ask to be removed at"
)


class _Resp:
    def __init__(self, payload=None, text="", ok=True, status=200, ctype="application/json"):
        self._payload = payload
        self.text = text
        self.ok = ok
        self.status_code = status
        self.headers = {"content-type": ctype}

    def json(self):
        return self._payload


def _product(title, variants):
    return {"title": title, "available": any(v["available"] for v in variants), "tags": [], "variants": variants}


class FetchCacheTests(unittest.TestCase):
    def test_shared_shopify_js_is_fetched_once_per_variant_status(self):
        js = _product("Storybook", [
            {"id": 11, "title": "A5", "public_title": "A5", "available": True, "price": "3200"},
            {"id": 22, "title": "B5", "public_title": "B5", "available": False, "price": "3600"},
        ])
        other = _product("Songbird", [
            {"id": 33, "title": "Default Title", "available": True, "price": "2800"},
        ])
        calls = []

        class Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                calls.append(url)
                if url.endswith("/robots.txt"):
                    return _Resp(text="User-agent: *\nAllow: /\n", ctype="text/plain")
                if url.endswith("/storybook.js"):
                    return _Resp(js)
                if url.endswith("/songbird.js"):
                    return _Resp(other)
                raise AssertionError(url)

        store = {"id": "archerolive", "name": "Archer and Olive (official)", "platform": "shopify",
                 "url": "https://www.archerandolive.com/", "products": [
                     {"label": "Storybook · A5", "type": "Dot grid notebook", "canonical": "ao-storybook-navy",
                      "url": "https://www.archerandolive.com/products/storybook?variant=11", "variant_id": 11},
                     {"label": "Storybook · B5", "type": "Dot grid notebook", "canonical": "ao-storybook-navy",
                      "url": "https://www.archerandolive.com/products/storybook?variant=22", "variant_id": 22},
                     {"label": "Songbird", "type": "Dot grid notebook", "canonical": "ao-songbird-blue",
                      "url": "https://www.archerandolive.com/products/songbird", "variant_id": 33},
                 ]}
        with patch.object(checker, "GuardedSession", Session), patch.object(checker, "DELAY", 0):
            rows = checker.check_shopify_store(store)
        js_calls = [u for u in calls if u.endswith(".js")]
        self.assertEqual(js_calls, [
            "https://www.archerandolive.com/products/storybook.js",
            "https://www.archerandolive.com/products/songbird.js",
        ])
        by_url = {r["url"]: r for r in rows}
        self.assertEqual(by_url[store["products"][0]["url"]]["status"], "in_stock")
        self.assertEqual(by_url[store["products"][1]["url"]]["status"], "sold_out")
        self.assertIn("A5", by_url[store["products"][0]["url"]]["title"])
        self.assertIn("B5", by_url[store["products"][1]["url"]]["title"])
        self.assertEqual(by_url[store["products"][2]["url"]]["status"], "in_stock")
        self.assertEqual([r["url"] for r in rows], [p["url"] for p in store["products"]])

    def test_a_failed_fetch_is_not_retried(self):
        calls = []

        class Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                calls.append(url)
                if url.endswith("/robots.txt"):
                    return _Resp(text="User-agent: *\nAllow: /\n", ctype="text/plain")
                raise TimeoutError("slow")

        store = {"id": "baum", "name": "Baum-kuchen", "platform": "shopify",
                 "url": "https://www.baum-kuchen.net/", "products": [
                     {"label": "A", "type": "Weeks", "url": "https://www.baum-kuchen.net/products/weeks?variant=1", "variant_id": 1},
                     {"label": "B", "type": "Weeks", "url": "https://www.baum-kuchen.net/products/weeks?variant=2", "variant_id": 2},
                 ]}
        with patch.object(checker, "GuardedSession", Session), patch.object(checker, "DELAY", 0):
            rows = checker.check_shopify_store(store)
        self.assertEqual(sum(u.endswith("/weeks.js") for u in calls), 1)
        self.assertTrue(all(r["status"] == "unknown" and "TimeoutError" in r["error"] for r in rows))


class RobotsTests(unittest.TestCase):
    def allowed(self, body, url, ua=UA):
        return checker.Robots(body.splitlines()).allowed(ua, url)

    def test_shopify_allow_root_does_not_override_a_longer_disallow(self):
        body = "User-agent: *\nAllow: /\nDisallow: /cart.js\nDisallow: /cdn/wpm/*.js\n"
        self.assertFalse(self.allowed(body, "https://milligram.com/cart.js"))
        self.assertFalse(self.allowed(body, "https://milligram.com/cdn/wpm/shop.js"))
        self.assertTrue(self.allowed(body, "https://milligram.com/products/hobonichi-2027-techo-original-planner-book.js"))
        self.assertTrue(self.allowed(body, "https://milligram.com/products/hobonichi-2027-techo-original-planner-book?variant=1"))

    def test_wildcard_js_and_end_anchor(self):
        body = "User-agent: *\nDisallow: /*.js$\nAllow: /products/page.js$\n"
        self.assertFalse(self.allowed(body, "https://shop.example/products/foo.js"))
        self.assertTrue(self.allowed(body, "https://shop.example/products/foo.js?variant=1"))
        self.assertTrue(self.allowed(body, "https://shop.example/products/page.js"))
        self.assertTrue(self.allowed(body, "https://shop.example/products/page"))

    def test_allow_wins_an_equal_length_tie(self):
        body = "User-agent: *\nDisallow: /products\nAllow: /products\n"
        self.assertTrue(self.allowed(body, "https://shop.example/products/foo"))
        longer = "User-agent: *\nAllow: /p\nDisallow: /\n"
        self.assertTrue(self.allowed(longer, "https://shop.example/page"))
        self.assertFalse(self.allowed(longer, "https://shop.example/other"))

    def test_named_agent_group_wins_over_star(self):
        body = (
            "User-agent: *\nDisallow: /\n\n"
            "User-agent: StationeryDropWatch\nAllow: /products/\nDisallow: /cart.js\n"
        )
        self.assertTrue(self.allowed(body, "https://shop.example/products/foo.js"))
        self.assertFalse(self.allowed(body, "https://shop.example/cart.js"))
        self.assertTrue(self.allowed(body, "https://shop.example/other"))
        self.assertFalse(self.allowed(body, "https://shop.example/products/foo.js", ua="Mozilla/5.0"))
        # An empty Disallow closes the named group. It does not inherit the * rules.
        empty = "User-agent: stationerydropwatch\nDisallow:\n\nUser-agent: *\nDisallow: /\n"
        self.assertTrue(self.allowed(empty, "https://shop.example/products/foo.js"))


class ApexHistoryTests(unittest.TestCase):
    def test_www_row_is_the_same_listing_and_creates_no_event(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "data").mkdir()
        www = "https://www.goldspot.com/products/hobonichi-2027-techo-original-planner-book"
        apex = "https://goldspot.com/products/hobonichi-2027-techo-original-planner-book"
        seen = "2026-11-19T23:34:02+00:00"
        stores = {"stores": [{"id": "goldspot", "name": "Goldspot Pens", "platform": "shopify",
                              "url": "https://goldspot.com/", "products": [
                                  {"canonical": "planner-a6-en", "label": "Planner A6 book (English)",
                                   "type": "Book", "url": apex, "source_title": "Planner"}]}]}
        (tmp / "stores.json").write_text(json.dumps(stores))
        (tmp / "data" / "stock.json").write_text(json.dumps({"products": [{
            "url": www, "status": "in_stock", "first_seen": seen, "status_since": seen,
            "label": "Planner A6 book (English)", "store_id": "goldspot"}]}))
        (tmp / "data" / "changes.json").write_text("[]")
        js = _product("Planner", [{"id": 1, "title": "Default Title", "available": True}])

        class Session:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                if url.endswith("/robots.txt"):
                    return _Resp(text="User-agent: *\nAllow: /\n", ctype="text/plain")
                return _Resp(js)

        with patch.object(checker, "ROOT", tmp), patch.object(checker, "DELAY", 0), \
                patch.object(checker, "GuardedSession", Session):
            checker.main()
        row = json.loads((tmp / "data" / "stock.json").read_text())["products"][0]
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        self.assertEqual(row["url"], apex)
        self.assertEqual(row["status"], "in_stock")
        self.assertEqual(row["first_seen"], seen)
        self.assertEqual(row["status_since"], seen)
        self.assertEqual(changes, [])

        js["available"] = False
        js["variants"][0]["available"] = False
        with patch.object(checker, "ROOT", tmp), patch.object(checker, "DELAY", 0), \
                patch.object(checker, "GuardedSession", Session):
            checker.main()
        row = json.loads((tmp / "data" / "stock.json").read_text())["products"][0]
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        self.assertEqual(row["first_seen"], seen)
        self.assertEqual(row["status"], "sold_out")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["from"], "in_stock")
        self.assertEqual(changes[0]["to"], "sold_out")
        self.assertEqual(changes[0]["url"], apex)

    def test_other_www_hosts_are_left_alone(self):
        url = "https://www.penboutique.com/products/hobonichi-hon-a6-2027-english-slash-navy"
        self.assertEqual(checker.canonical_stock_url(url), url)
        self.assertIn("admin@stationerydropwatch.com", UA)
        self.assertNotIn("gmail.com", UA)
        self.assertIn("Agent/StationeryDropWatch", UA)
        self.assertIn("https://stationerydropwatch.com/", UA)


class CatalogFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stores = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data" / "stock.json").read_text())
        cls.changes = json.loads((ROOT / "data" / "changes.json").read_text())

    def test_three_shops_use_apex_urls_and_keep_history(self):
        blob = json.dumps(self.stores) + json.dumps(self.stock) + json.dumps(self.changes)
        for host in ("www.milligram.com", "www.cultpens.com", "www.goldspot.com"):
            self.assertNotIn(host, blob)
        expected = {
            "https://milligram.com/products/hobonichi-2027-techo-original-book-a6-japanese":
                ("in_stock", "2026-11-19T23:33:59+00:00", "2026-11-19T23:33:59+00:00"),
            "https://milligram.com/products/hobonichi-2027-techo-original-planner-book":
                ("in_stock", "2026-11-19T23:34:02+00:00", "2026-11-19T23:34:02+00:00"),
            "https://cultpens.com/products/leuchtturm1917-bullet-journal-edition-2-black":
                ("in_stock", "2026-11-19T23:34:18+00:00", "2026-11-19T23:34:18+00:00"),
            "https://goldspot.com/products/leuchtturm-1917-black-hardcover-medium-dotted":
                ("sold_out", "2026-11-20T03:04:51+00:00", "2026-11-20T03:04:51+00:00"),
        }
        # The rows as saved when they moved to apex URLs (frozen; see tests/fixtures/make_baselines.py).
        first_run = {p["url"]: p for p in baseline.load("checker_politeness")["products"]}
        for url, (status, first, since) in expected.items():
            row = first_run[url]
            self.assertEqual(row["status"], status, url)
            self.assertEqual(row["first_seen"], first, url)
            self.assertEqual(row["status_since"], since, url)
        # Live: Milligram is link-only now, so it has no rows; the others keep their first_seen.
        link_only = {s["id"] for s in self.stores["stores"] if s.get("link_only")}
        by_url = {p["url"]: p for p in self.stock["products"]}
        for url, (status, first, since) in expected.items():
            if "milligram.com" in url and "milligram" in link_only:
                self.assertNotIn(url, by_url)
                continue
            self.assertEqual(by_url[url]["first_seen"], first, url)
            self.assertFalse([c for c in self.changes if c["url"] == url and c["at"] <= first], url)
        for store in self.stores["stores"]:
            if store["id"] in ("milligram", "cultpens", "goldspot"):
                self.assertFalse(store["url"].startswith("https://www."))

    def test_pen_boutique_hon_a6_labels_are_distinct_and_history_stays(self):
        pen = next(s for s in self.stores["stores"] if s["id"] == "penboutique")
        labels = {p["url"]: p["label"] for p in pen["products"]}
        self.assertEqual({url: labels[url] for url in PEN}, PEN)
        saved = {p["url"]: p for p in self.stock["products"]}
        history = {
            "https://www.penboutique.com/products/hobonichi-hon-a6-2027-english-slash-navy":
                ("2026-11-09T03:56:07+00:00", "2026-11-09T03:56:07+00:00"),
            "https://www.penboutique.com/products/hobonichi-hon-light-hardcover-japanese-book-slash-navy-a6-january-start":
                ("2026-11-09T03:56:10+00:00", "2026-11-09T23:48:26+00:00"),
            "https://www.penboutique.com/products/hobonichi-hon-a6-2027-bow-tie-sheep-sheep-sheep":
                ("2026-11-15T01:03:06+00:00", "2026-11-15T01:03:06+00:00"),
            "https://www.penboutique.com/products/hobonichi-hon-light-hardcover-japanese-book-bow-tie-sheep-sheep-sheep-a6-january-start":
                ("2026-11-15T01:03:04+00:00", "2026-11-15T01:03:04+00:00"),
        }
        for url, (first, since) in history.items():
            row = saved[url]
            self.assertEqual(row["label"], PEN[url])
            self.assertEqual(row["status"], "sold_out")
            self.assertEqual(row["first_seen"], first)
            self.assertEqual(row["status_since"], since)
        groups = defaultdict(list)
        for store in self.stores["stores"]:
            for product in store["products"]:
                groups[(store["id"], product["label"])].append(product)
        for (sid, label), rows in groups.items():
            if len({p["url"] for p in rows}) < 2:
                continue
            canons = {p.get("canonical") for p in rows}
            self.assertEqual(canons, {rows[0].get("canonical")}, (sid, label))
            self.assertTrue(rows[0].get("canonical"))

    def test_laywines_a6_planner_keeps_its_history(self):
        lay = next(s for s in self.stores["stores"] if s["id"] == "laywines")
        row = next(p for p in lay["products"] if p["url"] == LAY)
        self.assertEqual(row["canonical"], "planner-a6-en")
        self.assertEqual(row["label"], "Planner A6 book (English)")
        originals = [p for p in lay["products"] if p.get("canonical") == "original-a6-en"]
        self.assertEqual(originals, [])
        # Laywine's was link-only Nov 23-26, 2026 and is checked again from Nov 26 (written permission from the shop).
        # Its first rows after the switch are first observations, so no event may predate the resume.
        self.assertFalse(lay.get("link_only"))
        self.assertEqual([c for c in self.changes if c["url"] == LAY and c["at"] < "2026-11-27T00:00"], [])


class DisclaimerAndPrivacyTests(unittest.TestCase):
    def test_footer_about_and_contact_name_the_removal_address(self):
        home = site.build_index()
        about = site.build_about()
        _fname, contact = site.build_contact()
        privacy = site.build_privacy()
        moved = site.redirect_page("about")
        for doc in (home, about, contact, privacy, moved, site.build_404()):
            self.assertIn(NOTE, doc)
            self.assertIn("admin@stationerydropwatch.com", doc)
        self.assertIn('class="muted">' + NOTE, home)
        self.assertIn("Cloudflare Web Analytics", privacy)
        self.assertIn("does not track individual end users across its customers", privacy)
        self.assertNotIn("does not currently run analytics beacons", privacy)
        self.assertIn("The site is hosted on Cloudflare Pages.", privacy)
        self.assertNotIn("hosted on GitHub (GitHub Pages)", privacy)
        self.assertNotIn("backup copy", privacy)
        self.assertIn("Kit", privacy)
        self.assertIn("On November 17, 2026, we reached out to Traveler's Company", site.TAKEDOWN_NOTICE[0])


if __name__ == "__main__":
    unittest.main()
