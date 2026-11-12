"""2027 beautiful people covers: catalog identity, baseline stock, no invented restock."""
import json
import re
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402
import checker  # noqa: E402
import new_in_stock  # noqa: E402

A6 = "cover-a6-beautiful-people-green"
A5 = "cover-a5-beautiful-people-pink"
A6_URL = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/oc27_bpeople/"
A5_URL = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/cc27_bpeople/"
PAPER_A5 = "https://www.thepapermouse.com/products/hobonichi-techo-a5-cousin-cover-beautiful-people-nothing-to-hide-pink-1"
JET_A6 = "https://www.jetpens.com/Hobonichi-Techo-2027-Cover-Only-A6-beautiful-people-Nothing-to-Hide-Green/pd/53982"
JET_A5 = "https://www.jetpens.com/Hobonichi-Techo-2027-Cover-Only-A5-beautiful-people-Nothing-to-Hide-Pink/pd/53943"
WEEKS = "weeks-beautiful-people-yellow"
WEEKS_URL = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wc27_bpeople/"


class BeautifulPeopleCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data/stock.json").read_text())
        cls.changes = json.loads((ROOT / "data/changes.json").read_text())
        cls.by_store = {s["id"]: s for s in cls.cfg["stores"]}

    def products(self, cid):
        return [p for s in self.cfg["stores"] for p in s.get("products") or [] if p.get("canonical") == cid]

    def test_canonical_labels(self):
        labels = {c["id"]: c["label"] for c in self.cfg["canonical"]}
        self.assertEqual(labels[A6], "A6 cover · beautiful people: Nothing to Hide (Green)")
        self.assertEqual(labels[A5], "A5 cover · beautiful people: Nothing to Hide (Pink)")

    def test_official_rows_are_english_pages_with_feed_keys(self):
        official = {p["canonical"]: p for p in self.by_store["1101"]["products"] if p.get("canonical") in (A6, A5)}
        self.assertEqual(official[A6]["url"], A6_URL)
        self.assertEqual(official[A6]["source_key"], "oc27_bpeople")
        self.assertEqual(official[A5]["url"], A5_URL)
        self.assertEqual(official[A5]["source_key"], "cc27_bpeople")
        joined = " ".join(p["url"] for p in self.by_store["1101"]["products"])
        self.assertNotIn("/ja/2027/", joined)

    def test_checked_shops(self):
        both = {"1101", "atlas", "wonder", "yoseka", "penboutique", "papermouse", "jennibick", "blesket", "journalshop", "buchan"}
        a6_only = {"mlovewell"}
        for sid in both:
            ids = {p["canonical"] for p in self.by_store[sid]["products"]}
            self.assertTrue({A6, A5} <= ids, sid)
        self.assertIn(A6, {p["canonical"] for p in self.by_store["mlovewell"]["products"]})
        self.assertNotIn(A5, {p["canonical"] for p in self.by_store["mlovewell"]["products"]})
        self.assertNotIn("loft", self.by_store)

    def test_paper_mouse_a5_uses_the_handle_that_exists(self):
        urls = [p["url"] for p in self.products(A5) if "thepapermouse.com" in p["url"]]
        self.assertEqual(urls, [PAPER_A5])

    def test_jetpens_is_a_link_not_a_status(self):
        self.assertEqual(self.by_store["jetpens"]["products"], [])
        self.assertEqual(site.UNCHECKED_LINKS["hobonichi-techo-2027-covers/nothing-to-hide-green"][0]["url"], JET_A6)
        self.assertEqual(site.UNCHECKED_LINKS["hobonichi-techo-2027-covers/nothing-to-hide-pink"][0]["url"], JET_A5)
        self.assertFalse(any("jetpens.com" in (r.get("url") or "") for r in self.stock["products"]))

    def test_design_pages_match_only_their_cover(self):
        green = next(d for d in site.DESIGNS if d["slug"] == "nothing-to-hide-green")
        pink = next(d for d in site.DESIGNS if d["slug"] == "nothing-to-hide-pink")
        self.assertTrue(green["match"]({"canonical": A6}))
        self.assertFalse(green["match"]({"canonical": A5}))
        self.assertTrue(pink["match"]({"canonical": A5}))
        self.assertFalse(pink["match"]({"canonical": "cover-a6-moomin"}))
        self.assertIn("4580812708883", site.design_about(green))
        self.assertIn("4580812709163", site.design_about(pink))
        self.assertIn("A5", site.design_about(pink))

    def test_baseline_does_not_invent_a_restock(self):
        rows = [r for r in self.stock["products"] if r.get("canonical") in (A6, A5)]
        self.assertEqual(len(rows), 21)
        self.assertTrue(all(r["first_seen"] == r["status_since"] for r in rows))
        self.assertTrue(all(r["status"] != "unknown" for r in rows))
        urls = {r["url"] for r in rows}
        self.assertFalse(any(c.get("url") in urls for c in self.changes))
        official = {r["canonical"]: r["status"] for r in rows if r["store_id"] == "1101"}
        self.assertEqual(official, {A6: "sold_out", A5: "sold_out"})

    def test_weeks_cover_is_a_weeks_design_not_a_second_language_row(self):
        labels = {c["id"]: c for c in self.cfg["canonical"]}
        self.assertEqual(labels[WEEKS]["type"], "Weeks")
        self.assertIn("Weeks cover", labels[WEEKS]["label"])
        official = next(p for p in self.by_store["1101"]["products"] if p.get("canonical") == WEEKS)
        self.assertEqual(official["url"], WEEKS_URL)
        self.assertEqual(official["source_key"], "wc27_bpeople")
        self.assertNotIn("/ja/2027/", official["url"])
        yellow = next(d for d in site.DESIGNS if d["slug"] == "nothing-to-hide-yellow")
        self.assertEqual(yellow["parent"], "hobonichi-weeks-2027")
        self.assertTrue(yellow["match"]({"canonical": WEEKS}))
        self.assertFalse(yellow["match"]({"canonical": A6}))
        about = site.design_about(yellow)
        self.assertIn("4580812710121", about)
        self.assertIn("cover", about.lower())
        self.assertIn("not the Weeks planner", about)
        rows = [r for r in self.stock["products"] if r.get("canonical") == WEEKS]
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r["first_seen"] == r["status_since"] for r in rows))
        self.assertFalse(any(c.get("url") in {r["url"] for r in rows} for c in self.changes))
        self.assertNotIn("nothing-to-hide-yellow", site.UNCHECKED_LINKS)

    def test_later_in_stock_change_is_an_alert_for_every_new_row(self):
        """The first observation stays quiet. A later sold-out, preview, or preorder
        flip to in stock uses the same change and webhook path as every other listing."""
        rows = [r for r in self.stock["products"] if r.get("canonical") in (A6, A5, WEEKS)]
        self.assertEqual(len(rows), 32)
        pages = {
            A6: "hobonichi-techo-2027-covers/nothing-to-hide-green/",
            A5: "hobonichi-techo-2027-covers/nothing-to-hide-pink/",
            WEEKS: "hobonichi-weeks-2027/nothing-to-hide-yellow/",
        }
        when = "2026-11-11T16:00:00+00:00"
        for row in rows:
            first = dict(row, status="in_stock", checked_at=when)
            quiet = checker.note_transition(None, first, [])
            self.assertEqual(quiet, [], row["url"])
            rec = dict(row, status="in_stock", checked_at=when)
            changes = checker.note_transition(row, rec, [])
            self.assertEqual(len(changes), 1, row["url"])
            event = changes[0]
            self.assertEqual(event["from"], row["status"])
            self.assertEqual(event["to"], "in_stock")
            self.assertEqual(event["label"], row["label"])
            self.assertEqual(event["store"], row["store"])
            self.assertEqual(event["store_id"], row["store_id"])
            self.assertEqual(event["url"], row["url"])
            self.assertEqual(event["at"], when)
            self.assertEqual(site.design_page_for([row]), pages[row["canonical"]])
            body = new_in_stock.webhook_body(new_in_stock.fresh_in_stock(self.changes, self.changes + changes), "2026-11-11T16:00:05+00:00")
            self.assertEqual(body["source"], "stationery-drop-watch")
            self.assertEqual(body["changes"], changes)
            self.assertNotIn("test", body)
        green = next(r for r in rows if r["canonical"] == A6 and r["store_id"] == "papermouse")
        self.assertEqual(green["status"], "sold_out")
        preview = next(r for r in rows if r["canonical"] == WEEKS and r["store_id"] == "wonder")
        self.assertEqual(preview["status"], "coming_soon")
        preorder = dict(green, status="preorder")
        event = checker.note_transition(preorder, dict(green, status="in_stock", checked_at=when), [])[0]
        self.assertEqual(event["from"], "preorder")
        self.assertEqual(new_in_stock.fresh_in_stock([], [event])[0]["url"], green["url"])

    def test_angela_thanks_is_only_on_the_three_design_pages(self):
        line = "Thank you to our follower Angela for suggesting we track these restocks."
        oe = site.amazon_main(site.stock["products"])
        wanted = {"nothing-to-hide-green", "nothing-to-hide-pink", "nothing-to-hide-yellow"}
        for design in site.DESIGNS:
            _, doc = site.build_design(design, oe)
            visible = re.sub(r"<script[\s\S]*?</script>", " ", doc)
            visible = re.sub(r"<meta[^>]*>", " ", visible)
            if design["slug"] in wanted:
                self.assertEqual(doc.count(line), 1)
                self.assertIn(f'<p class="suggest">{line}</p>', doc)
                self.assertLess(doc.index(line), doc.index('class="stats five"'))
                self.assertLess(doc.index('class="stats five"'), doc.index("Open a shop's name"))
                self.assertIn(line, visible)
                self.assertNotIn("Angela", re.search(r'name="description" content="([^"]*)"', doc).group(1))
                self.assertNotIn("Angela", re.search(r'property="og:description" content="([^"]*)"', doc).group(1))
                for block in re.findall(r'application/ld\+json">([\s\S]*?)</script>', doc):
                    self.assertNotIn("Angela", block)
            else:
                self.assertNotIn("Angela", doc)
        self.assertNotIn("Angela", site.build_index())
        self.assertNotIn("Angela", site.build_group(next(g for g in site.GROUPS if g["slug"] == "hobonichi-techo-2027-covers"), oe)[1])
        self.assertNotIn("Angela", site.build_group(next(g for g in site.GROUPS if g["slug"] == "hobonichi-weeks-2027"), oe)[1])


if __name__ == "__main__":
    unittest.main()
