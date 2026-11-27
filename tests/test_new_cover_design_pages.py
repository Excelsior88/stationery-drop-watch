"""One design page for each of the 24 covers added with the Avec PR (#86): A6 10, A5 11, Weeks covers 3."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

COV = "hobonichi-techo-2027-covers"
WK = "hobonichi-weeks-2027"
NEW = {
    "cover-a6-akiko-miyakoshi-airport": (COV, "akiko-miyakoshi-airport-a6"),
    "cover-a6-va-strawberry-thief": (COV, "va-strawberry-thief-a6"),
    "cover-a6-puppet-sunsun-wa": (COV, "puppet-sunsun-wa-a6"),
    "cover-a6-yoshie-watanabe-petit-bloom": (COV, "yoshie-watanabe-petit-bloom-a6"),
    "cover-a6-colors-bordeaux-terracotta": (COV, "colors-bordeaux-terracotta-a6"),
    "cover-a6-colors-blue-parasol": (COV, "colors-blue-parasol-a6"),
    "cover-a6-tanakadaisuke-handkerchief": (COV, "tanakadaisuke-white-handkerchief-diary-a6"),
    "cover-a6-glow-chianti": (COV, "glow-chianti-a6"),
    "cover-a6-natal-hello-new-day-camo": (COV, "natal-hello-new-day-camo-a6"),
    "cover-a6-arts-science-wax-coating-kip": (COV, "arts-science-wax-coating-kip-a6"),
    "cover-a5-yumi-kitagishi-white-cat-village": (COV, "yumi-kitagishi-white-cat-village-a5"),
    "cover-a5-va-blackthorn": (COV, "va-blackthorn-a5"),
    "cover-a5-akiko-miyakoshi-airport": (COV, "akiko-miyakoshi-airport-a5"),
    "cover-a5-puppet-sunsun-s": (COV, "puppet-sunsun-s-a5"),
    "cover-a5-colors-chiffon-greige": (COV, "colors-chiffon-greige-a5"),
    "cover-a5-colors-misty-cedar": (COV, "colors-misty-cedar-a5"),
    "cover-a5-colors-mango-latte": (COV, "colors-mango-latte-a5"),
    "cover-a5-moomin-my-yard-pink-gray": (COV, "moomin-my-yard-pink-gray-a5"),
    "cover-a5-mina-perhonen-felice-blue": (COV, "mina-perhonen-felice-blue-a5"),
    "cover-a5-tanakadaisuke-handkerchief": (COV, "tanakadaisuke-white-handkerchief-diary-a5"),
    "cover-a5-glow-chianti": (COV, "glow-chianti-a5"),
    "weeks-cover-tragen-bitter-plaid": (WK, "tragen-bitter-plaid-cover"),
    "weeks-cover-alettone-sweets": (WK, "alettone-sweets-cover"),
    "weeks-cover-mina-perhonen-felice-blue": (WK, "mina-perhonen-felice-blue-weeks-cover"),
}
# Nov 27, 2026: the two single-shop PUPPET SUNSUN pages folded into the Covers page (301); their rows stay there.
MERGED = {"cover-a6-puppet-sunsun-wa", "cover-a5-puppet-sunsun-s"}
FORBIDDEN = re.compile(r"midori|traveler|designphil|bullet journal", re.I)


class NewCoverDesignPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.rows = [(s["id"], p) for s in cls.cfg["stores"] for p in s["products"]]
        cls.designs = {}
        for cid in NEW:
            pool = site.MERGED_DESIGNS if cid in MERGED else site.DESIGNS
            ds = [d for d in pool if d["match"]({"canonical": cid, "type": "Cover", "label": "", "url": ""})]
            cls.designs[cid] = ds

    def test_count_is_24_and_split(self):
        self.assertEqual(len(NEW), 24)
        self.assertEqual(sum(c.startswith("cover-a6-") for c in NEW), 10)
        self.assertEqual(sum(c.startswith("cover-a5-") for c in NEW), 11)
        self.assertEqual(sum(c.startswith("weeks-cover-") for c in NEW), 3)

    def test_each_cover_has_exactly_one_page_with_the_expected_slug(self):
        for cid, (parent, slug) in NEW.items():
            ds = self.designs[cid]
            self.assertEqual(len(ds), 1, cid)
            self.assertEqual((ds[0]["parent"], ds[0]["slug"]), (parent, slug), cid)

    def test_every_listing_of_each_cover_belongs_to_its_page(self):
        for cid in NEW:
            self.assertTrue([p for _, p in self.rows if p["canonical"] == cid], cid)

    def test_paths_are_unique_and_have_about_text(self):
        paths = [site.design_fname(d) for d in site.DESIGNS]
        self.assertEqual(len(paths), len(set(paths)))
        for cid in NEW:
            d = self.designs[cid][0]
            about = site.design_about(d)
            self.assertTrue(about.endswith("."))
            self.assertNotRegex(about, FORBIDDEN)
            self.assertNotIn(" a A5", about)
            self.assertNotIn(" a A6", about)

    def test_about_text_makes_no_unsourced_claims(self):
        for cid in NEW:
            about = site.design_about(self.designs[cid][0]).lower()
            for word in ("leather", "cotton", "linen", "limited", "sold out fast", "price", "$"):
                self.assertNotIn(word, about, cid)

    def test_jan_only_where_kinokuniya_lists_it(self):
        kino = {p["canonical"]: re.search(r"/(\d{13})$", p["url"]) for sid, p in self.rows if sid == "kinousa"}
        for cid in NEW:
            about = site.design_about(self.designs[cid][0])
            m = kino.get(cid)
            if m:
                self.assertIn("JAN " + m.group(1), about, cid)
            else:
                self.assertNotIn("JAN", about, cid)

    def test_built_pages_exist_link_from_cards_and_sitemap(self):
        sitemap = (ROOT / "site/sitemap.xml").read_text()
        covers = (ROOT / "site" / COV / "index.html").read_text()
        weeks = (ROOT / "site" / WK / "index.html").read_text()
        tracker = (ROOT / "site/hobonichi-restock-tracker/index.html").read_text()
        for cid, (parent, slug) in NEW.items():
            page = ROOT / "site" / parent / slug / "index.html"
            self.assertTrue(page.exists(), slug)
            html = page.read_text()
            if cid in MERGED:  # a redirect stub to the Covers page; the rows and their links live there now
                self.assertIn(f'<link rel="canonical" href="https://stationerydropwatch.com/{COV}/">', html)
                self.assertNotIn(f"/{parent}/{slug}/", sitemap)
                self.assertEqual(site.REDIRECTS[f"{parent}/{slug}"], COV + "/")
                self.assertNotIn(f"/{parent}/{slug}/", tracker)
                self.assertNotIn(f'href="{parent}/{slug}/"', covers)
                self.assertIn(site.E(site.design_about(self.designs[cid][0])), covers)
                continue
            self.assertIn(f"https://stationerydropwatch.com/{parent}/{slug}/", sitemap)
            self.assertIn(f'<link rel="canonical" href="https://stationerydropwatch.com/{parent}/{slug}/">', html)
            self.assertRegex(html, r'id="alerts-tag-hobonichi"[^>]* checked')
            self.assertNotRegex(html, FORBIDDEN)
            # first observations are never a restock: the feed shows exactly the logged restocks, or says there are none
            d = self.designs[cid][0]
            urls = {l["url"] for l in site.design_listings(d)}
            logged = [c for c in site.changes if c["url"] in urls and site.is_restock_event(c)]
            if logged:
                self.assertNotIn("No restocks spotted yet", html)
                self.assertIn(f'datetime="{max(c["at"] for c in logged)}"', html)
            else:
                self.assertIn("No restocks spotted yet", html)
            self.assertIn("/assets/brand/og-image.png", html)
            self.assertIn(f"/{parent}/{slug}/", tracker)
            self.assertIn(f"/{parent}/{slug}/", covers if parent == COV else weeks)

    def test_page_lists_every_shop_row_with_exact_url(self):
        for cid, (parent, slug) in NEW.items():
            html = (ROOT / "site" / (COV if cid in MERGED else f"{parent}/{slug}") / "index.html").read_text()
            for sid, p in self.rows:
                if p["canonical"] == cid:
                    self.assertIn(p["url"].replace("&", "&amp;"), html, f"{slug} {sid}")


if __name__ == "__main__":
    unittest.main()
