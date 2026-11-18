"""Made-by-us cards on the Weeks and Hobonichi trackers.

Facts come from the existing /shop Etsy items. The holiday card is seasonal
and drops off after Dec 31, 2026. Neither card carries a price or sale line.
"""
import datetime as dt
import re
import unittest

import scripts.build_site as site


BANNED = ("$6.99", "20% off", "Oct 31", "Nov 30", "GSM", "fountain", "lay-flat",
          "lay flat", "layflat", "Traveler", "Traveller")
SALE_NOTE = site.ETSY_PRICE[1]


def card(doc, item_id):
    start = doc.find(f'id="made-by-us-{item_id}"')
    if start < 0:
        return ""
    start = doc.rfind("<aside", 0, start)
    end = doc.find("</aside>", start)
    return doc[start:end + len("</aside>")]


def after_stock(self, doc, item_id):
    html = card(doc, item_id)
    self.assertTrue(html, item_id)
    pos = doc.find(html)
    tracker = doc.find('id="tracker"')
    self.assertGreaterEqual(tracker, 0)
    self.assertGreater(pos, tracker, "card must not appear above the stock listings")
    last_stock = max(doc.rfind('id="rows"'), doc.rfind('<table class="stock">'),
                     doc.rfind("id=\"tracker\""))
    self.assertGreater(pos, last_stock)
    faq = doc.find('id="faq"')
    self.assertGreater(faq, pos, "card must sit below stock and above the FAQ")
    return html


def assert_plain_etsy(self, html, url):
    self.assertIn(url, html)
    self.assertEqual(html.count(url), 2)
    for href in re.findall(r'href="(https://www\.etsy\.com/[^"]*)"', html):
        self.assertEqual(href, url)
        self.assertNotIn("?", href)
        self.assertNotIn("tag=", href)


class MadeByUsCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oe = site.amazon_main(site.stock["products"])
        cls.weeks = next(g for g in site.GROUPS if g["slug"] == "hobonichi-weeks-2027")
        cls.mega = next(g for g in site.GROUPS if g["slug"] == "hobonichi-weeks-mega-2027")
        cls.a6 = next(g for g in site.GROUPS if g["slug"] == "hobonichi-techo-2027-original-a6")
        cls.weeks_doc = site.build_group(cls.weeks, cls.oe)[1]
        cls.hobo_doc = site.build_hobo_tracker()
        cls.lines = next(e for e in site.SHOP_ETSY if e.get("id") == "lines-grid")
        cls.holiday = next(e for e in site.SHOP_ETSY if e.get("id") == "holiday-planner")

    def test_weeks_card_sits_below_stock_with_shop_facts(self):
        html = after_stock(self, self.weeks_doc, "lines-grid")
        self.assertIn("Made by us", html)
        self.assertIn(self.lines["title"], html)
        self.assertIn("/assets/shop/lines-for-the-grid-page.webp", html)
        self.assertIn(self.lines["alt"], html)
        self.assertIn("Printable tip-in liners in 13 undated layouts.", html)
        self.assertIn("Finished cut size is 85 × 175 mm, drawn for a narrow weekly planner "
                      "whose book is about 94 × 188 mm, including the Hobonichi Weeks.", html)
        self.assertIn("A digital download for personal use.", html)
        self.assertIn("Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi.", html)
        self.assertIn("View on Etsy", html)
        assert_plain_etsy(self, html, self.lines["url"])
        for banned in BANNED:
            self.assertNotIn(banned, html)
        self.assertNotIn(SALE_NOTE, html)

    def test_holiday_card_sits_below_stock_with_shop_facts(self):
        html = after_stock(self, self.hobo_doc, "holiday-planner")
        self.assertIn("Made by us", html)
        self.assertIn(self.holiday["title"], html)
        self.assertIn("/assets/shop/holiday-planner-pages.webp", html)
        self.assertIn(self.holiday["alt"], html)
        self.assertIn("Printable holiday tip-ins in three sizes: Narrow Weekly 85 × 175 mm, "
                      "Pocket A6 95 × 138 mm, and Standard A5 138 × 198 mm.", html)
        self.assertIn("Ten undated pages.", html)
        self.assertIn("A digital download for personal use.", html)
        self.assertIn("Not a physical planner, and not affiliated with any planner brand.", html)
        self.assertIn("View on Etsy", html)
        assert_plain_etsy(self, html, self.holiday["url"])
        for banned in BANNED:
            self.assertNotIn(banned, html)
        self.assertNotIn(SALE_NOTE, html)
        # These pages are for A6, A5, and Weeks sizes we already make. No other formats.
        self.assertNotIn("8.5", html)
        self.assertNotIn("Letter", html)
        self.assertNotIn("TN", html)
        self.assertNotIn("Regular", html)

    def test_cards_stay_off_other_pages(self):
        mega = site.build_group(self.mega, self.oe)[1]
        a6 = site.build_group(self.a6, self.oe)[1]
        home = site.build_index()
        for name, doc in (("mega", mega), ("a6", a6), ("home", home)):
            self.assertNotIn("made-by-us", doc, name)
            self.assertNotIn(self.lines["url"], doc, name)
            self.assertNotIn(self.holiday["url"], doc, name)

    def test_holiday_card_renders_through_dec_31_and_stops_after(self):
        orig = site.site_today
        try:
            site.site_today = lambda: dt.date(2026, 12, 31)
            on = site.build_hobo_tracker()
            self.assertIn('id="made-by-us-holiday-planner"', on)
            self.assertIn(self.holiday["title"], on)
            site.site_today = lambda: dt.date(2027, 1, 1)
            off = site.build_hobo_tracker()
            self.assertNotIn('id="made-by-us-holiday-planner"', off)
            self.assertNotIn(self.holiday["title"], off)
            self.assertNotIn(self.holiday["url"], off)
        finally:
            site.site_today = orig
        # The Weeks card is not seasonal.
        self.assertIn('id="made-by-us-lines-grid"', self.weeks_doc)

    def test_card_phrases_come_from_shop_source(self):
        lines_src = " ".join((self.lines["sub"], self.lines["blurb"], *self.lines["details"]))
        holiday_src = " ".join((self.holiday["sub"], self.holiday["blurb"], *self.holiday["details"]))
        for phrase in ("Printable tip-in liners", "13 undated layouts",
                       "Finished cut size is 85 × 175 mm, drawn for a narrow weekly planner whose book is about 94 × 188 mm, including the Hobonichi Weeks",
                       "A digital download for personal use",
                       "Not a Hobonichi product, and not affiliated with or endorsed by Hobonichi"):
            self.assertIn(phrase, lines_src)
        for phrase in ("Printable holiday tip-ins",
                       "Narrow Weekly 85 × 175 mm, Pocket A6 95 × 138 mm, and Standard A5 138 × 198 mm",
                       "Ten undated pages", "A digital download for personal use",
                       "Not a physical planner, and not affiliated with any planner brand"):
            self.assertIn(phrase, holiday_src)
