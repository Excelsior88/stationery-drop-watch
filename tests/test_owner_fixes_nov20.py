"""Owner-approved fixes from Nov 20, 2026.

Dot grid specs, Nanami removed from the link-only list, Wonder Pens PREVIEW
titles that are actually sold out, and the 2027 calendar citations.
"""
import html
import json
import re
import unittest

import scripts.checker as checker
import scripts.build_site as site
import scripts.new_in_stock as new_in_stock

MIDNIGHT = "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-english-weeks-colors-midnight-blue"
SLASH = "https://wonderpens.ca/products/b-preview-b-hobonichi-2027-a6-hon-english-slash-navy"
WONDER_TAGS = [
    "Hobonichi", "Hobonichi 2027", "Paper: Agendas and Planners",
    "Paper: Hobonichi", "Paper: Notebooks/Notepads", "Planners 2027",
]


def shopify(title, available, tags):
    return {
        "title": title,
        "available": available,
        "tags": list(tags),
        "variants": [{"id": 48774502711541, "title": "Default Title", "available": available}],
    }


def row(status, at):
    return dict(store_id="wonder", store="Wonder Pens", label="Weeks · Colors: Midnight Blue",
                url=MIDNIGHT, status=status, checked_at=at, first_seen="2026-10-25T21:40:52+00:00",
                status_since="2026-10-25T21:40:52+00:00")


class WonderPensPreviewTests(unittest.TestCase):
    def test_sold_out_preview_with_out_of_stock_tag_is_sold_out(self):
        """The 30 Wonder Pens rows: PREVIEW stays in the title, and the product is tagged out-of-stock."""
        js = shopify("<b>PREVIEW</b> - Hobonichi 2027 - English Weeks - Colors: Midnight Blue",
                     False, WONDER_TAGS + ["out-of-stock"])
        status, avail, total, title = checker.classify_shopify(js)
        self.assertEqual(status, "sold_out")
        self.assertEqual(avail, 0)
        self.assertEqual(total, 1)
        self.assertNotIn("<b>", title)
        self.assertIn("PREVIEW", title)
        variant = checker.classify_shopify_variant(js, 48774502711541)
        self.assertEqual(variant[0], "sold_out")
        self.assertEqual(variant[1], 0)

    def test_available_preview_title_stays_in_stock(self):
        """A6 HON Slash Navy keeps PREVIEW in the title and is actually in stock."""
        js = shopify("<b>PREVIEW</b> - Hobonichi 2027 - A6 HON ENGLISH - Slash (Navy)", True, WONDER_TAGS)
        status, avail, _total, title = checker.classify_shopify(js)
        self.assertEqual(status, "in_stock")
        self.assertEqual(avail, 1)
        self.assertNotIn("<b>", title)
        self.assertEqual(checker.classify_shopify_variant(js, 48774502711541)[0], "in_stock")
        # Availability wins even if a stale out-of-stock tag is still on the product.
        tagged = shopify(js["title"], True, WONDER_TAGS + ["out-of-stock"])
        self.assertEqual(checker.classify_shopify(tagged)[0], "in_stock")

    def test_a_real_preview_and_coming_soon_wording_stay_not_yet_on_sale(self):
        preview = shopify("<b>PREVIEW</b> - Hobonichi 2027 - English Weeks - Colors: Sea Glass", False, [])
        self.assertEqual(checker.classify_shopify(preview)[0], "coming_soon")
        soon = shopify("Hobonichi Weeks 2027 coming soon", False, ["out-of-stock"])
        self.assertEqual(checker.classify_shopify(soon)[0], "coming_soon")
        starts = shopify("Hobonichi Weeks 2027", False, ["order starts March 1"])
        self.assertEqual(checker.classify_shopify(starts)[0], "coming_soon")
        plain = shopify("Hobonichi Techo Weeks 2027 - Colors: Sea Glass", False, ["Hobonichi"])
        self.assertEqual(checker.classify_shopify(plain)[0], "sold_out")

    def test_coming_soon_to_sold_out_is_logged_and_is_not_a_restock_alert(self):
        old = row("coming_soon", "2026-11-09T03:56:07+00:00")
        rec = row("sold_out", "2026-11-20T03:20:09+00:00")
        changes = checker.note_transition(old, rec, [])
        self.assertEqual(len(changes), 1)
        event = changes[0]
        self.assertEqual(event["from"], "coming_soon")
        self.assertEqual(event["to"], "sold_out")
        self.assertEqual(event["url"], MIDNIGHT)
        self.assertFalse(site.is_restock_event(event))
        self.assertEqual(new_in_stock.fresh_in_stock([], changes), [])
        self.assertEqual(new_in_stock.fresh_in_stock([], [event]), [])
        body = new_in_stock.webhook_body(new_in_stock.fresh_in_stock([], changes), "2026-11-20T03:20:10+00:00")
        self.assertEqual(body["changes"], [])
        # A later real restock still alerts. The sold-out correction must not have swallowed it.
        back = row("in_stock", "2026-11-21T03:20:09+00:00")
        restock = checker.note_transition(rec, back, [])
        self.assertEqual(restock[0]["from"], "sold_out")
        self.assertEqual(restock[0]["to"], "in_stock")
        self.assertTrue(site.is_restock_event(restock[0]))
        self.assertEqual(new_in_stock.fresh_in_stock([], restock), restock)
        launch = checker.note_transition(old, row("in_stock", "2026-11-21T04:00:00+00:00"), [])
        self.assertTrue(site.is_restock_event(launch[0]))
        self.assertEqual(launch[0]["from"], "coming_soon")


class GuideAndShopListTests(unittest.TestCase):
    def test_dot_grid_guide_specs_and_detroit_date(self):
        raw = site.build_dotgrid_guide()[1]
        doc = html.unescape(raw)
        self.assertIn("updated Nov 22, 2026", doc)
        self.assertIn("as of Nov 20, 2026", doc)
        self.assertNotIn("Nov 4, 2026", doc)
        self.assertNotIn("dimensions not listed", doc)
        self.assertNotIn("traveler's notebook", doc.lower())
        self.assertIn("a TN size", doc)
        self.assertIn("A5: 5.75 × 8.5 in (14.5 × 21 cm); B5: 7 × 10 in; B6: 5 × 7 in (from STM's size chart)", doc)
        self.assertIn("Not listed on the product page", doc)
        self.assertIn("B6 comes in 120gsm only", doc)
        self.assertIn("B5 (160gsm or 120gsm) and B6 (120gsm only)", doc)
        for size in ("Pocket (A6)", "Paperback (B6+)", "Medium (A5)", "Composition (B5)", "Master Slim (A4+)", "Master (A4+)"):
            self.assertIn(size, doc)
        blocks = [json.loads(html.unescape(b.replace("<\\/", "</")))
                  for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', raw)]
        art = next(b for b in blocks if b.get("@type") == "Article")
        self.assertEqual(art["datePublished"], "2026-11-04")
        self.assertEqual(art["dateModified"], site.guide_modified(site.build_dotgrid_guide))  # the visible "updated" day
        self.assertEqual(site.DG_GUIDE_LASTMOD, "2026-11-20")  # still the "specs as of" date in the page text

    def test_nanami_is_gone_and_jetpens_is_the_only_link_only_shop(self):
        self.assertEqual(site.link_only_clause(),
                         "JetPens is listed as a link only, because its site blocks automated checks.")
        pages = {
            "where": site.build_where_to_buy()[1],
            "tracker": site.build_hobo_tracker(),
            "home": site.build_index(),
            "about": site.build_about(),
            "calendar": site.build_hobonichi(),
        }
        for name, doc in pages.items():
            self.assertNotIn("nanami", doc.lower(), name)
            self.assertNotIn("nanamipaper.com", doc.lower(), name)
        where = pages["where"]
        self.assertIn("<h2>Shop we list but can't check</h2>", where)
        self.assertIn("Its site blocks automated checks, so we link to it without a status.", where)
        self.assertIn("https://www.jetpens.com/", where)
        self.assertNotIn("Shops we list but can't check", where)
        tracker = pages["tracker"]
        self.assertIn("Store we list but don't check automatically", tracker)
        self.assertIn("https://www.jetpens.com/", tracker)
        self.assertIn("JetPens is listed as a link only, because its site blocks automated checks.", pages["home"])

    def test_calendar_cites_atlas_and_the_sale_schedule(self):
        cal = site.build_hobonichi()
        self.assertIn("While some standard planners and accessories may be replenished, special or limited collaborations may only be available during the initial launch", cal)
        self.assertNotIn("core colors", cal)
        self.assertNotIn("Standard planner books", cal)
        hours = cal.split("each retail store opens at its own store hours", 1)[1].split("<br>", 1)[0]
        self.assertIn('href="#s-faq-schedule"', hours)
        self.assertNotIn("s-faq-retail", hours)
        self.assertNotIn("retail hours", hours)
        self.assertIn('href="#s-faq-release">[Hobonichi, release time]</a>', cal)
        self.assertIn("The 11:00 AM Japan time official Hobonichi Store online release time.", cal)
        self.assertNotIn("each store's opening hours", cal)
        self.assertIn("each retail store opening at its own hours.", cal)
        self.assertIn("https://www.1101.com/store/techo/en/faq/articles/4889938317854.html", cal)
        self.assertIn("https://www.1101.com/store/techo/en/faq/articles/4889935445534.html", cal)
