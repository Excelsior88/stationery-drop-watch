"""Shop lists share one search, store, and status filter. The Hobonichi tracker keeps its own.

The table is in the HTML, so the listings are there with no JavaScript. The browser test
drives the real app.js with synthetic rows, not shop data.
"""
import html
import json
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
                for needle in ('id="f-product"', 'id="f-type"', 'id="f-store"', 'id="f-status"', 'id="f-q"', 'id="f-reset"', 'aria-label="Filters"'):
                    self.assertIn(needle, doc, name)
                self.assertIn("<noscript>", doc, name)
                continue
            rows = doc.count('data-store="')
            if rows < 2:
                continue
            self.assertIn('class="filters page-filter card-filter"', doc, name)
            self.assertIn('aria-label="Filters"', doc, name)
            self.assertIn('data-filter="store"', doc, name)
            self.assertIn('data-filter="status"', doc, name)
            self.assertIn('data-filter="q"', doc, name)
            self.assertIn('data-filter="reset"', doc, name)
            self.assertIn("Nothing on this page matches those filters.", doc, name)
            self.assertGreaterEqual(rows, 2, name)

    def test_jump_row_is_gone_and_design_pages_fold(self):
        for name, doc in self.docs:
            self.assertNotIn("Jump to", doc, name)
            self.assertNotIn('aria-label="Products on this page"', doc, name)
        for g in site.GROUPS:
            name = g["slug"] + "/"
            doc = next(doc for n, doc in self.docs if n == name)
            ds = site.designs_of(g["slug"])
            if not ds:
                self.assertNotIn("design-fold", doc, name)
                continue
            self.assertIn(f"<summary>Design pages ({len(ds)})</summary>", doc, name)
            self.assertNotIn('class="design-fold" open', doc, name)
            self.assertNotIn(">Design pages:</span>", doc, name)
            for d in ds:
                self.assertIn(f'href="/{site.design_fname(d)}"', doc, name)
            # The old jump targets stay on the groups, so a #link still has somewhere to land.
            for cid in re.findall(r'<section class="group-sec" id="([^"]+)"', doc):
                self.assertTrue(cid, name)
            self.assertNotIn('class="shop-head"', doc, name)
            if g["slug"] == "archer-and-olive-dot-grid-journal":
                self.assertIn("Leuchtturm1917 · Hardcover Medium (A5) dotted notebook", doc)
                self.assertIn("Leuchtturm1917 · Bullet Journal Edition 2", doc)
                self.assertIn("Leuchtturm1917 · Medium (A5) 120G dotted notebook", doc)
                self.assertIn(">A5 Notepad Refill · white dot grid<", doc)
                self.assertIn(">A5 Soft Cover Refill Notebook · white dot grid<", doc)

    def test_signup_is_one_list_and_shop_counts_agree(self):
        hobo = site.build_hobo_tracker()
        self.assertIn("<h1>Hobonichi 2027 restock tracker</h1>", hobo)
        self.assertNotIn("Know the moment your planner is back", hobo)
        self.assertIn("Hobonichi 2027 restock tracker", hobo)
        for name, doc in self.docs:
            if "signup-strip" not in doc:
                continue
            label = re.search(r'class="strip-label"[^>]*>(.*?)</label>', doc)
            self.assertIsNotNone(label, name)
            self.assertEqual(label.group(1), "Get every restock alert by email", name)
            self.assertNotIn("next time", label.group(1))
            self.assertNotRegex(label.group(1), r"\bis back\b")
            note = re.search(r'class="strip-note">(.*?)</p>', doc).group(1)
            self.assertIn("multiple emails a day", note, name)
            self.assertNotRegex(note, r"\d+ emails a day")
        for g in site.GROUPS:
            ls = site.group_listings(g)
            tracked, checked, _ = site.shop_sets(ls)
            name, doc = site.build_group(g, site.amazon_main(site.stock["products"]))
            self.assertIn(f"{site.nshops(len(tracked))} ·", doc.split("<h1>")[0], name)
            self.assertIn(f"{len(checked)} of {site.nshops(len(tracked))} checked", doc, name)
            unk = sum(1 for l in ls if l["status"] == "unknown")
            self.assertIn(f'<div class="unk"><b>{unk}</b><span>couldn\'t check this run</span></div>', doc, name)
        for d in site.DESIGNS:
            ls = site.design_listings(d)
            if not ls:
                continue
            tracked, checked, _ = site.shop_sets(ls)
            doc = next(doc for n, doc in self.docs if n == site.design_fname(d))
            self.assertIn(f"{site.nshops(len(tracked))} ·", doc.split("<h1>")[0], d["slug"])
            self.assertIn(f"{len(checked)} of {site.nshops(len(tracked))} checked", doc, d["slug"])
            unk = sum(1 for l in ls if l["status"] == "unknown")
            self.assertIn(f'<div class="unk"><b>{unk}</b><span>couldn\'t check this run</span></div>', doc, d["slug"])

    def test_every_tracker_uses_the_same_section_order(self):
        markers = [
            ("hero", r'<section class="hero'),
            ("stats", r'class="stats five"'),
            ("signup", r'class="signup-strip"'),
            ("recent", r"<h2>Recent restocks</h2>"),
            ("list", r'id="tracker"'),
            ("good", r"<h2>Good to know</h2>"),
            ("more", r'<p class="eyebrow">More restock pages</p>'),
        ]
        expected = [key for key, _pat in markers]
        pages = [("hobonichi-restock-tracker/", site.build_hobo_tracker())]
        oe = site.amazon_main(site.stock["products"])
        for g in site.GROUPS:
            pages.append(site.build_group(g, oe))
        sequences = {}
        for name, doc in pages:
            body = doc.split("<footer", 1)[0]
            found = []
            for key, pat in markers:
                match = re.search(pat, body)
                self.assertIsNotNone(match, name + " missing " + key)
                found.append((match.start(), key))
            found.sort()
            sequences[name] = [key for _pos, key in found]
            self.assertEqual(sequences[name], expected, name)
            self.assertNotIn("m-lead", body, name)
            self.assertEqual(body.count('class="stats five"'), 1, name)
            self.assertIn(">in stock<", body, name)
            self.assertIn(">preorder<", body, name)
            self.assertIn(">sold out<", body, name)
            self.assertIn(">not yet on sale<", body, name)
            self.assertIn(">couldn't check this run<", body, name)
            if "design-fold" in body:
                self.assertLess(body.index("<h2>Recent restocks</h2>"), body.index("design-fold"), name)
                self.assertLess(body.index("design-fold"), body.index('class="filters'), name)
                self.assertNotIn('class="design-fold" open', body, name)
        self.assertEqual(len(sequences), 1 + len(site.GROUPS))

    def test_sold_out_note_is_inside_the_product_group(self):
        oe = site.amazon_main(site.stock["products"])

        def sentence(n):
            if n > 1:
                return f"Sold out at every shop we track ({n} shops)."
            return "Sold out at the only shop we track."

        for g in site.GROUPS:
            _name, doc = site.build_group(g, oe)
            buckets = {}
            for listing in site.group_listings(g):
                buckets.setdefault(site.listing_group_id(listing), []).append(listing)
            expected = {}
            for sl in buckets.values():
                if {l["status"] for l in sl} != {"sold_out"}:
                    continue
                text = sentence(len({l["store_id"] for l in sl}))
                expected[text] = expected.get(text, 0) + 1
            for text, count in expected.items():
                self.assertEqual(doc.count(text), count, (g["slug"], text))

        prods = site.hobo_products()
        rows = site.tracker_rows(prods, site.amazon_main(prods))
        groups = {}
        for row in rows:
            groups.setdefault(row["g"], []).append(row)
        hobo = site.build_hobo_tracker()
        expected = {}
        for ls in groups.values():
            if {r["st"] for r in ls} != {"sold_out"}:
                continue
            text = sentence(len({r["sid"] for r in ls}))
            expected[text] = expected.get(text, 0) + 1
        for text, count in expected.items():
            self.assertEqual(hobo.count(text), count, text)
        self.assertEqual(
            site.sold_everywhere_html([
                {"status": "sold_out", "store_id": "a"},
                {"status": "sold_out", "store_id": "b"},
            ]),
            '<p class="muted small">Sold out at every shop we track (2 shops).</p>')
        self.assertEqual(
            site.sold_everywhere_html([{"status": "sold_out", "store_id": "a"}]),
            '<p class="muted small">Sold out at the only shop we track.</p>')
        self.assertEqual(site.sold_everywhere_html([
            {"status": "sold_out", "store_id": "a"},
            {"status": "unknown", "store_id": "b"},
        ]), "")
        self.assertEqual(site.sold_everywhere_html([{"status": "coming_soon", "store_id": "a"}]), "")
        card = site.compare_product([
            {"st": "sold_out", "sid": "a", "s": "Alpha", "gn": "Camel", "g": "tn-regular-camel",
             "p": "Camel", "t": "Notebook", "u": "https://example.test/a", "rg": "", "title": "",
             "az": "https://www.amazon.com/dp/TEST?tag=excelsior88-20", "azl": "View on Amazon", "azm": 1},
            {"st": "sold_out", "sid": "b", "s": "Beta", "gn": "Camel", "g": "tn-regular-camel",
             "p": "Camel", "t": "Notebook", "u": "https://example.test/b", "rg": "", "title": "",
             "az": "https://www.amazon.com/dp/TEST?tag=excelsior88-20", "azl": "View on Amazon", "azm": 1},
        ])
        self.assertIn("Sold out at every shop we track (2 shops).", card)
        self.assertIn("https://www.amazon.com/dp/TEST?tag=excelsior88-20", card)
        self.assertEqual(card.count("Sold out at every shop we track (2 shops)."), 1)
        one = site.compare_product([{
            "st": "sold_out", "sid": "a", "s": "Alpha", "gn": "Camel", "g": "tn-regular-camel",
            "p": "Camel", "t": "Notebook", "u": "https://example.test/a", "rg": "", "title": "",
        }])
        self.assertIn("Sold out at the only shop we track.", one)
        mixed = site.compare_product([
            {"st": "in_stock", "sid": "a", "s": "Alpha", "gn": "Camel", "g": "tn-regular-camel",
             "p": "Camel", "t": "Notebook", "u": "https://example.test/a", "rg": "", "title": ""},
            {"st": "sold_out", "sid": "b", "s": "Beta", "gn": "Camel", "g": "tn-regular-camel",
             "p": "Camel", "t": "Notebook", "u": "https://example.test/b", "rg": "", "title": ""},
        ])
        self.assertNotIn("Sold out at every shop we track", mixed)
        self.assertNotIn("Sold out at the only shop we track", mixed)
        self.assertNotIn('id="sold-out-everywhere"', hobo)
        self.assertNotIn("Restock pages by product", hobo)
        self.assertNotIn("<h2>Sold out at every shop we track</h2>", hobo)
        fold_at = hobo.index('id="by-product"')
        fold = hobo[fold_at:hobo.index("</details>", fold_at)]
        self.assertIn("<summary>Design pages (", fold)
        self.assertNotIn(" open", fold[:fold.index(">")])
        more_at = hobo.index("More restock pages")
        self.assertLess(hobo.index("<h2>Good to know</h2>"), more_at)
        for g in site.GROUPS:
            if site.g_sec(g) != "hobonichi":
                continue
            self.assertIn(f'href="/{g["slug"]}/"', hobo[more_at:])
            for d in site.designs_of(g["slug"]):
                self.assertIn(f'href="/{site.design_fname(d)}"', fold)
        for match in site.amazon_main(prods).values():
            self.assertIn(match["url"], hobo)
        self.assertIn('href="/sold-out-everywhere/"', site.build_index())
        js = (ROOT / "site/assets/app.js").read_text()
        self.assertIn('location.hash === "#sold-out-everywhere"', js)
        self.assertIn('location.replace("/sold-out-everywhere/"', js)
        self.assertIn("Sold out at every shop we track (${n} shops).", js)
        self.assertIn("Sold out at the only shop we track.", js)

    def test_good_to_know_is_the_same_three_questions_plus_one_note(self):
        shared = [q for q, _a in site.TRACKER_FAQ]
        removed = (
            "How often do you check the shops?",
            "Which shops do you check?",
            "What do you track?",
            "Do you sell planners?",
            "How do restock alerts work?",
        )
        pages = [("hobonichi-restock-tracker/", site.build_hobo_tracker())]
        oe = site.amazon_main(site.stock["products"])
        for g in site.GROUPS:
            pages.append(site.build_group(g, oe))
        for name, doc in pages:
            questions = re.findall(r'<details class="faq-item"><summary>(.*?)</summary>', doc)
            self.assertEqual(questions[:3], [site.E(q) for q in shared], name)
            self.assertEqual(len(questions), 4, name)
            self.assertNotIn('faq-item" open', doc, name)
            self.assertNotIn("<ul>\n        <li>Statuses are exactly", doc, name)
            for q in removed:
                self.assertNotIn(q, doc, name)
            start = doc.rfind("<script", 0, doc.index('"@type": "FAQPage"'))
            end = doc.index("</script>", start)
            schema = json.loads(html.unescape(doc[start:end].split(">", 1)[1].replace("<\\/", "</")))
            self.assertEqual([q["name"] for q in schema["mainEntity"]], [html.unescape(x) for x in questions], name)
        hobo = site.build_hobo_tracker()
        self.assertIn("Hobonichi 2027 launch", hobo)
        dot = next(doc for n, doc in pages if n.startswith("archer-and-olive"))
        self.assertIn("best dot grid journals compared", dot)
        self.assertIn("sells out on its own", dot)
        tn = next(doc for n, doc in pages if "travelers-company" in n)
        self.assertIn("No. 13714006", tn)
        self.assertIn("counterfeit", tn)
        self.assertIn("Regular vs Passport vs Card Size", tn)
        midori = next(doc for n, doc in pages if "midori-md" in n)
        self.assertIn("once a year", midori)
        self.assertIn("plain MD notebooks", midori)
        home = site.build_index()
        home_q = re.findall(r'<section class="card faq" id="good-to-know">.*?</section>', home, re.S)[0]
        home_names = re.findall(r"<summary>(.*?)</summary>", home_q)
        self.assertEqual([html.unescape(q) for q in home_names], list(site.HUB_FAQ))
        self.assertEqual(len(home_names), 6)
        self.assertNotIn('What does "Couldn&#x27;t check" mean?', home_q)
        self.assertNotIn('What does "Not yet on sale" mean?', home_q)
        status_q = site.TRACKER_FAQ[1][0]
        home_answer = re.search(
            rf"<summary>{re.escape(site.E(status_q))}</summary><p>(.*?)</p>", home).group(1)
        self.assertIn("That's different from sold out.", html.unescape(home_answer))
        self.assertIn("shop's site didn't respond", html.unescape(home_answer))
        self.assertIn("instead of guessing", html.unescape(home_answer))
        self.assertIn(site.TRACKER_FAQ[1][1].split(".")[0], html.unescape(home_answer))
        home_start = home.rfind("<script", 0, home.index('"@type": "FAQPage"'))
        home_end = home.index("</script>", home_start)
        home_schema = json.loads(html.unescape(home[home_start:home_end].split(">", 1)[1].replace("<\\/", "</")))
        self.assertEqual([q["name"] for q in home_schema["mainEntity"]], list(site.HUB_FAQ))
        self.assertEqual(home_schema["mainEntity"][2]["acceptedAnswer"]["text"], html.unescape(home_answer))
        self.assertNotIn('faq-item" open', home_q)
        self.assertIn('href="/#good-to-know">FAQ</a>', home)
        faq_page = site.redirect_page("#good-to-know")
        self.assertIn("https://stationerydropwatch.com/#good-to-know", faq_page)
        js = (ROOT / "site/assets/app.js").read_text()
        self.assertIn('location.replace("/#good-to-know"', js)
        self.assertNotIn('faq: "faq"', js)

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

    def test_long_guide_lists_start_collapsed(self):
        _name, where = site.build_where_to_buy()
        slugs = [g["slug"] for g in site.GROUPS if site.g_sec(g) == "hobonichi" and site.group_listings(g)]
        folds = re.findall(r'<details class="card group-fold" id="([^"]+)">', where)
        self.assertEqual(folds, slugs)
        self.assertNotIn('group-fold" open', where)
        self.assertLess(where.index('id="quick"'), where.index("group-fold"))
        self.assertLess(where.index("<h1>"), where.index("group-fold"))
        src = where.index("<h2>Sources</h2>")
        self.assertNotIn("<details", where[src:where.index("</ol>", src)])
        self.assertIn('id="tips"', where)
        vs = site.build_vs()[1]
        article = vs[vs.index("<h2>Side by side</h2>"):vs.index("<h2>Sources</h2>")]
        self.assertNotIn("group-fold", article)
        self.assertNotIn("group-fold", vs)
        self.assertIn("<h2>Sources</h2>", vs)
        guides = site.build_guides_index()[1]
        self.assertNotIn("group-fold", guides)
        self.assertIn("<h3>Hobonichi</h3>", guides)
        dot = site.build_dotgrid_guide()[1]
        self.assertNotIn("group-fold", dot)
        tn = site.build_tn_sizes()[1]
        self.assertIn("<h2>Sources</h2>", tn)
        self.assertNotIn("group-fold", tn)
        cal = site.build_hobonichi()
        self.assertNotIn("group-fold", cal)

    def test_guide_drawings_match_the_page_copy(self):
        vs = site.build_vs()[1]
        self.assertNotIn("guide-figure", vs)
        self.assertNotIn("techo-cousin-weeks-format-guide", vs)
        self.assertEqual(vs.count('class="fmt-icon"'), 3)
        self.assertIn('aria-hidden="true"', vs)
        # Same scale as the source drawing: A5 is the largest page, Weeks is taller than it is wide.
        self.assertIn('viewBox="0 0 99 142"', vs)
        self.assertIn('viewBox="0 0 142 204"', vs)
        self.assertIn('viewBox="0 0 88 182"', vs)
        tn = site.build_tn_sizes()[1]
        self.assertNotIn("guide-figure", tn)
        self.assertNotIn("travelers-notebook-sizes.png", tn)
        self.assertEqual(tn.count('class="fmt-icon"'), 3)
        self.assertIn('viewBox="0 0 120 220"', tn)
        self.assertIn('viewBox="0 0 98 134"', tn)
        self.assertIn('viewBox="0 0 75 110"', tn)
        self.assertIn('fill="#b2522f"', tn)
        self.assertIn('fill="#5e7f62"', tn)
        self.assertIn('fill="#d1992e"', tn)
        for pair in ("220 × 120", "210 × 110", "134 × 98", "124 × 89", "110 × 75", "100 × 65"):
            h, w = pair.split(" × ")
            self.assertIn(f"H{h} × W{w}", tn)

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
