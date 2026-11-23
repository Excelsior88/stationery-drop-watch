"""Link-only shops: no restock events anywhere, and every Link only pill has a More Information link (owner t1866u, Nov 23, 2026)."""
import json, pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import checker

class LinkOnlyEventsTests(unittest.TestCase):
    def lo(self):
        return {s["id"] for s in json.loads((ROOT / "stores.json").read_text())["stores"] if s.get("link_only")}

    def test_data_and_published_changes_have_no_link_only_events(self):
        lo = self.lo()
        for f in ("data/changes.json", "site/data/changes.json"):
            self.assertFalse([c for c in json.loads((ROOT / f).read_text()) if c["store_id"] in lo], f)

    def test_checker_never_logs_a_link_only_transition(self):
        sid = sorted(self.lo())[0]
        rec = dict(store_id=sid, store="x", label="l", url="u", status="in_stock", checked_at="2026-11-23T00:00:00+00:00")
        old = dict(status="sold_out", first_seen="a", status_since="a")
        self.assertEqual(checker.note_transition(old, rec, []), [])

    def test_every_link_only_pill_has_more_information_to_its_left(self):
        for f in (ROOT / "site").rglob("index.html"):
            t = f.read_text()
            self.assertEqual(t.count('class="badge link_only"'), len(re.findall(
                r'<a class="more-info" href="/transparency/"[^>]*>More Information</a><span class="badge link_only">', t)), str(f))

if __name__ == "__main__":
    unittest.main()
