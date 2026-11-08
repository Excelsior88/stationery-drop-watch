"""Visitor-local labels rewrite marked instants only. The stored ISO time and the Eastern Time fallback stay."""
import html
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402


class TimeTagTests(unittest.TestCase):
    def test_fallback_is_eastern_and_keeps_the_stored_instant(self):
        iso = "2026-11-08T08:14:52+00:00"
        tag = site.time_tag(iso)
        self.assertIn('class="time-instant"', tag)
        self.assertIn(f'datetime="{iso}"', tag)
        self.assertIn("ET", html.unescape(tag))
        self.assertNotIn("your local", tag.lower())
        self.assertNotIn("GMT", tag)

    def test_homepage_marks_the_last_check_and_explains_the_fallback(self):
        doc = site.build_index()
        self.assertIn('class="time-instant"', doc)
        self.assertIn('src="/assets/local-time.js', doc)
        self.assertIn("Eastern Time", doc)
        self.assertIn("If it cannot, the Eastern Time label stays", doc)
        self.assertIn("Guide dates and the 2027 calendar dates stay as written", doc)

    def test_calendar_dates_are_not_instants(self):
        doc = site.build_hobonichi()
        self.assertIn("<time>Aug 25, 2026</time>", doc)
        self.assertIn("<time>Aug 31, 2026 · 10 PM ET</time>", doc)
        self.assertIn("<time>Sep 30 – Oct 1, 2026</time>", doc)
        self.assertNotIn('time class="time-instant">Aug 25', doc)
        # The launch line is an editorial fact, not a check timestamp.
        self.assertNotIn('datetime="2026-08-31', doc)

    def test_design_faq_html_can_localize_and_schema_stays_eastern(self):
        design = next(d for d in site.DESIGNS if d["slug"] == "midnight-blue" and d["parent"] == "hobonichi-weeks-2027")
        _fname, doc = site.build_design(design, {})
        self.assertIn('class="time-instant"', doc)
        self.assertIn("ET", html.unescape(doc))
        start = doc.find("FAQPage")
        schema = html.unescape(doc[start:start + 2500])
        self.assertIn("PM ET", schema)
        self.assertNotIn("time-instant", schema)


class MidoriCardTests(unittest.TestCase):
    def test_approved_bytes_and_alt_describe_the_artwork(self):
        import hashlib
        raw = (ROOT / "site/assets/brand/og-midori.png").read_bytes()
        self.assertEqual(len(raw), 174111)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), site.MIDORI_OG_SHA)
        self.assertNotIn("30 minutes", site.OG_MIDORI_ALT)
        self.assertIn("Diaries, diary stickers and paper", site.OG_MIDORI_ALT)
        self.assertIn("stationerydropwatch.com", site.OG_MIDORI_ALT)
        group = next(g for g in site.GROUPS if g.get("section") == "midori")
        _fname, doc = site.build_group(group, {})
        self.assertIn(site.OG_MIDORI_ALT, html.unescape(doc))
        self.assertIn('og:image:width" content="1200"', doc)
        self.assertIn('og:image:height" content="630"', doc)
        design = next(d for d in site.DESIGNS if d["parent"] == group["slug"])
        _df, ddoc = site.build_design(design, {})
        self.assertIn(site.OG_MIDORI_ALT, html.unescape(ddoc))
        script = (ROOT / "scripts/brand/make_og.py").read_text()
        self.assertNotIn('card("og-midori.png"', script)
        self.assertIn("left og-midori.png unchanged", script)

    def test_restock_note_does_not_claim_the_visible_time_is_eastern_after_a_switch(self):
        doc = site.build_index()
        self.assertIn("Times are labeled Eastern Time.", doc)
        self.assertNotIn("It is Eastern Time here", doc)
        self.assertIn('class="time-zone-note"', doc)


class LocalTimeScriptTests(unittest.TestCase):
    def test_node_zones_dst_boundaries_and_bad_timestamps(self):
        script = ROOT / "tests" / "local-time.test.js"
        run = subprocess.run(["node", str(script)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
