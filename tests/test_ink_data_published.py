"""The drop-alert routine reads the live site data, so ink status and changes are published under /data/inks/ (no hidden rows)."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InkDataPublishedTests(unittest.TestCase):
    def test_published_files_match_data_without_hidden_rows(self):
        stock = json.loads((ROOT / "site/data/inks/stock.json").read_text())
        src = json.loads((ROOT / "data/inks/stock.json").read_text())
        self.assertEqual(len(stock["products"]), len([r for r in src["products"] if not r.get("hidden")]))
        self.assertFalse(any(r.get("hidden") for r in stock["products"]))
        self.assertTrue(all(r.get("section") == "inks" for r in stock["products"]))
        changes = json.loads((ROOT / "site/data/inks/changes.json").read_text())
        self.assertIsInstance(changes, list)
        self.assertFalse(any(c.get("hidden") for c in changes))


if __name__ == "__main__":
    unittest.main()
