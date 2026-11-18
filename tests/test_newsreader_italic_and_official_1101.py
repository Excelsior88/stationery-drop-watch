"""True Newsreader italic, plus official 1101 Planner Book and One Piece rows."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "site" / "assets" / "style.css").read_text()
PLANNER = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/pb27_jan/"
ONE_PIECE = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/ob27_op/"


class NewsreaderItalicAndOfficial1101Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data" / "stock.json").read_text())
        cls.changes = json.loads((ROOT / "data" / "changes.json").read_text())
        cls.by_url = {p["url"]: p for p in cls.stock["products"]}

    def test_self_hosted_newsreader_italic(self):
        font = ROOT / "site" / "assets" / "fonts" / "newsreader-italic-500.woff2"
        self.assertTrue(font.is_file())
        self.assertGreater(font.stat().st_size, 8000)
        self.assertIn("fonts/newsreader-italic-500.woff2", CSS)
        self.assertRegex(
            CSS,
            r'@font-face\{font-family:"Newsreader";src:url\(fonts/newsreader-italic-500\.woff2\) format\("woff2"\);font-weight:500;font-style:italic',
        )
        self.assertRegex(CSS, r"\.suggest\{[^}]*font-style:italic;font-weight:500")
        self.assertIn(".hero .suggest{margin:.15em 0 1.35em;font-size:1rem;font-weight:500;", CSS)
        for cdn in ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net"):
            self.assertNotIn(cdn, CSS)

    def test_official_planner_and_one_piece_are_observed(self):
        official = next(s for s in self.cfg["stores"] if s["id"] == "1101")
        by_key = {p["source_key"]: p for p in official["products"]}
        self.assertEqual(by_key["pb27_jan"]["canonical"], "planner-a6-en")
        self.assertEqual(by_key["pb27_jan"]["url"], PLANNER)
        self.assertEqual(by_key["pb27_jan"]["label"], "Planner A6 book (English)")
        self.assertEqual(by_key["ob27_op"]["canonical"], "original-a6-jp-one-piece")
        self.assertEqual(by_key["ob27_op"]["url"], ONE_PIECE)
        self.assertIn("One Piece", by_key["ob27_op"]["label"])

        event_urls = {c["url"] for c in self.changes}
        for url, canonical in ((PLANNER, "planner-a6-en"), (ONE_PIECE, "original-a6-jp-one-piece")):
            row = self.by_url[url]
            self.assertEqual(row["store_id"], "1101")
            self.assertEqual(row["canonical"], canonical)
            self.assertEqual(row["status"], "in_stock")
            self.assertEqual(row["method"], "1101 items.json")
            self.assertIsNone(row["error"])
            # first_seen/status_since stay at the first observed time; later checker
            # runs update checked_at only.
            self.assertEqual(row["first_seen"], "2026-11-18T04:25:57+00:00")
            self.assertEqual(row["status_since"], "2026-11-18T04:25:57+00:00")
            self.assertGreaterEqual(row["checked_at"], row["first_seen"])
            self.assertNotIn(url, event_urls)

    def test_official_rows_render_on_their_pages(self):
        planner = (ROOT / "site" / "hobonichi-techo-2027-planner-a6" / "index.html").read_text()
        one = (ROOT / "site" / "hobonichi-techo-2027-original-a6" / "one-piece-edition" / "index.html").read_text()
        self.assertIn(PLANNER, planner)
        self.assertIn("Hobonichi Online Store", planner)
        self.assertIn(ONE_PIECE, one)
        self.assertIn("Hobonichi Online Store", one)


if __name__ == "__main__":
    unittest.main()
