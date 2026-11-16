"""Fixes from the Nov 16 2026 site audit: breadcrumbs, About copy, homepage restock switch, checker push."""
import html
import json
import re
import unittest
from pathlib import Path

import yaml

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def crumb_names(doc):
    nav = re.search(r'<nav class="crumbs" aria-label="Breadcrumb">(.*?)</nav>', doc, re.S).group(1)
    return [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in nav.split('<span aria-hidden="true">›</span>')]


def ld_crumb_names(doc):
    for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
        data = json.loads(raw)
        for d in data if isinstance(data, list) else [data]:
            if d.get("@type") == "BreadcrumbList":
                return [i["name"] for i in d["itemListElement"]]
    return None


class BreadcrumbTests(unittest.TestCase):
    def test_hobonichi_trackers_and_designs_sit_under_the_hub(self):
        weeks = (SITE / "hobonichi-weeks-2027/index.html").read_text()
        self.assertEqual(crumb_names(weeks), ["Home", "Hobonichi tracker", "Weeks"])
        self.assertEqual(ld_crumb_names(weeks), ["Home", "Hobonichi tracker", "Weeks"])
        star = (SITE / "hobonichi-weeks-2027/starlight/index.html").read_text()
        self.assertEqual(crumb_names(star), ["Home", "Hobonichi tracker", "Weeks", "tanakadaisuke: Starlight"])
        self.assertEqual(ld_crumb_names(star), ["Home", "Hobonichi tracker", "Weeks", "tanakadaisuke: Starlight"])
        self.assertIn('<a href="/hobonichi-restock-tracker/">Hobonichi tracker</a>', star)

    def test_other_sections_stay_top_level(self):
        stag = (SITE / "archer-and-olive-dot-grid-journal/archer-and-olive-stag/index.html").read_text()
        self.assertEqual(crumb_names(stag), ["Home", "Dot grid journals", "Archer and Olive Stag"])
        tn = (SITE / "travelers-company-limited-edition/index.html").read_text()
        self.assertEqual(crumb_names(tn), ["Home", "Traveler's Company"])

    def test_shop_crumb_matches_the_nav(self):
        shop = (SITE / "shop/index.html").read_text()
        self.assertEqual(crumb_names(shop), ["Home", "Shop"])
        self.assertEqual(ld_crumb_names(shop), ["Home", "Shop"])
        self.assertIn("<h1>Our planners and journals</h1>", shop)


class AboutTests(unittest.TestCase):
    def test_no_coming_soon_and_hamtramck_line_stays(self):
        about = (SITE / "about.html").read_text()
        self.assertNotIn("tag-soon", about)
        self.assertNotIn("Coming soon", about)
        self.assertNotIn("coming soon", about)
        self.assertIn("Stationery Drop Watch is built in Hamtramck, Michigan.</p>", about)
        self.assertIn("The couple behind Drop Watch</h2>", about)


class HomeRestockSwitchTests(unittest.TestCase):
    def test_all_lists_sold_out_restocks_in_time_order_like_the_hub(self):
        home = site.build_index()
        self.assertNotIn("feed-fold", home)
        self.assertNotIn("Show earlier restocks", home)
        self.assertIn('class="restock-all" checked', home)
        self.assertIn('class="restock-in"', home)
        css = (SITE / "assets/style.css").read_text()
        self.assertNotIn("feed-fold", css)
        self.assertIn('.restocks:has(.restock-in:checked) .feed-item:not([data-now="in_stock"]){display:none}', css)
        self.assertNotIn("feed-fold", (SITE / "assets/app.js").read_text())


class CheckerWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.wf = yaml.safe_load((ROOT / ".github/workflows/check-and-deploy.yml").read_text())
        self.steps = self.wf["jobs"]["check"]["steps"]

    def test_one_run_at_a_time(self):
        self.assertEqual(self.wf["concurrency"], {"group": "drop-watch", "cancel-in-progress": False})

    def test_run_starts_from_latest_main_before_the_checker(self):
        names = [s.get("name") or s.get("uses") for s in self.steps]
        sync = names.index("Start from the latest main")
        self.assertLess(sync, names.index("Run stock checker"))
        self.assertIn("git reset --hard origin/main", self.steps[sync]["run"])

    def test_rejected_push_rewrites_data_instead_of_rebasing_json(self):
        commit = next(s for s in self.steps if s.get("name", "").startswith("Commit data changes"))["run"]
        self.assertNotIn("pull --rebase", commit)
        self.assertNotIn("git rebase", commit)
        self.assertIn("git reset --hard origin/main", commit)
        self.assertIn('cp "$results/stock.json" "$results/changes.json" data/', commit)
        self.assertIn("python scripts/build_site.py", commit)


if __name__ == "__main__":
    unittest.main()
