"""Search titles keep the words people search for (Nov 27, 2026).

The Nov 10 title trim dropped "restock" and "2027" from the tracker titles, and Search Console
impressions fell soon after. These checks run on the same builders as the site rebuild, so a later
length trim can't strip them again.
"""
import html
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

TITLE_RE = re.compile(r"<title>(.*?)</title>")
DESC_RE = re.compile(r'<meta name="description" content="(.*?)">')


def title(doc):
    return html.unescape(TITLE_RE.search(doc).group(1))


def desc(doc):
    return html.unescape(DESC_RE.search(doc).group(1))


def is_2027(slug):
    return "2027" in slug


class TrackerTitleTests(unittest.TestCase):
    def test_hobonichi_tracker_and_calendar(self):
        t = title(site.build_hobo_tracker())
        self.assertIn("restock", t)
        self.assertIn("2027", t)
        cal = site.build_hobonichi()
        self.assertEqual(title(cal), "Hobonichi 2027 restock calendar: when stock comes back")

    def test_every_group_tracker_title_says_restock_and_2027_where_it_is_a_2027_product(self):
        for g in site.GROUPS:
            fname, doc = site.build_group(g, {})
            t = title(doc)
            with self.subTest(page=fname, title=t):
                self.assertIn("restock", t.lower())
                self.assertLessEqual(len(t), site.TITLE_LIMIT)
                if is_2027(g["slug"]):
                    self.assertIn("2027", t)

    def test_every_checked_design_title_says_restock_and_2027_where_it_is_a_2027_product(self):
        checked = [d for d in site.DESIGNS if not site.design_is_link_only(d)]
        self.assertGreater(len(checked), 40)
        for d in checked:
            fname, doc = site.build_design(d)
            t = title(doc)
            with self.subTest(page=fname, title=t):
                self.assertIn("restock", t.lower())
                self.assertLessEqual(len(t), site.TITLE_LIMIT)
                if is_2027(d["parent"]):
                    self.assertIn("2027", t)

    def test_weeks_and_dot_grid_patterns(self):
        star = next(d for d in site.DESIGNS if d["parent"] == "hobonichi-weeks-2027" and d["slug"] == "starlight")
        self.assertTrue(title(site.build_design(star)[1]).startswith("Hobonichi Weeks 2027 Starlight restock tracker"))
        apo = next(d for d in site.DESIGNS if d["slug"] == "archer-and-olive-apothecary-shelf")
        self.assertEqual(title(site.build_design(apo)[1]), "Archer and Olive Apothecary Shelf dot grid restock tracker")

    def test_homepage_title_unchanged(self):
        self.assertEqual(title(site.build_index()), "Hobonichi, dot grid and ink restock tracker · Drop Watch")


class DescriptionTests(unittest.TestCase):
    def test_tracker_description_uses_the_built_shop_count(self):
        doc = site.build_hobo_tracker()
        d = desc(doc)
        n = re.search(r"at (\d+) shops", d)
        self.assertIsNotNone(n, d)
        self.assertTrue(d.startswith("Is your Hobonichi Techo 2027 back in stock?"))
        self.assertIn(site.CHECK_FREQ, d)
        self.assertLessEqual(len(d), site.DESC_LIMIT)
        self.assertIn(f"{n.group(1)} shops", html.unescape(re.sub(r"<[^>]+>", " ", doc)))  # same count the page shows

    def test_calendar_description(self):
        self.assertEqual(desc(site.build_hobonichi()),
                         "When will Hobonichi Techo 2027 restock? Launch dates, the October wave, and when restocks usually land, with sources.")


class CalendarLayoutTests(unittest.TestCase):
    def test_restock_heading_and_signup_after_timeline(self):
        doc = site.build_hobonichi()
        self.assertIn("<h2>When will Hobonichi 2027 restock?</h2>", doc)
        self.assertNotIn("Will it come back?", doc)
        timeline_end = doc.index("</ol>", doc.index('<ol class="timeline">'))
        signup_at = doc.index('id="alerts"')
        self.assertGreater(signup_at, timeline_end)
        self.assertLess(signup_at, doc.index("Which 2027 books have an April-start"))
        self.assertEqual(doc.count('id="alerts"'), 1)


class LinkOnlyDesignTests(unittest.TestCase):
    def test_link_only_tsuki_pages_are_noindex_not_in_sitemap_and_still_linked(self):
        lo = [d for d in site.DESIGNS if site.design_is_link_only(d)]
        self.assertEqual(sorted(d["slug"] for d in lo), sorted([
            "notebook-therapy-tsuki-160gsm", "notebook-therapy-tsuki-dark-academia",
            "notebook-therapy-tsuki-ravens-secret", "notebook-therapy-tsuki-violet-nocturne"]))
        sitemap = site.build_sitemap()
        parent = next(g for g in site.GROUPS if g["slug"] == site.DOTGRID_SLUG)
        _, tracker = site.build_group(parent, {})
        for d in lo:
            fname, doc = site.build_design(d)
            with self.subTest(page=fname):
                self.assertIn('<meta name="robots" content="noindex">', doc)
                self.assertNotIn(site.url_for(fname), sitemap)
                self.assertRegex(tracker, r'href="/?' + re.escape(fname) + '"')  # still reachable from the dot grid tracker
        for d in site.DESIGNS:
            if not site.design_is_link_only(d):
                self.assertIn(site.url_for(site.design_fname(d)) + "</loc>", sitemap)
                self.assertNotIn('content="noindex"', site.build_design(d)[1])


if __name__ == "__main__":
    unittest.main()
