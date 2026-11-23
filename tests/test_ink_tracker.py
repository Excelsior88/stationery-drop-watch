"""Limited-edition ink tracker: statuses, baselines, discovery, approval gate and retirement."""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import checker  # noqa: E402
import ink_tracker as ink  # noqa: E402


def js(available, tags=(), title="Diamine Inkvent Ruby - 50ml Bottled Ink", variants=None):
    return {"title": title, "available": available, "tags": list(tags),
            "variants": variants or [{"id": 1, "title": "Default Title", "available": available}]}


class StatusTests(unittest.TestCase):
    def test_unavailable_in_coming_soon_collection_is_not_sold_out(self):
        st = checker.classify_shopify(js(False))[0]
        self.assertEqual(st, "sold_out")
        self.assertEqual(ink.apply_collections(st, "h", {"h"}, None), "coming_soon")
        self.assertEqual(ink.apply_collections(st, "other", {"h"}, None), "sold_out")

    def test_available_in_preorder_collection_is_preorder(self):
        self.assertEqual(ink.apply_collections("in_stock", "h", None, {"h"}), "preorder")
        self.assertEqual(ink.apply_collections("in_stock", "x", None, {"h"}), "in_stock")

    def test_preorder_tag_is_preorder(self):
        self.assertEqual(checker.classify_shopify(js(True, tags=["Pre-order"]))[0], "preorder")

    def test_in_stock_in_a_title_is_ignored(self):
        # Goldspot's sold-out Inkvent title ends with "In Stock"; only availability counts.
        self.assertEqual(checker.classify_shopify(js(False, title="Diamine Inkvent Calendar 2026 In Stock"))[0], "sold_out")


class BaselineTests(unittest.TestCase):
    def test_first_observation_writes_no_change(self):
        changes = []
        rec = {"checked_at": "2026-11-22T03:00:00+00:00", "status": "in_stock", "store_id": "atlas",
               "store": "Atlas", "label": "x", "url": "u", "section": "inks"}
        checker.note_transition(None, rec, changes)
        self.assertEqual(changes, [])
        self.assertEqual(rec["first_seen"], rec["checked_at"])

    def test_failed_check_is_not_a_change(self):
        changes = []
        old = {"status": "sold_out", "status_since": "2026-11-01T00:00:00+00:00", "first_seen": "2026-11-01T00:00:00+00:00"}
        rec = {"checked_at": "2026-11-22T03:00:00+00:00", "status": "unknown", "store_id": "a", "store": "A", "label": "x", "url": "u"}
        checker.note_transition(old, rec, changes)
        self.assertEqual(changes, [])
        self.assertEqual(rec["status_since"], old["status_since"])

    def test_ink_files_stay_under_data_inks(self):
        self.assertEqual(ink.DATA, ROOT / "data" / "inks")


class RetireTests(unittest.TestCase):
    def rows(self, since, status="sold_out"):
        return [{"ink_id": "i", "ink": "Ink", "brand": "sailor", "store_id": s, "status": status, "status_since": since} for s in ("a", "b")]

    def test_sold_out_everywhere_for_60_days_retires(self):
        now = "2026-11-22T00:00:00+00:00"
        retired = {}
        self.assertEqual(ink.retire(self.rows("2026-09-20T00:00:00+00:00"), retired, now), ["i"])
        self.assertIn("i", retired)

    def test_59_days_or_one_shop_in_stock_does_not_retire(self):
        now = "2026-11-22T00:00:00+00:00"
        self.assertEqual(ink.retire(self.rows("2026-09-25T00:00:00+00:00"), {}, now), [])
        rows = self.rows("2026-01-01T00:00:00+00:00")
        rows[1]["status"] = "in_stock"
        self.assertEqual(ink.retire(rows, {}, now), [])
        rows[1]["status"] = "unknown"
        self.assertEqual(ink.retire(rows, {}, now), [])


class DiscoveryTests(unittest.TestCase):
    RX = r"\bsailor\b"

    def p(self, title, vendor="Sailor", tags=(), ptype="Bottled Ink", available=False, handle="h"):
        return {"title": title, "vendor": vendor, "tags": list(tags), "product_type": ptype, "handle": handle,
                "variants": [{"available": available, "title": "Default Title"}]}

    def test_limited_ink_matches(self):
        self.assertTrue(ink.is_candidate(self.p("Sailor Manyo Ink Bottle - Kaki - 50ml (Limited Edition)"), self.RX))
        self.assertTrue(ink.is_candidate(self.p("Sailor x Pentel 2026 Advent Calendar - Keep the Sparkle", ptype="Pens"), self.RX))

    def test_pens_regular_ink_other_brands_and_designphil_do_not_match(self):
        self.assertFalse(ink.is_candidate(self.p("Sailor Pro Gear Fountain Pen - Limited Edition", ptype="Fountain Pen"), self.RX))
        self.assertFalse(ink.is_candidate(self.p("Sailor Jentle Ink - Blue Black - 50ml"), self.RX))
        self.assertFalse(ink.is_candidate(self.p("Sailor Ink Cartridges - Limited Edition"), self.RX))
        self.assertFalse(ink.is_candidate(self.p("Pilot Iroshizuku Limited Ink", vendor="Pilot"), self.RX))
        self.assertFalse(ink.is_candidate(self.p("MIDORI Sailor limited ink", vendor="Midori"), self.RX))

    def test_upcoming(self):
        self.assertEqual(ink.upcoming_kind(self.p("Sailor ink (Coming Soon)"), set()), "coming_soon")
        self.assertEqual(ink.upcoming_kind(self.p("Sailor ink", handle="z"), {"z"}), "coming_soon")
        self.assertEqual(ink.upcoming_kind(self.p("Sailor ink PRE-ORDER", available=True), set()), "preorder")
        self.assertIsNone(ink.upcoming_kind(self.p("Sailor ink"), set()))

    def test_owner_note_only_when_there_are_finds(self):
        self.assertEqual(ink.owner_note([], {}, {}), "")


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads((ROOT / "inks.json").read_text())
        self.shops = ink.stores_by_id()

    def test_config_is_valid_and_only_verified_pairs(self):
        ink.validate(self.cfg, self.shops)
        verified = {"diamine": {"atlas", "dromgooles", "goldspot", "penboutique", "goulet", "cultpens"},
                    "sailor": {"yoseka", "goulet", "dromgooles", "penboutique", "wonder", "cultpens"},
                    "robert-oster": {"atlas", "goulet", "blesket", "cultpens"}}
        self.assertEqual({b: set(v["shops"]) for b, v in self.cfg["brands"].items()}, verified)

    def test_no_banned_brands_or_shops(self):
        blob = json.dumps(self.cfg).lower()
        for word in ("midori", "traveler", "designphil", "milligram.com", "pelikan", "colorverse", "lamy", "montblanc"):
            self.assertNotIn(word, re.sub(r'"about": "[^"]*"', "", blob), word)

    def test_validate_rejects_unverified_pair(self):
        bad = json.loads(json.dumps(self.cfg))
        bad["inks"][0]["listings"].append({"store_id": "yoseka", "url": "https://yosekastationery.com/products/x"})  # Diamine at Yoseka
        with self.assertRaises(SystemExit):
            ink.validate(bad, self.shops)

    def test_every_ink_shop_is_already_a_tracked_shop(self):
        ids = {l["store_id"] for i in self.cfg["inks"] for l in i["listings"]}
        self.assertTrue(ids <= set(self.shops))


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_site as site
        cls.site = site

    def test_hidden_and_unapproved_rows_never_render(self):
        s = self.site
        self.assertFalse(s._ink_public({"hidden": True, "ink_id": next(iter(s.INKS)), "url": next(iter(s._INK_URLS)), "store_id": "atlas"}))
        self.assertFalse(s._ink_public({"ink_id": "find-atlas-x", "url": "https://www.atlasstationers.com/products/x", "store_id": "atlas"}))

    def test_page_copy(self):
        s = self.site
        if not s.INK_LIVE:
            self.skipTest("no ink data yet")
        fname, doc = s.build_inks()
        self.assertEqual(fname, "limited-edition-fountain-pen-ink/")
        low = doc.lower()
        self.assertNotIn("bullet journal", low)
        self.assertNotIn("amazon.", low)
        self.assertNotIn("tag=", low)
        self.assertNotRegex(doc, "[\U0001F300-\U0001FAFF\u2600-\u27BF]")
        self.assertIn("Not yet on sale", doc) if any(r["status"] == "coming_soon" for r in s.INK_ROWS) else None
        self.assertIn(("limited-edition-fountain-pen-ink/", "Limited inks"), s.NAV_TRACKERS)
        self.assertIn("limited-edition-fountain-pen-ink/", s.build_sitemap())

    def test_color_table_waits_for_a_shops_first_check(self):
        """A shop added to inks.json gets a column only after its first check, never a column of "Not listed"."""
        s = self.site
        ink = {"id": "t", "listings": [{"store_id": "atlas", "url": "a", "color": "Red"},
                                       {"store_id": "goldspot", "url": "g", "color": "Red"}]}
        rows = [dict(store_id="atlas", store="Atlas Stationers", url="a", color="Red", label="Red", status="in_stock")]
        html = s.ink_color_table(ink, rows)
        self.assertIn("Atlas Stationers", html)
        self.assertNotIn("Goldspot", html)
        self.assertNotIn("Not listed", html)
        rows.append(dict(store_id="goldspot", store="Goldspot Pens", url="g", color="Red", label="Red", status="sold_out"))
        self.assertIn("Goldspot Pens", s.ink_color_table(ink, rows))

    def test_teal_singles_listings_are_unique_colors_per_shop(self):
        """Each Teal Edition 50ml colour appears at most once per shop, using the tracker's own colour names."""
        cfg = json.loads((ROOT / "inks.json").read_text())
        ink = next(i for i in cfg["inks"] if i["id"] == "diamine-inkvent-teal-singles")
        names = {l["color"] for l in ink["listings"] if l["store_id"] == "atlas"}
        self.assertEqual(len(names), 25)
        seen = set()
        for l in ink["listings"]:
            self.assertIn(l["color"], names, l["url"])
            self.assertNotIn((l["store_id"], l["color"]), seen, l["url"])
            seen.add((l["store_id"], l["color"]))
            if l.get("variant_id"):
                self.assertIn(f"variant={l['variant_id']}", l["url"])

    def test_shop_count_is_union_not_sum(self):
        s = self.site
        ids = {p["store_id"] for p in s.stock["products"]} | {r["store_id"] for r in s.INK_ROWS}
        self.assertEqual(s.N_STORES, len(ids))


if __name__ == "__main__":
    unittest.main()
