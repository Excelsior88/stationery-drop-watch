"""Privacy, terms, signup agreement, and the Cloudflare Web Analytics CSP allowlist.

Report-only CSP allows the edge-injected beacon host. Automatic Web Analytics
reports to same-origin /cdn-cgi/rum, so connect-src stays 'self'.
"""
import html
import re
import unittest
from pathlib import Path

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(r"midori|traveler'?s company|designphil|bullet journal", re.I)
AGREE = (
    'By signing up, you agree to our <a href="/terms/">Terms</a> '
    "(personal use only, no reselling or bots) and "
    '<a href="/privacy/">Privacy notice</a>.'
)


def visible(doc):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", doc)).split())


def article(doc):
    return doc.split("<article", 1)[1].split("</article>", 1)[0]


class CspHeaderTests(unittest.TestCase):
    def setUp(self):
        self.headers = (ROOT / "cloudflare" / "_headers").read_text()
        self.csp = next(line.strip() for line in self.headers.splitlines()
                        if line.strip().startswith("Content-Security-Policy:"))

    def test_beacon_script_host_and_tight_connect_src(self):
        script = re.search(r"script-src [^;]+", self.csp).group(0)
        connect = re.search(r"connect-src [^;]+", self.csp).group(0)
        self.assertIn("https://static.cloudflareinsights.com", script)
        self.assertNotIn("https://cloudflareinsights.com", self.csp)
        self.assertEqual(connect, "connect-src 'self'")
        self.assertIn("https://challenges.cloudflare.com", script)
        self.assertIn("'sha256-GZIcz60Uwd6wT3vaYke/atSr53TehbYAPepOa3d03Vw='", script)

    def test_existing_security_and_cache_headers_stay(self):
        self.assertIn("Strict-Transport-Security: max-age=31536000", self.headers)
        self.assertNotIn("includeSubDomains", self.headers)
        self.assertIn("X-Frame-Options: SAMEORIGIN", self.headers)
        self.assertIn("Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()", self.headers)
        rules = {}
        current = None
        for line in self.headers.splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if not line[:1].isspace():
                current = line.strip()
            elif current and "Cache-Control:" in line:
                rules[current] = line.strip()
        self.assertEqual(rules["/assets/fonts/*"], "Cache-Control: public, max-age=2592000")
        self.assertNotIn("immutable", rules["/assets/fonts/*"])
        self.assertNotIn("/data/search-index.json", rules)
        self.assertNotIn("data/search-index.json", rules)
        self.assertIn("Cache-Control: public, max-age=31536000, immutable", rules["/assets/style.css"])


class PrivacyCopyTests(unittest.TestCase):
    def setUp(self):
        self.doc = site.build_privacy()
        self.text = visible(self.doc)

    def test_hosting_analytics_and_required_disclosures(self):
        self.assertIn("updated Nov 23, 2026", self.text)
        self.assertIn("The site is hosted on Cloudflare Pages.", self.text)
        self.assertNotIn("GitHub Pages", self.text)
        self.assertNotIn("backup copy", self.text)
        self.assertNotIn("hosted on GitHub", self.text)
        self.assertIn("cookie-free", self.text)
        self.assertIn("static.cloudflareinsights.com", self.text)
        self.assertIn("/cdn-cgi/rum", self.text)
        self.assertIn("does not track individual end users across its customers", self.text)
        self.assertIn("click.kit-mail3.com", self.text)
        self.assertIn("standard open pixel", self.text)
        self.assertIn("whether restock alerts are read", self.text)
        self.assertIn("clean out inactive addresses", self.text)
        self.assertIn("email delivery stats", self.text)
        self.assertIn("sets no cookies and runs no ad trackers", self.text)
        self.assertIn("After December 8, 2026, when the move from Buttondown to Kit finishes, we will delete the old Buttondown subscriber list.", self.text)
        self.assertIn("Clicking unsubscribe stops future alerts by placing your address on a suppression list so we don't re-email you, whereas emailing admin@stationerydropwatch.com permanently deletes your record.", self.text)
        self.assertIn("We never sell, rent, or share subscriber emails.", self.text)
        self.assertIn("Alerts run on your consent", self.text)
        self.assertIn("request access, export, or permanent deletion", self.text)
        self.assertIn("Data is processed in the United States.", self.text)
        self.assertIn("The site and alerts are for people 13 and older.", self.text)
        self.assertIn("If a child under 13 signed up, email admin@stationerydropwatch.com and we will delete it.", self.text)
        self.assertIn("We don't use affiliate links on Stationery Drop Watch.", self.text)

    def test_no_inline_handlers_styles_or_forbidden_terms(self):
        assert_clean(self.doc)


class TermsPageStructureTests(unittest.TestCase):
    def setUp(self):
        self.doc = site.build_terms()
        self.body = article(self.doc)

    def test_twenty_one_anchors_and_collapsed_jump_menu(self):
        headings = re.findall(r'<h2 id="([^"]+)">(\d+)\. ([^<]+)</h2>', self.body)
        self.assertEqual(len(headings), 21)
        ids = [slug for slug, _n, _title in headings]
        self.assertEqual(len(set(ids)), 21)
        self.assertEqual([n for _slug, n, _title in headings], [str(i) for i in range(1, 22)])
        self.assertIn("prohibited-uses", ids)
        self.assertEqual(ids, [slug for slug, _title in site.TERMS_SECTIONS])
        opening = re.search(r"<details class=\"terms-jump\"[^>]*>", self.body)
        self.assertIsNotNone(opening)
        self.assertNotIn("open", opening.group(0))
        links = re.findall(r'<details class="terms-jump">.*?<ol>(.*?)</ol>', self.body, re.S)[0]
        hrefs = re.findall(r'<a href="#([^"]+)">', links)
        self.assertEqual(hrefs, ids)
        self.assertEqual(len(re.findall(r"<details class=\"terms-jump\"", self.body)), 1)

    def test_sections_13_and_14_are_callouts_without_shouting(self):
        callouts = re.findall(r'<section class="terms-callout">(.*?)</section>', self.body, re.S)
        self.assertEqual(len(callouts), 2)
        self.assertIn('id="disclaimer-of-warranties"', callouts[0])
        self.assertIn('id="limitation-of-liability"', callouts[1])
        self.assertIn("<strong>The Service is provided \"as is\" and \"as available\".</strong>", callouts[0])
        self.assertIn("<strong>our total liability for any claim arising from or related to the Service is limited to fifty US dollars (US$50)</strong>", callouts[1])
        joined = " ".join(callouts)
        self.assertNotIn("style=", joined)
        self.assertNotRegex(joined, r"\son[a-z]+=", re.I)
        letters = re.sub(r"[^A-Za-z]", "", visible(joined))
        self.assertNotEqual(letters, letters.upper())
        self.assertNotIn("AS IS", visible(joined))
        css = (ROOT / "site/assets/style.css").read_text()
        block = css.split("/* Terms:", 1)[1]
        self.assertIn(".terms-callout{", block)
        self.assertIn(".terms-jump{", block)
        self.assertNotIn("text-transform", block)
        self.assertNotIn("uppercase", block)

    def test_section_anchors_clear_the_sticky_masthead(self):
        css = (ROOT / "site/assets/style.css").read_text()
        block = css.split("/* Terms:", 1)[1]
        desktop = block.split("@media (max-width:900px)", 1)[0]
        self.assertIn(".prose h2[id]{scroll-margin-top:8.5rem}", desktop)
        self.assertNotIn("scroll-margin-top:5.5rem", desktop)
        self.assertIn("@media (max-width:900px){.prose h2[id]{scroll-margin-top:5.5rem}}", block)
        self.assertIn("@media (max-width:900px){\n  .masthead .wrap{flex-wrap:nowrap", css)

    def test_prohibited_uses_is_linked_from_the_homepage_faq_and_robots(self):
        home = site.build_index()
        self.assertIn('href="/terms/#prohibited-uses"', home)
        self.assertIn("Can I use alerts for reselling?", home)
        target = "https://stationerydropwatch.com/terms/#prohibited-uses"
        self.assertIn(target, site.ROBOTS)
        self.assertEqual((ROOT / "site/robots.txt").read_text(), site.ROBOTS)
        self.assertNotIn("https://stationerydropwatch.com/terms/\n", site.ROBOTS)

    def test_no_inline_handlers_styles_or_forbidden_terms(self):
        assert_clean(self.doc)


class SignupAgreementTests(unittest.TestCase):
    def test_notify_me_agreement_links_terms_and_privacy(self):
        home = site.build_index()
        notes = re.findall(r'class="strip-agree">(.*?)</p>', home)
        self.assertGreaterEqual(len(notes), 1)
        for note in notes:
            self.assertEqual(note, AGREE)
            self.assertNotRegex(note, r"\son[a-z]+=", re.I)
            self.assertNotIn("style=", note)
        box = site.signup()
        self.assertIn('href="terms/"', box)
        self.assertIn('href="privacy/"', box)
        self.assertIn("By signing up, you agree to our", box)
        assert_clean(box, allow_external_scripts=False)


def assert_clean(doc, allow_external_scripts=True):
    """New pages stay free of inline handlers, inline styles, and forbidden brand terms."""
    if "<body" in doc:
        body = doc.split("<body", 1)[1]
    else:
        body = doc
    assert not re.search(r"\son[a-z]+=", body, re.I), body[:200]
    assert "style=" not in body
    assert "<style" not in body.lower()
    if allow_external_scripts:
        for attrs, inner in re.findall(r"<script\b([^>]*)>(.*?)</script>", doc, re.S | re.I):
            if "application/ld+json" in attrs:
                continue
            assert " src=" in attrs
            assert inner.strip() == ""
    else:
        assert "<script" not in doc.lower()
    assert not FORBIDDEN.search(visible(doc))


if __name__ == "__main__":
    unittest.main()
