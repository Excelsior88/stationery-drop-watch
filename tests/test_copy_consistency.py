"""Copy and metadata stay tied to tracker scope, not to a stale shop count or a narrow slug.

Shop totals are derived from data/stock.json. The default share-image alt describes the
Hobonichi card and does not repeat a shop count, because that image is reused on pages
whose totals differ and the artwork itself has no count.
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

ALT_RE = re.compile(r'(?:og:image:alt|twitter:image:alt)" content="([^"]*)"')
SHOP_COUNT_RE = re.compile(r"\d+\s+shops?")


def alts(doc):
    return [html.unescape(v) for v in ALT_RE.findall(doc)]


def plain(doc):
    return html.unescape(doc)


class ShareImageAltTests(unittest.TestCase):
    def test_default_alt_describes_the_hobonichi_card_without_a_shop_count(self):
        self.assertIn("Hobonichi Techo 2027 restock tracker", site.OG_ALT)
        self.assertIn("Books, Weeks and covers", site.OG_ALT)
        self.assertIn(site.CHECK_FREQ, site.OG_ALT)
        self.assertNotRegex(site.OG_ALT, SHOP_COUNT_RE)
        # The year 2027 contains the digits of a shop total. Match the count only as its own number.
        self.assertNotRegex(site.OG_ALT, rf"(?<!\d){site.N_HOBO}(?!\d)")
        self.assertNotRegex(site.OG_ALT, rf"(?<!\d){site.N_STORES}(?!\d)")

    def test_pages_that_share_the_default_card_use_that_alt(self):
        pages = {
            "home": site.build_index(),
            "hobonichi tracker": site.build_hobo_tracker(),
            "about": site.build_about(),
            "404": site.build_404(),
            "calendar": site.build_hobonichi(),
        }
        for name, doc in pages.items():
            found = alts(doc)
            self.assertTrue(found, name)
            self.assertTrue(all(a == site.OG_ALT for a in found), (name, found))
            self.assertIn(site.OG_IMAGE, doc)
            self.assertNotIn("across 13 shops", doc)
            self.assertNotIn(f"across {site.N_HOBO} shops", plain(doc))

    def test_hobonichi_page_copy_still_uses_the_derived_hobonichi_shop_count(self):
        doc = plain(site.build_hobo_tracker())
        self.assertIn(f"at {site.N_HOBO} shops", doc)
        faq = site.faq_block()[1]
        shops = next(q for q in faq["mainEntity"] if q["name"] == "Which shops do you check?")
        text = shops["acceptedAnswer"]["text"]
        self.assertIn(f"{site.N_STORES} shops across all trackers", text)
        self.assertIn(f"Hobonichi: {site.N_HOBO} shops", text)
        self.assertIn("counted once in the total", text)

    def test_section_cards_keep_their_own_count_free_alts(self):
        oe = {}
        for key, expected_image in (
            ("dotgrid", site.OG_DOTGRID),
            ("travelers", site.BASE + "assets/brand/og-travelers.png"),
            ("midori", site.BASE + "assets/brand/og-midori.png"),
        ):
            group = next(g for g in site.GROUPS if g.get("section") == key)
            _fname, doc = site.build_group(group, oe)
            found = alts(doc)
            self.assertTrue(found)
            self.assertTrue(all(a == group["og_alt"] for a in found))
            self.assertNotRegex(group["og_alt"], SHOP_COUNT_RE)
            self.assertIn(expected_image, doc)
            design = next(d for d in site.DESIGNS if d["parent"] == group["slug"])
            _df, ddoc = site.build_design(design, oe)
            self.assertTrue(all(a == group["og_alt"] for a in alts(ddoc)))


class ShopCountDefinitionTests(unittest.TestCase):
    def test_sitewide_total_is_distinct_stores_not_the_sum_of_sections(self):
        products = site.stock["products"]
        distinct = {p["store_id"] for p in products}
        self.assertEqual(site.N_STORES, len(distinct))
        self.assertEqual(site.N_HOBO, site.N_SEC["hobonichi"])
        self.assertEqual(site.N_HOBO, len({p["store_id"] for p in products if site.section_of(p) == "hobonichi"}))
        self.assertGreaterEqual(sum(site.N_SEC.values()), site.N_STORES)
        # Current catalog overlaps (a shop can sell more than one brand). The total must not add those twice.
        self.assertGreater(sum(site.N_SEC.values()), site.N_STORES)
        self.assertEqual(len(site.NAV_TRACKERS), 1 + len(site.LIVE))


class HeroAndScopeTests(unittest.TestCase):
    def test_home_counts_trackers_only_and_points_at_the_other_resources(self):
        doc = plain(site.build_index())
        self.assertIn(site.tracker_count_label(), doc)
        self.assertIn(f"{site.N_STORES} shops", doc)
        self.assertIn("More on the site:", doc)
        self.assertIn("2027 calendar", doc)
        self.assertIn('href="/guides/"', site.build_index())
        self.assertIn('href="/shop/"', site.build_index())
        self.assertNotIn(f"{len(site.NAV_TRACKERS) + len(site.NAV)} restock", doc)
        self.assertNotIn("refills and limited editions", doc)
        card = re.search(
            r'<li class="hub-card"><a href="/travelers-company-limited-edition/">(.*?)</a></li>',
            site.build_index(), re.S)
        self.assertIsNotNone(card)
        card_text = plain(card.group(1))
        self.assertIn("Regular size colors", card_text)
        self.assertIn("limited editions", card_text)
        self.assertNotIn("refill", card_text.lower())
        self.assertNotIn("Passport", card_text)

    def test_dot_grid_page_names_every_maker_and_keeps_the_legacy_url(self):
        group = next(g for g in site.GROUPS if g.get("section") == "dotgrid")
        self.assertEqual(group["slug"], "archer-and-olive-dot-grid-journal")
        self.assertEqual(site.REDIRECTS["archer-and-olive-bullet-journal"], group["slug"] + "/")
        _fname, doc = site.build_group(group, {})
        text = plain(doc)
        self.assertIn("https://stationerydropwatch.com/archer-and-olive-dot-grid-journal/", doc)
        self.assertIn("<h1>Dot grid journal restock tracker</h1>", doc)
        self.assertNotIn("<h1>Archer and Olive", doc)
        for name in ("Archer and Olive", "Leuchtturm1917", "Scribbles That Matter", "Notebook Therapy"):
            self.assertIn(name, text)
        self.assertIn("dot grid refills", text)
        self.assertIn("Dot grid journals", text)  # nav and breadcrumb
        # Our heading and intro say "dot grid". A maker's own product name may still say Bullet Journal.
        lede = re.search(r'<p class="lede">(.*?)</p>', text, re.S).group(1)
        self.assertNotIn("bullet journal", lede.lower())
        self.assertIn(site.OG_DOTGRID_ALT, alts(doc))

    def test_travelers_page_names_regular_colors_and_keeps_the_legacy_url(self):
        group = next(g for g in site.GROUPS if g.get("section") == "travelers")
        self.assertEqual(group["slug"], "travelers-company-limited-edition")
        self.assertEqual(site.REDIRECTS["travelers-notebook-regular-size"], group["slug"] + "/#tracker")
        _fname, doc = site.build_group(group, {})
        text = plain(doc)
        self.assertIn("https://stationerydropwatch.com/travelers-company-limited-edition/", doc)
        self.assertIn("<h1>Traveler's Notebook restock tracker: regular colors and limited editions</h1>", text)
        self.assertNotIn("notebook and limited edition restock tracker", text)
        self.assertIn("Regular size colors", group["og_alt"])
        self.assertIn("limited editions", group["og_alt"])
        self.assertIn("Black", text)
        self.assertIn("Olive", text)
        self.assertIn("For refills, check the shops directly.", text)
        self.assertIn("Every Traveler's Notebook regular-color and limited-edition listing we track", text)
        self.assertIn('href="/travelers-company-limited-edition/">Traveler\'s Company</a>', text)  # compact footer link
        home = plain(site.build_index())
        self.assertIn("Traveler's Notebook regular colors and limited editions", home)
        self.assertNotIn("across 13 shops", doc)
        before = json.loads((ROOT / "data/guide_dates.json").read_text())["build_tn_sizes"]["date"]
        _gfname, guide = site.build_tn_sizes()
        after = json.loads((ROOT / "data/guide_dates.json").read_text())["build_tn_sizes"]["date"]
        self.assertEqual(before, after)
        self.assertEqual(before, "2026-11-05")
        self.assertTrue(all(a == site.OG_TRAVELERS_ALT for a in alts(guide)))
        self.assertNotIn("limited edition tracker", plain(guide))


if __name__ == "__main__":
    unittest.main()
