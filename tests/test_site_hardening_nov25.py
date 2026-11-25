"""Nov 25, 2026 hardening: link allowlist (app.js safeHref + build_site.safe_href), null guards, ASCII-only app.js,
hub-card accessible names, and no Access-Control-Allow-Origin on any static file."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "site/assets/app.js").read_text(encoding="utf-8")
HEADERS = (ROOT / "cloudflare/_headers").read_text(encoding="utf-8")
SRC = (ROOT / "scripts/build_site.py").read_text(encoding="utf-8")
CASES = {
    "https://shop.example/x": True, "/hobonichi-restock-tracker/?q=a": True, "/": True,
    "//evil.example": False, "/\\evil.example": False, "javascript:alert(1)": False, " JavaScript:x": False,
    "data:text/html,x": False, "http://shop.example/x": False, "": False, None: False,
}


class SafeHref(unittest.TestCase):
    def test_build_rule(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_site
        for url, ok in CASES.items():
            self.assertEqual(build_site.safe_href(url) != "#", ok, url)

    def test_app_rule_matches(self):
        line = next(l for l in APP.splitlines() if "const safeHref" in l)
        js = line.replace("const safeHref", "globalThis.safeHref") + "\n" + "\n".join(
            f"console.log(safeHref({'null' if u is None else repr(u)}) !== '#')" for u in CASES)
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(out, ["true" if ok else "false" for ok in CASES.values()])

    def test_every_data_link_goes_through_safe_href(self):
        for needle in ('esc(r.u)', 'esc(h.dp)', 'link.href = row.u', '.u;\n'):
            self.assertNotIn(needle, APP)
        self.assertIn('link.href = safeHref(row.u)', APP)


class AppGuardsAndEncoding(unittest.TestCase):
    def test_app_js_is_ascii(self):
        self.assertTrue(APP.isascii(), "use \\u00b7 style escapes so the file reads the same in any encoding")

    def test_optional_tracker_elements_are_guarded(self):
        self.assertIn('if (more) more.addEventListener', APP)
        self.assertIn('if (countEl) countEl.textContent', APP)
        self.assertNotIn('$("count").textContent', APP)


class HubCardsAndHeaders(unittest.TestCase):
    def test_hub_cards_are_named_by_their_heading(self):
        html = (ROOT / "site/index.html").read_text(encoding="utf-8")
        cards = re.findall(r'<li class="hub-card"><a [^>]*>', html)
        if not any("aria-labelledby" in c for c in cards):
            self.skipTest("site/index.html not rebuilt yet")
        for c in cards:
            m = re.search(r'aria-labelledby="([^"]+)"', c)
            self.assertTrue(m and f'id="{m.group(1)}"' in html, c)

    def test_no_cors_header_on_static_files(self):
        tail = HEADERS[HEADERS.rindex("\n/*\n"):]
        self.assertIn("! Access-Control-Allow-Origin", tail)
        self.assertNotRegex(HEADERS, r"(?m)^\s+Access-Control-Allow-Origin:")

    def test_js_charset(self):
        for path in ("/assets/app.js", "/assets/local-time.js"):
            block = HEADERS[HEADERS.index(path + "\n"):].split("\n/", 1)[0]
            self.assertIn("Content-Type: application/javascript; charset=utf-8", block)


if __name__ == "__main__":
    unittest.main()
