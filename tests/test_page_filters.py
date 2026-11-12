"""Shop lists share one search, store, and status filter. The Hobonichi tracker keeps its own.

The table is in the HTML, so the listings are there with no JavaScript. The browser test
drives the real app.js with synthetic rows, not shop data.
"""
import os
import re
import urllib.request
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]


class PageFilterMarkupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        oe = site.amazon_main(site.stock["products"])
        cls.docs = []
        cls.docs.append(("hobonichi-restock-tracker/", site.build_hobo_tracker()))
        for g in site.GROUPS:
            cls.docs.append(site.build_group(g, oe))
        for d in site.DESIGNS:
            cls.docs.append(site.build_design(d, oe))

    def test_every_multi_shop_list_has_the_same_filter(self):
        for name, doc in self.docs:
            if name == "hobonichi-restock-tracker/":
                for needle in ('id="f-product"', 'id="f-type"', 'id="f-store"', 'id="f-status"', 'id="f-q"', 'id="f-reset"'):
                    self.assertIn(needle, doc, name)
                self.assertIn("<noscript>", doc, name)
                continue
            rows = doc.count('data-store="')
            if rows < 2:
                continue
            self.assertIn('class="filters page-filter card-filter"', doc, name)
            self.assertIn('data-filter="store"', doc, name)
            self.assertIn('data-filter="status"', doc, name)
            self.assertIn('data-filter="q"', doc, name)
            self.assertIn('data-filter="reset"', doc, name)
            self.assertIn("Nothing on this page matches those filters.", doc, name)
            self.assertGreaterEqual(rows, 2, name)

    def test_product_groups_start_collapsed(self):
        for name, doc in self.docs:
            if name == "hobonichi-restock-tracker/":
                blocks = re.findall(r"<details class=\"fam-block\"[^>]*>", doc)
                self.assertGreaterEqual(len(blocks), 2, name)
                self.assertTrue(all(" open" not in tag for tag in blocks), blocks[:2])
                self.assertIn('class="fam-name"', doc)
                self.assertIn("listings in stock", doc)
                continue
            sections = re.findall(r'<section class="group-sec"', doc)
            folds = re.findall(r'<details class="card group-fold">', doc)
            if sections:
                self.assertEqual(len(folds), len(sections), name)
                self.assertNotIn('group-fold" open', doc, name)
                self.assertNotIn('<section class="card group-sec"', doc, name)
            else:
                self.assertEqual(folds, [], name)

    def test_angela_line_is_unchanged(self):
        thanks = "Thank you to our follower Angela for suggesting we track these restocks."
        hits = [name for name, doc in self.docs if thanks in doc]
        self.assertCountEqual(hits, [
            "hobonichi-techo-2027-covers/nothing-to-hide-green/",
            "hobonichi-techo-2027-covers/nothing-to-hide-pink/",
            "hobonichi-weeks-2027/nothing-to-hide-yellow/",
        ])

    def test_built_site_internal_links_resolve(self):
        missing = []
        site_dir = ROOT / "site"
        for path in site_dir.rglob("*.html"):
            text = path.read_text()
            for href in re.findall(r'\b(?:href|src)="(/[^"]*)"', text):
                bare = href.split("#", 1)[0].split("?", 1)[0]
                if not bare or bare.startswith("//"):
                    continue
                rel = bare.lstrip("/")
                if rel.endswith("/"):
                    target = site_dir / rel / "index.html"
                elif rel == "":
                    target = site_dir / "index.html"
                else:
                    target = site_dir / rel
                    if not target.exists() and not rel.endswith(".html"):
                        target = site_dir / (rel + ".html")
                if not target.exists():
                    missing.append(f"{path.relative_to(site_dir)} -> {href}")
        self.assertEqual(missing, [])


class PageFilterBrowserTests(unittest.TestCase):
    def test_chrome_filters_search_reset_and_back(self):
        chrome = "/usr/local/bin/google-chrome"
        if not Path(chrome).exists() or not Path("/tmp/qa-browser/node_modules/puppeteer-core").exists():
            self.skipTest("Chrome or puppeteer-core is not available")
        out = Path("/tmp/qa-filters")
        if out.exists():
            shutil.rmtree(out)
        (out / "assets").mkdir(parents=True)
        shutil.copy(ROOT / "site/assets/app.js", out / "assets/app.js")
        shutil.copy(ROOT / "site/assets/local-time.js", out / "assets/local-time.js")
        (out / "list.html").write_text("""<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body>
<main id="content"><section class="card group-sec" id="stock">
<form class="filters page-filter" role="search" onsubmit="return false">
<label>Store<select data-filter="store"><option value="">All stores</option><option value="atlas">Atlas</option><option value="yoseka">Yoseka</option></select></label>
<label>Status<select data-filter="status"><option value="">Any status</option><option value="in_stock">In stock</option><option value="sold_out">Sold out</option></select></label>
<label class="grow">Search<input data-filter="q" type="search"></label>
<button type="button" data-filter="reset">Reset</button></form>
<table><tbody>
<tr data-store="atlas" data-status="in_stock"><td>Atlas Sage dotted</td></tr>
<tr data-store="yoseka" data-status="sold_out"><td>Yoseka Black</td></tr>
<tr data-store="paper" data-status="in_stock"><td>Paper Mouse Navy</td></tr>
</tbody></table>
<p class="card-empty" hidden>Nothing on this page matches those filters.</p>
</section></main>
<script src="/assets/local-time.js"></script><script src="/assets/app.js"></script>
</body></html>""")
        (out / "tracker.html").write_text("""<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body>
<form onsubmit="return false">
<select id="f-product"><option value="">All products</option><option value="sage">Sage</option></select>
<select id="f-type"><option value="">All types</option><option value="Cover">Cover</option></select>
<select id="f-store"><option value="">All stores</option><option value="atlas">Atlas</option></select>
<select id="f-status"><option value="">Any status</option><option value="in_stock">In stock</option><option value="sold_out">Sold out</option></select>
<input id="f-q" type="search"><button type="button" id="f-reset">Reset</button></form>
<p id="count"></p><table><tbody id="rows"></tbody></table><button id="more" hidden></button>
<script id="stock-data" type="application/json">[{"g":"sage","p":"Sage","gn":"Sage","c":"sage","t":"Cover","s":"Atlas","sid":"atlas","st":"in_stock","u":"https://example.test/sage","title":"Sage dotted","az":"","azl":""},{"g":"black","p":"Black","gn":"Black","c":"black","t":"Cover","s":"Yoseka","sid":"yoseka","st":"sold_out","u":"https://example.test/black","title":"Black","az":"","azl":""}]</script>
<script src="/assets/local-time.js"></script><script src="/assets/app.js"></script>
</body></html>""")
        (out / "fam.html").write_text("""<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body>
<form onsubmit="return false">
<select id="f-product"><option value="">All products</option></select>
<select id="f-type"><option value="">All types</option><option value="Book">Book</option></select>
<select id="f-store"><option value="">All stores</option></select>
<select id="f-status"><option value="">Any status</option><option value="in_stock">In stock</option></select>
<input id="f-q" type="search"><button type="button" id="f-reset">Reset</button></form>
<p id="count"></p><div id="rows"></div><button id="more" hidden></button>
<script id="stock-data" type="application/json">[{"g":"a6-en","p":"English","gn":"English book","c":"original-a6-en","t":"Book","s":"Atlas","sid":"atlas","st":"in_stock","u":"https://example.test/a","title":"","az":"","azl":"","fam":"original-a6","famn":"Original A6","fo":0},{"g":"weeks","p":"Weeks","gn":"Weeks book","c":"weeks-en","t":"Book","s":"Yoseka","sid":"yoseka","st":"sold_out","u":"https://example.test/w","title":"","az":"","azl":"","fam":"weeks","famn":"Weeks","fo":1}]</script>
<script src="/assets/local-time.js"></script><script src="/assets/app.js"></script>
</body></html>""")
        env = os.environ.copy()
        env["NODE_PATH"] = "/tmp/qa-browser/node_modules"
        env["FIXTURE_ORIGIN"] = "http://127.0.0.1:8794"
        server = subprocess.Popen([sys.executable, "-m", "http.server", "8794", "--bind", "127.0.0.1"],
                                  cwd=out, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            try:
                urllib.request.urlopen("http://127.0.0.1:8794/list.html", timeout=1).read()
                break
            except Exception:
                time.sleep(0.1)
        try:
            run = subprocess.run(["node", str(ROOT / "tests/page_filter_browser.mjs")],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
        finally:
            server.kill()
            server.wait(timeout=5)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("browser page filters ok", run.stdout)
