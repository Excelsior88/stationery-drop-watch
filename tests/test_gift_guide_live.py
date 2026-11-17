"""Holiday gift guide: every stock line is generated from data/stock.json at build time, never fixed text."""
import copy
import html
import json
import re
import unittest
from pathlib import Path
from unittest import mock

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def with_status(canonical, status):
    """A copy of stock.json with every listing of one canonical set to status."""
    data = copy.deepcopy(site.stock)
    for p in data["products"]:
        if p.get("canonical") == canonical:
            p["status"] = status
    return data


def section(doc, name):
    """One pick's write-up: its list item, from the bold name to the end of the item."""
    i = doc.index(f"<strong>{name}")
    return doc[i:doc.index("</li>", i)]


def glance_row(doc, name):
    table = doc[doc.index('<h2 id="prices">'):doc.index('<h2 id="hobonichi">')]
    return next(r for r in table.split("<tr>") if html.escape(name) in r or name in r)


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


MOOMIN = "Weeks, Moomin: At the Table (English)"


class GiftGuideLiveStockTests(unittest.TestCase):
    def render(self, data=None):
        if data is None:
            return site.build_gift_guide()[1]
        with mock.patch.object(site, "stock", data):
            return site.build_gift_guide()[1]

    def test_flipping_a_fixture_status_changes_the_rendered_page(self):
        n = len({p["store_id"] for p in site.stock["products"] if p.get("canonical") == "weeks-moomin-table"})
        doc = self.render(with_status("weeks-moomin-table", "sold_out"))
        sold = section(doc, MOOMIN)
        self.assertIn(f"at all {n} shops", text(glance_row(doc, MOOMIN)))
        self.assertIn('<span class="badge sold_out">Sold out</span>', sold)
        self.assertNotIn("badge in_stock", sold)
        doc = self.render(with_status("weeks-moomin-table", "in_stock"))
        live = section(doc, MOOMIN)
        self.assertIn(f"{n} of {n} shops", text(glance_row(doc, MOOMIN)))
        self.assertIn('<span class="badge in_stock">In stock</span>', live)
        self.assertNotEqual(sold, live)

    def test_glance_table_follows_the_same_data(self):
        doc = self.render(with_status("tn-regular-black", "sold_out"))
        self.assertIn("Sold out at all", text(glance_row(doc, "Traveler's notebook Regular, Black")))

    def test_unchecked_listings_are_not_called_sold_out(self):
        sec = text(section(self.render(with_status("weeks-moomin-table", "unknown")), MOOMIN))
        self.assertIn("Couldn't check", sec)
        self.assertNotIn("Sold out", sec)

    def test_a_pick_that_leaves_tracking_gets_no_availability_claim(self):
        data = copy.deepcopy(site.stock)
        data["products"] = [p for p in data["products"] if p.get("canonical") != "weeks-moomin-table"]
        sec = section(self.render(data), MOOMIN)
        self.assertNotIn("badge", sec)
        self.assertNotIn("in stock", text(sec).lower())

    def test_current_lines_match_stock_json(self):
        doc = self.render()
        for key in site.GIFT_PICKS:
            self.assertTrue(site.gift_listings(key), f"{key} has no tracked listings")
            cls, badge, _ = site.gift_status(key)
            self.assertIn(f'<span class="badge {cls}">{badge}</span> <a href=', doc, key)
            self.assertIn(site.gift_glance(key), doc, key)
        self.assertIn(site.time_tag(site.stock["run_finished"]), doc)


class GiftGuideCopyTests(unittest.TestCase):
    doc = (SITE / "holiday-stationery-gift-guide-2026/index.html").read_text()

    def test_every_price_comes_from_data_and_no_dated_notes(self):
        # Shop prices are rendered from stock.json at build time; the only other prices are our own
        # list prices (AMAZON_LIST_PRICES) and the shared Etsy price, the same ones /shop shows.
        recorded = {site._usd(c) for p in site.stock["products"]
                    for c in (p.get("price_cents"), p.get("price_max_cents")) if isinstance(c, int)}
        prices = set(re.findall(r"\$\d+(?:,\d{3})*(?:\.\d\d)?", text(self.doc)))
        self.assertLessEqual(prices, set(site.AMAZON_LIST_PRICES.values()) | {site.ETSY_PRICE[0]} | recorded)
        low = text(self.doc).lower()
        for banned in ("black friday", "cyber monday", "ships within", "prices when we checked", "price seen",
                       "b0nem0ther", "bullet journal\u00a0", "#bulletjournal"):
            self.assertNotIn(banned, low)
        self.assertNotIn("bullet journal", low.replace("bullet journal edition 2", ""))

    def test_own_books_are_plain_links_and_affiliate_asins_come_from_the_link_file(self):
        amz = json.loads((ROOT / "content/amazon_links.json").read_text())
        known = {m["asin"] for m in amz["products"].values()} | {m["asin"] for m in amz.get("listings", {}).values()}
        for a in re.findall(r'<a\b[^>]*amazon\.com[^>]*>', self.doc):
            asin = re.search(r"/dp/([A-Z0-9]{10})", a).group(1)
            if asin in site.AMAZON_LIST_PRICES:
                self.assertIn("data-own-product", a)
                self.assertNotIn("tag=", a)
            else:
                self.assertIn(asin, known)
                self.assertIn(f"tag={site.AMAZON_TAG}", a)

    def test_one_signup_and_faq_markup_matches_visible_questions(self):
        self.assertEqual(self.doc.count("<form "), 1)
        self.assertEqual(self.doc.count('id="alerts"'), 1)
        ld = [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', self.doc, re.S)]
        faq = next(d for d in ld if d.get("@type") == "FAQPage")
        faq_html = self.doc[self.doc.index('id="faq"'):]
        visible = [html.unescape(q) for q in re.findall(r"<summary>(.*?)</summary>", faq_html)]
        self.assertEqual([q["name"] for q in faq["mainEntity"]], visible)

    def test_every_live_link_exists(self):
        for key, (_, _, live, _) in site.GIFT_PICKS.items():
            self.assertTrue((SITE / live / "index.html").is_file(), live)
            self.assertIn(f'href="/{live}"', self.doc)

    def test_listed_in_guides_and_sitemap_and_matches_guide_design(self):
        self.assertIn('href="/holiday-stationery-gift-guide-2026/"', (SITE / "guides/index.html").read_text())
        self.assertIn("https://stationerydropwatch.com/holiday-stationery-gift-guide-2026/", (SITE / "sitemap.xml").read_text())
        for part in ('<article class="prose guide vs-page">', 'class="signup-strip" id="alerts"', '<section class="card faq" id="faq">',
                     '<ol class="sources two-col">', '<section class="card related"'):
            self.assertIn(part, self.doc)
        self.assertNotIn("document.cookie", self.doc)
        self.assertIn('<a href="/guides/" aria-current=page>Guides</a>', self.doc)


if __name__ == "__main__":
    unittest.main()
