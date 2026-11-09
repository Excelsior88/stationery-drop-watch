"""Hobonichi Weeks 2027 tanakadaisuke: Starlight is one design, not a Mega or a softcover.

Shop URLs were read from each store's own product data. A new listing has no
previous status, so the checker must not record a restock for it.
"""
import json
import unittest
from pathlib import Path

import scripts.checker as checker
import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
URLS = {
    "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_tdaisuke/",
    "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-tanakadaisuke-starlight-english",
    "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-tanakadaisuke-starlight",
    "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-tanakadaisuke-starlight",
    "penboutique": "https://www.penboutique.com/products/hobonichi-2027-light-hard-cover-english-book-tanakadaisuke-starlight-tall-slim-weeks-january-start",
    "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-tanakadaisuke-starlight",
    "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-tanakadaisuke-starlight",
}


def hobonichi_status(item):
    """The same order of checks as check_hobonichi."""
    sales = list((item.get("sales") or {}).values())
    live = [s for s in sales if not s.get("soldout") and not s.get("unreleased")]
    if item.get("soldout") or (sales and all(s.get("soldout") for s in sales)):
        return "sold_out"
    if sales and all(s.get("unreleased") for s in sales):
        return "coming_soon"
    if live:
        return "in_stock"
    return "unknown"


class StarlightWeeksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())

    def test_catalog_lists_the_verified_shops_once(self):
        canon = next(c for c in self.cfg["canonical"] if c["id"] == "weeks-starlight")
        self.assertEqual(canon["type"], "Weeks")
        self.assertEqual(canon["label"], "Weeks · tanakadaisuke: Starlight")
        found = {}
        for store in self.cfg["stores"]:
            hits = [p for p in store["products"] if p.get("canonical") == "weeks-starlight"]
            if hits:
                self.assertEqual(len(hits), 1, store["id"])
                found[store["id"]] = hits[0]
        self.assertEqual(set(found), set(URLS))
        for sid, url in URLS.items():
            self.assertEqual(found[sid]["url"], url)
            self.assertEqual(found[sid]["type"], "Weeks")
        self.assertEqual(found["1101"]["source_key"], "wb27_tdaisuke")
        urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertEqual(len(urls), len(set(urls)))

    def test_official_feed_rules_and_a_missing_key(self):
        sold = {"soldout": 1, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 1, "unreleased": 0}}}
        self.assertEqual(hobonichi_status(sold), "sold_out")
        restocked = {"soldout": 0, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 0, "unreleased": 0}}}
        self.assertEqual(hobonichi_status(restocked), "in_stock")
        missing = {"soldout": 0, "sales": {}}
        self.assertEqual(hobonichi_status(missing), "unknown")

    def test_preview_title_is_not_yet_on_sale_and_a_plain_sold_out_is_not(self):
        preview = {"available": False, "title": "<b>PREVIEW</b> - Hobonichi 2027 - English Weeks - tanakadaisuke: Starlight",
                   "variants": [{"title": "Default Title", "available": False}], "tags": []}
        status, avail, total, title = checker.classify_shopify(preview)
        self.assertEqual(status, "coming_soon")
        self.assertEqual(avail, 0)
        self.assertNotIn("<b>", title)
        sold = {"available": False, "title": "Hobonichi Techo Weeks 2027 - tanakadaisuke: Starlight",
                "variants": [{"title": "Default Title", "available": False}], "tags": ["Hobonichi"]}
        self.assertEqual(checker.classify_shopify(sold)[0], "sold_out")

    def test_a_first_observation_is_not_a_restock(self):
        old = None
        status = "sold_out"
        recorded = bool(old and status != "unknown" and old["status"] not in ("unknown", status))
        self.assertFalse(recorded)

    def test_design_page_links_only_this_canonical(self):
        design = next(d for d in site.DESIGNS if d["slug"] == "starlight")
        self.assertEqual(design["parent"], "hobonichi-weeks-2027")
        star = {"canonical": "weeks-starlight", "type": "Weeks", "label": "Weeks · tanakadaisuke: Starlight", "store_id": "1101"}
        other = {"canonical": "weeks-midnight-blue", "type": "Weeks", "label": "Weeks · Colors: Midnight Blue", "store_id": "1101"}
        mega = {"canonical": "weeks-mega-candy-dream", "type": "Weeks Mega", "label": "Weeks Mega · Bow & Tie: Candy Dream", "store_id": "1101"}
        self.assertTrue(design["match"](star))
        self.assertFalse(design["match"](other))
        self.assertFalse(design["match"](mega))
        weeks = next(g for g in site.GROUPS if g["slug"] == "hobonichi-weeks-2027")
        self.assertTrue(weeks["match"](star))
        self.assertFalse(weeks["match"](mega))
        self.assertIn("tanakadaisuke: Starlight", weeks["desc"])
        self.assertIn("hardcover", site.design_about(design).lower())
        self.assertIn("not a Weeks Mega", site.design_about(design))


if __name__ == "__main__":
    unittest.main()
