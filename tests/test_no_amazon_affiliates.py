"""Affiliate links were removed: only the owner's own /shop books may link to Amazon."""
import re
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site

OWN_ASINS = {
    "B0HP9PXSR1", "B0HPBDNS7F", "B0HQ5TLDK3", "B0HQ5X3C7D",
    "B0HQW8273V", "B0HRTLMZ1M", "B0HRTTCH4D",
}
AMAZON_HREF = re.compile(r'href="(https?://(?:www\.)?(?:amazon\.com|amzn\.to|a\.co)/[^"]*)"', re.I)

class NoAmazonAffiliateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = [
            ("index", site.build_index()),
            ("hobo", site.build_hobo_tracker()),
            ("about", site.build_about()),
            ("privacy", site.build_privacy()),
        ]
        cls.pages.extend(site.build_group(g) for g in site.GROUPS)
        cls.pages.extend(site.build_design(d) for d in site.DESIGNS)
        for build in (site.build_where_to_buy, site.build_vs, site.build_january_april,
                      site.build_dotgrid_guide, site.build_guides_index,
                      site.build_shop, site.build_follow, site.build_contact, site.build_sold_out):
            cls.pages.append(build())

    def test_no_associates_tag_or_disclosure(self):
        banned = (
            "excelsior88-20",
            "As an Amazon Associate",
            "affiliate link",
            "Affiliate links",
            "Amazon and affiliate",
            "btn-amz",
            "rel=\"sponsored",
        )
        for name, doc in self.pages:
            low = doc.lower()
            for needle in banned:
                self.assertNotIn(needle.lower(), low, f"{name} still has {needle!r}")

    def test_only_own_shop_books_link_to_amazon(self):
        shop = dict(self.pages)["shop/"]
        shop_hrefs = AMAZON_HREF.findall(shop)
        self.assertTrue(shop_hrefs, "shop page should still link to the owner's Amazon books")
        for href in shop_hrefs:
            self.assertNotIn("tag=", href)
            self.assertTrue(any(a in href for a in OWN_ASINS), href)
        for name, doc in self.pages:
            hrefs = AMAZON_HREF.findall(doc)
            if name == "shop/":
                continue
            # Other pages may mention Amazon in prose or link to our books from house ads.
            for href in hrefs:
                self.assertNotIn("tag=", href, f"{name}: {href}")
                self.assertTrue(any(a in href for a in OWN_ASINS), f"{name} has a non-shop Amazon link: {href}")

if __name__ == "__main__":
    unittest.main()
