"""Nov 27, 2026 (owner t2081u): retired Traveler's Company / MIDORI pages return 410 Gone, the Hobonichi
tracker's listing rows move out of the HTML into a cached file, and the Transparency table keeps its
information as plain text with no links to the old pages."""
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

MIDDLEWARE = ROOT / "site/functions/_middleware.js"
OLD_URL = re.compile(r"(travelers-company-limited-edition/[a-z0-9-]+/|midori-md-limited-edition/md-|travelers-notebook-regular-(size|vs))")


class GonePagesTests(unittest.TestCase):
    def test_middleware_list_matches_build(self):
        src = MIDDLEWARE.read_text()
        listed = re.findall(r'^  "([a-z0-9/-]+)",$', src, re.M)
        self.assertEqual(sorted(listed), sorted(site.GONE_PATHS))
        self.assertEqual(len(site.GONE_PATHS), 11)

    def test_gone_paths_have_no_redirect_rule_stub_sitemap_entry_or_link(self):
        cf = (ROOT / "cloudflare/_redirects").read_text()
        sm = site.build_sitemap()
        for g in site.GONE_PATHS:
            self.assertNotIn(g, site.REDIRECTS)
            self.assertNotIn("/" + g, cf)
            self.assertNotIn("/" + g, sm)
        # the notice itself stays, and the MIDORI notice URL still 301s to it
        self.assertIn(f"/{site.TN_SLUG}/</loc>", sm)
        self.assertEqual(site.REDIRECTS[site.MIDORI_SLUG], site.TN_SLUG + "/")
        docs = [site.build_index(), site.build_hobo_tracker(), site.build_transparency(), site.build_takedown_notice(site.TN_SLUG)[1],
                site.build_404(), site.build_about()]
        docs += [site.build_group(g, {})[1] for g in site.GROUPS]
        for doc in docs:
            self.assertIsNone(OLD_URL.search(doc))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_middleware_answers_410_404_and_passes_everything_else(self):
        script = """
import { onRequest } from %s;
const ctx = (path) => ({
  request: new Request("https://stationerydropwatch.com" + path),
  env: { ASSETS: { fetch: async () => new Response("<p>not found page</p>", { status: 200, headers: { "content-type": "text/html" } }) } },
  next: async () => new Response("asset", { status: 200 }),
});
const out = {};
for (const p of %s) { const r = await onRequest(ctx(p)); out[p] = [r.status, r.headers.get("x-robots-tag")]; }
console.log(JSON.stringify(out));
""" % (json.dumps(MIDDLEWARE.as_uri()), json.dumps([
            "/travelers-company-limited-edition/regular-black/", "/travelers-company-limited-edition/regular-black",
            "/midori-md-limited-edition/md-diary-2027-a5/", "/travelers-notebook-regular-vs-passport-vs-card-size/",
            "/travelers-company-limited-edition/", "/midori-md-limited-edition/", "/404", "/hobonichi-2027/"]))
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.mjs"
            f.write_text(script)
            res = json.loads(subprocess.run(["node", str(f)], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(res["/travelers-company-limited-edition/regular-black/"], [410, "noindex"])
        self.assertEqual(res["/travelers-company-limited-edition/regular-black"], [410, "noindex"])
        self.assertEqual(res["/midori-md-limited-edition/md-diary-2027-a5/"], [410, "noindex"])
        self.assertEqual(res["/travelers-notebook-regular-vs-passport-vs-card-size/"], [410, "noindex"])
        self.assertEqual(res["/404"], [404, "noindex"])
        for kept in ("/travelers-company-limited-edition/", "/midori-md-limited-edition/", "/hobonichi-2027/"):
            self.assertEqual(res[kept], [200, None])  # passed on to the assets / _redirects


class TrackerDataFileTests(unittest.TestCase):
    def test_rows_are_a_separate_hashed_file_and_statuses_stay_in_the_html(self):
        site.TRACKER_DATA_FILES.clear()
        doc = site.build_hobo_tracker()
        m = re.search(r'<script id="stock-data" type="application/json" data-src="/(data/tracker/hobonichi-[0-9a-f]{12}\.json)"></script>', doc)
        self.assertIsNotNone(m)
        rows = json.loads(site.TRACKER_DATA_FILES[m.group(1)])
        self.assertGreater(len(rows["r"] if isinstance(rows, dict) else rows), 500)
        self.assertLess(len(doc.encode()), 600_000)  # was about 1 MB with the rows inline
        noscript = re.search(r'<div id="rows" class="tracker-groups"><noscript>(.*?)</noscript></div>', doc, re.S).group(1)
        text = html.unescape(re.sub(r"<[^>]+>", " ", noscript))
        for status in ("Sold out", "In stock"):
            self.assertIn(status, text)
        self.assertIn('id="restocked"', doc)  # Recent restocks stays server-rendered

    def test_app_js_fetches_the_file_and_falls_back_to_the_static_rows(self):
        js = (ROOT / "site/assets/app.js").read_text()
        self.assertIn("fetch(dataEl.dataset.src", js)
        self.assertIn(".catch(showStaticRows)", js)
        self.assertIn('document.querySelector("#rows noscript")', js)
        self.assertIn("runTracker(JSON.parse(dataEl.textContent))", js)  # inline rows (test fixtures) still work
        self.assertTrue(js.isascii())

    def test_tracker_files_are_cached_for_good(self):
        h = (ROOT / "cloudflare/_headers").read_text()
        self.assertRegex(h, r"/data/tracker/\*\n  Cache-Control: public, max-age=31536000, immutable\n  Content-Type: application/json; charset=utf-8")


class TransparencyTests(unittest.TestCase):
    def test_table_keeps_the_information_as_plain_text(self):
        doc = site.build_transparency()
        table = doc[doc.index('<table class="tp-table">'):doc.index("</table>")]
        text = html.unescape(re.sub(r"<[^>]+>", " ", table))
        for s in ("MIDORI*", "Traveler’s Company*", "Removal of all MIDORI products from the site.",
                  "Removal of all Traveler’s Company products from the site.", "Nov 19, 2026",
                  "Every MIDORI listing, stock tracker row, restock alert and restock email."):
            self.assertIn(s, text)
        self.assertNotIn("<a ", table)
        self.assertIsNone(re.search(r'href="[^"]*(travelers|midori)', doc, re.I))


if __name__ == "__main__":
    unittest.main()
