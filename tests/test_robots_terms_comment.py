import unittest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site

EXPECTED = """# Stationery Drop Watch is for personal shopping only.
# Using this site or its data for reselling, bulk buying,
# or automated purchasing is not allowed.
# See https://stationerydropwatch.com/terms/#prohibited-uses
User-agent: *
Allow: /

Sitemap: https://stationerydropwatch.com/sitemap.xml
"""


class RobotsTermsComment(unittest.TestCase):
    def test_generated_robots_is_exact(self):
        self.assertEqual(site.ROBOTS, EXPECTED)

    def test_committed_robots_is_exact(self):
        self.assertEqual((ROOT / "site/robots.txt").read_text(), EXPECTED)


if __name__ == "__main__":
    unittest.main()
