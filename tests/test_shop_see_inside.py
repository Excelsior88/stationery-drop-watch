"""Shop see-inside samples for Level Up and Soft Days.

The four existing Amazon previews and the two adult PDF previews stay on their
old jpg paths. Cover files are thumbs. Soft Days interiors are the three inserts.
"""
import hashlib
import unittest
from pathlib import Path

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]


def card(doc, title):
    i = doc.find(f"<h3>{title}</h3>")
    start = doc.rfind('<li class="shop-card"', 0, i)
    end = doc.find("</div></li>", i)
    return doc[start:end + len("</div></li>")]


class ShopSeeInsideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop_name, cls.shop = site.build_shop()
        site.guard_release("shop/index.html", cls.shop)
        cls.home = site.build_index()

    def test_preview_bytes_match_the_audit_prefix(self):
        # Prefixes are enough to catch a swapped or recompressed file. The full
        # digests are recorded in the task note.
        expected = {
            "site/assets/shop/levelup-etsy-cover.webp": "58996cadc76a1532",
            "site/assets/shop/levelup-print-front.webp": "4f6624098922b692",
            "site/assets/shop/inside/levelup-etsy-p009.webp": "bbe894f9b82b95c0",
            "site/assets/shop/inside/levelup-etsy-p012.webp": "8c13a3528f274ba3",
            "site/assets/shop/inside/levelup-etsy-p013.webp": "28dfa6dcd72da00a",
            "site/assets/shop/inside/levelup-print-p009.webp": "057c7e3ea5333d49",
            "site/assets/shop/inside/levelup-print-p012.webp": "500ddeef0d156812",
            "site/assets/shop/inside/levelup-print-p013.webp": "f9cc8eeaaa34c8bd",
            "site/assets/shop/inside/softdays-weekly-color.webp": "b8cbcd75471432ad",
            "site/assets/shop/inside/softdays-habit-gray.webp": "3619d2a802c9e9d7",
            "site/assets/shop/inside/softdays-swatches-color.webp": "9c7cd6d92eefd21f",
        }
        for rel, prefix in expected.items():
            digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            self.assertTrue(digest.startswith(prefix), rel)
        self.assertFalse((ROOT / "site/assets/shop/softdays-product-tile.webp").exists())
        self.assertNotIn("softdays-product-tile", self.shop)

    def test_covers_are_thumbs_and_interiors_stay_in_the_disclosure(self):
        etsy = card(self.shop, "Level Up! My 2027 Kids Planner")
        paper = card(self.shop, "Level Up! My 2027 Planner")
        self.assertIn('alt="Front cover of the Level Up! 2027 printable planner"', etsy)
        self.assertIn('alt="Front cover of the Level Up! 2027 paperback planner"', paper)
        self.assertIn("levelup-etsy-cover.webp", etsy)
        self.assertNotIn("levelup-etsy-cover.webp", etsy.split("<details", 1)[-1])
        self.assertIn("levelup-print-front.webp", paper)
        self.assertNotIn("levelup-print-front.webp", paper.split("See inside", 1)[-1])
        self.assertNotIn("Authentic final PDF interior", etsy.split("<details", 1)[0])
        self.assertNotIn("Print edition coming soon", self.shop)
        self.assertNotIn("Print edition coming soon", self.home)

    def test_each_edition_has_its_own_three_samples(self):
        etsy = card(self.shop, "Level Up! My 2027 Kids Planner")
        paper = card(self.shop, "Level Up! My 2027 Planner")
        days = card(self.shop, "Soft Days Narrow Planner Inserts")
        for name in ("levelup-etsy-p009.webp", "levelup-etsy-p012.webp", "levelup-etsy-p013.webp"):
            self.assertIn(name, etsy)
            self.assertNotIn(name, paper)
        for name in ("levelup-print-p009.webp", "levelup-print-p012.webp", "levelup-print-p013.webp"):
            self.assertIn(name, paper)
            self.assertNotIn(name, etsy)
        for name in ("softdays-weekly-color.webp", "softdays-habit-gray.webp", "softdays-swatches-color.webp"):
            self.assertIn(name, days)
        visible, hidden = paper.split("<details", 1)
        self.assertIn("ages 7 to 11", visible)
        self.assertIn("Reading Quest Log", visible)
        self.assertEqual(visible.count("168 pages"), 1)
        self.assertEqual(visible.count("8.5 x 11"), 1)
        self.assertEqual(visible.count("Monday start"), 1)
        self.assertEqual(visible.count("January to December 2027"), 1)
        self.assertEqual(visible.count("Paperback"), 1)
        self.assertNotIn("print-ready", visible)
        self.assertNotIn("local print master", visible)
        self.assertIn("Sample pages from the print-ready file, not photographs of a printed copy.", hidden)
        self.assertEqual(paper.count("Sample pages from the print-ready file"), 1)
        self.assertNotIn("Sample pages from the print-ready file", etsy)
        self.assertNotIn("Sample pages from the print-ready file", days)
        self.assertIn("Sample from the printable PDF.", etsy)
        self.assertIn("not a separate swatch product", days)
        self.assertIn('loading="lazy"', etsy)
        self.assertIn('width="812" height="1050"', etsy)
        self.assertIn('width="511" height="1051"', days)
        self.assertNotIn("<details class=\"shop-inside\" open", self.shop)
        self.assertIn(">Larger view</a>", days)
        self.assertIn('class="inside-grid samples inserts"', days)
        self.assertIn('class="inside-grid samples"', etsy)

    def test_paperback_uses_the_plain_amazon_link_and_no_hardcoded_price(self):
        paper = card(self.shop, "Level Up! My 2027 Planner")
        self.assertIn('href="https://www.amazon.com/dp/B0HQW8273V"', paper)
        self.assertIn("data-own-product", paper)
        self.assertNotIn("tag=", paper)
        self.assertNotIn("a.co/d/02grz96c", paper)
        self.assertIn("See price on Amazon", paper)
        self.assertNotIn("$19.99", paper)
        self.assertNotIn("In Stock", paper)
        self.assertNotIn("B0nem0ther", paper)
        self.assertNotIn("Excelsior", paper)
        self.assertIn("https://www.etsy.com/listing/4610143237", card(self.shop, "Level Up! My 2027 Kids Planner"))
        self.assertIn("https://www.etsy.com/listing/4611293526/soft-days-narrow-planner-inserts",
                      card(self.shop, "Soft Days Narrow Planner Inserts"))

    def test_existing_previews_are_unchanged(self):
        expected = [
            "/assets/shop/inside/B0HPBDNS7F-monthly-calendar-goals-spread-p6-7.jpg",
            "/assets/shop/inside/B0HPBDNS7F-weekly-spread-p12-13.jpg",
            "/assets/shop/inside/B0HQ5TLDK3-habit-and-mood-tracker-spread-p6-7.jpg",
            "/assets/shop/inside/B0HQ5TLDK3-weekly-checkin-spread-p8-9.jpg",
            "/assets/shop/inside/B0HQ5X3C7D-genre-tracker-books-read-log-spread-p12-13.jpg",
            "/assets/shop/inside/B0HQ5X3C7D-book-review-spread-p24-25.jpg",
            "/assets/shop/inside/B0HP9PXSR1-monthly-calendar-goals-spread-p6-7.jpg",
            "/assets/shop/inside/B0HP9PXSR1-weekly-spread-p12-13.jpg",
            "/assets/shop/inside/womens-04-weekly-spread-dec27-jan2.jpg",
            "/assets/shop/inside/womens-05-monthly-calendar-january.jpg",
            "/assets/shop/inside/womens-06-habit-tracker-january.jpg",
            "/assets/shop/inside/mens-04-weekly-spread-dec27-jan2.jpg",
            "/assets/shop/inside/mens-05-monthly-calendar-january.jpg",
            "/assets/shop/inside/mens-06-habit-tracker-january.jpg",
        ]
        for src in expected:
            self.assertIn(f'src="{src}"', self.shop)
        # Those older disclosures do not gain a larger-view link.
        blush = card(self.shop, "2027 Printable Planner, Blush")
        self.assertNotIn("Larger view", blush)
        self.assertNotIn(".webp", blush)

    def test_fit_claim_is_qualified_and_the_hub_names_both_editions(self):
        self.assertNotIn("has not been tested", self.shop.lower())
        self.assertNotIn("test-printed", self.shop.lower())
        self.assertNotIn("Tested in a Hobonichi Weeks Mega", self.shop)
        self.assertNotIn("Tested in a Hobonichi Weeks Mega", self.home)
        # The homepage does not show our own product row. Both editions stay on /shop.
        self.assertNotIn('id="our-planners"', self.home)
        self.assertNotIn("hub-own", self.home)
        self.assertNotIn("nav-shop", self.home)
        self.assertIn(">Shop</a>", self.home)
        self.assertIn('class="foot-nav"', self.home)
        self.assertIn('href="/follow/">Follow us</a>', self.home)
        self.assertIn("As an Amazon Associate we earn from qualifying purchases.", self.home)
        self.assertIn("Statuses come straight from each store's public product data", self.home)
        self.assertIn("Level Up! My 2027 Planner", self.shop)
        self.assertIn("Paperback", card(self.shop, "Level Up! My 2027 Planner"))
        self.assertIn("Front cover of the Level Up! 2027 printable planner", self.shop)
        self.assertIn("20% off launch sale Oct 31 to Nov 30", card(self.shop, "Level Up! My 2027 Kids Planner"))
        self.assertEqual(site.shop_lastmod(), "2026-11-13")
        grid = card(self.shop, "Lines for the Grid Page")
        self.assertIn("https://www.etsy.com/listing/4614089507/lines-for-the-grid-page-printable-tip-in", grid)
        self.assertIn("$6.99", grid)
        self.assertIn("20% off launch sale Oct 31 to Nov 30", grid)
        self.assertIn("not affiliated", grid.lower())
        self.assertIn("dot grid (5 mm)", grid.lower())
        self.assertIn("lines-grid-layouts.webp", grid)
        self.assertIn("not a photograph of a printed copy", grid.lower())
        self.assertNotIn("bullet journal", grid.lower())
        self.assertNotIn("launch20", grid.lower())
        self.assertIn("Lines for the Grid Page", self.shop)
        self.assertNotIn("Lines for the Grid Page", self.home)

    def test_holiday_planner_pages_follows_the_insert_card(self):
        from PIL import Image
        hero = ROOT / "site/assets/shop/holiday-planner-pages.webp"
        layouts = ROOT / "site/assets/shop/inside/holiday-planner-layouts.webp"
        with Image.open(hero) as im:
            self.assertEqual(im.size, (2000, 2000))
        with Image.open(layouts) as im:
            self.assertEqual(im.size, (2700, 2025))
        self.assertLess(hero.stat().st_size, 200_000)
        self.assertLess(layouts.stat().st_size, 200_000)
        self.assertFalse((ROOT / "site/assets/shop/holiday-planner-pages.png").exists())
        holiday = card(self.shop, "The Holiday Planner Pages")
        url = "https://www.etsy.com/listing/4616108634/holiday-planner-printable-tip-ins-gift"
        self.assertEqual(holiday.count(url), 2)
        self.assertIn('class="shop-img sheet"', holiday)
        self.assertIn('width="2000" height="2000"', holiday)
        self.assertIn("holiday-planner-pages.webp", holiday.split("<details", 1)[0])
        self.assertNotIn("holiday-planner-layouts.webp", holiday.split("<details", 1)[0])
        self.assertIn("$6.99", holiday)
        self.assertIn("20% off launch sale Oct 31 to Nov 30", holiday)
        self.assertNotIn("launch20", holiday.lower())
        self.assertNotIn("$5.59", holiday)
        self.assertIn("View on Etsy", holiday)
        self.assertIn('class="inside-grid samples inserts"', holiday)
        self.assertIn("not a photograph of a printed copy", holiday.lower())
        self.assertIn("holiday-planner-layouts.webp", holiday)
        self.assertIn('width="2700" height="2025"', holiday)
        self.assertIn(">Larger view</a>", holiday)
        self.assertIn("<summary>See inside</summary>", holiday)
        self.assertIn("<summary>7 trackers &amp; planners</summary>", holiday)
        for name in ("Gift Tracker", "Holiday Budget", "Order &amp; Package Tracker",
                     "Card Mailing List", "Party &amp; Menu Planner",
                     "Baking &amp; Meal Prep Timeline", "December Countdown &amp; Bucket List"):
            self.assertIn(name, holiday)
        for size in ("85 × 175 mm", "95 × 138 mm", "138 × 198 mm"):
            self.assertIn(size, holiday)
        self.assertIn("actual size (100%)", holiday)
        self.assertIn("US Letter", holiday)
        self.assertIn("A4", holiday)
        self.assertIn("personal use", holiday.lower())
        self.assertIn("not affiliated with any planner brand", holiday.lower())
        self.assertNotIn("<details class=\"shop-inside\" open", holiday)
        self.assertNotIn("The Holiday Planner Pages", self.home)
        self.assertIn(
            "https://stationerydropwatch.com/shop/</loc><lastmod>2026-11-13T00:00:00+00:00</lastmod>",
            site.build_sitemap())


if __name__ == "__main__":
    unittest.main()
