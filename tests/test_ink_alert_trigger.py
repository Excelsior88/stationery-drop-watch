"""Ink status changes reach the drop-alert feed (new_in_stock.py) as tracker=inks, never from a first observation."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import new_in_stock as nis  # noqa: E402
import checker  # noqa: E402


def change(at="2026-11-22T10:00:00+00:00", to="in_stock", store="atlas", **extra):
    return dict(at=at, store_id=store, store="Atlas", label="Sailor ink", url="u", section="inks", ink_id="sailor-x",
                **{"from": "sold_out", "to": to}, **extra)


class FreshInkTests(unittest.TestCase):
    def test_new_flip_to_in_stock_is_tagged_inks(self):
        out = nis.fresh_ink_in_stock([], [change()])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["tracker"], "inks")
        self.assertEqual(out[0]["section"], "inks")

    def test_changes_already_in_head_are_not_new(self):
        old = [change()]
        self.assertEqual(nis.fresh_ink_in_stock(old, old + [change(at="2026-11-22T11:00:00+00:00")])[0]["at"], "2026-11-22T11:00:00+00:00")
        self.assertEqual(nis.fresh_ink_in_stock(old, old), [])

    def test_only_in_stock_and_never_hidden(self):
        self.assertEqual(nis.fresh_ink_in_stock([], [change(to="sold_out"), change(to="coming_soon"), change(hidden=True)]), [])

    def test_first_observation_writes_no_change_so_nothing_alerts(self):
        changes = []
        rec = {"checked_at": "2026-11-22T03:00:00+00:00", "status": "in_stock", "store_id": "atlas", "store": "Atlas",
               "label": "x", "url": "u", "section": "inks"}
        checker.note_transition(None, rec, changes)
        self.assertEqual(nis.fresh_ink_in_stock([], changes), [])

    def test_stock_changes_are_not_tagged(self):
        c = dict(change(), section=None)
        c.pop("section")
        self.assertEqual(nis.fresh_in_stock([], [c])[0].get("tracker"), None)


class CliTests(unittest.TestCase):
    def run_in_repo(self, files, head_files):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True, text=True)
            run("git", "init", "-q")
            run("git", "config", "user.email", "a@b.c")
            run("git", "config", "user.name", "t")
            (d / "data" / "inks").mkdir(parents=True)
            for name, obj in head_files.items():
                (d / name).write_text(json.dumps(obj))
            run("git", "add", "-A")
            run("git", "commit", "-qm", "head", "--allow-empty")
            for name, obj in files.items():
                (d / name).write_text(json.dumps(obj))
            out = d / "out.json"
            r = subprocess.run([sys.executable, str(ROOT / "scripts/new_in_stock.py"), str(out)], cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return int(r.stdout.strip()), json.loads(out.read_text())

    def test_cli_counts_new_ink_flip_only(self):
        old = {"data/changes.json": [], "data/inks/changes.json": [change()]}
        new = {"data/changes.json": [], "data/inks/changes.json": [change(), change(at="2026-11-22T12:00:00+00:00")]}
        n, fresh = self.run_in_repo(new, old)
        self.assertEqual(n, 1)
        self.assertEqual(fresh[0]["tracker"], "inks")

    def test_cli_file_missing_from_head_is_history_not_news(self):
        n, fresh = self.run_in_repo({"data/changes.json": [], "data/inks/changes.json": [change()]}, {"data/changes.json": []})
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
