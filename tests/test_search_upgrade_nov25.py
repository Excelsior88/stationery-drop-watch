"""Nov 25, 2026 search upgrade (owner t1974u): '/' badge, Lamy pens and guides in Find my item, ink page ?q= filter,
Enter on ink matches opens the filtered ink page, Lamy cards in Older releases open from a link."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

APP = (ROOT / "site/assets/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "site/assets/style.css").read_text(encoding="utf-8")
BANNED = re.compile(r"midori|designphil|travell?er'?s\s+company|bullet", re.I)


class FindBar(unittest.TestCase):
    def setUp(self):
        self.bar = site.find_bar()

    def test_placeholder_badge_and_shortcuts(self):
        self.assertIn('placeholder="Planner, dot grid, ink, Lamy pen, guide or shop"', self.bar)
        self.assertIn('aria-keyshortcuts="/ Control+K Meta+K"', self.bar)
        self.assertIn('<kbd class="find-kbd" aria-hidden="true">/</kbd>', self.bar)

    def test_badge_hides_on_focus_text_and_touch(self):
        self.assertIn(".find-field input:focus~.find-kbd,.find-field input:not(:placeholder-shown)~.find-kbd{display:none}", CSS)
        self.assertIn("@media (hover:none),(pointer:coarse),(max-width:700px){.find-kbd{display:none}}", CSS)
        self.assertIn('(e.key === "k" || e.key === "K")', APP)
        self.assertIn('e.key === "/"', APP)


class SearchIndexAdditions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = site.search_index()
        cls.pens = [i for i in cls.idx["items"] if i["id"].startswith("lamy-") and i["id"] != "lamy-release-calendar"]
        cls.guides = [i for i in cls.idx["items"] if i["t"] == "g"]

    def test_every_pen_on_the_calendar_links_to_its_card(self):
        up, new, old = site.lamy_split(site.LAMY_CFG["pens"], site.lamy_today())
        shown = up + new + old
        self.assertEqual(len(self.pens), len(shown))
        self.assertEqual(len(self.pens), 11)
        for p, item in zip(shown, self.pens):
            self.assertEqual(item["t"], "p")
            self.assertEqual(item["n"], p["name"])
            self.assertEqual(item["u"], f"/{site.LAMY_SLUG}/#pen-{p['id']}")
            self.assertIn(p["kind"], item["s"])
            if p.get("first_listed") and not p.get("official_date"):
                d = site.dt.date.fromisoformat(p["first_listed"])
                self.assertIn(f"First listed {d.strftime('%b')} {d.day}, {d.year}", item["s"])
            self.assertEqual(item["sh"], [])

    def test_pen_anchors_exist_on_the_built_lamy_page(self):
        cards = "".join(site.lamy_card(p, {}) for p in site.LAMY_CFG["pens"])
        for item in self.pens:
            self.assertIn(f'id="{item["u"].split("#")[1]}"', cards)

    def test_guides_are_the_guides_page_list(self):
        self.assertEqual([(g["u"], g["n"]) for g in self.guides], [("/" + h, t) for h, t in site.GUIDES])
        for g in self.guides:
            self.assertEqual(g["s"], site.GUIDE_BLURBS["/".join([g["u"].strip("/"), ""])])
        self.assertEqual(self.idx["trackers"]["g"], {"l": "Guides", "u": "/guides/"})

    def test_new_entries_follow_house_style(self):
        for item in self.pens + self.guides:
            for k in ("n", "s", "q"):
                self.assertNotRegex(item.get(k, ""), BANNED, item["id"])
            self.assertRegex(item["u"], r"^/(?![/\\])")


class InkPageAndEnter(unittest.TestCase):
    def test_ink_cards_carry_search_words(self):
        for ink in site.INK_CFG["inks"]:
            card = site.ink_card(ink)
            if not card:
                continue
            m = re.search(r'data-q="([^"]*)"', card)
            self.assertTrue(m, ink["id"])
            for word in re.findall(r"[a-z0-9]+", site._search_fold(ink["name"])):
                self.assertIn(word, m.group(1), ink["id"])
            self.assertNotRegex(m.group(1), BANNED)

    def test_app_reads_q_on_the_ink_page_and_enter_goes_there(self):
        self.assertIn('const inkQ = (params.get("q") || "").trim().slice(0, 100);', APP)
        self.assertIn('`Showing inks that match "${inkQ}". `', APP)
        self.assertIn('`No ink on the tracker matches "${inkQ}". `', APP)
        self.assertIn('all.textContent = "Show all inks";', APP)
        self.assertNotIn('hits.find(item => item.t === "i")', APP)
        self.assertIn('const TYPE_RANK = { h: 0, d: 1, i: 2, p: 3, g: 4 };', APP)

    def test_lamy_older_fold_opens_for_a_linked_card(self):
        self.assertIn("if (older && older.contains(el) && !older.open) older.open = true;", APP)
        self.assertIn('window.addEventListener("hashchange", openPenHash);', APP)


if __name__ == "__main__":
    unittest.main()
