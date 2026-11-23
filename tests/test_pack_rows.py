"""pack_rows shrinks the tracker's JSON rows; app.js must be able to rebuild exactly the same rows."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402


def unpack(packed):
    if isinstance(packed, list):
        return packed
    return [{k: (packed["d"][k][v] if k in packed["d"] else v) for k, v in zip(packed["k"], vals) if v is not None}
            for vals in packed["r"]]


class PackRowsTests(unittest.TestCase):
    ROWS = [
        {"g": "a", "s": "Shop One", "st": "in_stock", "u": "https://x/1", "fo": 0},
        {"g": "a", "s": "Shop Two", "st": "sold_out", "u": "https://x/2", "fo": 0, "on": "note"},
        {"g": "b", "s": "Shop One", "st": "sold_out", "u": "https://x/3", "fo": 1},
        {"g": "b", "s": "Shop Two", "st": "sold_out", "u": "https://x/4", "fo": 1},
        {"g": "b", "s": "Shop One", "st": "sold_out", "u": "https://x/5", "fo": 1},
        {"g": "a", "s": "Shop Two", "st": "sold_out", "u": "https://x/6", "fo": 0},
    ]

    def test_round_trip_keeps_every_row_and_key(self):
        back = unpack(json.loads(json.dumps(site.pack_rows(self.ROWS))))
        self.assertEqual(back, self.ROWS)

    def test_null_values_fall_back_to_the_plain_list(self):
        rows = [{"g": "a", "x": None}]
        self.assertEqual(site.pack_rows(rows), rows)

    def test_built_hobonichi_page_is_packed_and_smaller(self):
        html = (ROOT / "site/hobonichi-restock-tracker/index.html").read_text()
        data = json.loads(re.search(r'<script id="stock-data" type="application/json">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
        self.assertIsInstance(data, dict)
        self.assertGreater(len(unpack(data)), 400)
        self.assertLess(len(html), 750_000)  # Nov 23, 2026: 750_000 after Minimaru and Take Note (98 rows); 700_000 after 95 rows from four new Hobonichi shops; raised from 420_000 when Avec and 20+ popular covers were added (gzip ~47 KB)

    def test_app_js_decodes_both_formats(self):
        js = (ROOT / "site/assets/app.js").read_text()
        self.assertIn("Array.isArray(raw)", js)
        self.assertIn("raw.d[k]", js)


if __name__ == "__main__":
    unittest.main()
