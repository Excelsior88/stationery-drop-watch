"""Status-color contrast, country-filter source, and no-JS / no-tracking checks for tracker polish."""
import re
import unittest
from pathlib import Path

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "site/assets/style.css").read_text()
JS = (ROOT / "site/assets/app.js").read_text()

# Ink, fill, and border for each status. Ratios are computed in this file, not copied from a note.
PILLS = {
    "in_stock": ("#14532d", "#dcfce7", "#bbf7d0"),
    "preorder": ("#1e3a8a", "#dbeafe", "#bfdbfe"),
    "coming_soon": ("#78350f", "#fef3c7", "#fde68a"),
    "sold_out": ("#5c564f", "#f5f4f1", "#e4dfd7"),
    "unknown": ("#475569", "#f8fafc", "#cbd5e1"),
}
ST_VAR = {
    "in_stock": "instock",
    "preorder": "preorder",
    "coming_soon": "coming",
    "sold_out": "soldout",
    "unknown": "unknown",
}
CARD_BG = "#fffdf8"  # --card, the stat-box background
PAPER_2 = "#f4ecdc"  # --paper-2, sold/past restock row background
# Old status colors that must not remain on pills, stat numbers, or restock accents.
OLD_STATUS = ("#2f6b45", "#5d3f73", "#80601a", "#9b3434", "#e7f2ea", "#f0e9f5",
              "#fbf1d8", "#f9e6e4", "#bcd9c5", "#d8c6e5", "#ecd59a", "#ebc0bb",
              "#e0c8c4")


def _srgb_lin(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color):
    hx = hex_color.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return 0.2126 * _srgb_lin(r) + 0.7152 * _srgb_lin(g) + 0.0722 * _srgb_lin(b)


def contrast_ratio(fg, bg):
    lighter, darker = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def css_var(name):
    m = re.search(rf"{re.escape(name)}:([#][0-9a-fA-F]{{3,8}})", CSS)
    assert m, f"missing {name}"
    return m.group(1)


class StatusPaletteTests(unittest.TestCase):
    def test_css_variables_match_the_documented_palette(self):
        for cls, (ink, fill, line) in PILLS.items():
            token = ST_VAR[cls]
            self.assertEqual(css_var(f"--st-{token}"), ink, cls)
            self.assertEqual(css_var(f"--st-{token}-bg"), fill, cls)
            self.assertEqual(css_var(f"--st-{token}-line"), line, cls)

    def test_pills_stats_and_restock_rows_use_the_shared_variables(self):
        for cls, token in ST_VAR.items():
            block = re.search(
                rf"\.badge\.{cls}\{{[^}}]*color:var\(--st-{token}\)[^}}]+\}}", CSS
            ).group(0)
            self.assertIn(f"color:var(--st-{token})", block, cls)
            self.assertIn(f"background:var(--st-{token}-bg)", block, cls)
            self.assertIn(f"border-color:var(--st-{token}-line)", block, cls)

        stats = re.search(r"\.stats div:nth-child\(1\) b\{[^}]+\}.*?\.stats div\.unk b\{[^}]+\}", CSS, re.S).group(0)
        self.assertIn("color:var(--st-instock)", stats)
        self.assertIn("color:var(--st-preorder)", stats)
        self.assertIn("color:var(--st-soldout)", stats)
        self.assertIn("color:var(--st-coming)", stats)
        self.assertIn("color:var(--st-unknown)", stats)
        for old in ("var(--sage)", "var(--plum)", "var(--rose)", "var(--mustard)", "var(--ink-2)"):
            self.assertNotIn(old, stats, old)

        self.assertIn('.feed-item[data-now="in_stock"]{border-left:4px solid var(--st-instock)}', CSS)
        self.assertIn('.feed-item[data-now="preorder"]{border-left:4px solid var(--st-preorder)}', CSS)
        self.assertIn('.feed-item[data-now="coming_soon"]{border-left:4px solid var(--st-coming)}', CSS)
        self.assertIn('.feed-item[data-now="unknown"]{border-left:4px solid var(--st-unknown)}', CSS)
        self.assertIn('.feed-item[data-now="sold_out"]{border-color:var(--st-soldout-line);border-left:4px solid var(--st-soldout)}', CSS)
        self.assertIn('.feed-item[data-now="sold_out"] .feed-when{color:var(--st-soldout)}', CSS)

    def test_old_status_colors_are_gone_from_status_rules(self):
        status_css = "".join(re.findall(
            r"\.badge\.(?:in_stock|preorder|coming_soon|sold_out|unknown)[^{]*\{[^}]+\}"
            r"|\.stats div:nth-child\([^}]+\}"
            r"|\.stats div\.unk b\{[^}]+\}"
            r"|\.feed-item\[data-now=[^]]+\][^{]*\{[^}]+\}",
            CSS,
        ))
        for hex_color in OLD_STATUS:
            self.assertNotIn(hex_color, status_css, hex_color)
            self.assertNotIn(hex_color, CSS, hex_color)
        # Brand tokens may still exist for non-status decoration, but status rules must not use them.
        for token in ("var(--sage)", "var(--plum)", "var(--rose)", "var(--mustard)"):
            self.assertNotIn(token, status_css, token)

    def test_text_on_fill_meets_wcag_aa(self):
        # Normal text (badges are under 18pt / 14pt bold) needs 4.5:1.
        ratios = {cls: round(contrast_ratio(ink, fill), 2) for cls, (ink, fill, _line) in PILLS.items()}
        for cls, ratio in ratios.items():
            self.assertGreaterEqual(ratio, 4.5, f"{cls} is {ratio}:1")
        # Keep the computed figures in the failure message if a color later regresses.
        self.assertEqual(ratios, {
            "in_stock": 8.3,
            "preorder": 8.49,
            "coming_soon": 8.15,
            "sold_out": 6.59,
            "unknown": 7.24,
        })

    def test_stat_numbers_and_sold_row_text_meet_wcag_aa(self):
        # Stat numbers sit on --card; sold restock "when" text sits on --paper-2.
        # Both pass the 4.5:1 normal-text bar (numbers are also large text).
        card = {cls: round(contrast_ratio(ink, CARD_BG), 2) for cls, (ink, _f, _l) in PILLS.items()}
        paper = {cls: round(contrast_ratio(ink, PAPER_2), 2) for cls, (ink, _f, _l) in PILLS.items()}
        for cls, ratio in card.items():
            self.assertGreaterEqual(ratio, 4.5, f"{cls} on card is {ratio}:1")
        for cls, ratio in paper.items():
            self.assertGreaterEqual(ratio, 4.5, f"{cls} on paper-2 is {ratio}:1")
        self.assertEqual(card, {
            "in_stock": 8.96,
            "preorder": 10.19,
            "coming_soon": 8.92,
            "sold_out": 7.13,
            "unknown": 7.45,
        })
        self.assertEqual(paper, {
            "in_stock": 7.76,
            "preorder": 8.82,
            "coming_soon": 7.72,
            "sold_out": 6.17,
            "unknown": 6.45,
        })


class CountryFilterSourceTests(unittest.TestCase):
    def test_region_map_comes_from_stores_json(self):
        self.assertEqual(set(site.REGION_NAME), {"US", "CA", "SG", "UK", "AU", "JP"})
        self.assertEqual(set(site.REGION.values()), {"US", "CA", "SG", "UK", "AU", "JP"})
        fixes = {}
        for store in site.stores["stores"]:
            raw = (store.get("country") or "").split()[0] if (store.get("country") or "").split() else ""
            expected = fixes.get(store["id"], raw)
            self.assertEqual(site.REGION[store["id"]], expected, store["id"])
            self.assertIn(store["id"] in fixes or bool(raw), (True,), store["id"])

    def test_countries_present_accepts_a_one_shot_iterable(self):
        ids = (p["store_id"] for p in site.hobo_products())
        self.assertEqual(site.countries_present(ids), ["US", "CA", "SG", "UK", "AU", "JP"])

    def test_filter_omits_a_country_the_page_does_not_use(self):
        dot = site.countries_present(p["store_id"] for p in site.section_products("dotgrid"))
        self.assertNotIn("SG", dot)
        self.assertNotIn("JP", dot)
        hobo = site.countries_present(p["store_id"] for p in site.hobo_products())
        self.assertEqual(hobo, ["US", "CA", "SG", "UK", "AU", "JP"])


class NoTrackingTests(unittest.TestCase):
    def test_new_filter_js_does_not_store_or_call_out(self):
        for needle in ("localStorage", "sessionStorage", "document.cookie", "indexedDB", "fonts.googleapis", "gtag", "analytics"):
            self.assertNotIn(needle, JS, needle)
            self.assertNotIn(needle, CSS, needle)

    def test_site_css_does_not_request_external_fonts(self):
        self.assertNotIn("fonts.google", CSS)
        self.assertNotIn("@import", CSS)


if __name__ == "__main__":
    unittest.main()
