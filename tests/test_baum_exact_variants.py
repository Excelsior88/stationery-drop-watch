"""Baum-kuchen Weeks and Mega are one Shopify product with many designs.

The whole product must not be reported in stock when one named option is sold out.
Each tracked option keeps its own URL. The old combined URL is not reused as a variant.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.checker as checker
import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
AGG = "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-colors-english"
MEGA = "https://www.baum-kuchen.net/products/hobonichi-2027-weeks-mega-english"
LEICESTER = AGG + "?variant=43546076676163"
MIDNIGHT = AGG + "?variant=43546058817603"
OMOI = "https://omoionline.com/products/md-notebook-2027-monthly-planners?variant=67760093626672"
OLD = "2026-10-25T21:40:55+00:00"


def mixed():
    return {"title": "[Hobonichi 2027] Weeks (English)", "available": True, "tags": ["Hobonichi Weeks"],
            "variants": [
                {"id": 43546058817603, "title": "Colors: Midnight Blue", "public_title": "Colors: Midnight Blue", "available": True},
                {"id": 43546076676163, "title": "V&A Series: Leicester [SOLD OUT]", "public_title": "V&A Series: Leicester [SOLD OUT]", "available": False},
            ]}


class _Resp:
    def __init__(self, payload):
        self._payload = payload
        self.ok = True
        self.status_code = 200
        self.text = ""
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._payload


class BaumExactVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())

    def test_aggregate_urls_are_gone_and_each_variant_is_separate(self):
        urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertNotIn(AGG, urls)
        self.assertNotIn(MEGA, urls)
        self.assertNotIn(OMOI, urls)  # MIDORI rows were removed on Nov 19, 2026
        baum = next(s for s in self.cfg["stores"] if s["id"] == "baum")
        weeks = [p for p in baum["products"] if "weeks-colors-english?variant=" in p["url"]]
        mega = [p for p in baum["products"] if "weeks-mega-english?variant=" in p["url"]]
        self.assertEqual(len(weeks), 11)
        self.assertEqual(len(mega), 7)
        self.assertEqual(len({p["variant_id"] for p in weeks + mega}), 18)
        lei = next(p for p in weeks if p["variant_id"] == 43546076676163)
        self.assertEqual(lei["canonical"], "weeks-va-leicester")
        self.assertEqual(lei["url"], LEICESTER)
        official = next(p for s in self.cfg["stores"] if s["id"] == "1101" for p in s["products"] if p.get("source_key") == "wb27_colorscyellow")
        self.assertEqual(official["canonical"], "weeks-canaria-yellow")
        self.assertEqual(official["type"], "Weeks")
        cover = next(p for s in self.cfg["stores"] if s["id"] == "1101" for p in s["products"] if p.get("source_key") == "oc27_kitagishi")
        self.assertEqual(cover["canonical"], "cover-a6-white-cat-house")
        self.assertEqual(cover["type"], "Cover")

    def test_mixed_product_is_not_in_stock_and_each_variant_keeps_its_status(self):
        js = mixed()
        whole = checker.classify_shopify(js)
        self.assertEqual(whole[0], "unknown")
        self.assertEqual(checker.classify_shopify_variant(js, 43546058817603)[0], "in_stock")
        self.assertEqual(checker.classify_shopify_variant(js, 43546076676163)[0], "sold_out")
        store = {"id": "baum", "name": "Baum-kuchen", "url": "https://www.baum-kuchen.net/", "platform": "shopify",
                 "products": [{"canonical": None, "label": "[Hobonichi 2027] Weeks (English)", "type": "Weeks",
                               "url": AGG, "source_title": "[Hobonichi 2027] Weeks (English)"}]}

        class Host:
            def __init__(self, base):
                pass
            def get(self, url, check_robots=True):
                return _Resp(js)

        with patch.object(checker, "Host", Host):
            rec = checker.check_shopify_store(store)[0]
        self.assertEqual(rec["status"], "unknown")
        self.assertIn("do not share one availability", rec["error"])

    def test_a_new_variant_does_not_inherit_the_aggregate_history(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "data").mkdir()
        stores = {"stores": [{"id": "baum", "name": "Baum-kuchen", "platform": "shopify",
                              "url": "https://www.baum-kuchen.net/", "products": [
            {"canonical": "weeks-va-leicester", "label": "Weeks · V&A: Leicester", "type": "Weeks",
             "url": LEICESTER, "variant_id": 43546076676163, "source_title": "Leicester"},
            {"canonical": "weeks-midnight-blue", "label": "Weeks · Colors: Midnight Blue", "type": "Weeks",
             "url": MIDNIGHT, "variant_id": 43546058817603, "source_title": "Midnight Blue"},
        ]}]}
        (tmp / "stores.json").write_text(json.dumps(stores))
        (tmp / "data" / "stock.json").write_text(json.dumps({"products": [
            {"url": AGG, "status": "in_stock", "first_seen": OLD, "status_since": OLD, "canonical": None},
            {"url": LEICESTER, "status": "sold_out", "first_seen": OLD, "status_since": OLD, "canonical": "weeks-va-leicester"},
        ]}))
        (tmp / "data" / "changes.json").write_text(json.dumps([
            {"at": OLD, "url": AGG, "from": "sold_out", "to": "in_stock", "store": "Baum-kuchen"}
        ]))

        class Host:
            def __init__(self, base):
                pass
            def get(self, url, check_robots=True):
                return _Resp(mixed())

        with patch.object(checker, "ROOT", tmp), patch.object(checker, "Host", Host):
            checker.main()
        rows = {p["url"]: p for p in json.loads((tmp / "data" / "stock.json").read_text())["products"]}
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        self.assertNotIn(AGG, rows)
        self.assertEqual(rows[LEICESTER]["status"], "sold_out")
        self.assertEqual(rows[LEICESTER]["first_seen"], OLD)
        self.assertEqual(rows[LEICESTER]["status_since"], OLD)
        self.assertEqual(rows[MIDNIGHT]["status"], "in_stock")
        self.assertEqual(rows[MIDNIGHT]["first_seen"], rows[MIDNIGHT]["checked_at"])
        self.assertEqual([c["url"] for c in changes], [AGG])

    def test_pages_place_the_official_books_and_not_the_aggregate(self):
        canaria = next(d for d in site.DESIGNS if d["slug"] == "canaria-yellow")
        cover = next(d for d in site.DESIGNS if d["slug"] == "white-cat-house")
        self.assertTrue(canaria["match"]({"canonical": "weeks-canaria-yellow", "type": "Weeks", "label": "Weeks · Colors: Canaria Yellow", "url": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_colorscyellow/"}))
        self.assertFalse(canaria["match"]({"canonical": "weeks-mega-canaria-yellow", "type": "Weeks Mega", "label": "Weeks Mega · Colors: Canaria Yellow", "url": "m"}))
        self.assertTrue(cover["match"]({"canonical": "cover-a6-white-cat-house", "type": "Cover", "label": "A6 cover · Yumi Kitagishi: White Cat House", "url": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_kitagishi/"}))
        self.assertIn("English and Japanese", site.design_about(canaria))
        self.assertIn("The other shops on this page sell the English book", site.design_about(canaria))
        self.assertIn("not a Weeks Mega", site.design_about(canaria))
        self.assertIn("A6 cover", site.design_about(cover))
        self.assertIn("not the Weeks White Cat Wallpaper", site.design_about(cover))
        cal = site.build_hobonichi()
        self.assertIn("<time>Aug 25, 2026</time>", cal)
        self.assertIn("updated Nov 27, 2026", cal)  # Nov 27: restock heading and signup position changed
        self.assertNotIn("Everything goes live at the same moment worldwide", cal)
        self.assertIn("September 1, 2026 at 11:00 AM Japan time (August 31, 2026 at 10:00 PM ET / 9:00 PM CT)", cal)
        self.assertIn("official Hobonichi Store's online launch time", cal)
        self.assertIn("opened online Aug 31 at 10 PM ET and in-store Sep 1 at 11 AM ET", cal)
        self.assertIn("opened online Aug 31 at 9 PM CT", cal)
        self.assertIn("week of September 7", cal)
        self.assertIn("each retail store opens at its own store hours", cal)
        wave = cal.split("Second fall wave", 1)[1].split("First restocks", 1)[0]
        self.assertIn("October 1, 2026 at 11:00 AM Japan time (September 30, 2026 at 10:00 PM ET)", wave)
        self.assertIn("One Piece 2027 editions are January-start and Monday-start only", wave)
        self.assertNotIn("That book is January-start", wave)
        self.assertIn("#s-hon", wave)
        self.assertIn("Weeksdays 2027 desk calendar", wave)
        self.assertIn("#s-papermouse", wave)
        self.assertLess(wave.index("#s-hon"), wave.index("Weeksdays 2027"))
        spring = cal.split("Spring launch", 1)[1].split("</ol>", 1)[0]
        self.assertIn("February 1, 2027 at 11:00 AM Japan time (January 31, 2027 at 9:00 PM ET)", spring)
        self.assertIn("own opening hours", spring)
        self.assertIn("has not published the Spring 2027 cover and book lineup yet", spring)
        self.assertIn("#s-1101", spring)
        self.assertNotIn("second release in February", cal)
        self.assertIn("October 15", cal)
        self.assertIn("Japanese Original (A6)", cal)
        self.assertIn("Japanese Cousin (A5)", cal)
        self.assertIn("Japanese Weeks", cal)
        for missing in ("English Original, Cousin, and Weeks", "Weeks Mega (English and Japanese)",
                        "HON (Japanese and English, A6 and A5)", "One Piece Original",
                        "Moomin Weeks Japanese Special Edition", "Day-Free", "Large 5-Year"):
            self.assertIn(missing, cal)
        self.assertIn("may be restocked for the April-start launch", cal)
        self.assertIn("some items are April-only", cal)
        self.assertIn("fabric availability can change the lineup", cal)
        self.assertIn('"If there is no notice, a restock has not been decided or is under consideration"', cal)
        self.assertIn("Techo books and Drawer Pouches", cal)
        self.assertIn("do not guarantee a purchase", cal)
        for note in ("Official store notes a restock is planned", "Restock undecided at official store", "Sales ended at official store"):
            self.assertIn(note, cal)
        self.assertEqual(cal.count("Plain Old Acorn Charm"), 1)
        self.assertEqual(cal.count("3-Color Jetstream Ballpoint Pen"), 1)
        self.assertEqual(cal.count("Tokyo Station Branch, Tobichi Tokyo/Kyoto, Hobono Eki AKAGI"), 1)
        self.assertEqual(cal.count("Avec Book 2 alone do not qualify"), 1)
        self.assertIn('href="#ordering-direct">Ordering direct from Hobonichi</a> above', cal)
        self.assertIn("The 11:00 AM Japan time official Hobonichi Store online release time.", cal)
        self.assertIn("The annual February 1 April-start schedule, and each retail store opening at its own hours.", cal)
        self.assertIn('href="#s-faq-schedule">[Hobonichi, sale schedule]</a>', cal)
        self.assertNotIn("retail hours", cal)
        self.assertNotIn("core colors", cal)
        self.assertIn("some standard planners and accessories may be replenished", cal)
        self.assertIn("1–3 business days", cal)
        self.assertIn("up to 10 business days after a new release", cal)
        self.assertIn("ship together once the latest item is ready", cal)
        self.assertIn("via FedEx", cal)
        self.assertIn("cannot estimate them in advance", cal)
        for url in (
            "https://www.1101.com/store/techo/en/2027/pc/shopping_guide/",
            "https://www.1101.com/store/techo/en/magazine/hon/",
            "https://www.1101.com/store/techo/en/faq/articles/4889929315230.html",
            "https://www.1101.com/store/techo/en/faq/articles/4889951964190.html",
            "https://www.1101.com/store/techo/en/faq/articles/4889935437854.html",
            "https://www.1101.com/store/techo/en/faq/articles/4889938317854.html",
            "https://www.1101.com/store/techo/en/faq/articles/4889935445534.html",
        ):
            self.assertIn(url, cal)
        self.assertNotIn("Traveler", cal)
        self.assertNotIn("MIDORI", cal)
        self.assertEqual(site.STATIC_LASTMOD["hobonichi-2027/"], "2026-11-27")
        self.assertIn("https://stationerydropwatch.com/hobonichi-2027/</loc><lastmod>2026-11-27T00:00:00+00:00</lastmod>", site.build_sitemap())
        about = site.design_about(canaria)
        self.assertIn("includes the English and Japanese books", about)
        self.assertNotIn("English book is in stock", about)

    def test_the_guard_changes_only_a_whole_product_whose_named_options_disagree(self):
        """Shapes taken from live .js on 2026-11-09. Default Title, a dash, and named options that all match stay put."""
        one = {"title": "Hobonichi Techo 2027 A6 Original", "available": True, "tags": [],
               "variants": [{"id": 52128560709861, "title": "Default Title", "available": True}]}
        sticker = {"title": "Traveler's notebook 2027 Customized Sticker Set", "available": False, "tags": [],
                   "variants": [{"id": 67620191928549, "title": "Default Title", "available": False}]}
        preview = {"title": "PREVIEW - Hobonichi 2027 - English Weeks - Colors: Midnight Blue", "available": False, "tags": [],
                   "variants": [{"id": 48774502711541, "title": "Default Title", "available": False}]}
        dash = {"title": "[Hobonichi 2027] Original Book (A6 / English)", "available": True, "tags": [],
                "variants": [{"id": 43546121633859, "title": "-", "available": True}]}
        same = {"title": "Storybook in Navy", "available": True, "tags": [],
                "variants": [
                    {"id": 48885118566555, "title": "A5: White / Dot Grid", "public_title": "A5: White / Dot Grid", "available": True},
                    {"id": 48885118501019, "title": "B5: White / Dot Grid", "public_title": "B5: White / Dot Grid", "available": True},
                ]}
        none = {"title": "Storybook in Navy", "available": False, "tags": [],
                "variants": [
                    {"id": 1, "title": "A5", "public_title": "A5", "available": False},
                    {"id": 2, "title": "B5", "public_title": "B5", "available": False},
                ]}
        songbird = {"title": "Songbird in Blue", "available": True, "tags": [],
                    "variants": [
                        {"id": 47128956928155, "title": "A5: 192 Pages / Dot Grid", "public_title": "A5: 192 Pages / Dot Grid", "available": False},
                        {"id": 47128956862619, "title": "B5: 160 Pages / Dot Grid", "public_title": "B5: 160 Pages / Dot Grid", "available": True},
                    ]}
        self.assertEqual(checker.classify_shopify(one)[0], "in_stock")
        self.assertEqual(checker.classify_shopify(sticker)[0], "sold_out")
        self.assertEqual(checker.classify_shopify(preview)[0], "coming_soon")
        self.assertEqual(checker.classify_shopify(dash)[0], "in_stock")
        self.assertEqual(checker.classify_shopify(same)[0], "in_stock")
        self.assertEqual(checker.classify_shopify(none)[0], "sold_out")
        self.assertEqual(checker.classify_shopify(songbird)[0], "unknown")
        self.assertEqual(checker.classify_shopify_variant(songbird, 47128956928155)[0], "sold_out")
        self.assertEqual(checker.classify_shopify_variant(songbird, 47128956862619)[0], "in_stock")

        store = {"id": "archerolive", "name": "Archer and Olive", "url": "https://www.archerandolive.com/", "platform": "shopify",
                 "products": [{"canonical": "ao-songbird-blue", "label": "Songbird in Blue · A5 dot grid", "type": "Dot grid",
                               "url": "https://www.archerandolive.com/products/songbird-in-blue?variant=47128956928155",
                               "variant_id": 47128956928155, "source_title": "A5"}]}

        class Host:
            def __init__(self, base):
                pass
            def get(self, url, check_robots=True):
                return _Resp(songbird)

        with patch.object(checker, "Host", Host):
            rec = checker.check_shopify_store(store)[0]
        self.assertEqual(rec["status"], "sold_out")
        self.assertIsNone(rec["error"])

    def test_current_stock_has_no_non_baum_whole_product_the_guard_would_flip(self):
        """A whole-product row flips only when named options already disagreed at the last check.
        Variant rows are classified one id at a time, so a mixed parent product does not flip them."""
        stock = {p["url"]: p for p in json.loads((ROOT / "data" / "stock.json").read_text())["products"]}
        flips = []
        for store in self.cfg["stores"]:
            if store["platform"] != "shopify" or store["id"] == "baum":
                continue
            for p in store["products"]:
                if p.get("variant_id"):
                    continue
                st = stock.get(p["url"])
                if not st or st.get("status") == "unknown":
                    continue
                avail, total = st.get("available_variants"), st.get("total_variants")
                if isinstance(avail, int) and isinstance(total, int) and total > 1 and avail not in (0, total):
                    flips.append((store["id"], p["url"], avail, total, st["status"]))
        self.assertEqual(flips, [])


if __name__ == "__main__":
    unittest.main()
