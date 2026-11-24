"""Robots.txt block record (owner t1910u, Nov 24, 2026): data/robots-blocks.json, never published."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import checker  # noqa: E402

STORES = [
    {"id": "shopa", "name": "Shop A", "url": "https://shopa.example/", "platform": "shopify", "products": []},
    {"id": "shopb", "name": "Shop B", "url": "https://shopb.example/", "platform": "shopify", "products": []},
]
ROBOTS = "User-agent: StationeryDropWatch\nDisallow: /products/\n\nUser-agent: *\nAllow: /\n"


def row(sid, url, blocked):
    return {"store_id": sid, "url": url, "status": "unknown" if blocked else "in_stock",
            "error": f"PermissionError: {checker.ROBOTS_DISALLOWED}" if blocked else None}


class FakeHost:
    def __init__(self, base, text):
        self.base, self.robots_text, self.robots = base, text, checker.Robots(text.splitlines())


class RobotsBlockTests(unittest.TestCase):
    def setUp(self):
        checker.ROBOTS_HITS.clear()
        self.tmp = Path(tempfile.mkdtemp()) / "robots-blocks.json"

    def tearDown(self):
        checker.ROBOTS_HITS.clear()

    def run_once(self, results, at):
        checker.write_robots_blocks(STORES, results, at, path=self.tmp)
        return json.loads(self.tmp.read_text())

    def test_host_records_snapshot_and_rules_on_disallow(self):
        h = FakeHost("https://shopa.example", ROBOTS)
        self.assertFalse(h.robots.allowed(checker.UA, "https://shopa.example/products/x.js"))
        checker.note_robots_block(h, "https://shopa.example/products/x.js")
        hit = checker.ROBOTS_HITS["https://shopa.example"]
        self.assertEqual(hit["urls"], ["https://shopa.example/products/x.js"])
        self.assertIn("User-agent: StationeryDropWatch", hit["robots_txt"])
        self.assertEqual(hit["rules"], "Disallow: /products/")

    def test_new_block_recorded_once_then_last_seen_moves(self):
        checker.note_robots_block(FakeHost("https://shopa.example", ROBOTS), "https://shopa.example/products/x.js")
        res = [row("shopa", "https://shopa.example/products/x", True), row("shopb", "https://shopb.example/products/y", False)]
        d1 = self.run_once(res, "2026-11-24T18:00:00+00:00")
        b = d1["blocks"]["shopa"]
        self.assertEqual((b["status"], b["first_detected"], b["last_seen"], b["scope"]),
                         ("blocked", "2026-11-24T18:00:00+00:00", "2026-11-24T18:00:00+00:00", "whole store"))
        self.assertIn("Disallow: /products/", b["robots_txt_at_detection"])
        self.assertEqual(b["sample_urls"], ["https://shopa.example/products/x.js"])
        self.assertNotIn("shopb", d1["blocks"])
        self.assertEqual([(e["kind"], e["store_id"], e["review"]) for e in d1["events"]], [("blocked", "shopa", "pending")])
        d2 = self.run_once(res, "2026-11-24T18:30:00+00:00")
        self.assertEqual(d2["blocks"]["shopa"]["first_detected"], "2026-11-24T18:00:00+00:00")
        self.assertEqual(d2["blocks"]["shopa"]["last_seen"], "2026-11-24T18:30:00+00:00")
        self.assertEqual(len(d2["events"]), 1)

    def test_clear_on_allow_and_reblock_is_a_new_episode(self):
        blocked = [row("shopa", "https://shopa.example/products/x", True)]
        self.run_once(blocked, "2026-11-24T18:00:00+00:00")
        d = self.run_once([row("shopa", "https://shopa.example/products/x", False)], "2026-11-24T19:00:00+00:00")
        self.assertEqual((d["blocks"]["shopa"]["status"], d["blocks"]["shopa"]["cleared_at"]), ("cleared", "2026-11-24T19:00:00+00:00"))
        self.assertEqual([e["kind"] for e in d["events"]], ["blocked", "cleared"])
        d = self.run_once(blocked, "2026-11-25T08:00:00+00:00")
        self.assertEqual(d["blocks"]["shopa"]["first_detected"], "2026-11-25T08:00:00+00:00")
        self.assertEqual(d["blocks"]["shopa"]["previously_cleared_at"], "2026-11-24T19:00:00+00:00")
        self.assertEqual([e["kind"] for e in d["events"]], ["blocked", "cleared", "blocked"])

    def test_unchecked_store_is_not_cleared(self):
        self.run_once([row("shopa", "https://shopa.example/products/x", True)], "2026-11-24T18:00:00+00:00")
        stores = [dict(STORES[0], link_only=True), STORES[1]]
        checker.write_robots_blocks(stores, [], "2026-11-24T19:00:00+00:00", path=self.tmp)
        self.assertEqual(json.loads(self.tmp.read_text())["blocks"]["shopa"]["status"], "blocked")

    def test_some_listings_scope(self):
        res = [row("shopa", "https://shopa.example/products/x", True), row("shopa", "https://shopa.example/products/z", False)]
        self.assertEqual(self.run_once(res, "2026-11-24T18:00:00+00:00")["blocks"]["shopa"]["scope"], "some listings")

    def test_record_errors_never_raise(self):
        self.tmp.write_text("{not json")
        checker.write_robots_blocks(STORES, [], "2026-11-24T18:00:00+00:00", path=self.tmp)  # must not raise


class EndToEndTests(unittest.TestCase):
    """Real Host and check_shopify_store with a fake session: robots.txt disallows our checker."""
    def test_disallowed_store_is_recorded(self):
        class Resp:
            def __init__(self, text, status=200):
                self.text, self.status_code, self.ok, self.headers = text, status, status == 200, {}
            def json(self):
                return json.loads(self.text)
        class FakeSession:
            def __init__(self):
                self.headers, self.calls = {}, []
            def get(self, url, timeout=None):
                self.calls.append(url)
                if url.endswith("/robots.txt"):
                    return Resp("User-agent: StationeryDropWatch\nDisallow: /\n")
                return Resp("{}", 404)
        orig, orig_delay = checker.GuardedSession, checker.DELAY
        checker.GuardedSession, checker.DELAY = FakeSession, 0
        checker.ROBOTS_HITS.clear()
        try:
            store = {"id": "shopz", "name": "Shop Z", "url": "https://shopz.example/", "platform": "shopify",
                     "products": [{"label": "X", "type": "Book", "url": "https://shopz.example/products/x"}]}
            rows = checker.check_shopify_store(store)
            self.assertIn(checker.ROBOTS_DISALLOWED, rows[0]["error"])
            tmp = Path(tempfile.mkdtemp()) / "rb.json"
            checker.write_robots_blocks([store], rows, "2026-11-24T18:00:00+00:00", path=tmp)
            b = json.loads(tmp.read_text())["blocks"]["shopz"]
            self.assertEqual((b["status"], b["scope"], b["rules_for_us_at_detection"]), ("blocked", "whole store", "Disallow: /"))
            self.assertIn("https://shopz.example/products/x.js", b["sample_urls"])
        finally:
            checker.GuardedSession, checker.DELAY = orig, orig_delay
            checker.ROBOTS_HITS.clear()


class NotPublishedTests(unittest.TestCase):
    def test_file_not_in_public_build(self):
        self.assertTrue((ROOT / "data/robots-blocks.json").exists())
        self.assertEqual(list((ROOT / "site").rglob("robots-blocks*")), [])
        src = (ROOT / "scripts/build_site.py").read_text()
        self.assertNotIn("robots-blocks", src)
        self.assertNotRegex(src, r"copytree\([^)]*data")
        wf = (ROOT / ".github/workflows/check-and-deploy.yml").read_text()
        self.assertIn("path: site\n", wf)  # only site/ is uploaded and deployed

    def test_status_changed_ignores_last_seen(self):
        src = (ROOT / "scripts/status_changed.py").read_text()
        self.assertIn('"last_seen"', src)
        self.assertIn('"data/robots-blocks.json"', src)

    def test_retry_path_keeps_the_record(self):
        wf = (ROOT / ".github/workflows/check-and-deploy.yml").read_text()
        self.assertIn('cp data/robots-blocks.json "$results/"', wf)
        self.assertIn('cp "$results/robots-blocks.json" data/', wf)


if __name__ == "__main__":
    unittest.main()
