"""Four Hobonichi shops added Nov 23, 2026 (owner t1796u), and the shop count without link-only shops.

Every URL came from the shop's own public /products.json and was then read once with the live checker.
The shops are on Hobonichi's official 2027 retailer list (placelist_en.json). Hobonichi only: no ink,
no dot grid, and never a Traveler's Company, MIDORI or Designphil item.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402
import checker  # noqa: E402

NEW = {"hunterpaper": ("Hunter Paper Co", "UK", "hunterpaperco.com"),
       "zakkajoy": ("Zakka Joy", "US", "zakkajoy.com"),
       "colorswatch": ("ColorSwatch", "US", "mycolorswatch.com"),
       "greenstar": ("Greenstar Paperie", "US", "www.greenstarpaperie.com")}
BANNED = re.compile(r"midori|traveler|designphil|\bmd\b", re.I)
DOTGRID_TYPES = ("Dot grid notebook", "Dot grid refill")


class NewHobonichiShopsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stores = {s["id"]: s for s in cls.cfg["stores"]}
        cls.canon = {c["id"]: c for c in cls.cfg["canonical"]}
        inks = json.loads((ROOT / "inks.json").read_text())
        cls.ink_text = json.dumps(inks)

    def test_shops_are_checked_shopify_hobonichi_only(self):
        for sid, (name, country, host) in NEW.items():
            s = self.stores[sid]
            self.assertEqual((s["name"], s["country"], s["platform"]), (name, country, "shopify"))
            self.assertFalse(s.get("link_only"))
            self.assertNotIn("brand", s)
            self.assertEqual(s["cols"], ["hobonichi"])
            self.assertTrue(s["products"])
            self.assertNotIn(f'"{sid}"', self.ink_text)  # no ink rows

    def test_each_listing_is_a_tracked_hobonichi_product_on_the_shops_own_host(self):
        for sid, (_n, _c, host) in NEW.items():
            seen = set()
            for p in self.stores[sid]["products"]:
                c = self.canon[p["canonical"]]
                self.assertNotIn(c["type"], DOTGRID_TYPES, p["url"])
                self.assertEqual(p["label"], c["label"])
                self.assertTrue(p["url"].startswith(f"https://{host}/products/"), p["url"])
                self.assertIsNone(BANNED.search(p["url"] + " " + p["source_title"]), p["url"])
                self.assertNotIn(p["canonical"], seen, p["url"])
                seen.add(p["canonical"])
                if "?variant=" in p["url"]:
                    self.assertEqual(p["url"].split("?variant=")[1], str(p["variant_id"]))

    def test_counts_per_shop(self):
        counts = {sid: len(self.stores[sid]["products"]) for sid in NEW}
        self.assertEqual(counts, {"hunterpaper": 59, "zakkajoy": 18, "colorswatch": 11, "greenstar": 2})

    def test_shop_totals_leave_out_link_only_shops(self):
        self.assertFalse(site.COUNT_LINK_ONLY_IN_SHOP_TOTALS)
        link_only = {s["id"] for s in self.cfg["stores"] if s.get("link_only")}
        self.assertEqual(link_only, {"blesket", "milligram", "kinousa", "kinosg", "notebooktherapy"})  # Laywine's checked again Nov 26
        checked = {s["id"] for s in self.cfg["stores"]
                   if s["products"] and s["platform"] in ("shopify", "hobonichi") and not s.get("link_only")}
        self.assertEqual(len(checked), 28)  # Laywine's back Nov 26 (written permission); 25 after Laywine's and Notebook Therapy went link-only, +Minimaru +Take Note

    def test_a_new_listing_is_a_first_observation_not_a_restock(self):
        rec = dict(checked_at="2026-11-23T09:00:00+00:00", status="in_stock", store_id="zakkajoy", store="Zakka Joy",
                   label="Weeks · Colors: Midnight Blue", url="https://zakkajoy.com/products/x")
        changes = checker.note_transition(None, rec, [])
        self.assertEqual(changes, [])
        self.assertEqual(rec["first_seen"], rec["status_since"])


if __name__ == "__main__":
    unittest.main()
