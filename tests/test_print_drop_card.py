"""The Print Drop card on the home page and /shop.

Copy comes from https://theprintdrop.com/ and its beta studio (read Nov 26, 2026).
The card links only to theprintdrop.com, with no tracking or affiliate params,
and carries no price, Pro or monthly-drop claims.
"""
import re
import unittest

import scripts.build_site as site

URL = "https://theprintdrop.com/"


def card(doc):
    start = doc.find('<aside class="card print-drop-card"')
    if start < 0:
        return ""
    end = doc.find("</aside>", start)
    return doc[start:end + len("</aside>")]


class PrintDropCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = site.build_index()
        cls.shop = site.build_shop()[1]

    def test_card_on_home_and_shop_once(self):
        for name, doc in (("home", self.home), ("shop", self.shop)):
            self.assertEqual(doc.count('id="the-print-drop"'), 1, name)
            html = card(doc)
            self.assertIn("The Print Drop", html)
            self.assertIn("Try the free beta", html)
            self.assertIn("open in beta", html)

    def test_links_are_plain_theprintdrop(self):
        html = card(self.home)
        hrefs = re.findall(r'href="([^"]*)"', html)
        self.assertEqual(hrefs, [URL, URL])
        self.assertIn('rel="noopener"', html)

    def test_no_prices_pro_or_monthly_claims(self):
        html = card(self.home)
        for banned in ("$", "Pro", "month", "membership", "subscri", "?utm", "tag="):
            self.assertNotIn(banned, html)

    def test_home_card_sits_below_guides_above_faq(self):
        pos = self.home.find('id="the-print-drop"')
        self.assertGreater(pos, self.home.find('id="guides"'))
        self.assertLess(pos, self.home.find('id="good-to-know"'))

    def test_shop_card_sits_above_product_sections(self):
        pos = self.shop.find('id="the-print-drop"')
        self.assertLess(pos, self.shop.find("Printed planners and journals on Amazon"))

    def test_shop_card_is_first_and_signup_is_last(self):
        """Owner, Nov 27: the beta invite is the first thing on /shop; the email signup sits at the bottom."""
        doc = self.shop
        card, lede, signup = doc.find('id="the-print-drop"'), doc.find('class="lede"'), doc.find('id="alerts"')
        self.assertTrue(0 < lede < card < signup)
        self.assertNotIn("<h2", doc[lede:card])
        self.assertLess(doc.find("See all our Teachers Pay Teachers resources"), signup)
        self.assertLess(signup, doc.find("</article>", signup))
        self.assertEqual(doc.count('class="signup-strip'), 1)

    def test_icon_is_local(self):
        self.assertTrue((site.SITE / site.PRINT_DROP_ICON.lstrip("/")).is_file())


if __name__ == "__main__":
    unittest.main()
