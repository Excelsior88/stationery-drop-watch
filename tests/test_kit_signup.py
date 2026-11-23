"""Signup now posts to Kit's form (10225471) with one tags[] checkbox per tracker."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402


class KitSignup(unittest.TestCase):
    def test_action_and_tags(self):
        self.assertEqual(site.KIT_SIGNUP_ACTION, "/api/subscribe")
        self.assertEqual([(s, i) for s, i, _ in site.KIT_TAGS],
                         [("hobonichi", "26280763"), ("dot-grid", "26280764"), ("inks", "26280765")])

    def test_plain_form_post_no_buttondown(self):
        doc = site.signup()
        self.assertIn('method="post"', doc)
        self.assertIn('name="email_address"', doc)
        self.assertEqual(len(re.findall(r'name="tags\[\]"', doc)), 3)
        self.assertEqual(len(re.findall(r" checked>", doc)), 3)
        self.assertNotIn("buttondown", doc.lower())
        self.assertIn("Dot grid journals", doc)
        self.assertIn("Limited-edition inks", doc)
        self.assertNotIn("bullet journal", doc.lower())

    def test_tracker_page_preselects_its_own(self):
        doc = site.signup_for(section="hobonichi")
        self.assertEqual(re.findall(r'value="(\d+)" id="[^"]*"( checked)?', doc),
                         [("26280763", " checked"), ("26280764", ""), ("26280765", "")])

    def test_no_surface_says_inks_are_not_emailed(self):
        for name, doc in [("home", site.build_index()), ("about", site.build_about()),
                          ("privacy", site.build_privacy())]:
            low = doc.lower()
            self.assertNotIn("don't cover inks", low, name)
            self.assertNotIn("emails don't cover", low, name)
            if name == "privacy":
                # Buttondown appears only in the one paragraph about the move to Kit (dual-send through Dec 7, 2026).
                m = re.search(r"<p>before november 22, 2026, signups went to .*?</p>", low)
                self.assertIsNotNone(m)
                self.assertIn("through december 7, 2026", m.group(0))
                self.assertIn("kit only", m.group(0))
                rest = low[:m.start()] + low[m.end():]
                self.assertNotIn("buttondown", rest.replace("buttondown-archive", ""), name)


class InkPageSignupTests(unittest.TestCase):
    def test_ink_page_has_the_standard_box_with_inks_ticked(self):
        import re
        doc = (ROOT / "site/limited-edition-fountain-pen-ink/index.html").read_text()
        self.assertEqual(doc.count('id="alerts"'), 1)
        self.assertEqual(doc.count('id="alerts-bottom"'), 1)
        self.assertIn('action="/api/subscribe"', doc)
        ticked = re.findall(r'id="alerts-tag-([a-z-]+)"[^>]*? checked>', doc)
        self.assertEqual(ticked, ["inks"])

    def test_every_tracker_design_and_guide_page_has_a_box_or_alerts_link(self):
        import glob
        skip = ("contact/", "privacy/", "terms/", "transparency/", "travelers-company-limited-edition/", "travelers-notebook-regular-vs-passport-vs-card-size/",
                "midori-md-limited-edition/")
        for f in glob.glob(str(ROOT / "site/**/index.html"), recursive=True):
            rel = f.split("/site/", 1)[1]
            if rel.startswith(skip):
                continue
            doc = open(f).read()
            if "http-equiv=\"refresh\"" in doc:
                continue
            self.assertTrue('id="alerts"' in doc or 'href="#alerts"' in doc or 'href="/#alerts"' in doc, rel)




class TurnstileSignupTests(unittest.TestCase):
    def test_box_has_turnstile_honeypot_and_status(self):
        doc = site.signup()
        self.assertIn('class="cf-turnstile"', doc)
        self.assertIn(f'data-sitekey="{site.TURNSTILE_SITEKEY}"', doc)
        self.assertIn('name="website"', doc)  # honeypot
        self.assertIn('class="signup-status"', doc)
        self.assertNotIn("app.kit.com/forms", doc)

    def test_no_secret_in_source(self):
        src = (ROOT / "site/functions/api/subscribe.js").read_text()
        self.assertNotRegex(src, r"0x4[A-Za-z0-9_-]{20,}")
        self.assertIn("env.TURNSTILE_SECRET", src)
        self.assertIn("env.KIT_API_KEY", src)

    def test_privacy_names_turnstile(self):
        doc = (ROOT / "site/privacy/index.html").read_text()
        self.assertIn("Cloudflare Turnstile", doc)
        self.assertIn("/api/subscribe", doc)

    def test_function_behaviour_with_mocked_fetch(self):
        import shutil, subprocess
        if not shutil.which("node"):
            self.skipTest("node not installed")
        r = subprocess.run(["node", str(ROOT / "tests/subscribe_function_test.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
