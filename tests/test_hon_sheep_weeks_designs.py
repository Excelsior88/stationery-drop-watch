"""HON Sheep Sheep Sheep and two 2027 Weeks designs, verified shop by shop.

New URLs are a first observation only (first_seen equals status_since, no
event in changes.json). Jenni Bick's A6 Sheep page is titled Japanese while
its barcode is the English JAN, so that URL is not tracked, matching the A6
Slash Navy conflict already on file.
"""
import json
import unittest
from pathlib import Path

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]

JENNI_A6 = "https://www.jennibick.com/products/hobonichi-techo-a6-hon-2027-bow-tie-sheep-sheep-sheep"
PEN_JP_A6 = "https://www.penboutique.com/products/hobonichi-hon-light-hardcover-japanese-book-bow-tie-sheep-sheep-sheep-a6-january-start"

A5_SHOPS = {
    "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/cb27_hon_tiesheep/",
    "dromgooles": "https://www.dromgooles.com/products/hobonichi-2026-a5-techo-hon-bow-tie-sheep-sheep-sheep",  # added Nov 20, 2026; handle says 2026, live title is 2027
    "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-a5-hon-planner-bow-tie-sheep-sheep-sheep-english",
    "atlas": "https://www.atlasstationers.com/products/hobonichi-a5-hon-bow-tie-sheep-sheep-sheep",
    "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-a5-hon-english-bow-tie-sheep-sheep-sheep",
    "penboutique": "https://www.penboutique.com/products/hobonichi-techo-2027-hon-a5-bow-tie-sheep-sheep-sheep",
    "yoseka": "https://yosekastationery.com/products/hobonichi-techo-hon-2027-a5-bow-tie-sheep-sheep-sheep",
    "jennibick": "https://www.jennibick.com/products/hobonichi-techo-a5-hon-2027-bow-tie-sheep-sheep-sheep",
    "blesket": "https://blesket.com/products/hobonichi-techo-2027-hon-bow-tie-sheep-sheep-sheep-eng-a5-hon-jan-start",
    "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-hon-a5-bow-tie-sheep-sheep-sheep",
    "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-original-a5-hon-planner-book-bow-tie-sheep-english-january-start-monday-start",
    "mlovewell": "https://www.mlovewell.com/products/2027-hobonichi-techo-hon-a5-english-hardcover-planner-book-bow-tie-sheep-sheep-sheep",
}

A6_EN_SHOPS = {
    "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/ob27_hon_tiesheep/",
    "dromgooles": "https://www.dromgooles.com/products/hobonichi-2027-a6-techo-hon-bow-tie-sheep-sheep-sheep",  # added Nov 20, 2026
    "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-a6-hon-planner-bow-tie-sheep-sheep-sheep-english",
    "atlas": "https://www.atlasstationers.com/products/hobonichi-a6-hon-bow-tie-sheep-sheep-sheep",
    "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-a6-hon-english-vbow-tie-sheep-sheep-sheep",
    "penboutique": "https://www.penboutique.com/products/hobonichi-hon-a6-2027-bow-tie-sheep-sheep-sheep",
    "yoseka": "https://yosekastationery.com/products/hobonichi-techo-hon-2027-a6-bow-tie-sheep-sheep-sheep-english",
    "blesket": "https://blesket.com/products/hobonichi-techo-2027-hon-bow-tie-sheep-sheep-sheep-eng-a6-hon-jan-start",
    "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-hon-a6-bow-tie-sheep-sheep-sheep",
    "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-original-a6-hon-planner-book-bow-tie-sheep-english-january-start-monday-start",
    "mlovewell": "https://www.mlovewell.com/products/2027-hobonichi-techo-hon-a6-english-hardcover-planner-book-bow-tie-sheep-sheep-sheep",
}

ONCE_SHOPS = {
    "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_miyakoshi/",
    "dromgooles": "https://www.dromgooles.com/products/hobonichi-2027-weeks-akiko-miyakoshi-once-in-spring",  # added Nov 20, 2026
    "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-akiko-miyakoshi-once-in-spring-english",
    "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-akiko-miyakoshi-once-in-spring",
    "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-akiko-miyakoshi-once-in-spring",
    "penboutique": "https://www.penboutique.com/products/hobonichi-2027-weeks-akiko-miyakoshi-once-in-spring",
    "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-akiko-miyakoshi-once-in-spring",
    "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-akiko-miyakoshi-once-in-spring",
    "kinousa": "https://usa.kinokuniya.com/products/4580812709774",
    "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-akiko-miyakoshi-once-in-spring-eng-tall-slim-jan-start",
    "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-akiko-miyakoshi-once-in-spring",
    "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-once-in-spring-english-tall-slim-jan-start",
    "mlovewell": "https://www.mlovewell.com/products/2027-hobonichi-techo-english-weeks-akiko-miyakoshi-once-in-spring",
}

METEOR_SHOPS = {
    "1101": "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_kubota/",
    # Added Nov 19, 2026 (JAN 4580812709767, same as the other English Weeks listings).
    "dromgooles": "https://www.dromgooles.com/products/hobonichi-2027-weeks-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
    "papermouse": "https://www.thepapermouse.com/products/hobonichi-techo-2027-weeks-planner-hiroko-kubota-meteor-shower-in-the-light-blue-forest-english",
    "atlas": "https://www.atlasstationers.com/products/hobonichi-techo-weeks-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
    "wonder": "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
    "penboutique": "https://www.penboutique.com/products/hobonichi-2027-weeks-hiroko-kubota-meteor-shower-light-blue-forest",
    "yoseka": "https://yosekastationery.com/products/hobonichi-techo-weeks-2027-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
    "jennibick": "https://www.jennibick.com/products/hobonichi-techo-weeks-2027-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
    "blesket": "https://blesket.com/products/hobonichi-techo-2027-weeks-hiroko-kubota-meteor-shower-in-the-light-blue-forest-eng-tall-slim-jan-start",
    "journalshop": "https://www.thejournalshop.com/products/hobonichi-2027-weeks-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
    "buchan": "https://www.buchanst.com/products/hobonichi-techo-2027-weeks-wallet-planner-book-meteor-shower-in-the-light-blue-forest-english-tall-slim-jan-start",
    "mlovewell": "https://www.mlovewell.com/products/2027-hobonichi-techo-english-weeks-hiroko-kubota-meteor-shower-in-the-light-blue-forest",
}

SKIPPED_NO_LISTING = {
    "bobo", "baum", "laywines", "kinosg", "goulet", "lovenotebooks",  # omoi and simplepaper left the catalog Nov 19, 2026
}

NEW_URLS = set(A5_SHOPS.values()) | set(A6_EN_SHOPS.values()) | set(ONCE_SHOPS.values()) | set(METEOR_SHOPS.values()) | {PEN_JP_A6}


class HonSheepWeeksDesignsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())
        cls.stock = json.loads((ROOT / "data" / "stock.json").read_text())
        cls.changes = json.loads((ROOT / "data" / "changes.json").read_text())

    def _hits(self, cid):
        found = {}
        for store in self.cfg["stores"]:
            hits = [p for p in store["products"] if p.get("canonical") == cid]
            if hits:
                found[store["id"]] = hits
        return found

    def test_canonical_labels_and_official_keys(self):
        by_id = {c["id"]: c for c in self.cfg["canonical"]}
        self.assertEqual(by_id["hon-a5-sheep"]["label"], "HON A5 · Bow & Tie: Sheep Sheep Sheep")
        self.assertEqual(by_id["hon-a5-sheep"]["type"], "HON")
        self.assertEqual(by_id["hon-a6-sheep"]["label"], "HON A6 · Bow & Tie: Sheep Sheep Sheep")
        self.assertEqual(by_id["hon-a6-sheep"]["type"], "HON")
        self.assertEqual(by_id["weeks-once-in-spring"]["label"], "Weeks · Akiko Miyakoshi: Once, in Spring")
        self.assertEqual(by_id["weeks-meteor-shower"]["label"], "Weeks · Hiroko Kubota: Meteor Shower in the Light Blue Forest")
        official = {p["source_key"]: p for s in self.cfg["stores"] if s["id"] == "1101" for p in s["products"]}
        self.assertEqual(official["cb27_hon_tiesheep"]["canonical"], "hon-a5-sheep")
        self.assertEqual(official["ob27_hon_tiesheep"]["canonical"], "hon-a6-sheep")
        self.assertEqual(official["wb27_miyakoshi"]["canonical"], "weeks-once-in-spring")
        self.assertEqual(official["wb27_kubota"]["canonical"], "weeks-meteor-shower")

    def test_verified_shop_urls_and_conflicts_left_out(self):
        a5 = self._hits("hon-a5-sheep")
        self.assertEqual({sid: rows[0]["url"] for sid, rows in a5.items()}, A5_SHOPS)
        self.assertTrue(all(len(rows) == 1 for rows in a5.values()))

        a6 = self._hits("hon-a6-sheep")
        self.assertEqual(set(a6), set(A6_EN_SHOPS) | {"penboutique"})
        for sid, url in A6_EN_SHOPS.items():
            urls = [p["url"] for p in a6[sid]]
            self.assertIn(url, urls)
        self.assertEqual({p["url"] for p in a6["penboutique"]}, {A6_EN_SHOPS["penboutique"], PEN_JP_A6})
        self.assertIn("Japanese", next(p for p in a6["penboutique"] if p["url"] == PEN_JP_A6)["source_title"])

        once = self._hits("weeks-once-in-spring")
        self.assertEqual({sid: rows[0]["url"] for sid, rows in once.items()}, ONCE_SHOPS)
        meteor = self._hits("weeks-meteor-shower")
        self.assertEqual({sid: rows[0]["url"] for sid, rows in meteor.items()}, METEOR_SHOPS)

        urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertNotIn(JENNI_A6, urls)
        for sid in SKIPPED_NO_LISTING:
            store = next(s for s in self.cfg["stores"] if s["id"] == sid)
            cids = {p.get("canonical") for p in store["products"]}
            self.assertTrue(cids.isdisjoint({"hon-a5-sheep", "hon-a6-sheep", "weeks-once-in-spring", "weeks-meteor-shower"}), sid)
        kinousa = next(s for s in self.cfg["stores"] if s["id"] == "kinousa")
        k_cids = {p.get("canonical") for p in kinousa["products"]}
        self.assertIn("weeks-once-in-spring", k_cids)
        self.assertTrue(k_cids.isdisjoint({"hon-a5-sheep", "hon-a6-sheep", "weeks-meteor-shower"}))

    def test_design_pages_cover_only_these_canonicals(self):
        a5 = next(d for d in site.DESIGNS if d["slug"] == "a5-sheep-sheep-sheep")
        a6 = next(d for d in site.DESIGNS if d["slug"] == "a6-sheep-sheep-sheep")
        once = next(d for d in site.DESIGNS if d["slug"] == "once-in-spring")
        meteor = next(d for d in site.DESIGNS if d["slug"] == "meteor-shower-in-the-light-blue-forest")
        self.assertEqual(a5["parent"], "hobonichi-techo-2027-hon")
        self.assertEqual(a6["parent"], "hobonichi-techo-2027-hon")
        self.assertEqual(once["parent"], "hobonichi-weeks-2027")
        self.assertEqual(meteor["parent"], "hobonichi-weeks-2027")
        book_a5 = {"canonical": "hon-a5-sheep", "type": "HON", "label": "HON A5 · Bow & Tie: Sheep Sheep Sheep", "url": "x"}
        book_a6 = {"canonical": "hon-a6-sheep", "type": "HON", "label": "HON A6 · Bow & Tie: Sheep Sheep Sheep", "url": PEN_JP_A6}
        slash = {"canonical": "hon-a5-slash-navy", "type": "HON", "label": "HON A5 · Slash (Navy)", "url": "y"}
        weeks_once = {"canonical": "weeks-once-in-spring", "type": "Weeks", "label": "Weeks · Akiko Miyakoshi: Once, in Spring", "url": "z"}
        weeks_meteor = {"canonical": "weeks-meteor-shower", "type": "Weeks", "label": "Weeks · Hiroko Kubota: Meteor Shower in the Light Blue Forest", "url": "w"}
        weeks_sheep = {"canonical": "weeks-sheep", "type": "Weeks", "label": "Weeks · Bow & Tie: Sheep Sheep Sheep", "url": "v"}
        ao = {"canonical": "ao-meteor-shower", "type": "Dot grid notebook", "label": "Archer and Olive · Meteor Shower", "url": "u"}
        self.assertTrue(a5["match"](book_a5))
        self.assertFalse(a5["match"](book_a6))
        self.assertFalse(a5["match"](slash))
        self.assertTrue(a6["match"](book_a6))
        self.assertFalse(a6["match"](book_a5))
        self.assertTrue(once["match"](weeks_once))
        self.assertFalse(once["match"](weeks_meteor))
        self.assertFalse(once["match"](weeks_sheep))
        self.assertTrue(meteor["match"](weeks_meteor))
        self.assertFalse(meteor["match"](ao))
        self.assertFalse(meteor["match"](weeks_sheep))

    def test_new_rows_are_first_observations_only(self):
        saved = {p["url"]: p for p in self.stock["products"]}
        event_urls = {c["url"] for c in self.changes}
        cfg_urls = [p["url"] for s in self.cfg["stores"] for p in s["products"]]
        self.assertEqual(set(saved), set(cfg_urls))
        for url in NEW_URLS:
            row = saved[url]
            self.assertEqual(row["first_seen"], row["status_since"])
            self.assertNotEqual(row["status"], "unknown")
            self.assertNotIn(url, event_urls)

    def test_footer_hosts_the_saashub_badge(self):
        badge = ROOT / "site" / "assets" / "badges" / "saashub_v2_300x100.png"
        self.assertTrue(badge.is_file())
        self.assertGreater(badge.stat().st_size, 1000)
        src = (ROOT / "scripts" / "build_site.py").read_text()
        self.assertIn('class="foot-badge"', src)
        self.assertIn('href="https://www.saashub.com/stationery-drop-watch?utm_source=badge&utm_campaign=badge&utm_content=stationery-drop-watch&badge_variant=color&badge_kind=approved"', src)
        self.assertIn('src="/assets/badges/saashub_v2_150x50.png"', src)
        self.assertIn('srcset="/assets/badges/saashub_v2_150x50.png 1x, /assets/badges/saashub_v2_300x100.png 2x"', src)
        self.assertIn('alt="Stationery Drop Watch on SaaSHub"', src)
        self.assertIn('class="badge-saashub"', src)
        css = (ROOT / "site" / "assets" / "style.css").read_text()
        self.assertIn(".foot-badge{margin:0;display:flex;flex-wrap:wrap;align-items:center;gap:12px}", css)
        self.assertIn(".foot-badge a{display:inline-block;line-height:0;max-width:100%}", css)
        self.assertIn(".foot-badge img{width:150px;height:63px;object-fit:contain;object-position:center;display:block;max-width:100%}", css)
