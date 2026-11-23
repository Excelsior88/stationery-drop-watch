"""Link-only shops (stores.json "link_only": true): never requested, shown as plain links, no status, no alerts.

The request proof patches requests.adapters.HTTPAdapter.send, the lowest layer every checker and ink-tracker request passes
through (redirect hops included), runs the real code paths against the real stores.json and inks.json, and asserts
that no recorded URL belongs to a link-only shop."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import checker  # noqa: E402
import ink_tracker  # noqa: E402
import new_in_stock  # noqa: E402
import build_site as site  # noqa: E402

LINK_ONLY_IDS = {"blesket", "milligram", "kinousa", "kinosg", "laywines", "notebooktherapy"}  # Laywine's and Notebook Therapy since Nov 23 (terms ban automated access)
BLOCKED = {"blesket.com", "www.blesket.com", "milligram.com", "www.milligram.com",
           "usa.kinokuniya.com", "kinokuniya.com.sg", "www.kinokuniya.com.sg",
           "laywines.com", "www.laywines.com", "notebooktherapy.com", "www.notebooktherapy.com"}
STORES = json.loads((ROOT / "stores.json").read_text())


def fake_response(url):
    r = requests.Response()
    r.url = url
    r.status_code = 200
    r.headers["content-type"] = "application/json"
    if url.endswith("/robots.txt"):
        r.headers["content-type"] = "text/plain"
        r._content = b"User-agent: *\nAllow: /\n"
    else:
        r._content = json.dumps({"title": "x", "available": True, "tags": [], "currency": "USD", "items": {}, "products": [],
                                 "variants": [{"id": 1, "title": "Default Title", "available": True, "price": 100}]}).encode()
    return r


class Recorder:
    def __init__(self):
        self.urls = []

    def send(self, session, request, **kwargs):
        self.urls.append(request.url)
        return fake_response(request.url)

    @property
    def hosts(self):
        return {(urlparse(u).hostname or "").lower() for u in self.urls}


def run_with_recorder(fn):
    rec = Recorder()
    with patch.object(requests.adapters.HTTPAdapter, "send", lambda self, request, **kw: rec.send(self, request, **kw)), \
            patch.object(checker, "DELAY", 0):
        fn()
    return rec


class FlagTests(unittest.TestCase):
    def test_exactly_the_six_shops_are_flagged(self):
        self.assertEqual({s["id"] for s in STORES["stores"] if s.get("link_only")}, LINK_ONLY_IDS)
        self.assertEqual(checker.link_only_ids(), LINK_ONLY_IDS)

    def test_blocked_hosts_cover_every_listing_url(self):
        hosts = checker.link_only_hosts()
        self.assertTrue(BLOCKED <= hosts, BLOCKED - hosts)
        for s in STORES["stores"]:
            if s.get("link_only"):
                for p in s["products"]:
                    self.assertIn(urlparse(p["url"]).hostname.lower(), hosts)

    def test_turning_a_shop_back_on_is_one_flag(self):
        cfg = json.loads(json.dumps(STORES))
        for s in cfg["stores"]:
            if s["id"] == "milligram":
                del s["link_only"]
        self.assertNotIn("milligram.com", checker.link_only_hosts(cfg))
        self.assertIn("blesket.com", checker.link_only_hosts(cfg))


class NoRequestTests(unittest.TestCase):
    def test_guard_refuses_each_host_before_the_network(self):
        sent = []
        with patch.object(requests.adapters.HTTPAdapter, "send", lambda self, request, **kw: sent.append(request.url)):
            for host in sorted(BLOCKED):
                with self.assertRaises(checker.LinkOnlyHostError):
                    checker.GuardedSession().get(f"https://{host}/products/x.js")
                with self.assertRaises(checker.LinkOnlyHostError):
                    checker.Host(f"https://{host}")
        self.assertEqual(sent, [])

    def test_redirect_into_a_link_only_host_is_refused(self):
        def send(self, request, **kw):
            r = requests.Response()
            r.url = request.url
            r.request = request
            if "blesket" in request.url:
                raise AssertionError("reached the network")
            r.status_code = 301
            r.headers["location"] = "https://blesket.com/products/x"
            r._content = b""
            return r
        with patch.object(requests.adapters.HTTPAdapter, "send", send):
            with self.assertRaises(checker.LinkOnlyHostError):
                checker.GuardedSession().get("https://elsewhere.example/a")

    def _tmp_root(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "data" / "inks").mkdir(parents=True)
        shutil.copy(ROOT / "stores.json", tmp / "stores.json")
        shutil.copy(ROOT / "inks.json", tmp / "inks.json")
        return tmp

    def test_full_checker_run_makes_zero_requests_to_link_only_hosts(self):
        tmp = self._tmp_root()
        # Prior data with live rows for the four shops, as on the first run after the switch.
        prior = [dict(store_id=sid, store=sid, label="old", type="Book", url=f"https://{h}/products/old", status="in_stock",
                      first_seen="2026-11-01T00:00:00+00:00", status_since="2026-11-01T00:00:00+00:00", checked_at="2026-11-23T00:00:00+00:00")
                 for sid, h in (("blesket", "blesket.com"), ("milligram", "milligram.com"), ("kinousa", "usa.kinokuniya.com"), ("kinosg", "kinokuniya.com.sg"),
                                ("laywines", "laywines.com"), ("notebooktherapy", "notebooktherapy.com"))]
        (tmp / "data" / "stock.json").write_text(json.dumps({"products": prior}))
        (tmp / "data" / "changes.json").write_text("[]")
        with patch.object(checker, "ROOT", tmp):
            rec = run_with_recorder(checker.main)
        self.assertGreater(len(rec.urls), 100, "the real checker path ran")
        self.assertFalse(rec.hosts & BLOCKED, rec.hosts & BLOCKED)
        stock = json.loads((tmp / "data" / "stock.json").read_text())
        self.assertFalse({p["store_id"] for p in stock["products"]} & LINK_ONLY_IDS)
        self.assertEqual({s["id"] for s in stock["link_only"]}, LINK_ONLY_IDS)
        changes = json.loads((tmp / "data" / "changes.json").read_text())
        self.assertFalse([c for c in changes if c["store_id"] in LINK_ONLY_IDS], "no sold-out or restock event for the switch")

    def test_ink_check_and_discovery_make_zero_requests_to_link_only_hosts(self):
        tmp = self._tmp_root()
        (tmp / "data" / "inks" / "pending.json").write_text("[]")
        cfg = json.loads((ROOT / "inks.json").read_text())
        # Robert Oster lists Blesket as a dealer: that is the ink path that would have reached blesket.com.
        self.assertIn("blesket", cfg["brands"]["robert-oster"]["shops"])
        with patch.object(ink_tracker, "ROOT", tmp), patch.object(ink_tracker, "CONFIG", tmp / "inks.json"), \
                patch.object(ink_tracker, "DATA", tmp / "data" / "inks"):
            rec = run_with_recorder(lambda: (ink_tracker.discover([]), ink_tracker.check([])))
        self.assertGreater(len(rec.urls), 5, "the real ink path ran")
        self.assertFalse(rec.hosts & BLOCKED, rec.hosts & BLOCKED)

    def test_nothing_else_in_the_repo_names_these_hosts_in_a_request_path(self):
        pat = re.compile(r"blesket\.com|milligram\.com|kinokuniya\.com", re.I)
        files = [*ROOT.glob("scripts/*.py"), *ROOT.glob("scripts/*.js"), *ROOT.glob("scripts/*.sh"),
                 ROOT / "build_stores.py", ROOT / "infra" / "checker-trigger" / "worker.js", *ROOT.glob(".github/workflows/*.yml")]
        hits = {f.name: [l.strip() for l in f.read_text().splitlines() if pat.search(l)] for f in files}
        hits = {k: v for k, v in hits.items() if v}
        # Only the www->apex mapping (a string table, never fetched) and the copy sentences in build_site.py.
        self.assertEqual(set(hits), {"checker.py", "build_stores.py"}, hits)
        self.assertEqual([l for l in hits["checker.py"] if "APEX" not in l and "www.milligram.com" not in l], [])
        self.assertTrue(all("GuardedSession" in (ROOT / "build_stores.py").read_text() for _ in [0]))
        for f in [*ROOT.glob(".github/workflows/*.yml"), ROOT / "infra" / "checker-trigger" / "worker.js"]:
            self.assertNotRegex(f.read_text(), pat, f.name)


class AlertTests(unittest.TestCase):
    def test_stray_events_for_link_only_shops_never_alert(self):
        ev = lambda sid: dict(at="2026-11-23T00:00:00+00:00", store_id=sid, label="x", to="in_stock", **{"from": "sold_out"})
        fresh = new_in_stock.fresh_in_stock([], [ev("blesket"), ev("kinousa"), ev("milligram"), ev("kinosg"), ev("goulet")])
        self.assertEqual([c["store_id"] for c in fresh], ["goulet"])

    def test_old_events_are_not_shown_on_any_page_or_feed(self):
        self.assertFalse([c for c in site.changes if c.get("store_id") in LINK_ONLY_IDS])
        self.assertFalse([p for p in site.stock["products"] if p["store_id"] in LINK_ONLY_IDS])


class PageTests(unittest.TestCase):
    ROW = re.compile(r'<tr[^>]*data-store="(blesket|milligram|kinousa|kinosg)"[^>]*>(.*?)</tr>', re.S)

    @classmethod
    def setUpClass(cls):
        cls.docs = [("tracker", site.build_hobo_tracker())]
        for g in site.GROUPS:
            cls.docs.append((g["slug"], site.build_group(g, None)[1]))
        for d in site.DESIGNS:
            cls.docs.append((d["slug"], site.build_design(d, None)[1]))
        cls.docs.append(("where", site.build_where_to_buy()[1]))

    def test_link_rows_have_no_status_time_or_stock_words(self):
        n = 0
        for name, doc in self.docs:
            for m in self.ROW.finditer(doc):
                n += 1
                row = m.group(0)
                self.assertIn('data-status="link_only"', row, name)
                self.assertIn("Link only", row, name)
                for bad in ("<time", "In stock", "Sold out", "Preorder", "Not yet on sale", "Couldn't check", "since "):
                    self.assertNotIn(bad, row, (name, bad))
        self.assertGreater(n, 50)

    def test_tracker_data_rows_for_link_only_shops_carry_no_status_or_time(self):
        doc = dict(self.docs)["tracker"]
        data = json.loads(re.search(r'<script id="stock-data" type="application/json">(.*?)</script>', doc, re.S).group(1).replace("<\\/", "</"))
        rows = data if isinstance(data, list) else [dict(zip(data["k"], [data["d"][k][v] if v is not None and k in data["d"] else v for k, v in zip(data["k"], r)])) for r in data["r"]]
        link = [r for r in rows if r["sid"] in LINK_ONLY_IDS]
        self.assertEqual(len(link), 135 - sum(1 for r in site.LINK_ROWS if site.section_of(r) != "hobonichi"))
        for r in link:
            self.assertEqual(r["st"], "link_only")
            for k in ("at", "since", "va", "tv", "on"):
                self.assertIsNone(r.get(k), (r["sid"], k))
        checked = [r for r in rows if r["st"] != "link_only"]
        self.assertFalse([r for r in checked if r["sid"] in LINK_ONLY_IDS])

    def test_in_stock_tally_ignores_link_only_rows(self):
        rows = [dict(st="link_only", sid="blesket", s="Blesket Canada"), dict(st="in_stock", sid="goulet", s="Goulet")]
        self.assertEqual(site.shop_tally([dict(r, g="x", gn="x", u="u") for r in rows]),
                         "1 of 1 listings in stock · 1 of 1 shop in stock · 1 shop link only")
        self.assertEqual(site.shop_tally([rows[0]]), "Link only, we don't check stock")

    def test_hero_and_totals_count_only_checked_listings(self):
        home = site.build_index()
        n = len(site.stock["products"]) + len([r for r in site.INK_ROWS])
        self.assertIn(f"{n} of {n}", home)


if __name__ == "__main__":
    unittest.main()
