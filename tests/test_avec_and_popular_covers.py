"""Cousin Avec A5 (Japanese, two-book set) and the 2027 covers on Hobonichi's first-week sales ranking.

Rows were verified against each shop's own product page; new rows are first observations (no restock alert)."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

AVEC = "cousin-avec-a5-jp"
OFFICIAL_AVEC = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/cb27_avec/"
YOSEKA_AVEC = "https://yosekastationery.com/products/hobonichi-techo-cousin-avec-2027-a5"
AVEC_SHOPS = {"1101", "atlas", "blesket", "buchan", "dromgooles", "jennibick", "journalshop", "kinousa",
              "laywines", "milligram", "mlovewell", "papermouse", "penboutique", "yoseka"}
FORBIDDEN = re.compile(r"midori|traveler|designphil|milligram:", re.I)


class AvecAndCoversTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data/stock.json").read_text())
        cls.changes = json.loads((ROOT / "data/changes.json").read_text())
        cls.rows = [(s["id"], p) for s in cls.cfg["stores"] for p in s["products"]]

    def test_avec_is_at_every_verified_shop(self):
        shops = {sid for sid, p in self.rows if p["canonical"] == AVEC}
        self.assertEqual(shops, AVEC_SHOPS)
        urls = {p["url"] for _, p in self.rows if p["canonical"] == AVEC}
        self.assertIn(OFFICIAL_AVEC, urls)
        self.assertIn(YOSEKA_AVEC, urls)
        official = next(p for sid, p in self.rows if sid == "1101" and p["canonical"] == AVEC)
        self.assertEqual(official["source_key"], "cb27_avec")

    def test_avec_label_is_japanese_a5_set(self):
        lab = next(c for c in self.cfg["canonical"] if c["id"] == AVEC)
        self.assertIn("A5", lab["label"])
        self.assertIn("Japanese", lab["label"])

    def test_avec_shares_the_cousin_page(self):
        group = next(g for g in site.GROUPS if g["slug"] == "hobonichi-techo-2027-cousin-a5")
        self.assertTrue(group["match"]({"canonical": AVEC, "type": "Book", "label": "", "store_id": "atlas"}))
        self.assertTrue(group["match"]({"canonical": "cousin-a5-en", "type": "Book", "label": "", "store_id": "atlas"}))
        self.assertFalse(group["match"]({"canonical": "original-a6-jp", "type": "Book", "label": "", "store_id": "atlas"}))

    def test_new_cover_rows_have_unique_urls_and_known_canonicals(self):
        canon = {c["id"] for c in self.cfg["canonical"]}
        urls = [p["url"] for _, p in self.rows]
        self.assertEqual(len(urls), len(set(urls)))
        for _, p in self.rows:
            self.assertIn(p["canonical"], canon)

    def test_official_cover_rows_use_english_pages_and_feed_keys(self):
        official = [p for sid, p in self.rows if sid == "1101" and re.match(r"(cover-a[56]|weeks-cover)-", p["canonical"])]
        self.assertGreaterEqual(len(official), 20)
        for p in official:
            m = re.fullmatch(r"https://www\.1101\.com/store/techo/en/2027/pc/detail_cover/((?:oc|cc|wc)27_[a-z0-9]+)/", p["url"])
            self.assertTrue(m, p["url"])
            self.assertEqual(p["source_key"], m.group(1))
            want = {"cover-a6": "oc27", "cover-a5": "cc27", "weeks-cover": "wc27"}[re.match(r"(cover-a6|cover-a5|weeks-cover)", p["canonical"]).group(1)]
            self.assertTrue(p["source_key"].startswith(want), p)

    def test_a5_covers_include_the_ranked_designs(self):
        a5 = {c["id"] for c in self.cfg["canonical"] if c["id"].startswith("cover-a5-")}
        for slug in ("yumi-kitagishi-white-cat-village", "va-blackthorn", "akiko-miyakoshi-airport", "colors-mango-latte",
                     "moomin-my-yard-pink-gray", "puppet-sunsun-s"):
            self.assertIn("cover-a5-" + slug, a5)

    def test_no_designphil_products_added(self):
        labels = " ".join(c["label"] for c in self.cfg["canonical"] if c["id"] in {p["canonical"] for _, p in self.rows if p["canonical"].startswith(("cover-a5", "weeks-cover", AVEC))})
        self.assertFalse(re.search(r"midori|traveler|designphil", labels, re.I))

    def test_new_rows_are_first_observations_only(self):
        new_canon = lambda c: c == AVEC or re.match(r"(cover-a5|weeks-cover)-", c) or (
            c.startswith("cover-a6-") and c not in {"cover-a6-moomin", "cover-a6-white-cat-house", "cover-a6-tragen-black",
                                                    "cover-a6-mina-felice", "cover-a6-beautiful-people-green"})
        new_urls = {p["url"] for _, p in self.rows if new_canon(p["canonical"]) and p["canonical"] != "cover-a5-beautiful-people-pink"}
        rows = [r for r in self.stock["products"] if r["url"] in new_urls]
        self.assertEqual(len(rows), len(new_urls))
        for r in rows:
            self.assertEqual(r["first_seen"], r["checked_at"], r["url"])
            self.assertEqual(r["status_since"], r["checked_at"], r["url"])
            self.assertIn(r["status"], ("in_stock", "sold_out"), r["url"])
        self.assertFalse([c for c in self.changes if c["url"] in new_urls])


if __name__ == "__main__":
    unittest.main()
