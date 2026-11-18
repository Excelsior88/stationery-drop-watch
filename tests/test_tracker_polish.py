"""Status-pill contrast, country-filter source, and no-JS / no-tracking checks for tracker polish."""
import re
import unittest
from pathlib import Path

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "site/assets/style.css").read_text()
JS = (ROOT / "site/assets/app.js").read_text()

# Ink on background for each status pill. Ratios are computed in this file, not copied from a note.
PILLS = {
    "in_stock": ("#14532d", "#dcfce7"),
    "preorder": ("#1e3a8a", "#dbeafe"),
    "coming_soon": ("#78350f", "#fef3c7"),
    "sold_out": ("#5c564f", "#f5f4f1"),
    "unknown": ("#475569", "#f8fafc"),
}


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


class StatusPillContrastTests(unittest.TestCase):
    def test_css_uses_the_documented_palette(self):
        for cls, (ink, fill) in PILLS.items():
            block = re.search(rf"\.badge\.{cls}\{{[^}}]*color:{ink}[^}}]+\}}", CSS).group(0)
            self.assertIn(f"background:{fill}", block, cls)

    def test_text_on_fill_meets_wcag_aa(self):
        # Normal text (badges are under 18pt / 14pt bold) needs 4.5:1.
        ratios = {cls: round(contrast_ratio(ink, fill), 2) for cls, (ink, fill) in PILLS.items()}
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


class CountryFilterSourceTests(unittest.TestCase):
    def test_region_map_comes_from_stores_json(self):
        self.assertEqual(set(site.REGION_NAME), {"US", "CA", "SG", "UK", "JP"})
        self.assertEqual(set(site.REGION.values()), {"US", "CA", "SG", "UK", "JP"})
        fixes = {"travelerscompanyusa": "US", "tokyopenshop": "US", "mdproductusa": "US"}
        for store in site.stores["stores"]:
            raw = (store.get("country") or "").split()[0] if (store.get("country") or "").split() else ""
            expected = fixes.get(store["id"], raw)
            self.assertEqual(site.REGION[store["id"]], expected, store["id"])
            self.assertIn(store["id"] in fixes or bool(raw), (True,), store["id"])

    def test_countries_present_accepts_a_one_shot_iterable(self):
        ids = (p["store_id"] for p in site.hobo_products())
        self.assertEqual(site.countries_present(ids), ["US", "CA", "SG", "UK", "JP"])

    def test_filter_omits_a_country_the_page_does_not_use(self):
        midori = site.countries_present(p["store_id"] for p in site.section_products("midori"))
        self.assertNotIn("SG", midori)
        self.assertNotIn("JP", midori)
        hobo = site.countries_present(p["store_id"] for p in site.hobo_products())
        self.assertEqual(hobo, ["US", "CA", "SG", "UK", "JP"])


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
