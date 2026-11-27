"""Thin design pages, Nov 27, 2026 (seo/thin-pages-plan-2026-11-27.md).

Eight single-shop design pages with no Search Console impressions fold into their
parent with a 301. The five merge candidates that did get impressions stay as pages.
Every other design page with checked listings gets sections built only from our own
logged data: stock history, where we track it, formats, related designs.
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

AO = "archer-and-olive-dot-grid-journal"
OLD = "dot-grid-journal-restock-tracker"
COVERS = "hobonichi-techo-2027-covers"
MERGED = {
    **{f"{OLD}/archer-and-olive-{s}": AO for s in ("cozy-critters", "ice-castle", "songbird-beige", "stag",
                                                    "storybook-olive", "winter-train")},
    f"{COVERS}/puppet-sunsun-s-a5": COVERS,
    f"{COVERS}/puppet-sunsun-wa-a6": COVERS,
}
# Merge candidates with Search Console impressions (Oct 25 to Nov 24, 2026 export): kept as pages.
HELD = ["archer-and-olive-apothecary-shelf", "archer-and-olive-storybook-navy", "scribbles-that-matter-iconic",
        "scribbles-that-matter-pro", "scribbles-that-matter-starry-night"]
TSUKI = ["notebook-therapy-tsuki-160gsm", "notebook-therapy-tsuki-dark-academia",
         "notebook-therapy-tsuki-ravens-secret", "notebook-therapy-tsuki-violet-nocturne"]


def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def section(doc, sid):
    m = re.search(rf'<section class="card" id="{sid}">([\s\S]*?)</section>', doc)
    return m.group(1) if m else None


class MergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sitemap = (ROOT / "site/sitemap.xml").read_text()
        cls.rules = [l.split() for l in (ROOT / "cloudflare/_redirects").read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
        cls.pages = {p: p.read_text() for p in (ROOT / "site").rglob("*.html")}

    def test_merged_pages_redirect_to_their_parent(self):
        self.assertEqual(site.MERGED_DESIGN_TARGETS, MERGED)
        rules = {r[0]: (r[1], r[2]) for r in self.rules if len(r) >= 3}
        for path, target in MERGED.items():
            slug = path.split("/", 1)[1]
            olds = [path] + ([f"{AO}/{slug}"] if target == AO else [])
            for old in olds:
                self.assertEqual(site.REDIRECTS[old], target + "/", old)
                self.assertEqual(rules[f"/{old}/"], (f"/{target}/", "301"), old)
                self.assertEqual(rules[f"/{old}"], (f"/{target}/", "301"), old)
                self.assertNotIn(f"/{old}/</loc>", self.sitemap)
                stub = (ROOT / "site" / old / "index.html").read_text()
                self.assertIn(f'<link rel="canonical" href="https://stationerydropwatch.com/{target}/">', stub)
            self.assertNotIn(slug, {d["slug"] for d in site.DESIGNS})

    def test_no_page_links_to_a_merged_page(self):
        for p, doc in self.pages.items():
            if "Moved:" in doc[:2000]:
                continue
            for path in MERGED:
                slug = path.split("/", 1)[1]
                for old in (path, f"{AO}/{slug}"):
                    self.assertNotIn(f'href="/{old}/"', doc, (p, old))

    def test_held_and_tsuki_pages_are_unchanged_in_kind(self):
        for slug in HELD:
            self.assertIn(f"/{OLD}/{slug}/</loc>", self.sitemap, slug)
            doc = (ROOT / "site" / OLD / slug / "index.html").read_text()
            self.assertNotIn("noindex", doc[:3000], slug)
            self.assertIn('id="history"', doc, slug)
        for slug in TSUKI:
            doc = (ROOT / "site" / OLD / slug / "index.html").read_text()
            self.assertIn('content="noindex', doc, slug)
            self.assertNotIn(f"/{OLD}/{slug}/</loc>", self.sitemap)
            for sid in ("history", "where", "formats", "related"):
                self.assertNotIn(f'id="{sid}"', doc, slug)

    def test_sitemap_count(self):
        self.assertEqual(self.sitemap.count("<loc>"), 92)

    def test_tracker_rows_point_merged_designs_at_the_parent(self):
        hob = (ROOT / "site/hobonichi-restock-tracker/index.html").read_text()
        src = re.search(r'data-src="/([^"]+)"', hob).group(1)
        packed = json.loads((ROOT / "site" / src).read_text())
        rows = packed if isinstance(packed, list) else [
            {k: (packed["d"][k][v] if k in packed["d"] else v) for k, v in zip(packed["k"], vals) if v is not None}
            for vals in packed["r"]]
        puppet = [r for r in rows if "puppet" in (r.get("c") or "")]
        self.assertTrue(puppet)
        for r in puppet:
            self.assertEqual((r["dp"], r["dpl"]), (f"/{COVERS}/", "Covers page"), r["u"])
        self.assertFalse([r for r in rows if r.get("dpl") and r.get("dp") != f"/{COVERS}/"])
        dot = (ROOT / "site" / OLD / "index.html").read_text()
        self.assertIn(f'<a href="/{AO}/">Archer and Olive page</a>', dot)

    def test_parent_pages_carry_the_merged_about_notes(self):
        for d in site.MERGED_DESIGNS:
            target = MERGED[f'{d["parent"]}/{d["slug"]}']
            doc = (ROOT / "site" / target / "index.html").read_text()
            self.assertIn(site.E(site.design_about(d)), doc, d["slug"])


class EnrichmentTests(unittest.TestCase):
    def test_history_numbers_match_the_change_log(self):
        log = json.loads((ROOT / "data/changes.json").read_text())
        seen = 0
        for d in site.DESIGNS:
            ls = site.design_listings(d)
            fname, doc = site.build_design(d)
            hist = section(doc, "history")
            if not ls:
                self.assertIsNone(hist, d["slug"])
                continue
            seen += 1
            t = text(hist)
            urls = {l["url"] for l in ls}
            evs = [c for c in log if c["url"] in urls]
            restocks = [c for c in evs if c["from"] in ("sold_out", "coming_soon") and c["to"] in ("in_stock", "preorder")]
            if evs:
                n = re.search(r"recorded (\d+) status changes?", t)
                self.assertEqual(int(n.group(1)), len(evs), d["slug"])
                r = re.search(r"(\d+|no) restocks?", t)
                self.assertEqual(int(r.group(1)) if r and r.group(1).isdigit() else 0, len(restocks), d["slug"])
                shown = len(re.findall(r" → ", t))
                self.assertEqual(shown, min(12, len(evs)), d["slug"])
            else:
                self.assertIn("We haven't recorded a status change", t, d["slug"])
            first = min(l["first_seen"] for l in ls if l.get("first_seen"))
            self.assertIn(site.fmt_et(first), t, d["slug"])
        self.assertGreater(seen, 40)

    def test_sections_make_no_unbacked_claims(self):
        for d in site.DESIGNS:
            _, doc = site.build_design(d)
            for sid in ("history", "where", "formats", "related"):
                body = section(doc, sid)
                if body is None:
                    continue
                t = text(body).lower()
                for word in ("usually", "always", "typically", "often", "designphil"):
                    self.assertNotIn(word, t, (d["slug"], sid, word))

    def test_where_table_lists_every_checked_listing_shop(self):
        for d in site.DESIGNS:
            ls = site.design_listings(d)
            if not ls:
                continue
            _, doc = site.build_design(d)
            t = text(section(doc, "where"))
            for shop in {l["store"] for l in ls}:
                self.assertIn(shop, t, d["slug"])


if __name__ == "__main__":
    unittest.main()
