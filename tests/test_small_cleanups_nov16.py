"""Small cleanups, Nov 16 2026: Actions Node 24 bumps. (The Traveler's size guide and its swipe hint were removed Nov 19, 2026.)"""
import re
import unittest
from pathlib import Path

import yaml

import scripts.build_site as site

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "site/assets/style.css").read_text()


class WorkflowNode24Tests(unittest.TestCase):
    def setUp(self):
        self.check = yaml.safe_load((ROOT / ".github/workflows/check-and-deploy.yml").read_text())
        self.cf = yaml.safe_load((ROOT / ".github/workflows/cloudflare-pages.yml").read_text())

    def _uses(self, wf):
        found = []
        for job in wf["jobs"].values():
            for step in job.get("steps", []):
                if "uses" in step:
                    found.append(step["uses"])
        return found

    def test_actions_run_on_current_node24_majors(self):
        self.assertEqual(self._uses(self.check), [
            "actions/checkout@v7",
            "actions/setup-python@v7",
            "actions/configure-pages@v6",
            "actions/upload-pages-artifact@v5",
        ])
        self.assertNotIn("deploy", self.check["jobs"])
        self.assertNotIn("uses: actions/deploy-pages", (ROOT / ".github/workflows/check-and-deploy.yml").read_text())
        self.assertEqual(self._uses(self.cf), [
            "actions/checkout@v7",
            "actions/download-artifact@v8",
            "actions/setup-node@v7",
        ])

    def test_checker_push_retry_and_concurrency_unchanged(self):
        self.assertEqual(self.check["concurrency"], {"group": "drop-watch", "cancel-in-progress": False})
        steps = self.check["jobs"]["check"]["steps"]
        names = [s.get("name") or s.get("uses") for s in steps]
        self.assertLess(names.index("Start from the latest main"), names.index("Run stock checker"))
        commit = next(s for s in steps if s.get("name", "").startswith("Commit data changes"))["run"]
        self.assertIn("git reset --hard origin/main", commit)
        self.assertIn('cp "$results/stock.json" "$results/changes.json" data/', commit)
        self.assertIn("for i in 1 2 3 4 5; do", commit)
        self.assertNotIn("pull --rebase", commit)
        self.assertEqual(self.check["jobs"]["check"]["steps"][steps.index(next(s for s in steps if s.get("uses") == "actions/setup-python@v7"))]["with"],
                         {"python-version": "3.12", "cache": "pip"})
        node = next(s for s in self.cf["jobs"]["deploy"]["steps"] if s.get("uses") == "actions/setup-node@v7")
        self.assertEqual(node["with"]["node-version"], "22")
        download = next(s for s in self.cf["jobs"]["deploy"]["steps"] if s.get("uses") == "actions/download-artifact@v8")
        self.assertEqual(download["with"]["name"], "github-pages")
        self.assertEqual(download["with"]["path"], "artifact")


if __name__ == "__main__":
    unittest.main()
