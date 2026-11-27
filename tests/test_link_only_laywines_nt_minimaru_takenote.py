"""Nov 23, 2026 (owner card, 4:16 AM ET): Laywine's and Notebook Therapy go link-only (their terms ban automated
access), and Minimaru (AU) and Take Note (CA) join the Hobonichi tracker. The checked-shop total stays 27."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402
import checker  # noqa: E402

NEW = {"minimaru": ("Minimaru", "AU", "minimaru.com"), "takenote": ("Take Note", "CA", "takenotestore.ca")}
BANNED = re.compile(r"midori|traveler|designphil", re.I)


class LinkOnlyAndNewShopsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stores = {s["id"]: s for s in cls.cfg["stores"]}
        cls.canon = {c["id"]: c for c in cls.cfg["canonical"]}

    def test_laywines_is_checked_again_after_written_permission(self):
        # Nov 26, 2026 (owner t2021u): Laywine's gave written permission, so it is checked like any other shop.
        s = self.stores["laywines"]
        self.assertNotIn("link_only", s)
        self.assertNotIn("link_only_reason", s)
        self.assertNotIn("laywines.com", checker.LINK_ONLY_HOSTS)
        self.assertNotIn("laywines", checker.link_only_ids())
        self.assertEqual(s["platform"], "shopify")

    def test_laywines_first_rows_are_first_observations_not_restocks(self):
        old = None
        rec = dict(checked_at="2026-11-27T00:47:00+00:00", status="in_stock", store_id="laywines", store="Laywine's",
                   label="x", url="https://laywines.com/products/x")
        self.assertEqual(checker.note_transition(old, rec, []), [])
        self.assertEqual(rec["first_seen"], rec["checked_at"])

    def test_notebook_therapy_is_link_only_and_never_requested(self):
        for sid, host in (("notebooktherapy", "notebooktherapy.com"),):
            s = self.stores[sid]
            self.assertTrue(s["link_only"])
            self.assertIn("written permission", s["link_only_reason"])
            self.assertTrue(s["products"])  # still listed as plain links
            self.assertEqual(checker.check_store(s), [])
            self.assertIn(host, checker.LINK_ONLY_HOSTS)
            self.assertIn("www." + host, checker.LINK_ONLY_HOSTS)
            with self.assertRaises(checker.LinkOnlyHostError):
                checker.GuardedSession().get(s["products"][0]["url"], timeout=1)

    def test_new_shops_are_checked_hobonichi_only(self):
        for sid, (name, country, host) in NEW.items():
            s = self.stores[sid]
            self.assertEqual((s["name"], s["country"], s["platform"], s["cols"]), (name, country, "shopify", ["hobonichi"]))
            self.assertFalse(s.get("link_only"))
            self.assertNotIn("brand", s)
            seen = set()
            for p in s["products"]:
                c = self.canon[p["canonical"]]
                self.assertFalse(c["type"].startswith("Dot"), p["url"])
                self.assertEqual(p["label"], c["label"])
                self.assertTrue(p["url"].startswith(f"https://{host}/products/"), p["url"])
                self.assertIsNone(BANNED.search(p["url"] + " " + p["source_title"]), p["url"])
                self.assertNotIn(p["canonical"], seen, p["url"])
                seen.add(p["canonical"])
                if c["type"] in ("Weeks", "Weeks Mega", "HON") or p["canonical"].endswith("-en"):
                    self.assertNotRegex(p["source_title"], r"(?i)\b(jpn|japanese)\b", p["url"])
                if "?variant=" in p["url"]:
                    self.assertEqual(p["url"].split("?variant=")[1], str(p["variant_id"]))
        self.assertEqual({sid: len(self.stores[sid]["products"]) for sid in NEW}, {"minimaru": 58, "takenote": 40})

    def test_checked_total_is_28_and_notebook_therapy_is_not_in_the_we_check_phrase(self):
        self.assertFalse(site.COUNT_LINK_ONLY_IN_SHOP_TOTALS)
        checked = {s["id"] for s in self.cfg["stores"]
                   if s["products"] and s["platform"] in ("shopify", "hobonichi") and not s.get("link_only")}
        self.assertEqual(len(checked), 28)  # Laywine's checked again from Nov 26, 2026
        self.assertTrue({"minimaru", "takenote", "laywines"} <= checked)
        self.assertNotIn("notebooktherapy", checked)
        self.assertNotIn("Notebook Therapy", site.dotgrid_where_checked())

    def test_faq_and_guide_make_no_stock_claim_for_notebook_therapy(self):
        import html
        self.assertNotIn("Notebook Therapy", site.dotgrid_names())
        home = html.unescape(site.build_index())
        self.assertNotIn("Scribbles That Matter (official) and Notebook Therapy (official). We check", home)
        self.assertIn("Notebook Therapy (official) are listed as links only", home)
        guide = html.unescape(site.build_dotgrid_guide()[1])
        self.assertNotIn("Live Notebook Therapy stock", guide)
        self.assertNotIn("which we track too", guide)
        self.assertIn("Notebook Therapy on the tracker", guide)
        self.assertIn("link only: we don't check its stock", guide)
        self.assertIn("Notebook Therapy is listed as a link only: we don't check its stock.", guide)

    def test_dot_grid_tracker_share_alt_and_design_pages_say_link_only(self):
        import html
        self.assertNotIn("Notebook Therapy,", site.OG_DOTGRID_ALT)
        self.assertIn("Notebook Therapy is listed as a link only", site.OG_DOTGRID_ALT)
        self.assertNotIn("Notebook Therapy", site.dotgrid_meta_desc())
        group = next(g for g in site.GROUPS if g.get("section") == "dotgrid")
        doc = html.unescape(site.build_group(group, {})[1])
        self.assertNotIn("from Archer and Olive, Leuchtturm1917, Scribbles That Matter and Notebook Therapy", doc)
        for d in site.DESIGNS:
            if d["slug"].startswith("notebook-therapy-"):
                page = html.unescape(site.build_design(d)[1])
                self.assertIn(": link only", page)
                self.assertIn("we don't check its stock", page)
                for bad in ("This page shows its stock", "Tracking started", "Recent restocks", "listings we track", "Statuses come from"):
                    self.assertNotIn(bad, page, (d["slug"], bad))


if __name__ == "__main__":
    unittest.main()
