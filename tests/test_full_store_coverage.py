"""New coverage rows are a first observation only.

Shop URLs were read from each store's catalog and then checked with the same
Shopify or Hobonichi reader the live checker uses. A first observation sets
first_seen and writes no event. Existing rows and data/changes.json stay as they were.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_SEA = "https://www.atlasstationers.com/products/hobonichi-techo-weeks-colors-sea-glass"
FELICE = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_minafelice/"
FOREST = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_classicfgreen/"


class FullStoreCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data" / "stock.json").read_text())
        cls.changes = json.loads((ROOT / "data" / "changes.json").read_text())

    def test_new_rows_are_baseline_and_old_history_stays(self):
        urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertEqual(len(urls), len(set(urls)))
        saved = {p["url"]: p for p in self.stock["products"]}
        self.assertEqual(set(saved), set(urls))
        fresh = [p for p in self.stock["products"] if p["first_seen"] == p["status_since"] and p["first_seen"] >= "2026-11-10T01"]
        self.assertGreaterEqual(len(fresh), 200)
        event_urls = {c["url"] for c in self.changes}
        for row in fresh:
            self.assertEqual(row["first_seen"], row["status_since"])
            self.assertNotEqual(row["status"], "unknown")
            self.assertNotIn(row["url"], event_urls)
        # A first observation writes no event. A later restock moves status_since, so the
        # event list may grow; a row still on its first status never appears in it.
        for row in self.stock["products"]:
            self.assertLessEqual(row["first_seen"], row["status_since"])
            if row["first_seen"] == row["status_since"]:
                self.assertNotIn(row["url"], event_urls)
        for event in self.changes:
            self.assertIn(event["url"], saved)
            self.assertNotEqual(event["from"], event["to"])
            self.assertNotIn(event["from"], ("unknown", None, ""))
            self.assertNotIn(event["to"], ("unknown", None, ""))
            self.assertGreater(event["at"], saved[event["url"]]["first_seen"])
        sea = saved[OLD_SEA]
        self.assertEqual(sea["first_seen"], "2026-10-25T21:40:57+00:00")
        self.assertEqual(sea["status_since"], "2026-10-25T21:40:57+00:00")
        self.assertEqual(sea["status"], "sold_out")

    def test_official_keys_and_blocked_stores(self):
        official = {p["source_key"]: p for s in self.cfg["stores"] if s["id"] == "1101" for p in s["products"]}
        self.assertEqual(official["oc27_minafelice"]["canonical"], "cover-a6-mina-felice")
        self.assertEqual(official["oc27_minafelice"]["url"], FELICE)
        self.assertEqual(official["wb27_classicfgreen"]["canonical"], "weeks-leather-forest")
        self.assertEqual(official["wb27_classicfgreen"]["url"], FOREST)
        self.assertEqual(official["wb27_moominsnufkin"]["canonical"], "weeks-moomin-snufkin")
        self.assertEqual(official["wb27_m_colorspred"]["canonical"], "weeks-mega-poppy-red")
        jet = next(s for s in self.cfg["stores"] if s["id"] == "jetpens")
        nanami = next(s for s in self.cfg["stores"] if s["id"] == "nanami")
        self.assertEqual(jet["products"], [])
        self.assertEqual(jet["platform"], "blocked")
        self.assertEqual(nanami["products"], [])
        self.assertEqual(nanami["platform"], "robots-disallow")
        felice = [p for s in self.cfg["stores"] for p in s["products"] if p.get("canonical") == "cover-a6-mina-felice"]
        tragen = [p for s in self.cfg["stores"] for p in s["products"] if p.get("canonical") == "cover-a6-tragen-black"]
        self.assertGreaterEqual(len(felice), 8)
        self.assertGreaterEqual(len(tragen), 7)
        self.assertTrue(all("a5" not in p["url"] and "pouch" not in p["url"] for p in tragen))
