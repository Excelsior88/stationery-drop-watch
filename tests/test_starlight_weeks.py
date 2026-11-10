"""Hobonichi Weeks 2027 tanakadaisuke: Starlight is one design, not a Mega or a softcover.

Shop URLs were read from each store's own product data. Checker tests call
check_hobonichi and main with a stand-in host, so a change in those functions
fails here.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-tanakadaisuke-starlight-eng-tall-slim-jan-start",
    "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-tanakadaisuke-starlight",
    "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-starlight-english-tall-slim-jan-start",
}


class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.ok = True
        self.status_code = 200
        self.text = ""
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


def _host(payload=None, error=None):
    class Host:
        def __init__(self, base):
            self.base = base

        def get(self, url, check_robots=True):
            if error:
                raise error
            return _Resp(payload)

    return Host


def _star_store():
    return {"id": "1101", "name": "Hobonichi Online Store (official)", "platform": "hobonichi",
            "url": "https://www.1101.com/store/techo/en/", "products": [{
                "canonical": "weeks-starlight", "label": "Weeks · tanakadaisuke: Starlight", "type": "Weeks",
                "url": URLS["1101"], "source_key": "wb27_tdaisuke", "source_title": "tanakadaisuke: Starlight"}]}


def _feed(item):
    return {"items": {"wb27_tdaisuke": item} if item is not None else {}}


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

    def test_check_hobonichi_uses_the_feed_and_a_failed_fetch_stays_unknown(self):
        store = _star_store()
        sold = {"soldout": 1, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 1, "unreleased": 0}}}
        one_live = {"soldout": 0, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 0, "unreleased": 0}}}
        with patch.object(checker, "Host", _host(_feed(sold))):
            both = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", _host(_feed(one_live))):
            english = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", _host(_feed(None))):
            missing = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", _host(error=TimeoutError("timed out"))):
            failed = checker.check_hobonichi(store)[0]
        self.assertEqual(both["status"], "sold_out")
        self.assertEqual(both["available_variants"], 0)
        self.assertEqual(both["total_variants"], 2)
        self.assertEqual(english["status"], "in_stock")
        self.assertEqual(english["available_variants"], 1)
        self.assertEqual(missing["status"], "unknown")
        self.assertEqual(missing["error"], "item key not in feed")
        self.assertEqual(failed["status"], "unknown")
        self.assertIn("TimeoutError", failed["error"])

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

    def test_main_does_not_record_a_restock_for_a_new_listing(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "stores.json").write_text(json.dumps({"stores": [_star_store()]}))
        with patch.object(checker, "ROOT", tmp), patch.object(checker, "Host", _host(_feed({
                "soldout": 1, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 1, "unreleased": 0}}}))):
            checker.main()
        stock = json.loads((tmp / "data" / "stock.json").read_text())
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        self.assertEqual([p["url"] for p in stock["products"]], [URLS["1101"]])
        self.assertEqual(stock["products"][0]["status"], "sold_out")
        self.assertEqual(stock["products"][0]["first_seen"], stock["products"][0]["status_since"])
        self.assertEqual(changes, [])
        self.assertEqual(stock["summary"]["sold_out"], 1)

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
        about = site.design_about(design)
        self.assertIn("2027 Weeks hardcover book, January start, Monday start", about)
        self.assertIn("Hobonichi's own listing includes the English and Japanese books", about)
        self.assertIn("The other shops on this page sell the English book", about)
        self.assertNotIn("The shop listings here are the English book", about)
        self.assertIn("not a Weeks Mega", about)


if __name__ == "__main__":
    unittest.main()
