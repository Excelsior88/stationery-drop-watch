"""Homepage, shop, follow, and footer polish from the 17 Nov 2026 audit."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "site" / "assets" / "style.css").read_text()
HOME = (ROOT / "site" / "index.html").read_text()
SHOP = (ROOT / "site" / "shop" / "index.html").read_text()
FOLLOW = (ROOT / "site" / "follow" / "index.html").read_text()
PRIVACY = (ROOT / "site" / "privacy.html").read_text()
ABOUT = (ROOT / "site" / "about.html").read_text()


def _hub_card(html, name):
    m = re.search(
        rf'<li class="hub-card">.*?<h3>{re.escape(name)}</h3><p>(.*?)</p>',
        html,
        flags=re.S,
    )
    return m.group(1) if m else None


class AuditPolishTests(unittest.TestCase):
    def test_shop_cards_stretch_and_pin_cta(self):
        self.assertIn("align-items:stretch", CSS)
        self.assertIn(".shop-card{", CSS)
        self.assertRegex(CSS, r"\.shop-card\{[^}]*height:100%")
        self.assertIn(".shop-wide .shop-body{min-width:0;display:flex;flex-direction:column;height:100%}", CSS)
        self.assertIn(".shop-wide .shop-body .btn{margin-top:auto}", CSS)
        self.assertIn('class="shop-card"', SHOP)
        self.assertIn('class="shop-body"', SHOP)
        self.assertIn("View on Amazon", SHOP)

    def test_footer_follow_us_is_in_the_nav_row_and_not_underlined(self):
        foot = re.search(r'<nav class="foot-nav"[^>]*>(.*?)</nav>', HOME, flags=re.S)
        self.assertIsNotNone(foot)
        self.assertIn('href="/follow/"', foot.group(1))
        self.assertIn(">Follow us</a>", foot.group(1))
        self.assertNotIn('class="foot-follow"', HOME)
        self.assertRegex(CSS, r"\.foot-nav a(?:,\.foot-follow a)?\{[^}]*text-decoration:none")
        # Order: Shop, then Follow us, then About
        self.assertRegex(
            foot.group(1),
            r'href="/shop/">Shop</a><a href="/follow/">Follow us</a><a href="/about">About</a>',
        )

    def test_follow_page_centers_a_lone_last_card(self):
        self.assertIn(
            ".follow-list>li:last-child:nth-child(odd){grid-column:1/-1;justify-self:center;width:calc((100% - 16px) / 2)}",
            CSS,
        )
        # Seven follow cards, so the last one is odd and should be centered on desktop.
        n = FOLLOW.count('class="follow-card"')
        self.assertEqual(n, 7)

    def test_homepage_sold_out_everywhere_stays_together(self):
        self.assertIn('class="nobr" href="/sold-out-everywhere/"', HOME)
        self.assertIn(">Sold out everywhere</a>", HOME)
        self.assertIn(".nobr{white-space:nowrap}", CSS)

    def test_homepage_dotgrid_blurb_is_short_and_omits_official_store_detail(self):
        blurb = _hub_card(HOME, "Dot grid journals")
        self.assertIsNotNone(blurb)
        self.assertIn("Flagship notebooks from", blurb)
        self.assertIn("Archer and Olive", blurb)
        self.assertIn("Leuchtturm1917", blurb)
        self.assertIn("Scribbles That Matter", blurb)
        self.assertIn("Notebook Therapy", blurb)
        self.assertIn("Archer and Olive refills", blurb)
        self.assertNotIn("We check", blurb)
        self.assertNotIn("official", blurb.lower())
        self.assertNotIn("independent", blurb.lower())
        self.assertNotIn("own store", blurb)
        # Official-store detail remains on the dot-grid hub.
        hub = (ROOT / "site" / "archer-and-olive-dot-grid-journal" / "index.html").read_text()
        self.assertIn("official US store", hub)
        self.assertIn("own store", hub)
        self.assertIn("We check Archer and Olive", hub)

    def test_fonts_badges_and_privacy_claims_unchanged(self):
        self.assertIn('--sans:"Liberation Sans"', CSS)
        self.assertIn('--serif:"Newsreader"', CSS)
        self.assertIn("Zero cookies: this site sets no cookies", HOME)
        self.assertIn("Cloudflare Web Analytics", PRIVACY)
        self.assertIn("cookie-free page view counts", PRIVACY)
        # No untrue "no analytics / no tracking" claims while the cookieless beacon stays on.
        for doc, label in ((HOME, "home"), (PRIVACY, "privacy"), (ABOUT, "about"), (CSS, "css")):
            low = doc.lower()
            self.assertNotIn("no analytics", low, label)
            self.assertNotIn("without analytics", low, label)
            self.assertNotIn("no tracking", low, label)
            self.assertNotIn("no trackers", low, label)
        for cdn in ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net"):
            self.assertNotIn(cdn, HOME)
            self.assertNotIn(cdn, CSS)


if __name__ == "__main__":
    unittest.main()
