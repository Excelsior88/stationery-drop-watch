"""Zero Cookies badge sits in the shared footer next to the SaaSHub badge."""
import hashlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BADGES = ROOT / "site" / "assets" / "badges"
SRC_1X = BADGES / "zero-cookies-badge_v1_300x126.png"
SRC_2X = BADGES / "zero-cookies-badge_v1_600x252.png"
SHA_1X = "ce991564143c2e78cc75588762b01c282c96f041fcbc701ca91563b273eec132"
SHA_2X = "9f54d9a76b4ac3b54e5e787a30645fdff13d023a1427e88110f6efbef0660854"


def _png_size(path: Path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


class FooterZeroCookiesBadgeTests(unittest.TestCase):
    def test_self_hosted_images_are_unchanged_exports(self):
        self.assertTrue(SRC_1X.is_file())
        self.assertTrue(SRC_2X.is_file())
        self.assertEqual(hashlib.sha256(SRC_1X.read_bytes()).hexdigest(), SHA_1X)
        self.assertEqual(hashlib.sha256(SRC_2X.read_bytes()).hexdigest(), SHA_2X)
        self.assertEqual(_png_size(SRC_1X), (300, 126))
        self.assertEqual(_png_size(SRC_2X), (600, 252))

    def test_footer_places_the_badge_beside_saashub(self):
        src = (ROOT / "scripts" / "build_site.py").read_text()
        css = (ROOT / "site" / "assets" / "style.css").read_text()
        self.assertIn('class="foot-badge"', src)
        saashub = src.find('src="/assets/badges/saashub-approved.png"')
        zero = src.find('src="/assets/badges/zero-cookies-badge_v1_300x126.png"')
        self.assertGreater(saashub, 0)
        self.assertGreater(zero, saashub)
        # One foot-badge paragraph contains both images, Zero Cookies after SaaSHub.
        close = src.find("</p>", zero)
        self.assertLess(zero, close)
        self.assertIn('srcset="/assets/badges/zero-cookies-badge_v1_300x126.png 1x, /assets/badges/zero-cookies-badge_v1_600x252.png 2x"', src)
        self.assertIn('alt="Zero cookies: this site sets no cookies"', src)
        self.assertIn('class="badge-zero-cookies"', src)
        self.assertIn('width="130"', src)
        self.assertIn('height="55"', src)
        self.assertIn('loading="lazy"', src[zero:close])
        self.assertIn('href="/privacy"', src[saashub:close])
        # The Zero Cookies image itself is not a raw unlinked sibling outside an anchor,
        # and it does not point off-site.
        img_open = src.rfind("<img", 0, zero + 1)
        before = src[src.rfind("<a ", 0, img_open):img_open]
        self.assertIn('href="/privacy"', before)
        self.assertNotIn("target=\"_blank\"", before)
        self.assertIn(".foot-badge{margin:12px 0 0;display:flex;flex-wrap:wrap;align-items:center;gap:12px}", css)
        self.assertIn(".foot-badge .badge-zero-cookies{width:130px}", css)
        self.assertIn(".foot-badge .badge-saashub{width:120px}", css)
