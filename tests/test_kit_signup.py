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
        self.assertEqual(site.KIT_SIGNUP_ACTION, "https://app.kit.com/forms/10225471/subscriptions")
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
            self.assertNotIn("buttondown", low.replace("buttondown-archive", ""), name) if name == "privacy" else None


if __name__ == "__main__":
    unittest.main()
