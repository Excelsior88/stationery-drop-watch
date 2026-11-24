import html
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_site as site  # noqa: E402


class TermsPageTests(unittest.TestCase):
    def setUp(self):
        self.fname, self.doc = "terms/", site.build_terms()

    def text(self):
        return html.unescape(re.sub(r"<[^>]+>", "", self.doc))

    def test_terms_page_uses_the_privacy_template(self):
        self.assertIn('<p class="eyebrow">Terms · updated Nov 23, 2026</p>', self.doc)
        self.assertIn("<h1>Terms of Use</h1>", self.doc)
        self.assertIn('<article class="prose">', self.doc)
        self.assertIn('class="foot"', self.doc)

    def test_owner_decisions_are_in_the_text(self):
        t = " ".join(self.text().split())
        self.assertIn("We prohibit anyone from using the Service to engage in reselling activities.", t)
        self.assertIn("hold harmless Stationery Drop Watch LLC and its members and managers", t)
        self.assertIn("fifty US dollars (US$50)", t)
        self.assertIn("Wayne County, Michigan", t)
        self.assertIn("Eastern District of Michigan", t)
        self.assertIn("at least 13 years old", t)
        self.assertIn('Some shops are listed as "Link only"', t)
        self.assertIn("For shops and brands", t)
        self.assertIn("or to switch to link only, by emailing admin@stationerydropwatch.com. We will honor every such request as promptly as possible.", t)
        self.assertNotIn("Brands and shops can also ask", t)
        self.assertNotIn("bullet journal", t.lower())

    def test_terms_is_linked_from_footer_signup_privacy_faq_and_sitemap(self):
        foot = site.build_privacy()
        self.assertIn('<a href="/privacy/">Privacy</a><a href="/terms/">Terms</a>', foot)
        self.assertIn('Terms of Use</a>', foot.split("<footer")[0])
        home = site.build_index()
        self.assertIn('By signing up, you agree to our <a href="/terms/">Terms</a> (personal use only, no reselling or bots) and <a href="/privacy/">Privacy notice</a>.</p>', home)
        self.assertIn('href="/terms/#prohibited-uses"', home)
        self.assertIn("Can I use alerts for reselling?", home)
        self.assertIn(site.url_for("terms/"), site.build_sitemap())


if __name__ == "__main__":
    unittest.main()
