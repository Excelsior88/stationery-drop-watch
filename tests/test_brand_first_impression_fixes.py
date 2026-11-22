"""Names, Hobonichi titles, dot-grid coverage copy, and official store marks."""
import html
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

PLANNER = "https://www.baum-kuchen.net/products/hobonichi-2027-planner-book-a6-english"
ORIGINAL = "https://www.baum-kuchen.net/products/hobonichi-2027-original-book-a6-english"
ONE_PIECE_WONDER = "https://wonderpens.ca/products/hobonichi-2027-japanese-original-book-one-piece-edition-a6-size-daily-jan-start-mon-start"
ONE_PIECE_KINO = "https://usa.kinokuniya.com/products/4580812710374"


def plain(doc):
    return html.unescape(re.sub(r"<[^>]+>", " ", doc))


class AboutContactNameTests(unittest.TestCase):
    def test_about_names_andrew_and_arden_and_keeps_the_story(self):
        doc = site.build_about()
        text = plain(doc)
        self.assertIn(
            "Drop Watch is run by Andrew Robinson. "
            "He built the tracker after seeing how frustrating it was for his partner, Arden, "
            "to keep up with planner restocks, and now they run it together.",
            text,
        )
        self.assertIn("The couple behind Drop Watch", text)
        self.assertIn("Stationery Drop Watch is built in Hamtramck, Michigan.", text)
        self.assertEqual(text.count("his partner"), 1)
        self.assertNotIn("Andrew Robinson and his partner, Arden", text)
        self.assertIn("admin@stationerydropwatch.com", text)
        self.assertNotIn("birthday", text.lower())
        self.assertNotRegex(text, r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")

    def test_contact_names_andrew_but_not_arden(self):
        _fname, doc = site.build_contact()
        text = plain(doc)
        self.assertIn("Andrew Robinson runs the site and can be reached at", text)
        self.assertIn("admin@stationerydropwatch.com", text)
        self.assertNotIn("Arden", text)
        self.assertNotIn("partner", text.lower())


class HobonichiTitleTests(unittest.TestCase):
    def test_one_piece_and_planner_have_clean_canonical_names(self):
        by_url = {p["url"]: p for p in site.stock["products"]}
        one_piece = [by_url[ONE_PIECE_WONDER], by_url[ONE_PIECE_KINO]]
        for row in one_piece:
            self.assertEqual(row["canonical"], "original-a6-jp-one-piece")
            self.assertEqual(row["label"], "Original A6 book (Japanese) · One Piece Edition")
        planner = by_url[PLANNER]
        original = by_url[ORIGINAL]
        self.assertEqual(planner["canonical"], "planner-a6-en")
        self.assertEqual(planner["label"], "Planner A6 book (English)")
        self.assertEqual(original["canonical"], "original-a6-en")
        self.assertNotEqual(planner["canonical"], original["canonical"])

    def test_history_and_first_seen_stay_put(self):
        by_url = {p["url"]: p for p in site.stock["products"]}
        self.assertEqual(by_url[PLANNER]["first_seen"], "2026-10-25T21:41:00+00:00")
        self.assertEqual(by_url[PLANNER]["status_since"], "2026-10-25T21:41:00+00:00")
        self.assertEqual(by_url[ONE_PIECE_WONDER]["first_seen"], "2026-10-25T21:40:49+00:00")
        self.assertEqual(by_url[ONE_PIECE_WONDER]["status_since"], "2026-10-31T19:06:20+00:00")
        self.assertEqual(by_url[ONE_PIECE_KINO]["first_seen"], "2026-10-25T21:41:09+00:00")
        events = [c for c in site.changes if c["url"] == ONE_PIECE_WONDER]
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev["at"], "2026-10-31T19:06:20+00:00")
        self.assertEqual(ev["from"], "in_stock")
        self.assertEqual(ev["to"], "sold_out")
        self.assertEqual(ev["label"], "Original A6 book (Japanese) · One Piece Edition")

    def test_tracker_headings_use_the_clean_names(self):
        doc = site.build_hobo_tracker()
        text = plain(doc)
        self.assertIn("Original A6 book (Japanese) · One Piece Edition", text)
        self.assertIn("Planner A6 book (English)", text)
        self.assertIn("Planner A6", text)  # family name
        headings = re.findall(r"<h3>(.*?)</h3>", doc, re.S)
        headings = [html.unescape(re.sub(r"<[^>]+>", "", h)).strip() for h in headings]
        self.assertIn("Original A6 book (Japanese) · One Piece Edition", headings)
        self.assertIn("Planner A6 book (English)", headings)
        self.assertTrue(all("[" not in h and "Daily/Jan" not in h for h in headings), headings)
        # Shop subtitles may still quote the store's own title.
        self.assertIn("[Hobonichi 2027] Planner Book (A6 / English)", text)


class DotGridCopyAndOfficialTests(unittest.TestCase):
    def test_coverage_copy_is_accurate(self):
        phrase = site.dotgrid_where_checked()
        self.assertIn("Archer and Olive", phrase)
        self.assertIn("Scribbles That Matter", phrase)
        self.assertIn("Notebook Therapy", phrase)
        self.assertIn("on each maker's own store", phrase)
        self.assertIn("Leuchtturm1917 at its official US store and", phrase)
        self.assertIn("independent", phrase)
        self.assertNotIn("(official)", phrase)
        group = next(g for g in site.GROUPS if g.get("section") == "dotgrid")
        _fname, doc = site.build_group(group, {})
        text = plain(doc)
        self.assertIn(phrase, text)
        self.assertNotIn("each on that maker's own store", text)
        self.assertNotIn("at each maker's shop", text)
        desc = site.dotgrid_meta_desc()
        self.assertGreaterEqual(len(desc), 140)
        self.assertLessEqual(len(desc), site.DESC_LIMIT)
        self.assertIn("Official stores", desc)
        self.assertIn("independent", desc)
        self.assertIn("Leuchtturm1917", desc)
        self.assertIn(desc, doc)
        self.assertNotIn("at each maker's official.", doc)
        home = plain(site.build_index())
        self.assertIn(phrase, home)
        self.assertNotIn("each checked on its own store", home)
        faq = site.faq_block()[0]
        self.assertIn(phrase.rstrip("."), plain(faq))

    def test_maker_stores_are_marked_official_consistently(self):
        shown = {s["id"]: s["name"] for s in site.DOTGRID_SHOPS}
        self.assertEqual(shown["archerolive"], "Archer and Olive (official)")
        self.assertEqual(shown["leuchtturm-us"], "Leuchtturm1917 (official)")
        self.assertEqual(shown["scribbles"], "Scribbles That Matter (official)")
        self.assertEqual(shown["notebooktherapy"], "Notebook Therapy (official)")
        group = next(g for g in site.GROUPS if g.get("section") == "dotgrid")
        _fname, doc = site.build_group(group, {})
        text = plain(doc)
        self.assertIn("Leuchtturm1917 (official)", text)
        self.assertNotIn("Leuchtturm1917 US (official)", text)
        self.assertIn("Archer and Olive (official)", text)
        self.assertIn("Scribbles That Matter (official)", text)
        self.assertIn("Notebook Therapy (official)", text)
        # Brand lists in the lede stay uncluttered.
        lede = re.search(r'<p class="lede">(.*?)</p>', doc, re.S).group(1)
        self.assertIn("Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy", html.unescape(lede))
        self.assertNotIn("(official)", lede)
