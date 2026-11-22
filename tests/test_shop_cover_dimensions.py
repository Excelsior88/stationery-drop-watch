"""Every local lazy-loaded cover on /shop must carry width and height so it reserves a box."""
import re, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ShopCoverDims(unittest.TestCase):
    def test_covers_have_dimensions(self):
        html = (ROOT / "site/shop/index.html").read_text()
        covers = re.findall(r'<a class="shop-img[^>]*>(<img[^>]*>)', html)
        self.assertGreater(len(covers), 10)
        for tag in covers:
            self.assertRegex(tag, r'width="\d+"', tag[:120])
            self.assertRegex(tag, r'height="\d+"', tag[:120])


if __name__ == "__main__":
    unittest.main()
