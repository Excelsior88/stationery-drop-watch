"""Pink Sapphire, Sea Glass, Welcome to the V&A, and Leicester are separate regular Weeks books.

Shop URLs were read from each store's own product data. Checker tests call
check_hobonichi, classify_shopify, classify_shopify_variant, and main. Build
tests call the page builders. A copied status rule would not fail these.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.checker as checker
import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
PINK = "weeks-pink-sapphire"
SEA = "weeks-sea-glass"
WELCOME = "weeks-va-welcome"
LEICESTER = "weeks-va-leicester"
URLS = {
    PINK: {
        "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorspsapphire/",
        "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-colors-pink-sapphire-english",
        "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-colors-pink-sapphire",
        "baum": "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43546059636803",
        "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-colors-pink-sapphire",
        "penboutique": "https://www.penboutique.com/products/hobonichi-2027-weeks-colors-pink-sapphire-english-january-start",
        "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-colors-pink-sapphire",
        "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-colors-pink-sapphire",
        "kinousa": "https://usa.kinokuniya.com/products/4580812709712",
        "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-colors-pink-sapphire-eng-tall-slim-jan-start-planner",
        "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-colors-pink-sapphire",
        "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-pink-sapphire-english-tall-slim-jan-start",
    },
    SEA: {
        "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorssglass/",
        "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-colors-sea-glass-english",
        "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-colors-sea-glass",
        "baum": "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43545928269891",
        "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-colors-sea-glass",
        "penboutique": "https://www.penboutique.com/products/hobonichi-2027-weeks-colors-sea-glass-english-january-start",
        "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-colors-sea-glass",
        "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-colors-sea-glass",
        "kinousa": "https://usa.kinokuniya.com/products/4580812709743",
        "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-colors-sea-glass-eng-tall-slim-jan-start-planner",
        "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-colors-sea-glass",
        "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-sea-glass-english-tall-slim-jan-start",
    },
    WELCOME: {
        "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_vawelcome/",
        "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-v-a-series-welcome-to-the-v-a-english",
        "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-v-a-series-welcome-to-the-v-a",
        "bobo": "https://bobodesignstudio.com/products/hobonichi-techo-2027-weeks-v-a-series-welcome-to-the-v-a",
        "baum": "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43546082246723",
        "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-v-a-series-welcome-to-the-v-a",
        "penboutique": "https://www.penboutique.com/products/hobonichi-weeks-2027-va-series-welcome-to-the-va",
        "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-v-a-series-welcome-to-the-v-a",
        "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-v-a-series-welcome-to-the-v-a",
        "kinousa": "https://usa.kinokuniya.com/products/4580812709880",
        "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-v-a-series-welcome-to-the-v-a-eng-tall-slim-jan-start",
        "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-v-a-series-welcome-to-the-v-a",
        "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-welcome-to-the-v-a-english-tall-slim-jan-start",
    },
    LEICESTER: {
        "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_valeicester/",
        "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-v-a-series-leicester-english",
        "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-v-a-series-leicester",
        "bobo": "https://bobodesignstudio.com/products/hobonichi-techo-2027-weeks-v-a-series-leicester",
        "baum": "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english?variant=43546076676163",
        "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-v-a-series-leicester",
        "penboutique": "https://www.penboutique.com/products/hobonichi-techo-2027-weeks-va-leicester",
        "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-v-a-series-leicester",
        "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-v-a-series-leicester",
        "kinousa": "https://usa.kinokuniya.com/products/4580812709873",
        "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-v-a-series-leicester-eng-tall-slim-jan-start-planner",
        "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-v-a-series-leicester",
        "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-leicester-english-tall-slim-jan-start",
    },
}
KEYS = {PINK: "wb27_colorspsapphire", SEA: "wb27_colorssglass", WELCOME: "wb27_vawelcome", LEICESTER: "wb27_valeicester"}
BAUM_MIXED = "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english"
ATLAS_PINK = URLS[PINK]["atlas"]
OLD_SEEN = "2026-10-25T21:41:00+00:00"
OLD_SINCE = "2026-11-06T23:17:52+00:00"


class _Resp:
    def __init__(self, payload=None, text=""):
        self._payload = payload if payload is not None else {}
        self.ok = True
        self.status_code = 200
        self.text = text
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


def _shopify(title, variants):
    return {"title": title, "available": any(v["available"] for v in variants), "variants": variants, "tags": ["Hobonichi"]}


class WeeksColorsVaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data" / "stock.json").read_text())

    def test_catalog_keeps_each_design_and_the_old_urls(self):
        labels = {
            PINK: "Weeks · Colors: Pink Sapphire",
            SEA: "Weeks · Colors: Sea Glass",
            WELCOME: "Weeks · V&A: Welcome to the V&A",
            LEICESTER: "Weeks · V&A: Leicester",
        }
        for cid, label in labels.items():
            canon = next(c for c in self.cfg["canonical"] if c["id"] == cid)
            self.assertEqual(canon["type"], "Weeks")
            self.assertEqual(canon["label"], label)
        found = {cid: {} for cid in URLS}
        for store in self.cfg["stores"]:
            for cid, urls in URLS.items():
                hits = [p for p in store["products"] if p.get("canonical") == cid]
                if hits:
                    self.assertEqual(len(hits), 1, store["id"] + " " + cid)
                    found[cid][store["id"]] = hits[0]
        for cid, urls in URLS.items():
            self.assertEqual(set(found[cid]), set(urls))
            for sid, url in urls.items():
                row = found[cid][sid]
                self.assertEqual(row["url"], url)
                self.assertEqual(row["type"], "Weeks")
                self.assertNotIn("mega", row["url"])
            self.assertEqual(found[cid]["1101"]["source_key"], KEYS[cid])
        self.assertEqual(found[PINK]["baum"]["variant_id"], 43546059636803)
        self.assertEqual(found[SEA]["baum"]["variant_id"], 43545928269891)
        self.assertEqual(found[WELCOME]["baum"]["variant_id"], 43546082246723)
        self.assertEqual(found[LEICESTER]["baum"]["variant_id"], 43546076676163)
        baum = next(s for s in self.cfg["stores"] if s["id"] == "baum")
        self.assertFalse(any(p["url"] == BAUM_MIXED for p in baum["products"]))
        absent = {"laywines", "kinosg", "omoi", "bobo"}
        self.assertTrue(absent.isdisjoint(found[PINK]))
        self.assertTrue(absent.isdisjoint(found[SEA]))
        self.assertNotIn("bobo", found[PINK])
        self.assertIn("bobo", found[WELCOME])
        urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertEqual(len(urls), len(set(urls)))
        saved = {p["url"]: p for p in self.stock["products"]}
        for url, seen, since in (
            (URLS[SEA]["atlas"], "2026-10-25T21:40:57+00:00", "2026-10-25T21:40:57+00:00"),
            (ATLAS_PINK, OLD_SEEN, OLD_SINCE),
            (URLS[WELCOME]["bobo"], "2026-10-25T21:40:57+00:00", "2026-10-25T21:40:57+00:00"),
            (URLS[LEICESTER]["bobo"], "2026-10-25T21:41:00+00:00", "2026-10-25T21:41:00+00:00"),
        ):
            self.assertEqual(saved[url]["first_seen"], seen)
            self.assertEqual(saved[url]["status_since"], since)
            self.assertEqual(saved[url]["status"], "sold_out")

    def test_official_feed_keeps_languages_distinct_and_a_failed_fetch_unknown(self):
        store = {"id": "1101", "name": "Hobonichi Online Store (official)", "platform": "hobonichi",
                 "url": "https://www.1101.com/store/techo/en/", "products": [{
                     "canonical": PINK, "label": "Weeks · Colors: Pink Sapphire", "type": "Weeks",
                     "url": URLS[PINK]["1101"], "source_key": KEYS[PINK], "source_title": "Pink Sapphire"}]}

        def feed(item):
            return {"items": {KEYS[PINK]: item} if item is not None else {}}

        def host(payload=None, error=None):
            class Host:
                def __init__(self, base):
                    self.base = base

                def get(self, url, check_robots=True):
                    if error:
                        raise error
                    return _Resp(payload)
            return Host

        both = {"soldout": 1, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 1, "unreleased": 0}}}
        english = {"soldout": 0, "sales": {"m": {"soldout": 1, "unreleased": 0}, "me": {"soldout": 0, "unreleased": 0}}}
        japanese = {"soldout": 0, "sales": {"m": {"soldout": 0, "unreleased": 0}, "me": {"soldout": 1, "unreleased": 0}}}
        with patch.object(checker, "Host", host(feed(both))):
            sold = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", host(feed(english))):
            en = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", host(feed(japanese))):
            jp = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", host(feed(None))):
            missing = checker.check_hobonichi(store)[0]
        with patch.object(checker, "Host", host(error=TimeoutError("timed out"))):
            failed = checker.check_hobonichi(store)[0]
        self.assertEqual(sold["status"], "sold_out")
        self.assertEqual(sold["available_variants"], 0)
        self.assertEqual(en["status"], "in_stock")
        self.assertEqual(en["available_variants"], 1)
        self.assertEqual(jp["status"], "in_stock")
        self.assertEqual(jp["available_variants"], 1)
        self.assertEqual(missing["status"], "unknown")
        self.assertEqual(missing["error"], "item key not in feed")
        self.assertEqual(failed["status"], "unknown")
        self.assertIn("TimeoutError", failed["error"])

    def test_a_mixed_page_is_checked_by_variant_and_preview_is_not_sold_out(self):
        mixed = _shopify("[Hobonichi 2027] Weeks (English)", [
            {"id": 43546059636803, "title": "Colors: Pink Sapphire", "public_title": "Colors: Pink Sapphire", "available": True, "sku": "Weeks27/Pink"},
            {"id": 43546076676163, "title": "V&A Series: Leicester [SOLD OUT]", "public_title": "V&A Series: Leicester [SOLD OUT]", "available": False, "sku": "Weeks27/Leicester"},
        ])
        whole, avail, total, _title = checker.classify_shopify(mixed)
        pink = checker.classify_shopify_variant(mixed, 43546059636803)
        leicester = checker.classify_shopify_variant(mixed, 43546076676163)
        self.assertEqual(whole, "unknown")
        self.assertEqual(avail, 1)
        self.assertEqual(total, 2)
        self.assertEqual(pink[0], "in_stock")
        self.assertEqual(leicester[0], "sold_out")
        self.assertIn("Pink Sapphire", pink[3])
        self.assertNotIn("Leicester", pink[3])
        preview = _shopify("<b>PREVIEW</b> - Hobonichi 2027 - English Weeks - Colors: Sea Glass",
                           [{"id": 1, "title": "Default Title", "available": False}])
        self.assertEqual(checker.classify_shopify(preview)[0], "coming_soon")
        self.assertNotIn("<b>", checker.classify_shopify(preview)[3])
        sold = _shopify("Hobonichi Techo Weeks 2027 - Colors: Sea Glass",
                        [{"id": 1, "title": "Default Title", "available": False}])
        self.assertEqual(checker.classify_shopify(sold)[0], "sold_out")
        store = {"id": "baum", "name": "Baum-kuchen", "url": "https://www.baum-kuchen.net/", "platform": "shopify",
                 "products": [{"canonical": LEICESTER, "label": "Weeks · V&A: Leicester", "type": "Weeks",
                               "url": URLS[LEICESTER]["baum"], "variant_id": 999, "source_title": "V&A Series: Leicester"}]}

        class Host:
            def __init__(self, base):
                self.base = base

            def get(self, url, check_robots=True):
                return _Resp(mixed)

        with patch.object(checker, "Host", Host):
            gone = checker.check_shopify_store(store)[0]
        self.assertEqual(gone["status"], "unknown")
        self.assertIn("variant 999", gone["error"])

    def _run_main(self, atlas_js, yoseka_js=None, fail=False):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "data").mkdir()
        products = [{
            "canonical": PINK, "label": "Weeks · Colors: Pink Sapphire", "type": "Weeks",
            "url": ATLAS_PINK, "source_title": "Hobonichi Techo Weeks - Colors: Pink Sapphire"}]
        if yoseka_js is not None:
            products.append({
                "canonical": PINK, "label": "Weeks · Colors: Pink Sapphire", "type": "Weeks",
                "url": URLS[PINK]["yoseka"], "source_title": "Hobonichi Techo Weeks 2027 - Colors: Pink Sapphire"})
        stores = {"stores": [
            {"id": "atlas", "name": "Atlas Stationers", "platform": "shopify", "url": "https://www.atlasstationers.com/", "products": [products[0]]},
        ]}
        if yoseka_js is not None:
            stores["stores"].append({"id": "yoseka", "name": "Yoseka Stationery", "platform": "shopify",
                                     "url": "https://yosekastationery.com/", "products": [products[1]]})
        (tmp / "stores.json").write_text(json.dumps(stores))
        prior = {"url": ATLAS_PINK, "status": "sold_out", "canonical": None,
                 "label": "Hobonichi Techo Weeks - Colors: Pink Sapphire",
                 "first_seen": OLD_SEEN, "status_since": OLD_SINCE}
        (tmp / "data" / "stock.json").write_text(json.dumps({"products": [prior]}))
        old_change = {"at": OLD_SINCE, "url": ATLAS_PINK, "from": "in_stock", "to": "sold_out", "store": "Atlas Stationers"}
        (tmp / "data" / "changes.json").write_text(json.dumps([old_change]))

        class Host:
            def __init__(self, base):
                self.base = base

            def get(self, url, check_robots=True):
                if fail and "atlasstationers" in url:
                    raise TimeoutError("timed out")
                payload = atlas_js if "atlasstationers" in url else yoseka_js
                return _Resp(payload)

        with patch.object(checker, "ROOT", tmp), patch.object(checker, "Host", Host):
            checker.main()
        stock = json.loads((tmp / "data" / "stock.json").read_text())
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        return {p["url"]: p for p in stock["products"]}, changes

    def test_an_existing_listing_keeps_its_history_and_a_new_one_is_not_a_restock(self):
        sold = _shopify("Hobonichi Techo Weeks - Colors: Pink Sapphire", [{"id": 1, "title": "Default Title", "available": False}])
        live = _shopify("Hobonichi Techo Weeks 2027 - Colors: Pink Sapphire", [{"id": 1, "title": "Default Title", "available": True}])
        rows, changes = self._run_main(sold, live)
        old, new = rows[ATLAS_PINK], rows[URLS[PINK]["yoseka"]]
        self.assertEqual(old["status"], "sold_out")
        self.assertEqual(old["canonical"], PINK)
        self.assertEqual(old["first_seen"], OLD_SEEN)
        self.assertEqual(old["status_since"], OLD_SINCE)
        self.assertEqual(new["status"], "in_stock")
        self.assertEqual(new["first_seen"], new["status_since"])
        self.assertEqual(new["first_seen"], new["checked_at"])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["url"], ATLAS_PINK)
        self.assertNotIn(URLS[PINK]["yoseka"], {c["url"] for c in changes})

    def test_a_real_flip_is_still_a_restock_and_a_failed_check_is_not(self):
        live = _shopify("Hobonichi Techo Weeks - Colors: Pink Sapphire", [{"id": 1, "title": "Default Title", "available": True}])
        rows, changes = self._run_main(live)
        self.assertEqual(rows[ATLAS_PINK]["status"], "in_stock")
        self.assertEqual(rows[ATLAS_PINK]["first_seen"], OLD_SEEN)
        self.assertNotEqual(rows[ATLAS_PINK]["status_since"], OLD_SINCE)
        self.assertEqual(changes[-1]["from"], "sold_out")
        self.assertEqual(changes[-1]["to"], "in_stock")
        self.assertEqual(changes[-1]["url"], ATLAS_PINK)
        failed, same = self._run_main(_shopify("x", [{"id": 1, "title": "Default", "available": True}]), fail=True)
        self.assertEqual(failed[ATLAS_PINK]["status"], "unknown")
        self.assertEqual(failed[ATLAS_PINK]["first_seen"], OLD_SEEN)
        self.assertEqual(failed[ATLAS_PINK]["status_since"], OLD_SINCE)
        self.assertEqual(len(same), 1)

    def test_pages_keep_the_designs_apart_and_name_every_status(self):
        pink = next(d for d in site.DESIGNS if d["slug"] == "pink-sapphire")
        sea = next(d for d in site.DESIGNS if d["slug"] == "sea-glass")
        family = next(d for d in site.DESIGNS if d["slug"] == "v-and-a")
        rows = {
            PINK: {"canonical": PINK, "type": "Weeks", "label": "Weeks · Colors: Pink Sapphire"},
            SEA: {"canonical": SEA, "type": "Weeks", "label": "Weeks · Colors: Sea Glass"},
            WELCOME: {"canonical": WELCOME, "type": "Weeks", "label": "Weeks · V&A: Welcome to the V&A"},
            LEICESTER: {"canonical": LEICESTER, "type": "Weeks", "label": "Weeks · V&A: Leicester"},
        }
        mega = {"canonical": "weeks-mega-midnight-blue", "type": "Weeks Mega", "label": "Weeks Mega · Colors: Pink Sapphire"}
        mixed = {"canonical": None, "type": "Weeks", "label": "[Hobonichi 2027] Weeks (English)"}
        self.assertTrue(pink["match"](rows[PINK]))
        self.assertFalse(pink["match"](rows[SEA]))
        self.assertFalse(pink["match"](rows[WELCOME]))
        self.assertFalse(pink["match"](mega))
        self.assertFalse(pink["match"](mixed))
        self.assertTrue(sea["match"](rows[SEA]))
        self.assertFalse(sea["match"](rows[PINK]))
        self.assertTrue(family["match"](rows[WELCOME]))
        self.assertTrue(family["match"](rows[LEICESTER]))
        self.assertFalse(family["match"](rows[PINK]))
        self.assertFalse(family["match"](mega))
        for design, cid in ((pink, PINK), (sea, SEA)):
            about = site.design_about(design)
            self.assertIn("2027 Weeks hardcover book, January start, Monday start", about)
            self.assertIn("Hobonichi's own listing includes the English and Japanese books", about)
            self.assertIn("The other shops on this page sell the English book", about)
            self.assertIn("not a Weeks Mega", about)
        family_about = site.design_about(family)
        self.assertIn("Welcome to the V&A and Leicester are two separate", family_about)
        self.assertIn("named design", family_about)
        self.assertIn("Neither design is a Weeks Mega", family_about)

        def listing(cid, store_id, store, url, status):
            return {"canonical": cid, "type": "Weeks", "label": rows[cid]["label"], "store_id": store_id,
                    "store": store, "url": url, "status": status, "title": rows[cid]["label"],
                    "checked_at": "2026-11-09T03:00:00+00:00", "status_since": "2026-11-09T03:00:00+00:00",
                    "first_seen": "2026-11-09T03:00:00+00:00"}

        products = [
            listing(PINK, "1101", "Hobonichi Online Store (official)", URLS[PINK]["1101"], "in_stock"),
            listing(PINK, "wonder", "Wonder Pens", URLS[PINK]["wonder"], "coming_soon"),
            listing(PINK, "atlas", "Atlas Stationers", ATLAS_PINK, "sold_out"),
            listing(PINK, "papermouse", "The Paper Mouse", URLS[PINK]["papermouse"], "unknown"),
            listing(SEA, "atlas", "Atlas Stationers", URLS[SEA]["atlas"], "sold_out"),
            listing(SEA, "kinousa", "Kinokuniya USA", URLS[SEA]["kinousa"], "sold_out"),
            listing(WELCOME, "baum", "Baum-kuchen", URLS[WELCOME]["baum"], "in_stock"),
            listing(LEICESTER, "bobo", "Bobo Design Studio", URLS[LEICESTER]["bobo"], "sold_out"),
            {"canonical": None, "type": "Weeks", "label": "[Hobonichi 2027] Weeks (English)", "store_id": "baum",
             "store": "Baum-kuchen", "url": BAUM_MIXED, "status": "in_stock", "title": "[Hobonichi 2027] Weeks (English)",
             "checked_at": "2026-11-09T03:00:00+00:00", "status_since": "2026-10-25T21:40:55+00:00",
             "first_seen": "2026-10-25T21:40:55+00:00"},
            {"canonical": "weeks-mega-midnight-blue", "type": "Weeks Mega", "label": "Weeks Mega · Colors: Pink Sapphire",
             "store_id": "yoseka", "store": "Yoseka Stationery",
             "url": "https://yosekastationery.com/products/hobonichi-techo-weeks-mega-2027-colors-pink-sapphire",
             "status": "in_stock", "title": "Weeks Mega Pink Sapphire",
             "checked_at": "2026-11-09T03:00:00+00:00", "status_since": "2026-11-09T03:00:00+00:00",
             "first_seen": "2026-11-09T03:00:00+00:00"},
        ]
        orig = site.stock["products"]
        try:
            site.stock["products"] = products
            oe = site.amazon_main(products)
            pink_doc = site.build_design(pink, oe)[1]
            sea_doc = site.build_design(sea, oe)[1]
            family_doc = site.build_design(family, oe)[1]
            weeks = next(g for g in site.GROUPS if g["slug"] == "hobonichi-weeks-2027")
            _weeks_name, weeks_doc = site.build_group(weeks, oe)
            tracker = site.build_hobo_tracker()
            _where_name, where = site.build_where_to_buy()
        finally:
            site.stock["products"] = orig

        self.assertIn('rel="canonical" href="https://stationerydropwatch.com/hobonichi-weeks-2027/pink-sapphire/"', pink_doc)
        self.assertIn("4 shops", pink_doc)
        self.assertIn(">In stock<", pink_doc)
        self.assertIn(">Not yet on sale<", pink_doc)
        self.assertIn(">Sold out<", pink_doc)
        self.assertIn('class="badge unknown">Couldn&#x27;t check</span>', pink_doc)
        self.assertIn(URLS[PINK]["1101"], pink_doc)
        self.assertNotIn(URLS[SEA]["atlas"], pink_doc)
        self.assertNotIn("hobonichi-techo-weeks-mega-2027-colors-pink-sapphire", pink_doc)
        self.assertNotIn(BAUM_MIXED + '"', pink_doc)
        self.assertNotIn("Sold out at the only shop we track", pink_doc)
        self.assertIn("B0H6P9F2S9", site.amazon_for(PINK, ATLAS_PINK)[0])
        self.assertIn("tag=excelsior88-20", site.amazon_for(PINK, ATLAS_PINK)[0])
        self.assertNotIn("B0H6P9F2S9", pink_doc)  # one listing is in stock and one could not be checked
        self.assertIn('rel="canonical" href="https://stationerydropwatch.com/hobonichi-weeks-2027/sea-glass/"', sea_doc)
        self.assertIn("Sold out at every shop we track (2 shops)", sea_doc)
        self.assertNotIn("only shop", sea_doc)
        self.assertIn(URLS[WELCOME]["baum"], family_doc)
        self.assertIn(URLS[LEICESTER]["bobo"], family_doc)
        self.assertNotIn(URLS[PINK]["1101"], family_doc)
        self.assertIn('rel="canonical" href="https://stationerydropwatch.com/hobonichi-weeks-2027/v-and-a/"', family_doc)
        self.assertIn("2 shops", family_doc)
        self.assertIn('id="weeks-pink-sapphire"', weeks_doc)
        self.assertIn('id="weeks-sea-glass"', weeks_doc)
        self.assertIn('id="weeks-va-welcome"', weeks_doc)
        self.assertIn('id="weeks-va-leicester"', weeks_doc)
        self.assertIn('href="/hobonichi-weeks-2027/pink-sapphire/"', weeks_doc)
        self.assertIn('href="/hobonichi-weeks-2027/v-and-a/"', weeks_doc)
        self.assertNotIn("hobonichi-techo-weeks-mega-2027-colors-pink-sapphire", weeks_doc)
        self.assertIn('value="weeks-pink-sapphire"', tracker)
        self.assertIn('value="weeks-va-leicester"', tracker)
        self.assertIn(URLS[PINK]["wonder"], tracker)
        self.assertIn('value="coming_soon"', tracker)
        self.assertIn('value="unknown"', tracker)
        self.assertIn("Pink Sapphire", where)
        self.assertIn("Welcome to the V&amp;A", where)
        self.assertIn("Leicester", where)
        rows_out = site.tracker_rows(products, oe)
        by_url = {r["u"]: r for r in rows_out}
        self.assertEqual(by_url[URLS[PINK]["1101"]]["g"], PINK)
        self.assertEqual(by_url[URLS[WELCOME]["baum"]]["g"], WELCOME)
        self.assertNotEqual(by_url[URLS[WELCOME]["baum"]]["g"], by_url[URLS[LEICESTER]["bobo"]]["g"])
        self.assertEqual(by_url[URLS[PINK]["1101"]]["dp"], "/hobonichi-weeks-2027/pink-sapphire/")
        self.assertEqual(by_url[URLS[WELCOME]["baum"]]["dp"], "/hobonichi-weeks-2027/v-and-a/")
        self.assertEqual(by_url[URLS[LEICESTER]["bobo"]]["dp"], "/hobonichi-weeks-2027/v-and-a/")
        self.assertNotIn("dp", by_url[BAUM_MIXED])


if __name__ == "__main__":
    unittest.main()
