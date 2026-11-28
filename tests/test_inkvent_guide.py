"""Where to buy Diamine Inkvent 2026 guide (built Nov 27, 2026; needs the owner's yes before it goes live)."""
import html as htmllib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site

SLUG = "where-to-buy-diamine-inkvent-2026"
BANNED = re.compile(r"designphil|midori|traveler|yoseka|pen heaven|appelboom|oblation|pen chalet|amazon\.|amzn\.|[?&]tag=", re.I)
# JetPens may appear in site-wide Hobonichi link-only notes; it must not be a source on this guide.
GUIDE_BANNED_SOURCES = re.compile(r"jetpens", re.I)


def doc():
    fname, html = site.build_inkvent()
    assert fname == SLUG + "/"
    return html


def visible(html):
    main = re.search(r"<main.*?</main>", html, re.S).group(0)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", main, flags=re.S)))


class InkventGuideTests(unittest.TestCase):
    def test_slug_and_listing_everywhere(self):
        self.assertIn((SLUG + "/", "Where to buy Diamine Inkvent 2026"), site.GUIDES)
        self.assertEqual(len(site.GUIDES), 7)
        self.assertIn(SLUG + "/", site.GUIDE_BLURBS)
        _, idx = site.build_guides_index()
        self.assertIn("7 guides", idx)
        self.assertIn(f'href="/{SLUG}/"', idx)
        start = idx.index('<ul class="guide-list">')
        self.assertEqual(idx[start:idx.index("</ul>", start)].count("<li>"), len(site.GUIDES))  # the "7 guides" count matches the list
        self.assertIn(f"/{SLUG}/", site.build_sitemap())
        items = site.search_index()["items"]
        self.assertTrue(any(i["id"] == "guide-" + SLUG and i["u"] == f"/{SLUG}/" for i in items))
        self.assertIn(f'href="/{SLUG}/"', site.build_inks()[1])  # the ink tracker links to the guide

    def test_meta_and_typography(self):
        html = doc()
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        self.assertLessEqual(len(htmllib.unescape(desc)), 160)
        self.assertIn(f'<link rel="canonical" href="https://stationerydropwatch.com/{SLUG}/">', html)
        text = visible(html) + desc
        self.assertNotIn("\u2014", html)  # no em dashes anywhere on the page
        self.assertNotIn("\u2013", text)  # nor en dashes in the visible text
        self.assertNotIn(" bullet journal", text.lower())
        self.assertNotRegex(html, BANNED)
        article = re.search(r"<article.*?</article>", html, re.S).group(0)
        self.assertNotRegex(article, GUIDE_BANNED_SOURCES)

    def test_json_ld_parses(self):
        html = doc()
        blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        kinds = {b["@type"] for b in blocks}
        self.assertTrue({"Article", "FAQPage", "BreadcrumbList"} <= kinds)
        art = next(b for b in blocks if b["@type"] == "Article")
        self.assertEqual(art["datePublished"], "2026-11-28")
        self.assertGreaterEqual(art["dateModified"], art["datePublished"])

    def test_signup_preselects_only_limited_edition_inks(self):
        html = doc()
        top = html[html.index('id="alerts"'):html.index('id="quick"')]
        boxes = re.findall(r'<input type="checkbox"[^>]*id="alerts-tag-(\w[\w-]*)"([^>]*)>', top)
        self.assertEqual([(s, " checked" in a) for s, a in boxes], [("hobonichi", False), ("dot-grid", False), ("inks", True)])

    def test_every_shop_is_on_diamines_own_list_and_statuses_are_live(self):
        diamine_shops = set(site.INK_CFG["brands"]["diamine"]["shops"])
        html = doc()
        rows = [r for r in site.INK_ROWS if r["ink_id"] in (site.INKVENT_CAL, site.INKVENT_TEAL)]
        self.assertTrue(rows)
        self.assertTrue({r["store_id"] for r in rows} <= diamine_shops)
        cal = [r for r in rows if r["ink_id"] == site.INKVENT_CAL]
        for r in cal:
            self.assertIn(r["url"].replace("&", "&amp;"), html)
        n_buy = sum(r["status"] in site.BUYABLE for r in cal)
        self.assertIn(f"<strong>{n_buy} of {len(cal)}</strong>" if n_buy else f"any of the {len(cal)} shops", html)

    def test_teal_table_has_25_inks_and_prices_match_the_snapshot(self):
        d = site.INKVENT_DATA
        self.assertEqual(len(d["teal_inks"]), 25)
        self.assertTrue({i["type"] for i in d["teal_inks"]} <= set(d["teal_price_by_type_usd_cents"]))
        html = doc()
        self.assertEqual(html.count('<td><span class="muted small">Not listed</span></td>') + len(re.findall(r'aria-label="[^"]+ at [^"]+"', html)),
                         25 * len({r["store_id"] for r in site.INK_ROWS if r["ink_id"] == site.INKVENT_TEAL}))
        self.assertIn(site.fmt_et(d["prices_as_of"]).replace("'", "&#x27;"), html)

    def test_pigment_and_pen_care_lines_are_sourced(self):
        html = doc()
        text = visible(html)
        self.assertIn("permanent, waterproof and lightfast", text)
        self.assertIn("Its page says this about pigment inks only", text)
        self.assertIn("regular cleaning is required", text)
        self.assertIn("rinsing the pen after use", text)
        self.assertIn(site.INKVENT_DATA["goldspot_mittens_url"], html)
        self.assertIn(site.INKVENT_DATA["cultpens_teal_url"], html)
        self.assertIn(site.INKVENT_DATA["dromgooles_mittens_url"], html)
        self.assertNotIn("once dry", text.lower())  # Diamine doesn't say this
        self.assertNotIn("not vintage", text.lower())  # Diamine and Dromgoole's say the inks can be used in vintage pens
        self.assertIn("fall 2027", text)
        self.assertIn("Nov 4, 2026", text)
        self.assertIn("hasn't announced", text)
        self.assertIn("$18 to $25", text)
        self.assertNotIn("June 12", text)
        self.assertNotIn("July 28", text)
        self.assertNotIn("sell out first", text)
        self.assertNotIn("delayed dealer", text)
        self.assertNotIn("first-ever pigment", text.lower())
        self.assertNotIn("first ever pigment", text.lower())
        self.assertIn("calendar at 6 shops, Teal bottles at 5", text.replace("\xa0"," "))


if __name__ == "__main__":
    unittest.main()
