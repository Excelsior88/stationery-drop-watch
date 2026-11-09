"""Replacements for the five dead Omoi listings, plus Floral Remedy.

Omoi's own URLs stay. New shop URLs were read from each store's product data.
Checker tests call check_hobonichi, classify_shopify, and main.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.checker as checker
import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
OMOI = {
    "mega": "https://omoionline.com/products/hobonichi-techo-2027-weeks-mega-colors-planner-midnight-blue",
    "a5": "https://omoionline.com/products/hobonichi-techo-2027-hon-a5-slash-planner-navy",
    "a6": "https://omoionline.com/products/hobonichi-techo-2027-hon-a6-slash-planner-navy",
    "plaid": "https://omoionline.com/products/hobonichi-techo-2027-weeks-shirt-fabric-planner-graph-plaid",
    "jade": "https://omoionline.com/products/hobonichi-techo-2027-weeks-paper-series-planner-jade",
}
JENNI_CONFLICT = "https://www.jennibick.com/products/hobonichi-techo-a6-hon-2027-slash-navy"
JETPENS = "https://www.jetpens.com/Hobonichi-Techo-Weeks-English-Liberty-Fabrics-Floral-Remedy-2027-Jan-Start/pd/54089"
OLD_SEEN = "2026-10-25T21:41:13+00:00"


class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.ok = True
        self.status_code = 200
        self.text = ""
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


def _shopify(title, available):
    return {"title": title, "available": available, "tags": [],
            "variants": [{"id": 1, "title": "Default Title", "available": available}]}


class OmoiGapsAndFloralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())

    def _rows(self, cid):
        found = {}
        for store in self.cfg["stores"]:
            hits = [p for p in store["products"] if p.get("canonical") == cid]
            if hits:
                found[store["id"]] = hits
        return found

    def test_catalog_keeps_the_dead_omoi_urls_and_adds_exact_listings(self):
        urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertNotIn(JENNI_CONFLICT, urls)
        self.assertNotIn(JETPENS, urls)
        jet = next(s for s in self.cfg["stores"] if s["id"] == "jetpens")
        self.assertEqual(jet["products"], [])
        self.assertEqual(jet["platform"], "blocked")
        for url in OMOI.values():
            self.assertIn(url, urls)
        omoi = next(s for s in self.cfg["stores"] if s["id"] == "omoi")
        by_url = {p["url"]: p for p in omoi["products"]}
        self.assertEqual(by_url[OMOI["mega"]]["canonical"], "weeks-mega-midnight-blue")
        self.assertEqual(by_url[OMOI["a5"]]["canonical"], "hon-a5-slash-navy")
        self.assertEqual(by_url[OMOI["a6"]]["canonical"], "hon-a6-slash-navy")
        self.assertEqual(by_url[OMOI["plaid"]]["canonical"], "weeks-shirt-graph-plaid")
        self.assertEqual(by_url[OMOI["jade"]]["canonical"], "weeks-paper-frosty-jade")
        self.assertEqual(by_url[OMOI["plaid"]]["url"], OMOI["plaid"])
        mega = self._rows("weeks-mega-midnight-blue")
        self.assertIn("1101", mega)
        self.assertEqual(mega["1101"][0]["source_key"], "wb27_m_colorsmblue")
        self.assertEqual(mega["1101"][0]["type"], "Weeks Mega")
        a6 = self._rows("hon-a6-slash-navy")
        self.assertEqual(len(a6["penboutique"]), 2)
        titles = {p["source_title"] for p in a6["penboutique"]}
        self.assertTrue(any("Japanese" in t for t in titles))
        self.assertTrue(any("English" in t for t in titles))
        floral = self._rows("weeks-floral-remedy")
        self.assertEqual(floral["1101"][0]["source_key"], "wb27_libertyfloral")
        self.assertNotIn("mega", floral["yoseka"][0]["url"])
        self.assertNotIn("cover", floral["atlas"][0]["url"])

    def test_designs_do_not_absorb_covers_mega_or_the_other_size(self):
        floral = next(d for d in site.DESIGNS if d["slug"] == "floral-remedy")
        jade = next(d for d in site.DESIGNS if d["slug"] == "paper-series-jade")
        plaid = next(d for d in site.DESIGNS if d["slug"] == "shirt-fabric-graph-plaid")
        a5 = next(d for d in site.DESIGNS if d["slug"] == "a5-slash-navy")
        a6 = next(d for d in site.DESIGNS if d["slug"] == "a6-slash-navy")
        book = {"canonical": "weeks-floral-remedy", "type": "Weeks", "label": "Weeks · Liberty Fabrics: Floral Remedy", "url": "https://example.test/floral"}
        cover = {"canonical": None, "type": "Cover", "label": "Weeks cover · Liberty Fabrics: Michelle", "url": "https://example.test/cover"}
        mega = {"canonical": "weeks-mega-midnight-blue", "type": "Weeks Mega", "label": "Weeks Mega · Colors: Midnight Blue", "url": "https://example.test/mega"}
        self.assertTrue(floral["match"](book))
        self.assertFalse(floral["match"](cover))
        self.assertFalse(floral["match"](mega))
        self.assertTrue(jade["match"]({"canonical": "weeks-paper-frosty-jade", "type": "Weeks", "label": "Weeks · Paper Series: Frosty Jade", "url": "x"}))
        self.assertTrue(jade["match"]({"canonical": None, "type": "Weeks", "label": "old", "url": OMOI["jade"]}))
        self.assertFalse(jade["match"]({"canonical": None, "type": "Weeks", "label": "Paper Series: Black Argyle", "url": "y"}))
        self.assertTrue(plaid["match"]({"canonical": None, "type": "Weeks", "label": "old", "url": OMOI["plaid"]}))
        self.assertFalse(plaid["match"]({"canonical": None, "type": "Cover", "label": "Shirt Fabric cover", "url": "z"}))
        self.assertTrue(a5["match"]({"canonical": "hon-a5-slash-navy", "type": "HON", "url": "a", "label": "HON A5"}))
        self.assertFalse(a5["match"]({"canonical": "hon-a6-slash-navy", "type": "HON", "url": "b", "label": "HON A6"}))
        self.assertTrue(a6["match"]({"canonical": None, "type": "HON", "url": OMOI["a6"], "label": "old"}))
        self.assertIn("Frosty Jade", site.design_about(jade))
        self.assertIn("not a Weeks cover", site.design_about(floral))
        self.assertIn("JetPens blocks automated checks", site.design_about(floral))
        self.assertIn("Japanese-book listing", site.design_about(a6))

    def test_preview_available_false_is_not_yet_on_sale_and_a_live_variant_is_in_stock(self):
        preview = _shopify("<b>PREVIEW</b> - Hobonichi 2027 - English Weeks - Liberty Fabrics: Floral Remedy", False)
        status, _a, _t, title = checker.classify_shopify(preview)
        self.assertEqual(status, "coming_soon")
        self.assertNotIn("<b>", title)
        live = _shopify("<b>PREVIEW</b> - Hobonichi 2027 - A6 HON ENGLISH - Slash (Navy)", True)
        self.assertEqual(checker.classify_shopify(live)[0], "in_stock")

    def test_official_one_language_is_in_stock_and_a_missing_key_stays_unknown(self):
        store = {"id": "1101", "name": "Hobonichi", "platform": "hobonichi", "url": "https://www.1101.com/store/techo/en/",
                 "products": [{"canonical": "weeks-floral-remedy", "label": "Weeks · Liberty Fabrics: Floral Remedy",
                               "type": "Weeks", "url": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_libertyfloral/",
                               "source_key": "wb27_libertyfloral", "source_title": "Floral Remedy"}]}
        both_live = {"soldout": 0, "sales": {"m": {"soldout": 0, "unreleased": 0}, "me": {"soldout": 0, "unreleased": 0}}}
        english_out = {"soldout": 0, "sales": {"m": {"soldout": 0, "unreleased": 0}, "me": {"soldout": 1, "unreleased": 0}}}

        def host(item):
            class Host:
                def __init__(self, base):
                    pass
                def get(self, url, check_robots=True):
                    return _Resp({"items": {"wb27_libertyfloral": item} if item is not None else {}})
            return Host

        with patch.object(checker, "Host", host(both_live)):
            live = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", host(english_out)):
            jp = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", host(None)):
            missing = checker.check_hobonichi(store)[0]
        self.assertEqual(live["status"], "in_stock")
        self.assertEqual(jp["status"], "in_stock")
        self.assertEqual(jp["available_variants"], 1)
        self.assertEqual(missing["status"], "unknown")

    def test_replacing_nothing_keeps_omoi_history_and_a_new_url_is_not_a_restock(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "data").mkdir()
        old_url = OMOI["plaid"]
        new_url = "https://www.atlasstationers.com/products/hobonichi-techo-weeks-shirt-fabric-graph-plaid"
        stores = {"stores": [
            {"id": "omoi", "name": "Omoi Zakka Shop", "platform": "shopify", "url": "https://omoionline.com/",
             "products": [{"canonical": "weeks-shirt-graph-plaid", "label": "Weeks · Shirt Fabric: Graph Plaid",
                           "type": "Weeks", "url": old_url, "source_title": "old"}]},
            {"id": "atlas", "name": "Atlas Stationers", "platform": "shopify", "url": "https://www.atlasstationers.com/",
             "products": [{"canonical": "weeks-shirt-graph-plaid", "label": "Weeks · Shirt Fabric: Graph Plaid",
                           "type": "Weeks", "url": new_url, "source_title": "new"}]},
        ]}
        (tmp / "stores.json").write_text(json.dumps(stores))
        (tmp / "data" / "stock.json").write_text(json.dumps({"products": [{
            "url": old_url, "status": "unknown", "canonical": None,
            "first_seen": OLD_SEEN, "status_since": OLD_SEEN}]}))
        (tmp / "data" / "changes.json").write_text("[]")

        class Host:
            def __init__(self, base):
                self.base = base
            def get(self, url, check_robots=True):
                if "omoionline" in url:
                    raise checker.requests.HTTPError("404")
                return _Resp(_shopify("Hobonichi Techo Weeks - Shirt Fabric: Graph Plaid", False))

        with patch.object(checker, "ROOT", tmp), patch.object(checker, "Host", Host):
            checker.main()
        rows = {p["url"]: p for p in json.loads((tmp / "data" / "stock.json").read_text())["products"]}
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        self.assertEqual(rows[old_url]["status"], "unknown")
        self.assertEqual(rows[old_url]["first_seen"], OLD_SEEN)
        self.assertEqual(rows[old_url]["status_since"], OLD_SEEN)
        self.assertEqual(rows[old_url]["canonical"], "weeks-shirt-graph-plaid")
        self.assertEqual(rows[new_url]["status"], "sold_out")
        self.assertEqual(rows[new_url]["first_seen"], rows[new_url]["status_since"])
        self.assertEqual(changes, [])

    def test_floral_page_names_jetpens_without_a_stock_badge(self):
        floral = next(d for d in site.DESIGNS if d["slug"] == "floral-remedy")
        product = {"canonical": "weeks-floral-remedy", "type": "Weeks", "label": "Weeks · Liberty Fabrics: Floral Remedy",
                   "store_id": "1101", "store": "Hobonichi Online Store (official)",
                   "url": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_libertyfloral/",
                   "status": "in_stock", "title": "Floral Remedy",
                   "checked_at": "2026-11-09T04:00:00+00:00", "status_since": "2026-11-09T04:00:00+00:00",
                   "first_seen": "2026-11-09T04:00:00+00:00"}
        orig = site.stock["products"]
        try:
            site.stock["products"] = [product]
            doc = site.build_design(floral, site.amazon_main([product]))[1]
        finally:
            site.stock["products"] = orig
        self.assertIn('rel="canonical" href="https://stationerydropwatch.com/hobonichi-weeks-2027/floral-remedy/"', doc)
        self.assertIn(JETPENS, doc)
        self.assertIn("not a stock status", doc)
        self.assertNotIn("JetPens</a> <span class=\"region\"", doc)
        self.assertIn(">In stock<", doc)
        self.assertNotIn('class="badge sold_out"', doc)
        self.assertIn("Not checked", doc)


if __name__ == "__main__":
    unittest.main()
