"""Nov 24, 2026 (owner t1906u): public stock feed trimmed, no "raw data" links, security.txt,
tracker text spacing, hidden Recent restocks empty note, and the /for-shops/ page."""
import json
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

ALERT_FIELDS = ("store_id", "store", "canonical", "label", "type", "url", "checked_at", "status",
                "status_since", "first_seen", "title", "method")


class PublicStockTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((ROOT / "data/stock.json").read_text())
        self.pub = site.public_stock(self.raw)

    def test_drops_only_internal_fields(self):
        self.assertEqual(len(self.pub["products"]), len(self.raw["products"]))
        for row in self.pub["products"]:
            for k in site.PUBLIC_STOCK_DROP:
                self.assertNotIn(k, row)
        self.assertEqual(set(site.PUBLIC_STOCK_DROP), {"error", "available_variants", "total_variants"})
        self.assertEqual({k for k in self.pub if k != "products"}, {k for k in self.raw if k != "products"})

    def test_keeps_every_field_the_alert_routine_reads(self):
        for raw_row, row in zip(self.raw["products"], self.pub["products"]):
            for k in ALERT_FIELDS:
                self.assertEqual(row.get(k), raw_row.get(k), k)
            for k in ("price_cents", "currency", "official_note"):
                self.assertEqual(row.get(k), raw_row.get(k), k)

    def test_raw_file_is_unchanged_by_publish(self):
        before = (ROOT / "data/stock.json").read_text()
        site.public_stock(json.loads(before))
        self.assertEqual((ROOT / "data/stock.json").read_text(), before)


class NoRawDataLinkTests(unittest.TestCase):
    def test_built_pages_do_not_link_stock_json(self):
        src = (ROOT / "scripts/build_site.py").read_text()
        self.assertNotIn('href="data/stock.json"', src)
        self.assertNotIn("raw data is public", src)
        self.assertNotIn("raw data for every check", src)
        for f in (ROOT / "site").glob("**/index.html"):
            self.assertNotIn("data/stock.json", f.read_text(), f)


class TrackerTextTests(unittest.TestCase):
    def test_space_before_sub_lines(self):
        src = (ROOT / "scripts/build_site.py").read_text()
        self.assertIn("since_html = f' <span class=\"sub\">since", src)
        dot = (ROOT / "site/dot-grid-journal-restock-tracker/index.html").read_text()
        self.assertNotRegex(dot, r'class="region"[^>]*>[A-Z]{2}</span><span class="sub"')
        self.assertNotIn('</span><span class="sub">since', dot)

    def test_empty_note_is_hidden_but_still_shown_by_css(self):
        home = (ROOT / "site/index.html").read_text()
        self.assertIn('<p class="feed-empty muted small" hidden>None of these are in stock now.</p>', home)
        css = (ROOT / "site/assets/style.css").read_text()
        self.assertIn('.feed-empty{display:block}', css)  # author display beats the UA [hidden] rule
        self.assertNotRegex(css, r"\[hidden\]\s*\{[^}]*!important")


class SecurityTxtTests(unittest.TestCase):
    def test_fields_and_expiry(self):
        txt = (ROOT / "cloudflare/security.txt").read_text()
        self.assertIn("Contact: mailto:admin@stationerydropwatch.com\n", txt)
        self.assertIn("Canonical: https://stationerydropwatch.com/.well-known/security.txt\n", txt)
        self.assertIn("Preferred-Languages: en\n", txt)
        exp = re.search(r"^Expires: (\S+)$", txt, re.M).group(1)
        when = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        self.assertGreater(when, datetime.now(timezone.utc) + timedelta(days=30), "renew security.txt Expires")

    def test_deploy_copies_it(self):
        wf = (ROOT / ".github/workflows/cloudflare-pages.yml").read_text()
        self.assertIn("cp cloudflare/security.txt out/.well-known/security.txt", wf)
        self.assertIn("test -f out/.well-known/security.txt", wf)


class ForShopsTests(unittest.TestCase):
    def setUp(self):
        self.fname, self.doc = site.build_for_shops()

    def test_claims_come_from_checker(self):
        checker = (ROOT / "scripts/checker.py").read_text()
        ua = re.search(r'^UA = "([^"]+)"', checker, re.M).group(1)
        self.assertIn(site.E(ua), self.doc)
        self.assertIn("contact: admin@stationerydropwatch.com", ua)
        delay = re.search(r"^DELAY = ([0-9.]+)", checker, re.M).group(1)
        self.assertIn(f"at least {delay} seconds", self.doc)
        self.assertIn(site.CHECK_FREQ, self.doc)
        self.assertIn("User-agent: StationeryDropWatch", self.doc)

    def test_listed_in_footer_and_sitemap(self):
        self.assertEqual(self.fname, "for-shops/")
        self.assertIn('href="/for-shops/">For shops and brands</a>', self.doc)
        self.assertIn("https://stationerydropwatch.com/for-shops/", site.build_sitemap())

    def test_copy_rules(self):
        body = self.doc.split('<main id="content"', 1)[1].split("</main>", 1)[0]
        for banned in ("Designphil", "MIDORI", "Midori", "Traveler", "Kinokuniya", "LLC", "ullet journal", "affiliate link"):
            self.assertNotIn(banned, body, banned)
        self.assertIn("no affiliate tag", body)


if __name__ == "__main__":
    unittest.main()
