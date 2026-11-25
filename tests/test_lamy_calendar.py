"""Lamy special and limited edition release calendar (owner-approved design, Nov 23, 2026; build started Nov 24)."""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site

AUTH_HOSTS = {"www.gouletpens.com", "goldspot.com", "www.penboutique.com", "yosekastationery.com",
              "www.dromgooles.com", "cultpens.com"}
SOURCE_HOSTS = {"www.lamy.com", "www.gouletpens.com", "www.stationerynews.net", "www.linkedin.com"}


def pen(i, first=None, official=None):
    return {"id": f"p{i}", "name": f"Pen {i:03d}", "line": "LAMY safari", "kind": "Special edition", "qty": "", "desc": "",
            "official_date": official, "first_listed": first, "first_listed_store": "goulet", "sources": [], "listings": []}


class SplitTests(unittest.TestCase):
    today = dt.date(2026, 11, 24)

    def test_latest_holds_20_newest_older_holds_50_more_and_the_rest_drop(self):
        start = dt.date(2020, 1, 1)
        pens = [pen(i, first=(start + dt.timedelta(days=7 * i)).isoformat()) for i in range(75)]
        up, latest, older = site.lamy_split(pens, self.today, 20, 50)
        self.assertEqual(up, [])
        self.assertEqual(len(latest), 20)
        self.assertEqual(len(older), 50)
        self.assertEqual([p["id"] for p in latest], [f"p{i}" for i in range(74, 54, -1)])  # newest first
        self.assertEqual([p["id"] for p in older], [f"p{i}" for i in range(54, 4, -1)])
        self.assertNotIn("p0", {p["id"] for p in latest + older})  # the five oldest are dropped

    def test_defaults_are_20_and_50(self):
        self.assertEqual((site.LAMY_LATEST_MAX, site.LAMY_OLDER_MAX), (20, 50))

    def test_fewer_than_20_all_latest(self):
        up, latest, older = site.lamy_split([pen(i, first=f"2026-0{1 + i}-01") for i in range(5)], self.today)
        self.assertEqual((len(latest), len(older)), (5, 0))

    def test_upcoming_moves_on_its_official_date(self):
        p = pen(1, official="2026-12-01")
        self.assertEqual(site.lamy_split([p], self.today)[0], [p])
        self.assertEqual(site.lamy_split([p], dt.date(2026, 12, 1))[1], [p])

    def test_no_official_date_moves_when_first_listed_and_tba_stays_upcoming(self):
        tba = pen(2)
        listed = pen(3, first="2026-11-24")
        up, latest, _ = site.lamy_split([tba, listed], self.today)
        self.assertEqual(up, [tba])
        self.assertEqual(latest, [listed])

    def test_official_date_wins_over_first_listed(self):
        p = pen(4, first="2026-11-01", official="2026-12-05")
        self.assertEqual(site.lamy_split([p], self.today)[0], [p])


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fname, cls.doc = site.build_lamy(today=dt.date(2026, 11, 24))
        cls.cfg = json.loads((ROOT / "lamy.json").read_text())

    def test_no_amazon_or_affiliate_links(self):
        self.assertNotRegex(self.doc, r'href="https?://(www\.)?(amazon\.|amzn\.to|a\.co/)')
        self.assertNotRegex(self.doc.lower(), r"[?&](tag|aff|affiliate)=")
        urls = re.findall(r'"(https?://[^"]+)"', json.dumps(self.cfg))
        self.assertTrue(urls)
        self.assertFalse([u for u in urls if re.search(r"amazon\.|amzn\.|//a\.co/", u)])

    def test_shop_links_only_go_to_authorized_shops_and_lamy(self):
        shop_links = re.findall(r'<a class="lamy-shop[^"]*" href="([^"]+)"', self.doc)
        self.assertTrue(shop_links)
        for u in shop_links:
            self.assertIn(urlparse(u).netloc, AUTH_HOSTS | {"www.lamy.com"}, u)
        for u in re.findall(r'<span class="lamy-src">Source: (.*?)</span>', self.doc):
            for h in re.findall(r'href="([^"]+)"', u):
                self.assertIn(urlparse(h).netloc, SOURCE_HOSTS, h)

    def test_lamy_us_store_only_on_pens_it_sells(self):
        self.assertEqual(self.doc.count("Lamy US store <small>maker, link only</small>"), 2)

    def test_no_status_without_checker_data(self):
        """No Lamy URL is in the checker's data, so no in-stock label and no in-stock filter."""
        idx = site.lamy_status_index()
        if not any(idx.get(l["url"]) for p in self.cfg["pens"] for l in p["listings"]):
            self.assertNotIn("in stock</span>", self.doc)
            self.assertNotIn('id="lamy-instock"', self.doc)

    def test_eleven_2026_pens_with_first_listed_dates_and_empty_upcoming(self):
        self.assertEqual(self.doc.count('<article class="lamy-entry"'), 11)
        self.assertIn("No upcoming Lamy special or limited editions are confirmed right now.", self.doc)
        self.assertEqual(self.doc.count('<span class="lbl">First listed</span>'), 11)

    def test_validate_rejects_unauthorized_shop_and_amazon(self):
        bad = json.loads(json.dumps(self.cfg))
        bad["pens"][0]["listings"].append({"store_id": "atlas", "url": "https://www.atlasstationers.com/products/x", "listed": "2026-11-01"})
        with self.assertRaises(SystemExit):
            site.lamy_validate(bad)
        bad = json.loads(json.dumps(self.cfg))
        bad["pens"][0]["sources"].append(["x", "https://www.amazon.com/dp/B000"])
        with self.assertRaises(SystemExit):
            site.lamy_validate(bad)
        bad = json.loads(json.dumps(self.cfg))
        bad["shops"]["milligram"] = {"evidence": "none"}
        with self.assertRaises(SystemExit):
            site.lamy_validate(bad)

    def test_no_link_only_shops_and_no_banned_words_or_emoji(self):
        link_only = {s["id"] for s in site.stores["stores"] if s.get("link_only")}
        self.assertFalse(link_only & set(self.cfg["shops"]))
        low = self.doc.lower()
        for word in ("midori", "traveler", "designphil", "bullet journal", "milligram"):
            self.assertNotIn(word, low)
        self.assertIsNone(re.search("[\U0001F300-\U0001FAFF\u2600-\u27BF]", self.doc))

    def test_linked_from_nav_footer_home_404_and_sitemap_but_not_a_tracker(self):
        href = f'href="/{site.LAMY_SLUG}/"'
        self.assertIn(href, site.build_index())
        self.assertIn(href, site.build_404())
        self.assertGreaterEqual(self.doc.count(href), 2)  # header and footer
        self.assertIn(f"/{site.LAMY_SLUG}/</loc>", site.build_sitemap())
        self.assertNotIn(site.LAMY_SLUG + "/", [h for h, _ in site.NAV_TRACKERS])

    def test_shop_count_stays_27(self):
        self.assertEqual(site.N_STORES, 27)


class LamyMentionTests(unittest.TestCase):
    """About, Guides and homepage search point to the calendar (owner yes, Nov 24, 2026)."""

    ABOUT = ("Separately, our <a href=\"/lamy-special-edition-release-calendar/\">Lamy release calendar</a> lists "
             "Lamy&#x27;s special and limited edition pens, when each was first listed, and the authorized shops that sell them. "
             "It is not a tracker, and we don&#x27;t check stock on those links.")

    def test_about_how_it_works_sentence(self):
        html = site.build_about()
        self.assertIn(self.ABOUT, html)
        self.assertLess(html.index("dealer list)."), html.index("Separately, our"))
        self.assertLess(html.index("Separately, our"), html.index("When a sold-out"))

    def test_guides_see_also_line_keeps_the_guide_count(self):
        _, html = site.build_guides_index()
        self.assertIn('See also: <a href="/lamy-special-edition-release-calendar/">Lamy release calendar</a>, '
                      "Lamy&#x27;s special and limited edition pens, when each was first listed, and the authorized shops that sell them.",
                      html)
        self.assertIn(f"{len(site.GUIDES)} guides", html)
        self.assertEqual(len(site.GUIDES), 6)
        self.assertNotIn(site.LAMY_SLUG, [h.strip("/") for h, _ in site.GUIDES])
        self.assertNotIn(site.LAMY_SLUG, html[html.index('<ul class="guide-list">'):html.index("</ul>", html.index('<ul class="guide-list">'))])

    def test_search_finds_the_calendar_for_lamy_and_pen_names(self):
        from test_find_item import hits
        idx = site.search_index()
        item = next(i for i in idx["items"] if i["id"] == "lamy-release-calendar")
        self.assertEqual(item["n"], "Lamy release calendar")
        self.assertEqual(item["u"], f"/{site.LAMY_SLUG}/")
        self.assertEqual(item["s"], f"{len(site.LAMY_CFG['pens'])} special and limited edition pens, no stock checks")
        self.assertEqual(item["sh"], [])
        self.assertEqual(idx["trackers"]["p"], {"l": "Lamy releases", "u": f"/{site.LAMY_SLUG}/"})
        for q in ("lamy", "bog oak", "pine", "safari", "al-star", "scala pearl"):
            self.assertIn("lamy-release-calendar", [i["id"] for i in hits(idx, q)], q)
        low = json.dumps(item).lower()
        for word in ("midori", "traveler", "designphil", "bullet", "amazon"):
            self.assertNotIn(word, low)

    def test_no_search_entry_without_pens(self):
        old = site.LAMY_LIVE
        try:
            site.LAMY_LIVE = False
            self.assertIsNone(site.lamy_search_item())
            self.assertEqual(site.lamy_see_also(), "")
        finally:
            site.LAMY_LIVE = old


if __name__ == "__main__":
    unittest.main()
