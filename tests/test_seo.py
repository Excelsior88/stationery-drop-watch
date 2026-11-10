"""Document titles, meta descriptions, sitemap lastmod, favicon and the /404 status rule.

Visible copy, stock rows and JSON-LD FAQ answers are not rewritten here. Titles and
descriptions are checked from the same builders the site rebuild uses, so a later
checker run cannot grow them back past the limits.
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

TITLE_RE = re.compile(r"<title>(.*?)</title>")
DESC_RE = re.compile(r'<meta name="description" content="(.*?)">')
OG_DESC_RE = re.compile(r'<meta property="og:description" content="(.*?)">')
TW_DESC_RE = re.compile(r'<meta name="twitter:description" content="(.*?)">')
LASTMOD_RE = re.compile(r"<lastmod>(.*?)</lastmod>")
W3C = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00")


def pages():
    found = [
        ("index.html", site.build_index()),
        (site.HOBO_TRACKER, site.build_hobo_tracker()),
        ("hobonichi-2027.html", site.build_hobonichi()),
        ("about.html", site.build_about()),
        ("privacy.html", site.build_privacy()),
        ("404.html", site.build_404()),
    ]
    oe = site.amazon_main(site.stock["products"])
    found.extend(site.build_group(g, oe) for g in site.GROUPS)
    found.extend(site.build_design(d, oe) for d in site.DESIGNS)
    for build in (site.build_where_to_buy, site.build_vs, site.build_dotgrid_guide,
                  site.build_tn_sizes, site.build_guides_index, site.build_shop, site.build_follow):
        found.append(build())
    return found


class SeoHeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = pages()

    def test_titles_are_unique_and_about_sixty_characters(self):
        titles = []
        for path, doc in self.docs:
            title = html.unescape(TITLE_RE.search(doc).group(1))
            self.assertLessEqual(len(title), 60, path)
            self.assertGreaterEqual(len(title), 15, path)
            self.assertNotIn("hourly", title.lower(), path)
            titles.append(title)
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(titles), 66)  # 65 sitemap URLs plus the noindex 404 page

    def test_descriptions_match_social_tags_and_stay_under_160(self):
        descs = []
        for path, doc in self.docs:
            desc = html.unescape(DESC_RE.search(doc).group(1))
            og = html.unescape(OG_DESC_RE.search(doc).group(1))
            tw = html.unescape(TW_DESC_RE.search(doc).group(1))
            self.assertEqual(desc, og, path)
            self.assertEqual(desc, tw, path)
            self.assertLessEqual(len(desc), 160, path)
            self.assertGreaterEqual(len(desc), 140, path)
            self.assertTrue(desc.endswith("."), path)
            self.assertNotIn("hourly", desc.lower(), path)
            descs.append(desc)
        self.assertEqual(len(descs), len(set(descs)))

    def test_faq_answers_still_name_the_thirty_minute_check(self):
        doc = dict(self.docs)["hobonichi-weeks-2027/midnight-blue/"]
        self.assertIn("Every shop is checked about every 30 minutes.", doc)
        meta = html.unescape(DESC_RE.search(doc).group(1))
        self.assertNotIn("30 minutes", meta)
        self.assertIn("Hobonichi Weeks 2027 Midnight Blue restock tracker", doc)

    def test_canonicals_og_images_and_404_noindex_stay(self):
        home = dict(self.docs)["index.html"]
        self.assertIn('<link rel="canonical" href="https://stationerydropwatch.com/">', home)
        self.assertIn("https://stationerydropwatch.com/assets/brand/og-image.png", home)
        self.assertIn('<link rel="icon" href="/favicon.ico"', home)
        missing = dict(self.docs)["404.html"]
        self.assertIn('<meta name="robots" content="noindex">', missing)
        self.assertNotIn('rel="canonical"', missing)
        dot = dict(self.docs)["archer-and-olive-dot-grid-journal/"]
        self.assertIn("og-dotgrid.png", dot)
        for path, doc in self.docs:
            for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc):
                json.loads(block)

    def test_sitemap_lastmod_is_one_w3c_datetime(self):
        mods = LASTMOD_RE.findall(site.build_sitemap())
        self.assertEqual(len(mods), 65)
        self.assertTrue(all(W3C.fullmatch(m) for m in mods), mods[:3])

    def test_favicon_is_the_existing_mark(self):
        ico = ROOT / "site" / "favicon.ico"
        self.assertTrue(ico.is_file())
        self.assertLess(ico.stat().st_size, 20_000)

    def test_shop_sheet_keeps_its_pixels_and_is_smaller(self):
        from PIL import Image
        path = ROOT / "site/assets/shop/soft-days-narrow-inserts.png"
        with Image.open(path) as im:
            self.assertEqual(im.size, (2700, 2025))
        self.assertLess(path.stat().st_size, 400_000)
        self.assertGreater(path.stat().st_size, 100_000)


class NotFoundStatusTests(unittest.TestCase):
    """Pages serves 404.html with status 404 for unknown paths. /404 matches that file, so it
    would be HTTP 200. Pages _redirects cannot use a 404 status, so site/functions/_middleware.js
    returns 404.html with status 404 for /404, /404/ and /404.html. The page stays noindex.
    """

    def test_redirects_do_not_claim_an_unsupported_404_status(self):
        for line in (ROOT / "cloudflare/_redirects").read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            self.assertFalse(line.endswith(" 404"), line)

    def test_middleware_serves_the_not_found_page_with_status_404(self):
        src = (ROOT / "site/functions/_middleware.js").read_text()
        for path in ("/404", "/404/", "/404.html"):
            self.assertIn(f'"{path}"', src)
        self.assertIn("status: 404", src)
        self.assertIn('pathname = "/404.html"', src)
        self.assertIn("noindex", src)
        page = site.build_404()
        self.assertIn('content="noindex"', page)
        self.assertNotIn('rel="canonical"', page)


if __name__ == "__main__":
    unittest.main()
