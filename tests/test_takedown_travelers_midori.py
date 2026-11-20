"""Traveler's Company and MIDORI takedown, Nov 19, 2026.

TRAVELER'S COMPANY USA asked us to remove every Traveler's Company and MIDORI product. The owner approved the
removal and the exact notice wording. These tests keep both brands out of the checker, the alerts and every page,
keep the old URLs reachable as the notice, and keep the site-wide shop count honest.
"""
import html
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402
import new_in_stock  # noqa: E402

GONE_STORES = {"travelerscompanyusa", "mdproductusa", "tokyopenshop", "omoi", "simplepaper"}
NEW_STORES = {"dromgooles", "milligram", "presentandcorrect", "cultpens", "goldspot"}
BRAND_WORDS = re.compile(r"traveler'?s (company|notebook)|midori|md product|md notebook|designphil", re.I)
APPROVED_FIRST = ("On November 17, 2026, we reached out to Traveler's Company and to MIDORI's parent company, Designphil, "
                  "through their official contact forms.")
APPROVED_LAST = "If you'd like restock news for these brands, the only route they've left you is their newsletter."


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "stores.json").read_text())

    def test_no_traveler_or_midori_row_is_checked(self):
        ids = {s["id"] for s in self.cfg["stores"]}
        self.assertTrue(GONE_STORES.isdisjoint(ids))
        for s in self.cfg["stores"]:
            self.assertNotIn(s.get("section"), ("travelers", "midori"), s["id"])
            self.assertNotIn("Traveler", s.get("note", ""), s["id"])
            for p in s["products"]:
                self.assertNotIn(p.get("section"), ("travelers", "midori"), p["url"])
                self.assertIsNone(BRAND_WORDS.search(p["label"] + " " + p.get("source_title", "")), p["url"])
        for c in self.cfg["canonical"]:
            self.assertNotIn(c.get("section"), ("travelers", "midori"), c["id"])
            self.assertFalse(c["id"].startswith(("tn-", "md-")), c["id"])

    def test_checked_shop_count_is_27_with_the_replacements(self):
        checked = {s["id"] for s in self.cfg["stores"] if s["products"] and s["platform"] in ("shopify", "hobonichi")}
        self.assertEqual(len(checked), 27)
        self.assertTrue(NEW_STORES <= checked)
        self.assertEqual(site.N_STORES, 27)

    def test_new_shops_track_only_products_we_already_track(self):
        canon = {c["id"] for c in self.cfg["canonical"]}
        for s in self.cfg["stores"]:
            if s["id"] in NEW_STORES:
                self.assertTrue(s["products"], s["id"])
                for p in s["products"]:
                    self.assertIn(p["canonical"], canon, p["url"])
                    if "?variant=" in p["url"]:
                        self.assertEqual(p["url"].split("?variant=")[1], str(p["variant_id"]))


class AlertTests(unittest.TestCase):
    def test_new_in_stock_never_alerts_for_either_brand(self):
        events = [{"at": "2026-11-20T00:00:00+00:00", "store_id": "travelerscompanyusa", "label": "x", "to": "in_stock", "url": "u1"},
                  {"at": "2026-11-20T00:00:00+00:00", "store_id": "papermouse", "label": "y", "to": "in_stock", "url": "u2", "section": "midori"},
                  {"at": "2026-11-20T00:00:00+00:00", "store_id": "papermouse", "label": "z", "to": "in_stock", "url": "u3"}]
        self.assertEqual([c["url"] for c in new_in_stock.fresh_in_stock([], events)], ["u3"])

    def test_old_rows_never_reach_a_page_or_feed(self):
        for p in site.stock["products"]:
            self.assertNotIn(p.get("section"), site.TAKEDOWN_SECTIONS)
        for c in site.changes:
            self.assertNotIn(c.get("section"), site.TAKEDOWN_SECTIONS)
        self.assertEqual(site.LIVE, ["dotgrid"])
        self.assertNotIn("travelers", site.SECTIONS)
        self.assertNotIn("midori", site.SECTIONS)


class NoticeTests(unittest.TestCase):
    def test_notice_text_is_the_approved_wording(self):
        self.assertEqual(site.TAKEDOWN_HEADING, "Why Traveler's Company and MIDORI are gone")
        self.assertEqual(len(site.TAKEDOWN_NOTICE), 5)
        self.assertTrue(site.TAKEDOWN_NOTICE[0].startswith(APPROVED_FIRST))
        self.assertEqual(site.TAKEDOWN_NOTICE[-1], APPROVED_LAST)
        self.assertIn('"pushes that stock toward resellers,"', site.TAKEDOWN_NOTICE[1])

    def test_old_urls_show_the_notice(self):
        for slug, noindex in ((site.TN_SLUG, False), (site.MIDORI_SLUG, False), (site.TN_GUIDE_SLUG, True)):
            fname, doc = site.build_takedown_notice(slug, noindex=noindex)
            text = html.unescape(doc)
            self.assertEqual(fname, slug + "/")
            self.assertIn(f"<h1>{site.TAKEDOWN_HEADING}</h1>", text)
            for para in site.TAKEDOWN_NOTICE:
                self.assertIn(f"<p>{para}</p>", text)
            self.assertEqual('<meta name="robots" content="noindex">' in doc, noindex)
            self.assertNotIn("og-travelers.png", doc)
            self.assertNotIn("og-midori.png", doc)

    def test_item_pages_redirect_to_their_notice(self):
        for parent, slugs in site.TAKEDOWN_ITEMS.items():
            for slug in slugs:
                self.assertEqual(site.REDIRECTS[f"{parent}/{slug}"], parent + "/")
        self.assertEqual(site.REDIRECTS["travelers-notebook-regular-size"], site.TN_SLUG + "/")
        cf = (ROOT / "cloudflare/_redirects").read_text()
        for parent, slugs in site.TAKEDOWN_ITEMS.items():
            for slug in slugs:
                self.assertIn(f"/{parent}/{slug}/  /{parent}/  301", cf)
        self.assertNotIn("#tracker", cf)


NOTICE_CARD = re.compile(r'<li class="hub-card hub-notice">.*?</li>', re.S)


class HomeNoticeCardTests(unittest.TestCase):
    """Owner, Nov 19: the announcement stays on the homepage as a third card beside the two tracker cards."""

    def setUp(self):
        self.doc = site.build_index()
        grid = re.search(r'<ul class="hub-grid">(.*?)</ul>', self.doc, re.S).group(1)
        self.cards = re.findall(r'<li class="hub-card[^"]*">.*?</li>', grid, re.S)

    def test_notice_is_the_third_card_after_the_two_trackers(self):
        self.assertEqual(len(self.cards), 3)
        self.assertNotIn("hub-notice", self.cards[0] + self.cards[1])
        self.assertTrue(self.cards[2].startswith('<li class="hub-card hub-notice">'))
        self.assertEqual(len(NOTICE_CARD.findall(self.doc)), 1)

    def test_card_has_heading_verbatim_line_and_button_only(self):
        card = self.cards[2]
        self.assertIn('href="/travelers-company-limited-edition/"', card)
        self.assertIn("<h3>Why Traveler&#x27;s Company and MIDORI are gone</h3>", card)
        self.assertIn('<span class="hub-go">Read the notice</span>', card)
        self.assertNotIn("hub-count", card)
        self.assertNotIn("in stock", html.unescape(card).lower())
        self.assertNotIn("shops", html.unescape(card).lower())
        line = html.unescape(re.search(r"</h3><p>(.*?)</p>", card).group(1))
        self.assertEqual(line, site.HOME_NOTICE_LINE)
        notice = " ".join(site.TAKEDOWN_NOTICE)
        for sentence in line.split(". "):
            self.assertIn(sentence.rstrip("."), notice)

    def test_phones_keep_every_card_icon_at_a_two_column_size(self):
        css = (ROOT / "site/assets/style.css").read_text()
        self.assertNotRegex(css, r"\.hub-art\{display:none\}")
        self.assertIn("  .hub-art svg{width:96px;max-width:96px}\n", css)
        self.assertIn('<span class="hub-art"><svg', self.cards[2])
        for card in self.cards:
            self.assertIn('<span class="hub-art"><svg', card)

    def test_grid_is_three_wide_and_the_card_spans_the_row_when_it_wraps(self):
        css = (ROOT / "site/assets/style.css").read_text()
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", css)
        self.assertIn("@media (max-width:1000px){.hub-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hub-notice{grid-column:1/-1}}", css)


GIFT_NOTE = re.compile(r'<aside class="gift-note">.*?</aside>', re.S)
GONE_SHOP_URLS = re.compile(r"simplepaper|travelerscompanyusa|md-product-usa|tokyopenshop|omoionline", re.I)


class GiftGuideTests(unittest.TestCase):
    """Owner, Nov 19: the gift guide drops both brands but its traveler section says we meant to feature them, and why."""

    def setUp(self):
        self.doc = site.build_gift_guide()[1]

    def test_only_the_traveler_note_names_either_brand(self):
        notes = GIFT_NOTE.findall(self.doc)
        self.assertEqual(len(notes), 1)
        rest = GIFT_NOTE.sub("", self.doc)
        self.assertIsNone(BRAND_WORDS.search(html.unescape(rest)))
        self.assertNotRegex(html.unescape(rest), re.compile(r"traveler'?s|midori", re.I))
        self.assertIsNone(GONE_SHOP_URLS.search(self.doc))
        self.assertNotIn(site.MIDORI_SLUG, self.doc)
        self.assertNotIn(site.TN_GUIDE_SLUG, self.doc)
        self.assertEqual(self.doc.count("/travelers-company-limited-edition/"), 1)
        self.assertIn('href="/travelers-company-limited-edition/">Read the full story</a>', notes[0])
        trav = self.doc[self.doc.index('<h2 id="traveler">'):self.doc.index('<h2 id="dot-grid">')]
        self.assertIn(notes[0], trav)

    def test_note_uses_only_approved_facts_and_the_one_allowed_quote(self):
        note = site.GIFT_NOTE
        facts = json.loads((ROOT / "takedown-2026-11-19/announcement-facts.json").read_text()) \
            if (ROOT / "takedown-2026-11-19/announcement-facts.json").exists() else None
        self.assertEqual(re.findall(r'"([^"]+)"', note), ["pushes that stock toward resellers."])
        notice = " ".join(site.TAKEDOWN_NOTICE)
        self.assertIn('"pushes that stock toward resellers,"', notice)
        for phrase in ("November 17", "November 19", "TRAVELER'S COMPANY USA", "Designphil",
                       "permission to use their official product photos", "remove every Traveler's Company and MIDORI product",
                       "a tracker telling everyone when something is back in stock"):
            self.assertIn(phrase, note)
            self.assertIn(phrase, notice)
        for banned in ("legal", "takedown", "lawyer", "cease"):
            self.assertNotIn(banned, note.lower())
        if facts:
            self.assertEqual(facts["approved_notice_text"][1:], list(site.TAKEDOWN_NOTICE))

    def test_new_to_journaling_has_cousin_avec_then_our_two_a5s(self):
        sec = self.doc[self.doc.index('<h2 id="journaling">For someone new to journaling</h2>'):self.doc.index('<h2 id="traveler">')]
        items = re.findall(r"<li>.*?</li>", sec, re.S)
        self.assertEqual(len(items), 3)
        self.assertIn("Cousin Avec (A5)", items[0])
        self.assertIn('href="https://www.1101.com/store/techo/en/2027/pc/detail_cover/cb27_avec/"', items[0])
        self.assertIn("my partner and I both use", items[0])
        self.assertIn('href="https://www.amazon.com/dp/B0HRTLMZ1M" data-own-product', items[1])
        self.assertIn('href="https://www.amazon.com/dp/B0HRTTCH4D" data-own-product', items[2])
        self.assertNotRegex(sec, r"tag=|arden|b0nem0ther|\bfan\b")
        self.assertNotRegex(sec.lower(), r"arden|b0nem0ther|\bfan\b")
        we_make = self.doc[self.doc.index('<h2 id="we-make">'):]
        self.assertNotIn("amazon.com/dp/B0HRTLMZ1M", we_make)  # listed once, under new to journaling
        self.assertNotIn("amazon.com/dp/B0HRTTCH4D", we_make)
        self.assertIn('href="#journaling"', we_make)

    def test_traveler_picks_are_tracked_listings(self):
        for k in ("plannera6", "tragen", "aostag"):
            self.assertTrue(site.gift_listings(k), k)
        for k, (canon, *_rest) in site.GIFT_PICKS.items():
            self.assertNotRegex(canon, r"^(tn-|md-)", k)


class SiteCopyTests(unittest.TestCase):
    def test_no_tracker_page_nav_or_faq_mentions_either_brand(self):
        docs = [("index.html", NOTICE_CARD.sub("", site.build_index())), ("about.html", site.build_about()), ("404.html", site.build_404()),
                (site.HOBO_TRACKER, site.build_hobo_tracker())]
        docs += [site.build_group(g, {}) for g in site.GROUPS]
        docs += [site.build_guides_index(), site.build_sold_out(), site.build_follow(), site.build_contact()]
        for name, doc in docs:
            self.assertIsNone(BRAND_WORDS.search(html.unescape(doc)), name)
            self.assertNotIn("/travelers-company-limited-edition/", doc, name)
            self.assertNotIn("/midori-md-limited-edition/", doc, name)
        sitemap = site.build_sitemap()
        self.assertNotIn(site.TN_GUIDE_SLUG, sitemap)
        self.assertNotIn("regular-black", sitemap)

    def test_every_shop_total_on_the_home_page_is_27(self):
        home = html.unescape(site.build_index())
        totals = set(re.findall(r"\b(\d+) shops\b", re.sub(r"<[^>]+>", " ", home)))
        self.assertIn("27", totals)
        self.assertIn("27 shops across all trackers", home)
        self.assertIn("checks 27 shops", home)


if __name__ == "__main__":
    unittest.main()
