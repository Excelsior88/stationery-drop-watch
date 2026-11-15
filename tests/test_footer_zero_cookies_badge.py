"""Footer badges share the live Zero Cookies 130x55 box: SaaSHub, cookies, Hamtramck."""
import hashlib
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BADGES = ROOT / "site" / "assets" / "badges"

SHA = {
    "saashub_v2_150x50.png": "a85efba2366e8cb6992eb934044c929f712f6bc7cff4eb2d919783aeb00a2d8f",
    "saashub_v2_300x100.png": "e5b17df4053540a62d614d185a794bc89b761895afc204545b72458e513c233b",
    "zero-cookies-badge_v1_300x126.png": "ce991564143c2e78cc75588762b01c282c96f041fcbc701ca91563b273eec132",
    "zero-cookies-badge_v1_600x252.png": "9f54d9a76b4ac3b54e5e787a30645fdff13d023a1427e88110f6efbef0660854",
    "made-in-hamtramck_v2_150x50.png": "1d1885ca474992dd9bb2e8f2a9278382e5b492c37c403419b613ad191d1d3031",
    "made-in-hamtramck_v2_300x100.png": "d318be99adeb3ed971a8656a766510e95b790fe2ab30d753f50ceb03a59e21c9",
    "made-in-hamtramck_v2_900x300.png": "8af5e36f5e7a2df2453581a44ba8f710e1a5cc70ab958593d8c93c9910659f50",
}
SIZE = {
    "saashub_v2_150x50.png": (150, 50),
    "saashub_v2_300x100.png": (300, 100),
    "zero-cookies-badge_v1_300x126.png": (300, 126),
    "zero-cookies-badge_v1_600x252.png": (600, 252),
    "made-in-hamtramck_v2_150x50.png": (150, 50),
    "made-in-hamtramck_v2_300x100.png": (300, 100),
    "made-in-hamtramck_v2_900x300.png": (900, 300),
}


def _png_size(path: Path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


class FooterMatchedBadgeTests(unittest.TestCase):
    def test_self_hosted_images_match_source_exports(self):
        for name, sha in SHA.items():
            path = BADGES / name
            self.assertTrue(path.is_file(), name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), sha, name)
            self.assertEqual(_png_size(path), SIZE[name], name)
        # SaaSHub 2x is the authentic 300x100 original, never redrawn.
        self.assertEqual(
            hashlib.sha256((BADGES / "saashub_v2_300x100.png").read_bytes()).hexdigest(),
            hashlib.sha256((BADGES / "saashub-approved.png").read_bytes()).hexdigest(),
        )

    def test_footer_order_equal_boxes_links_and_srcset(self):
        src = (ROOT / "scripts" / "build_site.py").read_text()
        css = (ROOT / "site" / "assets" / "style.css").read_text()
        start = src.find('<p class="foot-badge">')
        self.assertGreater(start, 0)
        footer = src[start:src.find("</p>", start)]
        saas = footer.find("saashub_v2_150x50.png")
        zero = footer.find("zero-cookies-badge_v1_300x126.png")
        ham = footer.find("made-in-hamtramck_v2_150x50.png")
        self.assertTrue(0 <= saas < zero < ham)

        self.assertIn(
            'href="https://www.saashub.com/stationery-drop-watch?utm_source=badge&utm_campaign=badge&utm_content=stationery-drop-watch&badge_variant=color&badge_kind=approved"',
            footer,
        )
        first_a = footer[footer.find("<a "):footer.find("<img")]
        self.assertIn('target="_blank"', first_a)
        self.assertIn('rel="noopener"', first_a)
        self.assertIn('alt="Stationery Drop Watch on SaaSHub"', footer)
        self.assertIn(
            'srcset="/assets/badges/saashub_v2_150x50.png 1x, /assets/badges/saashub_v2_300x100.png 2x"',
            footer,
        )
        # Never invent a SaaSHub file larger than the authentic 300x100.
        self.assertNotIn("saashub_v2_600", footer)
        self.assertNotIn("saashub_v2_900", footer)

        zero_img = footer.find("<img", footer.find("badge-zero-cookies"))
        zero_a = footer.rfind("<a ", 0, zero_img)
        self.assertIn('href="/privacy"', footer[zero_a:zero_img])
        self.assertNotIn('target="_blank"', footer[zero_a:zero_img])
        self.assertIn('alt="Zero cookies: this site sets no cookies"', footer)
        self.assertIn(
            'srcset="/assets/badges/zero-cookies-badge_v1_300x126.png 1x, /assets/badges/zero-cookies-badge_v1_600x252.png 2x"',
            footer,
        )

        self.assertIn('alt="Made in Hamtramck, MI"', footer)
        self.assertIn(
            'srcset="/assets/badges/made-in-hamtramck_v2_150x50.png 150w, /assets/badges/made-in-hamtramck_v2_300x100.png 300w, /assets/badges/made-in-hamtramck_v2_900x300.png 900w"',
            footer,
        )
        self.assertIn('sizes="130px"', footer)
        ham_img = footer.find("<img", footer.find("badge-hamtramck"))
        self.assertNotIn("<a ", footer[footer.find("</a>", zero_img):ham_img])

        for tag in re.findall(r"<img[^>]+>", footer):
            self.assertIn('width="130"', tag)
            self.assertIn('height="55"', tag)
            self.assertIn('loading="lazy"', tag)

        self.assertIn(
            ".foot-badge{margin:12px 0 0;display:flex;flex-wrap:wrap;align-items:center;gap:12px}",
            css,
        )
        self.assertIn(".foot-badge a{display:inline-block;line-height:0;max-width:100%}", css)
        self.assertIn(
            ".foot-badge img{width:130px;height:55px;object-fit:contain;object-position:center;display:block;max-width:100%}",
            css,
        )
