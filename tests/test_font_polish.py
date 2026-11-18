"""Typography consistency: one self-hosted sans, matching header/footer, phone copy."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "site" / "assets" / "style.css").read_text()
FONTS = ROOT / "site" / "assets" / "fonts"
FOOTER_RE = re.compile(
    r'<p class="foot-follow"><a href="follow/">Follow us</a></p>'
)


class FontPolishTests(unittest.TestCase):
    def test_liberation_sans_is_self_hosted_site_sans(self):
        self.assertIn('--sans:"Liberation Sans"', CSS)
        self.assertIn("fonts/liberation-sans-regular.woff2", CSS)
        self.assertIn("fonts/liberation-sans-italic.woff2", CSS)
        self.assertIn("fonts/liberation-sans-bold.woff2", CSS)
        self.assertIn("fonts/liberation-sans-bolditalic.woff2", CSS)
        for face in ("regular", "italic", "bold", "bolditalic"):
            path = FONTS / f"liberation-sans-{face}.woff2"
            self.assertTrue(path.is_file(), path)
            self.assertGreater(path.stat().st_size, 8000)
        for cdn in (
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "use.typekit.net",
            "fonts.adobe.com",
            "cloud.typography.com",
        ):
            self.assertNotIn(cdn, CSS)

    def test_pages_preload_liberation_sans(self):
        html = (ROOT / "site" / "index.html").read_text()
        self.assertIn("fonts/liberation-sans-regular.woff2", html)
        self.assertRegex(html, r'rel="preload"[^>]+liberation-sans-regular\.woff2|liberation-sans-regular\.woff2[^>]+rel="preload"')

    def test_header_nav_and_footer_use_site_sans(self):

        self.assertRegex(CSS, r"nav a\{[^}]*font-family:var\(--sans\)")
        self.assertRegex(CSS, r"\.foot\{[^}]*font-family:var\(--sans\)")
        self.assertRegex(CSS, r"\.foot-nav a,\.foot-follow a\{[^}]*font-family:var\(--sans\)")
        self.assertRegex(CSS, r"\.nav-menu>summary\{[^}]*font-family:var\(--sans\)")

    def test_footer_brand_name_uses_heading_serif(self):
        self.assertIn(".foot-brand strong{font-family:var(--serif);font-weight:600}", CSS)

    def test_follow_us_matches_other_footer_links(self):
        self.assertRegex(
            CSS, r"\.foot-nav a,\.foot-follow a\{[^}]*text-decoration:none"
        )
        # The follow link is not inside nav, so it must not rely on `nav a`.
        html = (ROOT / "site" / "index.html").read_text()
        self.assertRegex(html, r'<p class="foot-follow"><a href="/?follow/">Follow us</a></p>')

    def test_phone_shows_lede_and_homepage_card_blurbs(self):
        blocks = re.findall(r"@media \(max-width:700px\)\{(.*?)\n\}", CSS, flags=re.S)
        hidden_lede = any(
            re.search(r"\.hero \.lede[^\{]*\{[^}]*display:none", block) or
            re.search(r"\.hero \.eyebrow,\.hero \.lede[^\{]*\{display:none", block)
            for block in blocks
        )
        self.assertFalse(hidden_lede, "phone CSS still hides .hero .lede")
        hidden_blurb = any(
            ".hub-card p:not(.hub-count){display:none}" in block
            or re.search(r"\.hub-art,\.hub-card p:not\(\.hub-count\)\{display:none", block)
            for block in blocks
        )
        self.assertFalse(hidden_blurb, "phone CSS still hides homepage card blurbs")
        self.assertIn(".hero .lede{font-size:1rem;line-height:1.45;margin:0 0 .85em}", CSS)

    def test_phone_footer_badges_center_when_wrapped(self):
        self.assertRegex(
            CSS,
            r"@media \(max-width:700px\)\{\s*\.clip\{[^}]+\}\s*\.foot-badge\{justify-content:center\}",
        )
        self.assertIn(".foot-badge img{width:150px;height:63px;", CSS)

    def test_no_third_party_font_links_in_pages(self):
        for path in (ROOT / "site").rglob("*.html"):
            text = path.read_text()
            self.assertNotIn("fonts.googleapis.com", text)
            self.assertNotIn("fonts.gstatic.com", text)


if __name__ == "__main__":
    unittest.main()
