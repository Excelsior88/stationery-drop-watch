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
        self.assertEqual(visible.count("Paperback"), 1)
        self.assertNotIn('<ul class="small">', visible)
        self.assertIn("<summary>Details</summary>", paper)
        self.assertEqual(paper.count("168 pages"), 1)
        self.assertEqual(paper.count("8.5 x 11"), 1)
        self.assertEqual(paper.count("Monday start"), 1)
        self.assertEqual(paper.count("January to December 2027"), 1)
        self.assertIn("168 pages", hidden)
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

    def test_paperback_uses_the_plain_amazon_link_and_its_list_price(self):
        paper = card(self.shop, "Level Up! My 2027 Planner")
        self.assertIn('href="https://www.amazon.com/dp/B0HQW8273V"', paper)
        self.assertIn("data-own-product", paper)
        self.assertNotIn("tag=", paper)
        self.assertNotIn("a.co/d/02grz96c", paper)
        self.assertNotIn("See price on Amazon", paper)
        self.assertIn("<strong>$19.99</strong> <span class=\"muted small\">List price, check current price on Amazon</span>", paper)
        self.assertNotIn("In Stock", paper)
        self.assertNotIn("B0nem0ther", paper)
        self.assertNotIn("Excelsior", paper)
        self.assertIn("https://www.etsy.com/listing/4610143237", card(self.shop, "Level Up! My 2027 Kids Planner"))
        self.assertIn("https://www.etsy.com/listing/4611293526/soft-days-narrow-planner-inserts",
                      card(self.shop, "Soft Days Narrow Planner Inserts"))

    def test_a5_blush_planner_replaces_the_featured_hardcover_card(self):
        blush = card(self.shop, "2027 Planner, Blush")
        self.assertIn('href="https://www.amazon.com/dp/B0HRTLMZ1M"', blush)
        self.assertEqual(blush.count("https://www.amazon.com/dp/B0HRTLMZ1M"), 2)
        self.assertIn("data-own-product", blush)
        self.assertNotIn("tag=", blush)
        self.assertIn("Paperback", blush)
        self.assertNotIn("Hardcover · on Amazon", blush)
        self.assertIn("<strong>$14.99</strong>", blush)
        self.assertIn("List price, check current price on Amazon", blush)
        self.assertNotIn("See price on Amazon", blush)
        self.assertNotIn("$19.99", blush)
        self.assertNotIn("Currently unavailable", blush)
        self.assertNotIn("In Stock", blush)
        self.assertIn("Monday start", blush)
        self.assertIn("5.83 x 8.27 in (A5) paperback, 174 pages, color interior", blush)
        self.assertIn("Soft blush, sage and cream design", blush)
        self.assertIn("Dated Jan 1 to Dec 31, 2027", blush)
        self.assertIn("/assets/books/B0HRTLMZ1M.jpg", blush.split("<details", 1)[0])
        self.assertNotIn("B0HRTLMZ1M.jpg", blush.split("See inside", 1)[-1])
        self.assertIn("/assets/shop/inside/B0HRTLMZ1M-january-month-pages.jpg", blush)
        self.assertIn("/assets/shop/inside/B0HRTLMZ1M-weekly-spread-dec28-2026-jan3-2027.jpg", blush)
        self.assertIn("January calendar and Goals &amp; Priorities pages", blush)
        self.assertIn("Weekly spread, Dec 28, 2026 to Jan 3, 2027", blush)
        # Kiln did not confirm the January pages face each other in print.
        january = blush[blush.find("january-month-pages"):blush.find("weekly-spread-dec28")]
        self.assertNotIn("spread", january.lower())
        self.assertIn("Also comes in ", blush)
        self.assertIn(">8.5x11 hardcover, Sunday start</a>", blush)
        self.assertIn('href="https://www.amazon.com/dp/B0HPBDNS7F"', blush)
        self.assertIn("data-own-product", blush[blush.find("Also comes in"):])
        # The 8.5x11 hardcover is no longer a featured Amazon card, only the note link.
        amazon = self.shop.split("<h2>Printable PDFs on Etsy</h2>", 1)[0]
        self.assertNotIn("/assets/books/B0HPBDNS7F.jpg", amazon)
        self.assertNotIn("/assets/shop/inside/B0HPBDNS7F-", amazon)
        self.assertEqual(amazon.count("https://www.amazon.com/dp/B0HPBDNS7F"), 1)
        self.assertIn('class="inside-grid spreads"', blush)

    def test_a5_mens_planner_replaces_the_featured_paperback_card(self):
        mens = card(self.shop, "2027 Planner for Men")
        self.assertIn('href="https://www.amazon.com/dp/B0HRTTCH4D"', mens)
        self.assertEqual(mens.count("https://www.amazon.com/dp/B0HRTTCH4D"), 2)
        self.assertIn("data-own-product", mens)
        self.assertNotIn("tag=", mens)
        self.assertIn("Paperback", mens)
        self.assertIn("<strong>$14.99</strong>", mens)
        self.assertIn("List price, check current price on Amazon", mens)
        self.assertNotIn("See price on Amazon", mens)
        self.assertNotIn("Currently unavailable", mens)
        self.assertNotIn("In Stock", mens)
        self.assertIn("Monday start", mens)
        self.assertIn("5.83 x 8.27 in (A5) paperback, 174 pages, color interior", mens)
        self.assertIn("Charcoal, navy, forest green and rust design", mens)
        self.assertIn("Dated Jan 1 to Dec 31, 2027", mens)
        self.assertIn("/assets/books/B0HRTTCH4D.jpg", mens.split("<details", 1)[0])
        self.assertNotIn("B0HRTTCH4D.jpg", mens.split("See inside", 1)[-1])
        self.assertIn("/assets/shop/inside/B0HRTTCH4D-january-month-pages.jpg", mens)
        self.assertIn("/assets/shop/inside/B0HRTTCH4D-weekly-spread-dec28-2026-jan3-2027.jpg", mens)
        self.assertIn("January calendar and Goals &amp; Priorities pages", mens)
        self.assertIn("Weekly spread, Dec 28, 2026 to Jan 3, 2027", mens)
        # Caption does not call the January pages a spread.
        january = mens[mens.find("january-month-pages"):mens.find("weekly-spread-dec28")]
        self.assertNotIn("spread", january.lower())
        self.assertIn("Also comes in ", mens)
        self.assertIn(">8.5x11 paperback, Sunday start</a>", mens)
        self.assertIn('href="https://www.amazon.com/dp/B0HP9PXSR1"', mens)
        self.assertIn("data-own-product", mens[mens.find("Also comes in"):])
        # The 8.5x11 paperback is no longer a featured Amazon card, only the note link.
        amazon = self.shop.split("<h2>Printable PDFs on Etsy</h2>", 1)[0]
        self.assertNotIn("/assets/books/B0HP9PXSR1.jpg", amazon)
        self.assertNotIn("/assets/shop/inside/B0HP9PXSR1-", amazon)
        self.assertEqual(amazon.count("https://www.amazon.com/dp/B0HP9PXSR1"), 1)
        self.assertIn('class="inside-grid spreads"', mens)

    def test_hardcover_gift_pick_on_dotgrid_is_unchanged(self):
        # /shop no longer features the 8.5x11 hardcover; the existing dot-grid gift pick stays.
        self.assertNotIn("B0HRTLMZ1M", self.home)
        pick = next(b for b in site.picks["books"] if b["id"] == "B0HPBDNS7F")
        self.assertEqual(pick.get("pages"), ["dotgrid"])
        self.assertEqual(pick["format"], "Hardcover")
        self.assertIn("8.5 x 11 in hardcover, 172 pages", pick["details"])
        self.assertFalse(pick.get("hidden"))

    def test_mens_paperback_gift_pick_on_home_is_unchanged(self):
        # /shop no longer features the 8.5x11 men's paperback; the existing homepage gift pick stays.
        self.assertNotIn("B0HRTTCH4D", self.home)
        pick = next(b for b in site.picks["books"] if b["id"] == "B0HP9PXSR1")
        self.assertIsNone(pick.get("pages"))
        self.assertEqual(pick["format"], "Paperback")
        self.assertIn("8.5 x 11 in paperback", pick["details"])
        self.assertFalse(pick.get("hidden"))

    def test_existing_previews_are_unchanged(self):
        expected = [
            "/assets/shop/inside/B0HRTLMZ1M-january-month-pages.jpg",
            "/assets/shop/inside/B0HRTLMZ1M-weekly-spread-dec28-2026-jan3-2027.jpg",
            "/assets/shop/inside/B0HQ5TLDK3-habit-and-mood-tracker-spread-p6-7.jpg",
            "/assets/shop/inside/B0HQ5TLDK3-weekly-checkin-spread-p8-9.jpg",
            "/assets/shop/inside/B0HQ5X3C7D-genre-tracker-books-read-log-spread-p12-13.jpg",
            "/assets/shop/inside/B0HQ5X3C7D-book-review-spread-p24-25.jpg",
            "/assets/shop/inside/B0HRTTCH4D-january-month-pages.jpg",
            "/assets/shop/inside/B0HRTTCH4D-weekly-spread-dec28-2026-jan3-2027.jpg",
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
        self.assertNotIn("As an Amazon Associate", self.home)
        self.assertNotIn("affiliate link", self.home.lower())
        self.assertIn("Statuses come straight from each store's public product data", self.home)
        self.assertIn("Level Up! My 2027 Planner", self.shop)
        self.assertIn("Paperback", card(self.shop, "Level Up! My 2027 Planner"))
        self.assertIn("Front cover of the Level Up! 2027 printable planner", self.shop)
        self.assertIn("20% off launch sale Oct 31 to Nov 30", card(self.shop, "Level Up! My 2027 Kids Planner"))
        self.assertEqual(site.shop_lastmod(), "2026-11-18")
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
            "https://stationerydropwatch.com/shop/</loc><lastmod>2026-11-18T00:00:00+00:00</lastmod>",
            site.build_sitemap())

    def test_happy_mail_and_seasonal_dashboards_follow_the_insert_card(self):
        from PIL import Image
        files = {
            ROOT / "site/assets/shop/happy-mail-washi-club.webp": (2000, 2000),
            ROOT / "site/assets/shop/inside/happy-mail-washi-club-included.webp": (2000, 2000),
            ROOT / "site/assets/shop/seasonal-reset-dashboards.webp": (2000, 2000),
            ROOT / "site/assets/shop/inside/seasonal-reset-dashboards-included.webp": (2000, 2000),
        }
        for path, size in files.items():
            with Image.open(path) as im:
                self.assertEqual(im.size, size)
            self.assertLess(path.stat().st_size, 200_000)
            self.assertFalse(path.with_suffix(".png").exists())
            self.assertFalse(path.with_suffix(".jpg").exists())

        happy = card(self.shop, "Happy Mail &amp; Washi Club")
        happy_url = "https://www.etsy.com/listing/4620269140/happy-mail-washi-club-printable-tip-ins"
        self.assertEqual(happy.count(happy_url), 2)
        self.assertIn('class="shop-img sheet"', happy)
        self.assertIn('width="2000" height="2000"', happy)
        self.assertIn("happy-mail-washi-club.webp", happy.split("<details", 1)[0])
        self.assertNotIn("happy-mail-washi-club-included.webp", happy.split("<details", 1)[0])
        self.assertIn("$5.99", happy)
        self.assertNotIn("$4.79", happy)
        self.assertIn("20% off launch sale Oct 31 to Nov 30", happy)
        self.assertNotIn("launch20", happy.lower())
        self.assertIn("View on Etsy", happy)
        self.assertIn('class="inside-grid samples inserts"', happy)
        self.assertIn("not a photograph of a printed copy", happy.lower())
        self.assertIn("happy-mail-washi-club-included.webp", happy)
        self.assertIn(">Larger view</a>", happy)
        self.assertIn("<summary>See inside</summary>", happy)
        self.assertIn("<summary>4 tip-ins</summary>", happy)
        for name in ("Washi Swatch Club", "Happy Mail Tracker", "Snapshot Memories", "Color Palette Lab"):
            self.assertIn(name, happy)
        self.assertIn("85 × 175 mm", happy)
        self.assertIn("94 × 188 mm", happy)
        self.assertIn("actual size (100%)", happy)
        self.assertIn("50 mm", happy)
        self.assertIn("US Letter", happy)
        self.assertIn("A4", happy)
        self.assertIn("personal use", happy.lower())
        self.assertIn("Not a Hobonichi product", happy)
        self.assertIn("not affiliated", happy.lower())
        self.assertNotIn("Tested in a Hobonichi Weeks Mega", happy)
        self.assertNotIn("weeks size", happy.lower())
        self.assertNotIn("guaranteed to fit", happy.lower())
        self.assertNotIn("<details class=\"shop-inside\" open", happy)
        self.assertNotIn("Happy Mail &amp; Washi Club", self.home)
        self.assertNotIn("Happy Mail & Washi Club", self.home)

        seasonal = card(self.shop, "Seasonal Reset Dashboards &amp; Slip Pocket")
        seasonal_url = "https://www.etsy.com/listing/4620269960/seasonal-reset-dashboard-printable"
        self.assertEqual(seasonal.count(seasonal_url), 2)
        self.assertIn('class="shop-img sheet"', seasonal)
        self.assertIn('width="2000" height="2000"', seasonal)
        self.assertIn("seasonal-reset-dashboards.webp", seasonal.split("<details", 1)[0])
        self.assertNotIn("seasonal-reset-dashboards-included.webp", seasonal.split("<details", 1)[0])
        self.assertIn("$6.99", seasonal)
        self.assertNotIn("$5.59", seasonal)
        self.assertIn("20% off launch sale Oct 31 to Nov 30", seasonal)
        self.assertNotIn("launch20", seasonal.lower())
        self.assertIn("View on Etsy", seasonal)
        self.assertIn('class="inside-grid samples inserts"', seasonal)
        self.assertIn("not a photograph of a printed copy", seasonal.lower())
        self.assertIn("seasonal-reset-dashboards-included.webp", seasonal)
        self.assertIn(">Larger view</a>", seasonal)
        self.assertIn("<summary>See inside</summary>", seasonal)
        self.assertIn("<summary>4 dashboards &amp; slip pocket</summary>", seasonal)
        for name in ("Spring", "Summer", "Autumn", "Winter", "Slip pocket"):
            self.assertIn(name, seasonal)
        self.assertIn("85 × 175 mm", seasonal)
        self.assertIn("84 × 138 mm", seasonal)
        self.assertIn("94 × 188 mm", seasonal)
        self.assertIn("actual size (100%)", seasonal)
        self.assertIn("50 mm", seasonal)
        self.assertIn("no-fill", seasonal)
        self.assertIn("vellum", seasonal.lower())
        self.assertIn("US Letter", seasonal)
        self.assertIn("A4", seasonal)
        self.assertIn("personal use", seasonal.lower())
        self.assertIn("Not a Hobonichi product", seasonal)
        self.assertIn("not affiliated", seasonal.lower())
        self.assertNotIn("Tested in a Hobonichi Weeks Mega", seasonal)
        self.assertNotIn("weeks size", seasonal.lower())
        self.assertNotIn("guaranteed to fit", seasonal.lower())
        self.assertNotIn("<details class=\"shop-inside\" open", seasonal)
        self.assertNotIn("Seasonal Reset Dashboards", self.home)

        etsy_at = self.shop.find("<h2>Printable PDFs on Etsy</h2>")
        tpt_at = self.shop.find('<h2 id="classroom-printables">Classroom printables on Teachers Pay Teachers</h2>')
        etsy_section = self.shop[etsy_at:tpt_at]
        self.assertLess(etsy_section.find("The Holiday Planner Pages"), etsy_section.find("Happy Mail &amp; Washi Club"))
        self.assertLess(etsy_section.find("Happy Mail &amp; Washi Club"), etsy_section.find("Seasonal Reset Dashboards &amp; Slip Pocket"))

    def test_etsy_and_amazon_detail_lists_are_behind_a_collapsed_details_toggle(self):
        etsy_at = self.shop.find("<h2>Printable PDFs on Etsy</h2>")
        tpt_at = self.shop.find('<h2 id="classroom-printables">Classroom printables on Teachers Pay Teachers</h2>')
        etsy_section = self.shop[etsy_at:tpt_at]
        amazon_section = self.shop.split("<h2>Printable PDFs on Etsy</h2>", 1)[0]
        tpt_section = self.shop[tpt_at:]
        etsy_titles = [
            "2027 Printable Planner, Blush",
            "2027 Printable Planner for Men",
            "Level Up! My 2027 Kids Planner",
            "Soft Days Narrow Planner Inserts",
            "Lines for the Grid Page",
            "The Holiday Planner Pages",
            "Happy Mail &amp; Washi Club",
            "Seasonal Reset Dashboards &amp; Slip Pocket",
        ]
        amazon_titles = [
            "2027 Planner, Blush",
            "Habit &amp; Mood Tracker Journal",
            "Reading Journal",
            "2027 Planner for Men",
            "Level Up! My 2027 Planner",
        ]
        def assert_collapsed_details(html, section, title, marketplace, button):
            self.assertIn(html, section)
            visible, rest = html.split("<details", 1)
            self.assertIn(f"<h3>{title}</h3>", visible)
            self.assertIn(marketplace, visible)
            self.assertIn('<p class="shop-price">', visible)
            self.assertIn("<p>", visible)  # blurb
            self.assertNotIn('<ul class="small">', visible)
            self.assertIn('class="shop-inside"><summary>Details</summary><ul class="small">', html)
            self.assertIn(button, html)
            self.assertGreater(html.rfind(button), html.find("<summary>Details</summary>"))
            self.assertTrue(html.rstrip().endswith(f"{button}</a></div></li>"))
            self.assertNotIn('<details class="shop-inside" open', html)
            if "<summary>See inside</summary>" in html:
                self.assertIn("<summary>See inside</summary>", rest)
                self.assertLess(html.find("<summary>Details</summary>"), html.find("<summary>See inside</summary>"))
            return visible

        for title in etsy_titles:
            html = card(etsy_section, title)
            visible = assert_collapsed_details(html, etsy_section, title, "instant download from Etsy", "View on Etsy")
            self.assertIn("20% off launch sale Oct 31 to Nov 30", visible)
        for title in amazon_titles:
            html = card(amazon_section, title)
            visible = assert_collapsed_details(html, amazon_section, title, "on Amazon", "View on Amazon")
            self.assertNotIn("tag=", html)
            self.assertIn("data-own-product", html)
        blush = card(amazon_section, "2027 Planner, Blush")
        visible, _ = blush.split("<details", 1)
        self.assertIn("Also comes in ", visible)
        self.assertIn(">8.5x11 hardcover, Sunday start</a>", visible)
        self.assertIn('href="https://www.amazon.com/dp/B0HPBDNS7F"', visible)
        self.assertIn("5.83 x 8.27 in (A5) paperback, 174 pages, color interior", blush)
        self.assertNotIn("5.83 x 8.27 in (A5) paperback, 174 pages, color interior", visible)
        mens = card(amazon_section, "2027 Planner for Men")
        visible, _ = mens.split("<details", 1)
        self.assertIn("Also comes in ", visible)
        self.assertIn(">8.5x11 paperback, Sunday start</a>", visible)
        self.assertNotIn("<summary>Details</summary>", tpt_section)

    def test_tpt_section_is_two_collection_cards(self):


        from PIL import Image
        store = "https://www.teacherspayteachers.com/store/stationery-drop-watch"
        etsy_at = self.shop.find("<h2>Printable PDFs on Etsy</h2>")
        tpt_at = self.shop.find('<h2 id="classroom-printables">Classroom printables on Teachers Pay Teachers</h2>')
        self.assertGreater(etsy_at, 0)
        self.assertGreater(tpt_at, etsy_at)
        etsy_section = self.shop[etsy_at:tpt_at]
        group = self.shop[tpt_at:]
        self.assertIn("Level Up! My 2027 Kids Planner", etsy_section)
        self.assertLess(etsy_section.find("2027 Printable Planner for Men"), etsy_section.find("Level Up! My 2027 Kids Planner"))
        self.assertLess(etsy_section.find("Level Up! My 2027 Kids Planner"), etsy_section.find("Soft Days Narrow Planner Inserts"))
        self.assertNotIn("teacherspayteachers.com", etsy_section)
        etsy = card(etsy_section, "Level Up! My 2027 Kids Planner")
        self.assertEqual(etsy.count("https://www.etsy.com/listing/4610143237"), 2)
        self.assertIn("Personal-use edition on Etsy", etsy)
        self.assertIn("$6.99", etsy)
        self.assertNotIn("<h3>Level Up! 2027 Student Planner</h3>", group)
        self.assertNotIn("18365866", group)
        self.assertNotIn("18381628", group)
        self.assertNotIn("18381644", group)
        self.assertNotIn("bundle", group.lower())
        self.assertNotIn("bestseller", group.lower())
        self.assertNotIn("popular", group.lower())
        cards = group[group.find("<ul"):group.find("</ul>")]
        self.assertNotIn("$", cards)
        level = card(group, "Level Up!")
        pastel = card(group, "Cute Pastel")
        self.assertEqual(level.count(store), 1)
        self.assertEqual(pastel.count(store), 1)
        self.assertEqual(level.count("See the collection on TpT"), 1)
        self.assertEqual(pastel.count("See the collection on TpT"), 1)
        self.assertNotIn("Part of Level Up!", level)
        self.assertIn("Pixel-art, video-game classroom printables for grades 2-5.", level)
        self.assertIn("Soft pastel picture supports for PreK-2 and special ed.", pastel)
        self.assertIn('id="level-up-collection"', level)
        self.assertIn('class="collection-grid"', level)
        self.assertIn('class="collection-grid"', pastel)
        self.assertNotIn("collection-thumbs", group)
        self.assertNotIn("level-up-collection-cover", group)
        self.assertNotIn("shop-img", level)
        css = (ROOT / "site/assets/style.css").read_text()
        self.assertIn('font-family:"Liberation Sans"', css)
        self.assertIn("#ffcb2e", css)
        self.assertIn("#22223a", css)
        self.assertIn("#fff5f8", css)
        for url in (
            "https://www.teacherspayteachers.com/Product/Level-Up-2027-Student-Planner-Video-Game-Theme-Printable-Planner-Grades-2-5-18365192",
            "https://www.teacherspayteachers.com/Product/Level-Up-Goal-Setting-Quest-Pack-Video-Game-Theme-Goal-Habit-Trackers-18365256",
            "https://www.teacherspayteachers.com/Product/Level-Up-End-of-Year-Review-Packet-Video-Game-Theme-Summer-Review-Puzzles-18365295",
            "https://www.teacherspayteachers.com/Product/Level-Up-Classroom-Quest-Kit-Video-Game-Reading-Log-XP-Chart-Brag-Tags-18365332",
        ):
            self.assertEqual(level.count(url), 1)
            self.assertNotIn("?", url)
        for url in (
            "https://www.teacherspayteachers.com/Product/Cute-Pastel-Visual-Schedule-Cards-43-Kawaii-Daily-Routine-Cards-PreK2-SpEd-18381500",
            "https://www.teacherspayteachers.com/Product/Cute-Pastel-First-Then-Now-Next-Boards-Kawaii-Visual-Supports-Reward-Cards-18381421",
            "https://www.teacherspayteachers.com/Product/Cute-Pastel-Classroom-Labels-Editable-Kawaii-Supply-Bin-Labels-with-Pictures-18381372",
            "https://www.teacherspayteachers.com/Product/Cute-Pastel-Calm-Down-Corner-Kit-Kawaii-Breathing-Cards-Calm-Choices-SEL-18381516",
        ):
            self.assertEqual(pastel.count(url), 1)
        self.assertIn("Printable classroom resources from our Teachers Pay Teachers store.", group)
        self.assertIn('width="600" height="600"', level)
        self.assertIn("300w", level)
        self.assertIn("600w", level)
        self.assertEqual(level.count("<img "), 4)
        self.assertEqual(pastel.count("<img "), 4)
        for stem in (
            "level-up-student-planner", "level-up-goal-quest", "level-up-end-of-year", "level-up-classroom-kit",
            "cute-pastel-visual-schedule", "cute-pastel-first-then", "cute-pastel-classroom-labels", "cute-pastel-calm-down",
        ):
            for size in (600, 300):
                path = ROOT / f"site/assets/shop/tiles/{stem}-{size}.webp"
                with Image.open(path) as im:
                    self.assertEqual(im.size, (size, size), path.name)
        self.assertFalse((ROOT / "site/assets/shop/level-up-collection-cover.webp").exists())
        self.assertFalse((ROOT / "site/assets/shop/cute-pastel-collection-cover.webp").exists())
        self.assertNotIn("teacherspayteachers.com", self.home)
        self.assertNotIn("Level Up! 2027 Student Planner", self.home)
        self.assertNotIn("<script src=\"https://", self.shop)
        self.assertEqual(self.shop.count("application/ld+json"), 1)


if __name__ == "__main__":
    unittest.main()
