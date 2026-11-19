"""Traveler's Company and MIDORI takedown, Nov 19, 2026.

TRAVELER'S COMPANY USA asked us to remove every Traveler's Company and MIDORI product. The owner approved the
removal and the exact notice wording. These tests keep both brands out of the checker, the alerts and every page,
keep the old URLs reachable as the notice, and keep the site-wide shop count honest.
"""
import html
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402
import new_in_stock  # noqa: E402

GONE_STORES = {"travelerscompanyusa", "mdproductusa", "tokyopenshop", "omoi", "simplepaper"}
NEW_STORES = {"dromgooles", "milligram", "presentandcorrect", "cultpens", "goldspot"}
BRAND_WORDS = re.compile(r"traveler'?s (company|notebook)|midori|md product|md notebook|designphil", re.I)
APPROVED_FIRST = ("On November 17, 2026, we reached out to Traveler's Company and to MIDORI's parent company, Designphil, "
                  "through their official contact forms.")
APPROVED_LAST = "If you'd like restock news for these brands, the only route they've left you is their newsletter."


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())

    def test_no_traveler_or_midori_row_is_checked(self):
        ids = {s["id"] for s in self.cfg["stores"]}
        self.assertTrue(GONE_STORES.isdisjoint(ids))
        for s in self.cfg["stores"]:
            self.assertNotIn(s.get("section"), ("travelers", "midori"), s["id"])
            self.assertNotIn("Traveler", s.get("note", ""), s["id"])
            for p in s["products"]:
                self.assertNotIn(p.get("section"), ("travelers", "midori"), p["url"])
                self.assertIsNone(BRAND_WORDS.search(p["label"] + " " + p.get("source_title", "")), p["url"])
        for c in self.cfg["canonical"]:
            self.assertNotIn(c.get("section"), ("travelers", "midori"), c["id"])
            self.assertFalse(c["id"].startswith(("tn-", "md-")), c["id"])

    def test_checked_shop_count_is_27_with_the_replacements(self):
        checked = {s["id"] for s in self.cfg["stores"] if s["products"] and s["platform"] in ("shopify", "hobonichi")}
        self.assertEqual(len(checked), 27)
        self.assertTrue(NEW_STORES <= checked)
        self.assertEqual(site.N_STORES, 27)

    def test_new_shops_track_only_products_we_already_track(self):
        canon = {c["id"] for c in self.cfg["canonical"]}
        for s in self.cfg["stores"]:
            if s["id"] in NEW_STORES:
                self.assertTrue(s["products"], s["id"])
                for p in s["products"]:
                    self.assertIn(p["canonical"], canon, p["url"])
                    if "?variant=" in p["url"]:
                        self.assertEqual(p["url"].split("?variant=")[1], str(p["variant_id"]))


class AlertTests(unittest.TestCase):
    def test_new_in_stock_never_alerts_for_either_brand(self):
        events = [{"at": "2026-11-20T00:00:00+00:00", "store_id": "travelerscompanyusa", "label": "x", "to": "in_stock", "url": "u1"},
                  {"at": "2026-11-20T00:00:00+00:00", "store_id": "papermouse", "label": "y", "to": "in_stock", "url": "u2", "section": "midori"},
                  {"at": "2026-11-20T00:00:00+00:00", "store_id": "papermouse", "label": "z", "to": "in_stock", "url": "u3"}]
        self.assertEqual([c["url"] for c in new_in_stock.fresh_in_stock([], events)], ["u3"])

    def test_old_rows_never_reach_a_page_or_feed(self):
        for p in site.stock["products"]:
            self.assertNotIn(p.get("section"), site.TAKEDOWN_SECTIONS)
        for c in site.changes:
            self.assertNotIn(c.get("section"), site.TAKEDOWN_SECTIONS)
        self.assertEqual(site.LIVE, ["dotgrid"])
        self.assertNotIn("travelers", site.SECTIONS)
        self.assertNotIn("midori", site.SECTIONS)


class NoticeTests(unittest.TestCase):
    def test_notice_text_is_the_approved_wording(self):
        self.assertEqual(site.TAKEDOWN_HEADING, "Why Traveler's Company and MIDORI are gone")
        self.assertEqual(len(site.TAKEDOWN_NOTICE), 5)
        self.assertTrue(site.TAKEDOWN_NOTICE[0].startswith(APPROVED_FIRST))
        self.assertEqual(site.TAKEDOWN_NOTICE[-1], APPROVED_LAST)
        self.assertIn('"pushes that stock toward resellers,"', site.TAKEDOWN_NOTICE[1])

    def test_old_urls_show_the_notice(self):
        for slug, noindex in ((site.TN_SLUG, False), (site.MIDORI_SLUG, False), (site.TN_GUIDE_SLUG, True)):
            fname, doc = site.build_takedown_notice(slug, noindex=noindex)
            text = html.unescape(doc)
            self.assertEqual(fname, slug + "/")
            self.assertIn(f"<h1>{site.TAKEDOWN_HEADING}</h1>", text)
            for para in site.TAKEDOWN_NOTICE:
                self.assertIn(f"<p>{para}</p>", text)
            self.assertEqual('<meta name="robots" content="noindex">' in doc, noindex)
            self.assertNotIn("og-travelers.png", doc)
            self.assertNotIn("og-midori.png", doc)

    def test_item_pages_redirect_to_their_notice(self):
        for parent, slugs in site.TAKEDOWN_ITEMS.items():
            for slug in slugs:
                self.assertEqual(site.REDIRECTS[f"{parent}/{slug}"], parent + "/")
        self.assertEqual(site.REDIRECTS["travelers-notebook-regular-size"], site.TN_SLUG + "/")
        cf = (ROOT / "cloudflare/_redirects").read_text()
        for parent, slugs in site.TAKEDOWN_ITEMS.items():
            for slug in slugs:
                self.assertIn(f"/{parent}/{slug}/  /{parent}/  301", cf)
        self.assertNotIn("#tracker", cf)


class SiteCopyTests(unittest.TestCase):
    def test_no_tracker_page_nav_or_faq_mentions_either_brand(self):
        docs = [("index.html", site.build_index()), ("about.html", site.build_about()), ("404.html", site.build_404()),
                (site.HOBO_TRACKER, site.build_hobo_tracker())]
        docs += [site.build_group(g, {}) for g in site.GROUPS]
        docs += [site.build_guides_index(), site.build_sold_out(), site.build_follow(), site.build_contact()]
        for name, doc in docs:
            self.assertIsNone(BRAND_WORDS.search(html.unescape(doc)), name)
            self.assertNotIn("/travelers-company-limited-edition/", doc, name)
            self.assertNotIn("/midori-md-limited-edition/", doc, name)
        sitemap = site.build_sitemap()
        self.assertNotIn(site.TN_GUIDE_SLUG, sitemap)
        self.assertNotIn("regular-black", sitemap)

    def test_every_shop_total_on_the_home_page_is_27(self):
        home = html.unescape(site.build_index())
        totals = set(re.findall(r"\b(\d+) shops\b", re.sub(r"<[^>]+>", " ", home)))
        self.assertIn("27", totals)
        self.assertIn("27 shops across all trackers", home)
        self.assertIn("checks 27 shops", home)


if __name__ == "__main__":
    unittest.main()
