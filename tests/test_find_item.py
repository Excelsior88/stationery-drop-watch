"""Homepage Find my item search.

The index is built from the same stock and ink rows as the pages. Link-only shops stay
out of every in-stock total. The homepage field is a real search box, and app.js does
not request the index until that field is focused or typed in.
"""
import gzip
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

LINK_ONLY = "Link only, we don't check stock"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def raw_index(idx):
    return json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode()


def hits(idx, query):
    labels = {key: val["l"] for key, val in idx["trackers"].items()}
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    found = []
    for item in idx["items"]:
        shops = " ".join(idx["shops"][i]["n"] for i in item["sh"])
        hay = " ".join((item["n"], item.get("q", ""), shops, labels[item["t"]])).lower()
        if all(token in hay for token in tokens):
            found.append(item)
    return found


class NavProbe(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.nested = 0
        self.find_inside_nav = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "find-bar" in attrs.get("class", "").split():
            self.find_inside_nav = "nav" in self.stack
        if tag == "nav" and "nav" in self.stack:
            self.nested += 1
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack:
                if self.stack.pop() == tag:
                    break


class SearchIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idx = site.search_index()
        cls.by_id = {item["id"]: item for item in cls.idx["items"]}

    def test_covers_every_active_canonical_and_live_ink(self):
        keys = {item["t"] for item in self.idx["items"]}
        self.assertEqual(keys, {"h", "d", "i", "p", "g"})
        self.assertEqual(set(self.idx["trackers"]), {"h", "d", "i", "p", "g"})
        self.assertEqual(
            {key: self.idx["trackers"][key]["l"] for key in ("h", "d", "i")},
            {"h": "Hobonichi", "d": "Dot grid", "i": "Limited inks"})
        active = {p["canonical"] for p in site.stock["products"] + site.LINK_ROWS if p.get("canonical")}
        got = {item["id"] for item in self.idx["items"] if item["t"] not in ("i", "p", "g")}
        self.assertEqual(got, active)
        self.assertGreaterEqual(sum(item["t"] == "h" for item in self.idx["items"]), 1)
        self.assertGreaterEqual(sum(item["t"] == "d" for item in self.idx["items"]), 1)
        live = {ink["id"] for ink in site.INK_CFG["inks"]
                if ink["id"] not in site.INK_RETIRED and any(r["ink_id"] == ink["id"] for r in site.INK_ROWS)}
        self.assertEqual({item["id"] for item in self.idx["items"] if item["t"] == "i"}, live)
        self.assertTrue(live)

    def test_design_page_summaries_match_count_line_and_skip_link_only(self):
        for design in site.DESIGNS:
            url = "/" + site.design_fname(design)
            rows = site.design_listings(design)
            links = site.link_listings(design["match"])
            items = [item for item in self.idx["items"] if item["u"] == url]
            if not rows and not links:
                self.assertEqual(items, [], design["slug"])
                continue
            self.assertTrue(items, design["slug"])
            expected = site.count_line(rows).capitalize() if rows else LINK_ONLY
            for item in items:
                self.assertEqual(item["s"], expected, item["id"])
                if rows and links:
                    counted = int(re.match(r"(\d+) of (\d+)", item["s"]).group(2))
                    self.assertEqual(counted, len(rows), item["id"])
                    self.assertNotEqual(counted, len(rows) + len(links), item["id"])

    def test_group_and_ink_summaries_match_their_pages(self):
        for item in self.idx["items"]:
            if item["t"] == "i":
                rows = [r for r in site.INK_ROWS if r["ink_id"] == item["id"]]
                self.assertEqual(item["s"], site.count_line(rows).capitalize(), item["id"])
                self.assertTrue(item["u"].endswith("#ink-" + item["id"]))
            elif item["t"] in ("h", "d") and "#" in item["u"]:
                rows = [p for p in site.stock["products"] if p.get("canonical") == item["id"]]
                expected = site.count_line(rows).capitalize() if rows else LINK_ONLY
                self.assertEqual(item["s"], expected, item["id"])

    def test_shop_summaries_match_checked_rows_only(self):
        saw_link_only = False
        for shop in self.idx["shops"]:
            for page in shop["p"]:
                if page["t"] == "h":
                    rows = [p for p in site.stock["products"] if p["store_id"] == shop["i"] and site.section_of(p) != "dotgrid"]
                elif page["t"] == "d":
                    rows = [p for p in site.stock["products"] if p["store_id"] == shop["i"] and site.section_of(p) == "dotgrid"]
                else:
                    rows = [r for r in site.INK_ROWS if r["store_id"] == shop["i"]]
                self.assertEqual(page["c"], len(rows), (shop["i"], page["t"]))
                if rows:
                    self.assertEqual(page["s"], site.count_line(rows).capitalize(), (shop["i"], page["t"]))
                else:
                    saw_link_only = True
                    self.assertEqual(page["s"], LINK_ONLY, (shop["i"], page["t"]))
                    self.assertNotRegex(page["s"], r"\d+ of \d+")
        self.assertTrue(saw_link_only)
        nt = self.by_id["nt-tsuki-160"]
        self.assertEqual(nt["s"], LINK_ONLY)
        self.assertEqual(nt["t"], "d")
        self.assertNotRegex(nt["s"], r"in stock")

    def test_examples_and_no_banned_wording(self):
        self.assertTrue(any("kitagishi" in item["n"].lower() for item in hits(self.idx, "Yumi Kitagishi")))
        self.assertTrue(any("slash" in item["n"].lower() and "navy" in item["n"].lower() for item in hits(self.idx, "Slash Navy")))
        mega = hits(self.idx, "Midnight Blue Mega")
        self.assertTrue(any("mega" in item["n"].lower() and "midnight" in item["n"].lower() for item in mega))
        self.assertTrue(all("weeks mega" in item["n"].lower() for item in mega if "midnight" in item["n"].lower()))
        self.assertTrue(any(item["t"] == "i" and "inkvent" in item["n"].lower() for item in hits(self.idx, "Inkvent")))
        self.assertTrue(any("starlight" in item["n"].lower() for item in hits(self.idx, "Starlight")))
        yoseka = next(shop for shop in self.idx["shops"] if shop["n"] == "Yoseka Stationery")
        self.assertIn("h", {page["t"] for page in yoseka["p"]})
        blob_items = json.dumps([{k: v for k, v in item.items() if k != "id"} for item in self.idx["items"]]).lower()
        blob_shops = json.dumps(self.idx["shops"]).lower()
        for blob in (blob_items, blob_shops):
            self.assertNotIn("midori", blob)
            self.assertNotIn("designphil", blob)
            self.assertNotRegex(blob, r"travell?er'?s\s+company")
            self.assertNotIn("bullet", blob)
        self.assertNotIn("bullet", self.by_id["lt-bullet-journal-ed2"]["n"].lower())
        self.assertIn("dot grid", self.by_id["lt-bullet-journal-ed2"]["n"].lower())

    def test_compact_and_written_by_the_build(self):
        raw = raw_index(self.idx)
        zipped = len(gzip.compress(raw, mtime=0))
        self.assertLess(len(raw), 60000)
        self.assertLess(zipped, 12000, zipped)
        try:
            import brotli
        except ImportError:
            brotli = None
        if brotli is not None:
            self.assertLess(len(brotli.compress(raw, quality=11)), 20480)
        path = ROOT / "site" / "data" / "search-index.json"
        self.assertTrue(path.is_file(), "scripts/build_site.py writes site/data/search-index.json")
        self.assertEqual(json.loads(path.read_text()), self.idx)
        self.assertEqual(path.read_bytes().rstrip(b"\n"), raw)


class HomepageSearchMarkupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = site.build_index()
        start = cls.doc.index('class="find-bar"')
        cls.bar = cls.doc[start:cls.doc.index('id="trackers"')]

    def test_bar_sits_below_the_signup_card_and_outside_any_nav(self):
        self.assertLess(self.doc.index("signup-strip"), self.doc.index('class="find-bar"'))
        self.assertLess(self.doc.index('class="find-bar"'), self.doc.index('id="trackers"'))
        self.assertNotIn("find-bar", self.doc[self.doc.index("signup-strip"):self.doc.index("</form>")])
        probe = NavProbe()
        probe.feed(self.doc)
        self.assertFalse(probe.find_inside_nav)
        self.assertEqual(probe.nested, 0)
        self.assertNotIn("<nav", self.bar)
        self.assertEqual(self.doc.count('id="find-q"'), 1)

    def test_search_box_is_accessible_and_submits_without_javascript(self):
        self.assertIn('role="search"', self.bar)
        self.assertIn('aria-label="Find my item"', self.bar)
        self.assertIn(">Find my item</label>", self.bar)
        self.assertIn('id="find-q" type="search" name="q"', self.bar)
        self.assertIn('role="combobox"', self.bar)
        self.assertIn('aria-expanded="false"', self.bar)
        self.assertIn('aria-controls="find-list"', self.bar)
        self.assertIn('aria-autocomplete="list"', self.bar)
        self.assertIn('role="listbox"', self.bar)
        self.assertIn('aria-live="polite"', self.bar)
        self.assertIn('action="/hobonichi-restock-tracker/" method="get"', self.bar)
        self.assertIn("Planner, dot grid, ink, Lamy pen, guide or shop", self.bar)
        self.assertNotIn("bullet", self.bar.lower())
        self.assertNotIn("midori", self.bar.lower())
        self.assertNotIn("traveler", self.bar.lower())
        self.assertNotRegex(self.bar, r"\son[a-z]+=", re.I)
        self.assertNotIn("<script", self.bar.lower())
        self.assertNotIn("<style", self.bar.lower())
        self.assertNotIn("style=", self.bar.lower())


class LazyClientAndHeadersTests(unittest.TestCase):
    def test_index_fetch_is_only_on_focus_or_input(self):
        src = (ROOT / "site" / "assets" / "app.js").read_text()
        self.assertEqual(src.count('"/data/search-index.json"'), 1)
        self.assertEqual(src.count("loadFindIndex()"), 2)
        focus = src.index('findInput.addEventListener("focus"')
        typed = src.index('findInput.addEventListener("input"')
        self.assertEqual(src[focus:typed + 80].count("loadFindIndex()"), 2)
        self.assertNotIn("search-index.json", src[:src.index("find-item:")])
        tail = src[src.index("find-item:"):]
        self.assertNotIn("innerHTML", tail)
        self.assertNotIn("insertAdjacentHTML", tail)
        self.assertNotIn("document.write", tail)
        self.assertIn('location.replace("/hobonichi-restock-tracker/" + location.search', src)

    def test_search_index_is_not_cached_for_30_days(self):
        headers = (ROOT / "cloudflare" / "_headers").read_text()
        for line in headers.splitlines():
            if line.lstrip().startswith("#"):
                continue
            self.assertNotIn("search-index", line)
        self.assertIn("data/search-index.json stays on Pages' default", headers)
        self.assertIn("Cache-Control: public, max-age=2592000", headers)
        self.assertEqual(headers.count("max-age=2592000"), 1)


if __name__ == "__main__":
    unittest.main()
