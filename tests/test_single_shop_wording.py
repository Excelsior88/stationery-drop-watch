"""Design-page wording when only one shop carries the item, versus several shops.

Single-shop pages used to say "Yes, at 1 of 1 shop", "In each shop's own words" and "1 of 1 shop checked".
Each case is built from the real page builder with the listings' statuses patched, so the visible FAQ and
the FAQPage JSON-LD (both made from the same answers) are checked together."""
import json
import re
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402


def design(slug):
    return next(d for d in site.DESIGNS if d["slug"] == slug)


@contextmanager
def statuses(listings, values):
    """Temporarily set each listing's status (values cycle if shorter than listings)."""
    old = [l["status"] for l in listings]
    try:
        for i, l in enumerate(listings):
            l["status"] = values[i % len(values)]
        yield
    finally:
        for l, s in zip(listings, old):
            l["status"] = s


def faq_answers(doc):
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', doc, re.S):
        data = json.loads(block)
        if data.get("@type") == "FAQPage":
            return [q["acceptedAnswer"]["text"] for q in data["mainEntity"]]
    raise AssertionError("no FAQPage JSON-LD")


def hero_line(doc):
    return re.search(r'<p class="muted small hero-check">(.*?)</p>', doc, re.S).group(1)


class SingleShopWording(unittest.TestCase):
    def single(self):
        d = design("archer-and-olive-storybook-navy")
        ls = site.design_listings(d)
        self.assertEqual(len({l["store_id"] for l in ls}), 1, "fixture should be a one-shop design")
        return d, ls

    def multi(self):
        d = design("starlight")
        ls = site.design_listings(d)
        self.assertGreater(len({l["store_id"] for l in ls}), 1, "fixture should be a multi-shop design")
        return d, ls

    def test_single_shop_in_stock(self):
        d, ls = self.single()
        with statuses(ls, ["in_stock", "sold_out"]):
            _, doc = site.build_design(d)
        a = faq_answers(doc)
        self.assertTrue(a[0].startswith("Yes, in stock at Archer and Olive (official) at the last check ("), a[0])
        self.assertIn("In the shop's own words:", a[1])
        self.assertNotIn("1 of 1 shop", doc)
        self.assertNotIn("each shop's own words", doc)
        self.assertNotIn("each shop&#x27;s own words", doc)
        self.assertIn("1 shop checked", hero_line(doc))
        self.assertIn("In the shop&#x27;s own words:", doc)  # the visible FAQ matches the JSON-LD

    def test_single_shop_preorder_only(self):
        d, ls = self.single()
        with statuses(ls, ["preorder", "sold_out"]):
            _, doc = site.build_design(d)
        self.assertTrue(faq_answers(doc)[0].startswith("Yes, on preorder at Archer and Olive (official)"))

    def test_single_shop_sold_out(self):
        d, ls = self.single()
        with statuses(ls, ["sold_out"]):
            _, doc = site.build_design(d)
        a0 = faq_answers(doc)[0]
        self.assertTrue(a0.startswith("No. At the last check ("), a0)
        self.assertIn("Archer and Olive (official) didn't have it in stock or on preorder.", a0)

    def test_single_shop_partly_unchecked_says_so(self):
        d, ls = self.single()
        with statuses(ls, ["unknown", "in_stock", "sold_out"]):
            _, doc = site.build_design(d)
        a0 = faq_answers(doc)[0]
        n = sum(1 for i in range(len(ls)) if i % 3 == 0)
        self.assertIn(f"We couldn't check {n} listing{'s' if n != 1 else ''} at Archer and Olive (official) this run", a0)
        self.assertIn("1 shop checked", hero_line(doc))

    def test_single_shop_check_failed_is_honest(self):
        d, ls = self.single()
        with statuses(ls, ["unknown"]):
            _, doc = site.build_design(d)
        self.assertIn("the one shop we track couldn't be checked this run", hero_line(doc).replace("&#x27;", "'"))
        self.assertNotIn("1 shop checked", hero_line(doc))
        self.assertTrue(faq_answers(doc)[0].startswith("We don't know."))

    def test_multi_shop_wording_unchanged(self):
        d, ls = self.multi()
        n = len({l["store_id"] for l in ls})
        with statuses(ls, ["in_stock", "sold_out"]):
            _, doc = site.build_design(d)
        a = faq_answers(doc)
        self.assertRegex(a[0], r"^Yes, at \d+ of \d+ shops at the last check \(")
        self.assertIn("In each shop's own words:", a[1])
        self.assertIn(f"of {n} shops checked", hero_line(doc))

    def test_phrase_helper(self):
        self.assertEqual(site.shops_checked_phrase({"a"}, {"a"}), "1 shop checked")
        self.assertEqual(site.shops_checked_phrase({"a"}, set()), "the one shop we track couldn't be checked this run")
        self.assertEqual(site.shops_checked_phrase({"a", "b"}, {"a"}), "1 of 2 shops checked")
        self.assertEqual(site.shops_checked_phrase({"a", "b"}, {"a", "b"}), "2 of 2 shops checked")


class WhereToBuyLinkOnly(unittest.TestCase):
    """The "Where can I buy" answer names the link-only shops shown in the table above it."""

    def where_answer(self, doc):
        return faq_answers(doc)[2]

    def find_design(self, n_link_shops):
        for d in site.DESIGNS:
            if not site.design_listings(d):
                continue
            lo = {l["store"] for l in site.link_listings(d["match"])}
            if (len(lo) == 1) if n_link_shops == 1 else (len(lo) >= n_link_shops):
                return d, sorted(lo)
        self.skipTest("no design with that many link-only shops in this data")

    def test_one_link_only_shop(self):
        d, lo = self.find_design(1)
        _, doc = site.build_design(d)
        a = self.where_answer(doc)
        self.assertTrue(a.endswith(f" We also link to {lo[0]} (link only, so check stock on the shop's page)."), a)
        self.assertIn(site.E(f"We also link to {lo[0]} (link only, so check stock on the shop's page)."), doc)  # visible FAQ

    def test_several_link_only_shops(self):
        d, lo = self.find_design(2)
        _, doc = site.build_design(d)
        who = ", ".join(lo[:-1]) + " and " + lo[-1]
        self.assertTrue(self.where_answer(doc).endswith(f" We also link to {who} (links only, so check stock on each shop's page)."))

    def test_no_link_only_shops_no_sentence(self):
        d = next(d for d in site.DESIGNS if site.design_listings(d) and not site.link_listings(d["match"]))
        _, doc = site.build_design(d)
        self.assertNotIn("We also link to", doc)
        self.assertTrue(self.where_answer(doc).endswith("Each name in the table above opens that shop's own listing."))


class CardTally(unittest.TestCase):
    """Per-item cards on the Hobonichi tracker (shop_tally)."""

    def rows(self, *specs):
        return [dict(st=st, sid=sid, s=name, g="x", gn="x", u="u") for st, sid, name in specs]

    def test_one_shop_not_in_stock(self):
        self.assertEqual(site.shop_tally(self.rows(("sold_out", "1101", "Hobonichi Online Store (official)"))),
                         "Not in stock at Hobonichi Online Store (official)")

    def test_one_shop_in_stock_with_link_only(self):
        self.assertEqual(site.shop_tally(self.rows(("in_stock", "a", "Shop A"), ("link_only", "blesket", "Blesket Canada"))),
                         "In stock at Shop A · 1 shop link only")

    def test_one_shop_several_listings_keeps_count(self):
        self.assertEqual(site.shop_tally(self.rows(("in_stock", "a", "Shop A"), ("sold_out", "a", "Shop A"))),
                         "In stock at Shop A · 1 of 2 listings in stock")

    def test_one_shop_unchecked(self):
        self.assertEqual(site.shop_tally(self.rows(("unknown", "a", "Shop A"))), "Couldn't check Shop A this run")

    def test_multi_shop_unchanged(self):
        self.assertEqual(site.shop_tally(self.rows(("in_stock", "a", "A"), ("sold_out", "b", "B"), ("link_only", "c", "C"))),
                         "1 of 2 listings in stock · 1 of 2 shops in stock · 1 shop link only")

    def test_built_tracker_has_no_n_of_1_shop(self):
        self.assertNotIn(" of 1 shop in stock", site.build_hobo_tracker())


if __name__ == "__main__":
    unittest.main()
