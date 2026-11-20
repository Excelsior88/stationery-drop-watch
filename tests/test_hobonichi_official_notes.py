"""Hobonichi Store notes from 1101.com items.json: a short factual line on sold-out official rows only.

The note never changes a row's status, the changes log or drop alerts. Fixtures copy the real feed's shape
(Nov 19, 2026): message_lineup is {"en", "ja"} or 0, sales_termination is 0 on every live item.
"""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site as site  # noqa: E402
import checker  # noqa: E402

STARLIGHT_URL = "https://www.1101.com/store/techo/en/2027/pc/detail_cover/wb27_tdaisuke/"


def item(soldout, lineup=0, term=0, skus=((1, 0),)):
    """One items.json entry in the live feed's shape."""
    msg = {"en": lineup, "ja": ""} if lineup else 0
    return {"soldout": soldout, "sales_termination": term, "message_lineup": msg,
            "message_detail1": 0, "sales": {f"s{i}": {"soldout": so, "unreleased": un, "message": 0, "benefit": {}, "domestic": 0}
                                             for i, (so, un) in enumerate(skus)}}


class FakeHost:
    def __init__(self, feed):
        self.feed = feed

    def __call__(self, base):
        return self

    def get(self, url, check_robots=True):
        feed = self.feed
        return mock.Mock(json=lambda: {"items": feed})


STORE = {"id": "1101", "name": "Hobonichi Online Store (official)", "platform": "hobonichi",
         "products": [{"label": "Weeks · tanakadaisuke: Starlight", "type": "Weeks", "url": STARLIGHT_URL,
                       "source_key": "wb27_tdaisuke", "canonical": "weeks-starlight"}]}


def run(it):
    with mock.patch.object(checker, "Host", FakeHost({"wb27_tdaisuke": it})):
        return checker.check_hobonichi(STORE)[0]


class CheckerNoteTests(unittest.TestCase):
    def test_restock_coming_on_a_sold_out_item_gets_the_restock_note(self):
        rec = run(item(1, "Restock Coming", 0, ((1, 0), (1, 0))))
        self.assertEqual(rec["status"], "sold_out")
        self.assertEqual(rec["official_note"], "Official store notes a restock is planned")

    def test_no_restock_planned_gets_the_sales_ended_note(self):
        rec = run(item(1, "No Restock Planned"))
        self.assertEqual(rec["status"], "sold_out")
        self.assertEqual(rec["official_note"], "Sales ended at official store")

    def test_sales_termination_1_gets_the_sales_ended_note(self):
        rec = run(item(1, 0, 1))
        self.assertEqual(rec["official_note"], "Sales ended at official store")

    def test_restock_undecided_on_a_sold_out_item_gets_the_undecided_note(self):
        rec = run(item(1, "Restock Undecided", 0, ((1, 0), (1, 0))))
        self.assertEqual(rec["status"], "sold_out")
        self.assertEqual(rec["official_note"], "Restock undecided at official store")

    def test_restock_undecided_on_an_in_stock_item_has_no_note(self):
        rec = run(item(0, "Restock Undecided", 0, ((0, 0),)))
        self.assertEqual(rec["status"], "in_stock")
        self.assertNotIn("official_note", rec)
        rec = run(item(0, "Restock undecided for the English edition", 0, ((0, 0), (1, 0))))
        self.assertNotIn("official_note", rec)

    def test_sold_out_with_no_signal_has_no_note(self):
        for lineup in (0, ""):
            rec = run(item(1, lineup))
            self.assertEqual(rec["status"], "sold_out")
            self.assertNotIn("official_note", rec, lineup)

    def test_in_stock_has_no_note_even_with_a_stale_message(self):
        for lineup in ("Restock Coming", "Restock Undecided", "No Restock Planned"):
            rec = run(item(0, lineup, 0, ((0, 0),)))
            self.assertEqual(rec["status"], "in_stock")
            self.assertNotIn("official_note", rec)
        rec = run(item(0, 0, 1, ((0, 0),)))
        self.assertNotIn("official_note", rec)

    def test_coming_soon_and_edition_only_messages_have_no_note(self):
        rec = run(item(0, "Restock Coming", 0, ((0, 1),)))
        self.assertEqual(rec["status"], "coming_soon")
        self.assertNotIn("official_note", rec)
        rec = run(item(0, "Restock coming for the English edition", 0, ((0, 0), (1, 0))))
        self.assertEqual(rec["status"], "in_stock")
        self.assertNotIn("official_note", rec)

    def test_note_never_changes_status_or_the_changes_log(self):
        plain = run(item(1, 0))
        noted = run(item(1, "Restock Coming"))
        self.assertEqual(plain["status"], noted["status"])
        old = dict(plain, status="in_stock", status_since="2026-11-01T00:00:00+00:00")
        a = checker.note_transition(old, dict(plain), [])
        b = checker.note_transition(old, dict(noted), [])
        self.assertEqual(a, b)
        self.assertNotIn("official_note", json.dumps(b))


class RenderTests(unittest.TestCase):
    def stock_with(self, note):
        data = copy.deepcopy(site.stock)
        hit = False
        for p in data["products"]:
            if p["store_id"] == "1101" and p.get("canonical") == "weeks-starlight":
                p["status"] = "sold_out"
                p.pop("official_note", None)
                if note:
                    p["official_note"] = note
                hit = True
        self.assertTrue(hit, "Starlight's official row is tracked")
        return data

    def pages(self, data):
        d = next(d for d in site.DESIGNS if d.get("canonical") == "weeks-starlight" or "starlight" in (d.get("slug") or ""))
        g = next(g for g in site.GROUPS if any(p.get("canonical") == "weeks-starlight" for p in data["products"] if g["match"](p)))
        with mock.patch.object(site, "stock", data):
            return site.build_design(d)[1], site.build_group(g, {})[1]

    def test_note_renders_on_the_official_row_of_tracker_and_design_page(self):
        for note in ("Official store notes a restock is planned", "Restock undecided at official store", "Sales ended at official store"):
            for doc in self.pages(self.stock_with(note)):
                row = next(r for r in doc.split("<tr ")[1:] if f'href="{STARLIGHT_URL}"' in r.split("</tr>")[0])
                row = row.split("</tr>")[0]
                self.assertIn('data-store="1101"', row)
                self.assertIn(f'<span class="sub official-note">{note}</span>', row)
                self.assertEqual(doc.count("official-note"), 1)

    def test_note_renders_on_the_main_hobonichi_tracker_and_in_its_js_rows(self):
        note = "Official store notes a restock is planned"
        with mock.patch.object(site, "stock", self.stock_with(note)):
            doc = site.build_hobo_tracker()
        li = next(x for x in doc.split("<li>") if f'href="{STARLIGHT_URL}"' in x.split("</li>")[0]).split("</li>")[0]
        self.assertIn(f'<span class="official-note">{note}</span>', li)
        self.assertIn(f'"on": "{note}"', doc)  # the JSON rows app.js re-renders from
        js = (ROOT / "site/assets/app.js").read_text()
        self.assertIn('r.on && r.st === "sold_out"', js)
        with mock.patch.object(site, "stock", self.stock_with(None)):
            plain = site.build_hobo_tracker()
        self.assertNotIn("official-note", plain)
        self.assertNotIn('"on": ', plain)

    def test_rows_without_the_field_render_as_before(self):
        for doc in self.pages(self.stock_with(None)):
            self.assertNotIn("official-note", doc)

    def test_note_is_ignored_on_other_shops_and_on_rows_not_sold_out(self):
        data = self.stock_with("Official store notes a restock is planned")
        for p in data["products"]:
            if p.get("canonical") == "weeks-starlight":
                p["official_note"] = "Official store notes a restock is planned"
                if p["store_id"] == "1101":
                    p["status"] = "in_stock"
        for doc in self.pages(data):
            self.assertNotIn("official-note", doc)


if __name__ == "__main__":
    unittest.main()
