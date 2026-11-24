"""Header landmarks, Turnstile widget size, and Cloudflare Pages headers.

The header wrapper is a div. The desktop bar and the mobile menu are separate
nav landmarks, so a page never nests one nav inside another. Signup widgets
use Turnstile's flexible size. cloudflare/_headers adds a report-only content
security policy, a permissions policy, and a 30-day font cache.
"""
import base64
import hashlib
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402

CSP = (
    "default-src 'self'; script-src 'self' https://challenges.cloudflare.com https://static.cloudflareinsights.com 'unsafe-hashes' 'sha256-GZIcz60Uwd6wT3vaYke/atSr53TehbYAPepOa3d03Vw='; "
    "style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self'; font-src 'self'; "
    "connect-src 'self'; frame-src https://challenges.cloudflare.com; object-src 'none'; "
    "base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class NavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.open_tags = []
        self.nested = 0
        self.navs = []

    def handle_starttag(self, tag, attrs):
        if tag == "nav":
            if "nav" in self.open_tags:
                self.nested += 1
            self.navs.append(dict(attrs))
        if tag not in VOID:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in self.open_tags:
            while self.open_tags:
                if self.open_tags.pop() == tag:
                    break


def sample_pages():
    pages = [
        ("index.html", site.build_index()),
        (site.HOBO_TRACKER, site.build_hobo_tracker()),
        ("about/", site.build_about()),
        ("privacy/", site.build_privacy()),
        ("transparency/", site.build_transparency()),
        site.build_shop(),
        site.build_guides_index(),
        site.build_vs(),
        site.build_group(site.GROUPS[0]),
        site.build_design(site.DESIGNS[0]),
    ]
    return pages


class HeaderLandmarkTests(unittest.TestCase):
    def test_no_nested_navs_and_distinct_labels(self):
        for path, doc in sample_pages():
            parser = NavParser()
            parser.feed(doc)
            self.assertEqual(parser.nested, 0, path)
            labels = [n.get("aria-label") for n in parser.navs]
            self.assertEqual(labels.count("Main"), 1, (path, labels))
            self.assertEqual(labels.count("Menu"), 1, (path, labels))
            self.assertIn("Footer", labels, path)
            self.assertEqual(len(labels), len(set(labels)), (path, labels))
            bar = next(n for n in parser.navs if n.get("aria-label") == "Main")
            menu = next(n for n in parser.navs if n.get("aria-label") == "Menu")
            self.assertIn("site-nav-bar", bar.get("class", ""))
            self.assertIn("site-nav-panel", menu.get("class", ""))
            self.assertIn('<div class="site-nav"><nav class="site-nav site-nav-bar" aria-label="Main">', doc)
            self.assertNotIn('<nav class="site-nav" aria-label="Main">', doc)
            self.assertEqual(len(re.findall(r"<nav\b", doc)), len(parser.navs), path)


class TurnstileWidgetTests(unittest.TestCase):
    def test_every_widget_is_flexible(self):
        doc = site.signup()
        widgets = re.findall(r'<div class="cf-turnstile"[^>]*>', doc)
        self.assertEqual(len(widgets), 1)
        self.assertIn('data-size="flexible"', widgets[0])
        saw = False
        for path, page in sample_pages():
            found = re.findall(r'<div class="cf-turnstile"[^>]*>', page)
            if path in ("index.html", "about/", "shop/"):
                self.assertTrue(found, path)
            if found:
                saw = True
            self.assertTrue(all('data-size="flexible"' in w for w in found), (path, found))
        self.assertTrue(saw)


class CloudflareHeadersTests(unittest.TestCase):
    def setUp(self):
        self.headers = (ROOT / "cloudflare" / "_headers").read_text()

    def test_report_only_policy_permissions_and_font_cache(self):
        self.assertIn(f"Content-Security-Policy-Report-Only: {CSP}", self.headers)
        csp_line = next(line for line in self.headers.splitlines() if "Content-Security-Policy-Report-Only:" in line)
        self.assertIn("https://static.cloudflareinsights.com", csp_line)
        self.assertNotIn("https://cloudflareinsights.com", csp_line)
        self.assertIn("connect-src 'self'", csp_line)
        self.assertIn("Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()", self.headers)
        font = self.headers.split("/assets/fonts/*", 1)[1].split("/assets/", 1)[0]
        self.assertIn("Cache-Control: public, max-age=2592000", font)
        self.assertNotIn("immutable", font)
        self.assertIn("Strict-Transport-Security: max-age=31536000\n", self.headers)
        self.assertNotIn("includeSubDomains", self.headers)
        # The only Access-Control-Allow-Origin line detaches Pages' default "*" from the public stock feed (Nov 24, 2026).
        acao = [line.strip() for line in self.headers.splitlines() if "Access-Control-Allow-Origin" in line and not line.lstrip().startswith("#")]
        self.assertEqual(acao, ["! Access-Control-Allow-Origin"])
        self.assertNotIn("s-maxage", self.headers)
        handler = b"return false"
        digest = base64.b64encode(hashlib.sha256(handler).digest()).decode()
        self.assertIn(f"'sha256-{digest}'", csp_line)
        self.assertIn('onsubmit="return false"', (ROOT / "scripts" / "build_site.py").read_text())

    def test_subscribe_fallback_is_not_given_this_policy(self):
        src = (ROOT / "site/functions/api/subscribe.js").read_text()
        self.assertIn("<style>", src)
        self.assertNotIn("Content-Security-Policy", src)


if __name__ == "__main__":
    unittest.main()
