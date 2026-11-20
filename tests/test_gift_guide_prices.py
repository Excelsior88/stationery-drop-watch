"""Gift guide price column: every shop price comes from the checker's data for that run, never typed in.

The checker records a Shopify listing's price only when the shop sells in USD (its /meta.json says so).
The guide shows the lowest recorded price among shops that had the pick in stock or on preorder, and
says so plainly when there is no price. The Etsy sale line follows ETSY_PRICE and ends after Nov 30.
"""
import copy
import datetime as dt
import html
import re
import unittest
from unittest import mock

import scripts.build_site as site
import scripts.checker as checker

MOOMIN = "Weeks, Moomin: At the Table (English)"


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def row(doc, name):
    table = doc[doc.index('<h2 id="prices">'):doc.index('<h2 id="hobonichi">')]
    return text(next(r for r in table.split("<tr>") if html.escape(name) in r or name in r))


def fixture(canonical, status="in_stock", prices=None, currency="USD"):
    """stock.json copy: every listing of one canonical gets status; prices maps store_id -> cents."""
    data = copy.deepcopy(site.stock)
    for p in data["products"]:
        for k in ("price_cents", "price_max_cents", "currency"):
            p.pop(k, None)
        if p.get("canonical") == canonical:
            p["status"] = status
            if prices and p["store_id"] in prices:
                p.update(currency=currency, price_cents=prices[p["store_id"]])
    return data


def render(data):
    with mock.patch.object(site, "stock", data):
        return site.build_gift_guide()[1]


class _Resp:
    def __init__(self, js, ok=True):
        self.js, self.ok, self.status_code = js, ok, 200 if ok else 404
        self.headers = {"content-type": "application/json"}
        self.text = ""
    def json(self):
        return self.js


class CheckerRecordsPrices(unittest.TestCase):
    PRODUCT = {"title": "Weeks", "available": True, "variants": [
        {"id": 1, "title": "A5", "available": True, "price": 3700},
        {"id": 2, "title": "B5", "available": False, "price": 4200},
        {"id": 3, "title": "A6", "available": True, "price": 3100}]}

    def store(self, **p):
        return {"id": "s", "name": "Shop", "url": "https://shop.example/", "platform": "shopify",
                "products": [dict(canonical="c", label="L", type="Weeks", url="https://shop.example/products/w", **p)]}

    def run_store(self, store, currency):
        product = self.PRODUCT

        class Host:
            def __init__(self, base):
                pass
            def get(self, url, check_robots=True):
                return _Resp({"currency": currency} if url.endswith("/meta.json") else product)

        with mock.patch.object(checker, "Host", Host):
            return checker.check_shopify_store(store)[0]

    def test_price_comes_from_the_same_product_data(self):
        self.assertEqual(checker.shopify_price(self.PRODUCT), (3100, 3700))  # available variants only
        self.assertEqual(checker.shopify_price(self.PRODUCT, 2), (4200, 4200))  # the tracked variant
        self.assertIsNone(checker.shopify_price({"variants": [{"id": 1, "price": None}]}))

    def test_usd_shop_records_price(self):
        rec = self.run_store(self.store(), "USD")
        self.assertEqual((rec["currency"], rec["price_cents"], rec["price_max_cents"]), ("USD", 3100, 3700))
        rec = self.run_store(self.store(variant_id=1), "USD")
        self.assertEqual(rec["price_cents"], 3700)
        self.assertNotIn("price_max_cents", rec)

    def test_non_usd_or_unknown_currency_records_no_price(self):
        for cur in ("CAD", "GBP", None):
            rec = self.run_store(self.store(), cur)
            self.assertNotIn("price_cents", rec, cur)
            self.assertNotIn("currency", rec, cur)


class GuidePriceColumn(unittest.TestCase):
    def shops(self):
        return sorted({p["store_id"] for p in site.stock["products"] if p.get("canonical") == "weeks-moomin-table"})

    def test_price_renders_from_data_and_follows_it(self):
        a, b = self.shops()[:2]
        name = next(p["store"] for p in site.stock["products"] if p["store_id"] == a)
        r1 = row(render(fixture("weeks-moomin-table", prices={a: 3800, b: 4000})), MOOMIN)
        self.assertIn(f"$38.00 to $40.00 lowest at {name}", r1)
        r2 = row(render(fixture("weeks-moomin-table", prices={a: 3650})), MOOMIN)
        self.assertIn(f"$36.50 at {name}", r2)
        self.assertNotIn("$38.00", r2)

    def test_sold_out_shops_do_not_set_the_price(self):
        data = fixture("weeks-moomin-table", prices={s: 1000 + i for i, s in enumerate(self.shops())})
        for p in data["products"]:
            if p.get("canonical") == "weeks-moomin-table" and p["price_cents"] == 1000:
                p["status"] = "sold_out"
        self.assertNotIn("$10.00 ", row(render(data), MOOMIN))

    def test_missing_prices_say_so(self):
        self.assertIn("See price at the shop", row(render(fixture("weeks-moomin-table")), MOOMIN))
        cad = fixture("weeks-moomin-table", prices={s: 3800 for s in self.shops()}, currency="CAD")
        self.assertIn("See price at the shop", row(render(cad), MOOMIN))
        self.assertIn("Couldn't check", row(render(fixture("weeks-moomin-table", "unknown")), MOOMIN))
        self.assertIn("No price: not in stock", row(render(fixture("weeks-moomin-table", "sold_out", {self.shops()[0]: 3800})), MOOMIN))

    def test_checked_time_is_shown(self):
        doc = render(fixture("weeks-moomin-table"))
        self.assertIn("Stock checked " + site.time_tag(site.stock["run_finished"]), doc)


def price_rows(doc):
    """Visible text of each price-table row, from the prices heading to the next section."""
    table = doc[doc.index('<h2 id="prices">'):doc.index('<h2 id="hobonichi">')]
    return [text(r) for r in table.split("<tr>")[1:]]


class EtsySaleLine(unittest.TestCase):
    def html(self, day, etsy_price=None, listings=None):
        with mock.patch.object(site, "gift_today", lambda: day), \
             mock.patch.object(site, "ETSY_PRICE", etsy_price or site.ETSY_PRICE):
            if listings is not None:
                with mock.patch.object(site, "etsy_listings", lambda: listings):
                    return site.build_gift_guide()[1]
            return site.build_gift_guide()[1]

    def doc(self, day, etsy_price=None, listings=None):
        return text(self.html(day, etsy_price, listings))

    def test_shown_through_nov_30_and_gone_on_dec_1(self):
        happy = next(e for e in site.etsy_listings() if e.get("id") == "happy-mail")
        shared = f"{site.ETSY_PRICE[0]} each on Etsy"
        other = f"{happy['price']} on Etsy"
        for day in (dt.date(2026, 11, 20), dt.date(2026, 11, 30)):
            rows = price_rows(self.html(day))
            printable = next(r for r in rows if "Our printables" in r)
            happy_row = next(r for r in rows if happy["title"] in r)
            self.assertIn(f"{shared}, {site.ETSY_PRICE[1]}", printable)
            self.assertIn(f"{other}, {site.ETSY_PRICE[1]}", happy_row)
        dec_html = self.html(dt.date(2026, 12, 1))
        dec_rows = price_rows(dec_html)
        printable = next(r for r in dec_rows if "Our printables" in r)
        happy_row = next(r for r in dec_rows if happy["title"] in r)
        self.assertIn(shared, printable)
        self.assertIn(other, happy_row)
        self.assertNotIn("% off", printable)
        self.assertNotIn("% off", happy_row)
        self.assertNotIn("% off", text(dec_html))

    def test_mixed_price_rows_share_the_sale_line(self):
        """Happy Mail is $5.99 in shop data; both printable rows get the same sale wording, then drop it."""
        happy = next(e for e in site.etsy_listings() if e.get("id") == "happy-mail")
        self.assertEqual(site.etsy_item_price(happy), "$5.99")
        rows = price_rows(self.html(dt.date(2026, 11, 30)))
        shared = next(r for r in rows if "Our printables" in r)
        other = next(r for r in rows if happy["title"] in r)
        self.assertIn(f"{site.ETSY_PRICE[0]} each on Etsy, {site.ETSY_PRICE[1]}", shared)
        self.assertIn(f"{happy['price']} on Etsy, {site.ETSY_PRICE[1]}", other)
        dec_rows = price_rows(self.html(dt.date(2026, 12, 1)))
        shared = next(r for r in dec_rows if "Our printables" in r)
        other = next(r for r in dec_rows if happy["title"] in r)
        self.assertIn(f"{site.ETSY_PRICE[0]} each on Etsy", shared)
        self.assertIn(f"{happy['price']} on Etsy", other)
        self.assertNotIn("% off", shared)
        self.assertNotIn("% off", other)

    def test_off_price_row_follows_the_listing_data(self):
        items = [dict(e) for e in site.etsy_listings()]
        happy = next(e for e in items if e.get("id") == "happy-mail")
        happy["price"] = "$4.50"
        rows = price_rows(self.html(dt.date(2026, 11, 30), listings=items))
        other = next(r for r in rows if happy["title"] in r)
        self.assertIn(f"$4.50 on Etsy, {site.ETSY_PRICE[1]}", other)
        shared = next(r for r in rows if "Our printables" in r)
        self.assertIn(f"{site.ETSY_PRICE[0]} each on Etsy, {site.ETSY_PRICE[1]}", shared)
        dec = next(r for r in price_rows(self.html(dt.date(2026, 12, 1), listings=items)) if happy["title"] in r)
        self.assertIn("$4.50 on Etsy", dec)
        self.assertNotIn("% off", dec)

    def test_follows_the_shop_sale_line(self):
        self.assertNotIn("% off", self.doc(dt.date(2026, 11, 20), ("$6.99", "Regular price")))


if __name__ == "__main__":
    unittest.main()
