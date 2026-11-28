"""TpT catalog on /shop/teachers-pay-teachers/ matches the live store as of Nov 27, 2026."""
import json
from pathlib import Path
import re
import unittest

import scripts.build_site as site


def html_of(built):
    return built[1] if isinstance(built, tuple) else built


class TptStoreUpdateNov27(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = html_of(site.build_tpt_page())
        cls.shop = html_of(site.build_shop())

    def test_catalog_has_nineteen_live_resources(self):
        self.assertEqual(len(site.TPT_PRODUCTS), 19)
        self.assertIn("All 19 printable classroom resources", self.doc)
        self.assertIn("All 19 classroom printables", self.doc)
        self.assertNotIn("All 15 printable classroom resources", self.doc)
        self.assertNotIn("All 15 classroom printables", self.doc)

    def test_structured_data_lists_all_nineteen(self):
        items = []
        for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', self.doc):
            data = json.loads(raw)
            if data.get("@type") == "ItemList":
                items = data
        self.assertEqual(items.get("numberOfItems"), 19)
        names = [el["item"]["name"] for el in items["itemListElement"]]
        self.assertEqual(len(names), 19)
        self.assertIn("Level Up! Bundle | Video Game Planner, Goals, Review, Behavior & Reading Log", names)
        self.assertIn("Cute Pastel Classroom Jobs Chart | Editable Job Cards with Pictures + Name Clips", names)
        self.assertIn("Cute Pastel Morning Meeting Kit | Calendar, Weather, Feelings + Greeting Cards", names)
        self.assertIn("Level Up! Behavior & Reward System | Video Game XP Chart, Badges & Coupons", names)
        self.assertIn("Level Up! XP Reading Log | Video Game Reading Challenge, Quest Map & Bookmarks", names)

    def test_complete_pastel_bundle_is_eight_sets_and_191_pages(self):
        self.assertIn("191 pages across 8 resources", self.doc)
        self.assertIn("Eight matching Cute Pastel sets", self.doc)
        self.assertIn("Classroom Jobs Chart and Morning Meeting Kit", self.doc)
        self.assertNotIn("148 pages across 6 resources", self.doc)
        self.assertNotIn("Six matching Cute Pastel sets", self.doc)

    def test_level_up_bundle_includes_behavior_and_reading_log(self):
        self.assertIn("Level Up! Bundle | Video Game Planner, Goals, Review, Behavior & Reading Log", self.doc)
        self.assertIn("Behavior &amp; Reward System and XP Reading Log", self.doc)
        self.assertNotIn("Level Up! Bundle | Video Game Planner, Goals, Review &amp; Classroom Kit", self.doc)

    def test_level_up_titles_start_with_bang(self):
        for title in (
            "Level Up! 2027 Student Planner | Video Game Theme Printable Planner Grades 2-5",
            "Level Up! Goal Setting Quest Pack | Video Game Theme Goal &amp; Habit Trackers",
            "Level Up! End of Year Review Packet | Video Game Theme Summer Review Puzzles",
            "Level Up! Classroom Quest Kit | Video Game Reading Log, XP Chart &amp; Brag Tags",
        ):
            self.assertIn(f"<h3>{title}</h3>", self.doc)
        self.assertNotIn("<h3>Level Up 2027 Student Planner", self.doc)
        self.assertNotIn("<h3>Level Up Classroom Quest Kit", self.doc)
        self.assertNotIn("<h3>Level Up End of Year Review Packet", self.doc)
        self.assertNotIn("<h3>Level Up Goal Setting Quest Pack", self.doc)

    def test_new_listings_link_to_live_tpt_pages(self):
        for url in (
            "https://www.teacherspayteachers.com/Product/Cute-Pastel-Classroom-Jobs-Chart-Editable-Job-Cards-with-Pictures-Name-Clips-18536234",
            "https://www.teacherspayteachers.com/Product/Cute-Pastel-Morning-Meeting-Kit-Calendar-Weather-Feelings-Greeting-Cards-18536267",
            "https://www.teacherspayteachers.com/Product/Level-Up-Behavior-Reward-System-Video-Game-XP-Chart-Badges-Coupons-18536327",
            "https://www.teacherspayteachers.com/Product/Level-Up-XP-Reading-Log-Video-Game-Reading-Challenge-Quest-Map-Bookmarks-18536356",
        ):
            self.assertIn(url, self.doc)
            self.assertNotIn("?", url)
            self.assertNotIn(url, self.shop)

    def test_catalog_still_omits_prices(self):
        # Prices belong on TpT, not on this page.
        self.assertNotRegex(self.doc, r"\$\d")
        self.assertIn("For current price and availability, check the Teachers Pay Teachers page.", self.doc)

    def test_shop_page_still_uses_two_collection_cards(self):
        self.assertIn('id="level-up-collection"', self.shop)
        self.assertIn('id="cute-pastel-collection"', self.shop)
        self.assertIn("See all our Teachers Pay Teachers resources", self.shop)
        self.assertIn("classroom jobs, morning meeting, feelings and calm-down tools", self.doc)


    def test_catalog_cover_srcset_urls_are_root_relative(self):
        # A leading slash on only the first srcset URL left the 600w candidate page-relative,
        # so retina phones requested /shop/teachers-pay-teachers/assets/tpt/... and got a 404.
        srcsets = re.findall(r'srcset="([^"]*assets/tpt/[^"]*)"', self.doc)
        self.assertEqual(len(srcsets), 19)
        for val in srcsets:
            for part in val.split(","):
                url = part.strip().split()[0]
                self.assertTrue(url.startswith("/assets/tpt/"), val)

    def test_every_catalog_cover_has_300_and_600_webp(self):
        from PIL import Image
        root = Path(__file__).resolve().parent.parent
        slugs = [p["slug"] for p in site.TPT_PRODUCTS]
        self.assertEqual(len(slugs), 19)
        for slug in slugs:
            for size in (300, 600):
                path = root / f"site/assets/tpt/{slug}-{size}.webp"
                self.assertTrue(path.is_file(), path.name)
                with Image.open(path) as im:
                    self.assertEqual(im.size, (size, size), path.name)
                    self.assertEqual(im.format, "WEBP", path.name)
