"""One URL style (trailing slash on every page) and the dot grid tracker move (Nov 21, 2026)."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

REDIRECTS_FILE = (ROOT / "cloudflare/_redirects").read_text()
RULES = {}
for line in REDIRECTS_FILE.splitlines():
    if line.strip() and not line.startswith("#"):
        src, dst, code = line.split()
        RULES[src] = (dst, code)

NEW = "dot-grid-journal-restock-tracker"
OLD = "archer-and-olive-dot-grid-journal"
SITE = ROOT / "site"


def pages():
    """(path, html) for every built page the site publishes, from the checked-in site/ tree."""
    return [(str(p.relative_to(SITE)), p.read_text()) for p in SITE.rglob("*.html")]


class SlashStyleTests(unittest.TestCase):
    def test_no_flat_pages_left_except_404(self):
        flat = [p for p in SITE.glob("*.html") if p.name not in ("404.html", "index.html")]
        self.assertEqual(flat, [])
        for name in ("about", "privacy", "hobonichi-2027"):
            self.assertTrue((SITE / name / "index.html").exists(), name)

    def test_canonical_og_url_and_sitemap_all_end_in_a_slash(self):
        for path, doc in pages():
            if path == "404.html":
                continue
            for pat in (r'<link rel="canonical" href="([^"]+)"', r'property="og:url" content="([^"]+)"'):
                for url in re.findall(pat, doc):
                    self.assertTrue(url.endswith("/"), (path, url))
        for loc in re.findall(r"<loc>([^<]+)</loc>", site.build_sitemap()):
            self.assertTrue(loc.endswith("/"), loc)

    def test_internal_links_never_use_the_slashless_or_html_form(self):
        bad = re.compile(r'href="/(about|privacy|hobonichi-2027)(?:\.html)?(?=["#?])')
        for path, doc in pages():
            if path.startswith(("archer-and-olive-bullet-journal/", OLD + "/")) and path != OLD + "/index.html":
                continue  # redirect stubs
            self.assertIsNone(bad.search(doc), path)
            self.assertNotRegex(doc, r'href="/[^"#?]*\.html', path) if path != "404.html" else None

    def test_every_internal_link_resolves_to_a_built_page(self):
        built = {"/" + str(p.parent.relative_to(SITE)) + "/" for p in SITE.rglob("index.html")}
        built.add("/")
        built -= {"/./"}
        for path, doc in pages():
            for href in re.findall(r'href="(/[^"#?]*)', doc):
                if "." in href.rsplit("/", 1)[-1] or href.startswith("/assets/"):
                    continue
                self.assertTrue(href in built or href in ("/",), (path, href))

    def test_legacy_flat_urls_redirect_in_one_hop_to_the_slash_url(self):
        for name in ("about", "privacy", "hobonichi-2027"):
            self.assertEqual(RULES[f"/{name}.html"], (f"/{name}/", "301"))

    def test_no_redirect_loops_or_chains(self):
        for src, (dst, _code) in RULES.items():
            target = dst.split("#")[0]
            self.assertNotEqual(src, target, src)
            self.assertNotIn(target, RULES, f"chain: {src} -> {dst} -> {RULES.get(target)}")
            # the target must be a built page (or the homepage)
            self.assertTrue(target == "/" or (SITE / target.strip("/") / "index.html").exists(), (src, dst))
        # a slash-less source never points at its own slash form (Pages adds that 308 itself)
        for src, (dst, _c) in RULES.items():
            self.assertNotEqual(src + "/", dst)

    def test_rules_file_matches_REDIRECTS(self):
        for old, new in site.REDIRECTS.items():
            if old == "faq":
                continue
            self.assertEqual(RULES["/" + old + "/"][0], "/" + new, old)
            self.assertEqual(RULES["/" + old][0], "/" + new, old)
            self.assertEqual(RULES["/" + old + "/"][1], "301")


class DotGridMoveTests(unittest.TestCase):
    def test_tracker_lives_at_the_new_url_and_sitemap_lists_both_pages(self):
        self.assertEqual(site.DOTGRID_SLUG, NEW)
        sm = site.build_sitemap()
        self.assertIn(f"https://stationerydropwatch.com/{NEW}/</loc>", sm)
        self.assertIn(f"https://stationerydropwatch.com/{OLD}/</loc>", sm)
        self.assertNotIn(f"{OLD}/", "".join(re.findall(r"<loc>[^<]+(?:/[^</]+){1}/</loc>", sm)).replace(f"{OLD}/</loc>", ""))

    def test_old_url_is_an_archer_and_olive_page_with_its_own_canonical_and_a_link_to_the_tracker(self):
        g = next(g for g in site.GROUPS if g["slug"] == site.AO_SLUG)
        fname, doc = site.build_group(g)
        self.assertEqual(fname, OLD + "/")
        self.assertIn(f'<link rel="canonical" href="https://stationerydropwatch.com/{OLD}/">', doc)
        self.assertIn(f'href="/{NEW}/"', doc)
        self.assertIn("<h1>Archer and Olive dot grid journal restock tracker</h1>", doc)
        for other in ("Leuchtturm1917 · ", "Scribbles That Matter · ", "Notebook Therapy · "):
            self.assertNotIn(other, doc)
        self.assertNotRegex(doc.lower(), r"bullet.journal")

    def test_old_design_pages_301_to_their_new_home_and_new_pages_exist(self):
        moved = [d for d in site.DESIGNS if d["parent"] == NEW]
        self.assertGreater(len(moved), 20)
        for d in moved:
            self.assertEqual(RULES[f"/{OLD}/{d['slug']}/"], (f"/{NEW}/{d['slug']}/", "301"))
            self.assertEqual(RULES[f"/{OLD}/{d['slug']}"], (f"/{NEW}/{d['slug']}/", "301"))
            self.assertTrue((SITE / NEW / d["slug"] / "index.html").exists(), d["slug"])
        # the old URL itself keeps a page, so no rule may redirect it
        self.assertNotIn(f"/{OLD}/", RULES)
        self.assertNotIn(f"/{OLD}", RULES)
        self.assertEqual(RULES["/archer-and-olive-bullet-journal/"], (f"/{OLD}/", "301"))

    def test_no_internal_page_links_to_old_item_urls_or_names_the_old_tracker_as_the_tracker(self):
        for path, doc in pages():
            if path.startswith(OLD + "/") and path != OLD + "/index.html":
                continue  # redirect stubs
            self.assertIsNone(re.search(r'href="/' + OLD + r'/[a-z]', doc), path)

    def test_alert_and_checker_code_has_no_tracker_url(self):
        for f in ("checker.py", "render_alert.py", "alert_captions.py", "new_in_stock.py", "status_changed.py"):
            self.assertNotIn(OLD, (ROOT / "scripts" / f).read_text(), f)


if __name__ == "__main__":
    unittest.main()
