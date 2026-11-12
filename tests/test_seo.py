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
    for build in (site.build_where_to_buy, site.build_vs, site.build_january_april, site.build_dotgrid_guide,
                  site.build_tn_sizes, site.build_guides_index, site.build_shop, site.build_follow,
                  site.build_contact):
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
        self.assertEqual(len(titles), 68)  # sitemap URLs plus the noindex 404, minus /sold-out-everywhere/

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

    def test_header_marks_one_section_and_the_size_guide_marks_guides(self):
        for path, doc in self.docs:
            bar = re.search(r'<nav class="site-nav site-nav-bar" aria-label="Main">(.*?)</nav>', doc)
            self.assertIsNotNone(bar, path)
            current = re.findall(r'href="([^"]+)"[^>]*aria-current=page', bar.group(1))
            self.assertLessEqual(len(current), 1, (path, current))
            if path in ("hobonichi-techo-vs-cousin-vs-weeks/", "hobonichi-january-start-vs-april-start/"):
                self.assertEqual(current, ["/guides/"])
            elif path.startswith(("hobonichi-techo-", "hobonichi-weeks-")):
                self.assertEqual(current, ["/" + site.HOBO_TRACKER])

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

    def test_sold_out_description_is_a_finished_sentence(self):
        doc = site.build_sold_out()[1]
        desc = html.unescape(DESC_RE.search(doc).group(1))
        og = html.unescape(re.search(r'property="og:description" content="([^"]*)"', doc).group(1))
        tw = html.unescape(re.search(r'name="twitter:description" content="([^"]*)"', doc).group(1))
        self.assertEqual(desc, og)
        self.assertEqual(desc, tw)
        self.assertLessEqual(len(desc), 155)
        self.assertTrue(desc.endswith("."))
        self.assertIn("restock page", desc)
        self.assertNotIn("item's.", desc)

    def test_guide_article_dates_come_from_the_first_publish(self):
        where = site.build_where_to_buy()[1]
        vs = site.build_vs()[1]
        for doc in (where, vs):
            art = next(json.loads(html.unescape(b.replace("<\\/", "</")))
                       for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc)
                       if '"Article"' in b)
            self.assertEqual(art["datePublished"], "2026-10-29")
            self.assertEqual(art["dateModified"], "2026-10-29")
            self.assertNotIn(site.stock["run_finished"][:10], art["dateModified"])
        dot = site.build_group(next(g for g in site.GROUPS if g["slug"] == "archer-and-olive-dot-grid-journal"), {})[1]
        self.assertIn('href="/hobonichi-restock-tracker/">Hobonichi tracker</a>', dot)

    def test_sitemap_lastmod_is_one_w3c_datetime(self):
        mods = LASTMOD_RE.findall(site.build_sitemap())
        self.assertEqual(len(mods), 68)  # + /sold-out-everywhere/ and the January vs April guide
        self.assertTrue(all(W3C.fullmatch(m) for m in mods), mods[:3])

    def test_favicon_is_the_existing_mark(self):
        ico = ROOT / "site" / "favicon.ico"
        self.assertTrue(ico.is_file())
        self.assertLess(ico.stat().st_size, 20_000)

    def test_shop_sheet_keeps_its_pixels_and_is_smaller(self):
        from PIL import Image
        small = ROOT / "site/assets/shop/soft-days-narrow-inserts-900.webp"
        large = ROOT / "site/assets/shop/soft-days-narrow-inserts-1800.webp"
        with Image.open(small) as im:
            self.assertEqual(im.size, (900, 675))
        with Image.open(large) as im:
            self.assertEqual(im.size, (1800, 1350))
        self.assertLess(small.stat().st_size, 200_000)
        self.assertFalse((ROOT / "site/assets/shop/soft-days-narrow-inserts.png").exists())
        shop = site.build_shop()[1]
        self.assertIn("soft-days-narrow-inserts-900.webp 900w", shop)
        self.assertIn("soft-days-narrow-inserts-1800.webp 1800w", shop)

    def test_january_april_guide_publishes_the_approved_wording(self):
        path, doc = site.build_january_april()
        self.assertEqual(path, "hobonichi-january-start-vs-april-start/")
        title = html.unescape(TITLE_RE.search(doc).group(1))
        desc = html.unescape(DESC_RE.search(doc).group(1))
        self.assertLessEqual(len(title), 60)
        self.assertIn("January-start vs April-start", title)
        self.assertLessEqual(len(desc), 155)
        self.assertGreaterEqual(len(desc), 140)
        self.assertTrue(desc.startswith("Hobonichi's April-start (Spring) techo"))
        self.assertIn('<link rel="canonical" href="https://stationerydropwatch.com/hobonichi-january-start-vs-april-start/">', doc)
        self.assertIn('property="og:title"', doc)
        self.assertIn('name="twitter:image:alt"', doc)
        self.assertIn("<h1>Hobonichi Techo January-start vs April-start</h1>", doc)
        self.assertIn("goes on sale every year on February 1st", doc)
        self.assertIn("9:00 PM Eastern on January 31", doc)
        self.assertIn("it may be restocked for the April-start release.", doc)
        self.assertIn("<h2>Questions</h2>", doc)
        self.assertNotIn("<h2>FAQ</h2>", doc)
        self.assertNotIn("Jump to", doc)
        self.assertNotIn("Our planners and journals", doc)
        self.assertNotIn('<details class="faq-item" open', doc)
        questions = re.findall(r'<details class="faq-item"><summary>(.*?)</summary><p>(.*?)</p></details>', doc)
        self.assertEqual(len(questions), 3)
        blocks = [json.loads(html.unescape(b.replace("<\\/", "</")))
                  for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc)]
        art = next(b for b in blocks if b.get("@type") == "Article")
        faq = next(b for b in blocks if b.get("@type") == "FAQPage")
        self.assertEqual(art["datePublished"], "2026-11-12")
        self.assertEqual(art["dateModified"], "2026-11-12")
        visible = [(html.unescape(q), html.unescape(a)) for q, a in questions]
        schema = [(q["name"], q["acceptedAnswer"]["text"]) for q in faq["mainEntity"]]
        self.assertEqual(visible, schema)
        self.assertIn('href="/hobonichi-restock-tracker/">Hobonichi tracker</a>', doc)
        self.assertIn("https://stationerydropwatch.com/hobonichi-january-start-vs-april-start/", site.build_sitemap())
        self.assertIn('href="/hobonichi-january-start-vs-april-start/"', site.build_index())
        self.assertIn('href="/hobonichi-january-start-vs-april-start/"', site.build_guides_index()[1])
        self.assertIn('href="/hobonichi-january-start-vs-april-start/"', site.build_hobo_tracker())


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
