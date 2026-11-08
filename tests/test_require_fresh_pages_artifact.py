"""Cloudflare may publish only a fresh artifact from a successful main checker run."""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import require_fresh_pages_artifact as guard  # noqa: E402

RUN_ID = "424242"
HEAD = "30f6067daa191692deec2463fc015be4333f7ecf"
STARTED = dt.datetime(2026, 11, 8, 6, 0, tzinfo=dt.timezone.utc)
UPDATED = dt.datetime(2026, 11, 8, 6, 20, tzinfo=dt.timezone.utc)


def iso(when):
    return when.isoformat()


class FreshArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def stock(self, started, finished, status="sold_out", marker="artifact"):
        return {
            "run_started": iso(started),
            "run_finished": iso(finished),
            "marker": marker,
            "products": [{
                "url": "https://shop.example/card-black",
                "status": status,
                "label": "Card Size 20th Anniversary Set",
            }],
        }

    def make_tar(self, stock, changes=None, names=None):
        tar_path = self.tmp / f"artifact-{len(list(self.tmp.glob('*.tar')))}.tar"
        with tarfile.open(tar_path, "w") as tar:
            files = {
                "index.html": b"<html>fresh</html>",
                "404.html": b"<html>missing</html>",
                "data/stock.json": json.dumps(stock).encode(),
            }
            if changes is not None:
                files["data/changes.json"] = json.dumps(changes).encode()
            if names is not None:
                files = names
            for name, payload in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
        return tar_path

    def accept(self, tar_path, out=None, **overrides):
        out = out or (self.tmp / "out")
        args = dict(event_name="workflow_run", conclusion="success", branch="main", run_id=RUN_ID,
                    head_sha=HEAD, run_started_at=iso(STARTED), run_updated_at=iso(UPDATED))
        args.update(overrides)
        return guard.accept(tar_path, out, **args)

    def test_success_publishes_the_checker_artifact_not_history(self):
        stock_started = STARTED + dt.timedelta(minutes=2)
        stock_finished = STARTED + dt.timedelta(minutes=8)
        # A historical restock says in stock. The fresh check says sold out. The artifact wins.
        tar_path = self.make_tar(
            self.stock(stock_started, stock_finished, status="sold_out"),
            changes=[{"at": "2026-11-06T23:18:18+00:00", "to": "in_stock", "from": "sold_out",
                      "url": "https://shop.example/card-black"}])
        decoy = self.tmp / "data"
        decoy.mkdir()
        (decoy / "stock.json").write_text(json.dumps(self.stock(STARTED, UPDATED, marker="checkout")))
        finished = self.accept(tar_path)
        self.assertEqual(finished, stock_finished)
        published = json.loads((self.tmp / "out" / "data" / "stock.json").read_text())
        self.assertEqual(published["marker"], "artifact")
        self.assertEqual(published["products"][0]["status"], "sold_out")
        self.assertTrue((self.tmp / "out" / "index.html").is_file())
        self.assertFalse((self.tmp / "out.partial").exists())
        self.assertEqual(json.loads((decoy / "stock.json").read_text())["marker"], "checkout")

    def test_manual_failed_and_non_main_runs_are_refused(self):
        cases = [
            dict(event_name="workflow_dispatch", conclusion="success"),
            dict(event_name="push", conclusion="success"),
            dict(conclusion="failure"),
            dict(conclusion="timed_out"),
            dict(conclusion="cancelled"),
            dict(conclusion="skipped"),
            dict(conclusion="neutral"),
            dict(conclusion=""),
            dict(branch="feature"),
            dict(run_id=""),
            dict(head_sha=""),
            dict(run_started_at="", run_created_at=""),
            dict(run_updated_at=""),
        ]
        for overrides in cases:
            with self.subTest(overrides):
                with self.assertRaises(guard.DeployRefused) as caught:
                    guard.preflight(**{
                        "event_name": "workflow_run", "conclusion": "success", "branch": "main",
                        "run_id": RUN_ID, "head_sha": HEAD,
                        "run_started_at": iso(STARTED), "run_updated_at": iso(UPDATED),
                        **overrides,
                    })
                self.assertIn("refusing deploy", str(caught.exception))

    def test_missing_corrupt_and_stale_artifacts_are_refused(self):
        fresh = self.stock(STARTED + dt.timedelta(minutes=1), STARTED + dt.timedelta(minutes=4))
        stale = self.stock(STARTED - dt.timedelta(days=2), STARTED - dt.timedelta(days=2) + dt.timedelta(minutes=5))
        future = self.stock(UPDATED + dt.timedelta(hours=2), UPDATED + dt.timedelta(hours=3))
        outside = self.stock(STARTED - dt.timedelta(minutes=6), STARTED - dt.timedelta(minutes=5, seconds=1))
        cases = {
            "missing tar": self.tmp / "nope.tar",
            "corrupt": self._bytes_tar(b"this is not a tar"),
            "traversal": self._traversal_tar(),
            "no index": self.make_tar(fresh, names={"404.html": b"x", "data/stock.json": json.dumps(fresh).encode()}),
            "no 404": self.make_tar(fresh, names={"index.html": b"x", "data/stock.json": json.dumps(fresh).encode()}),
            "no stock": self.make_tar(fresh, names={"index.html": b"x", "404.html": b"y"}),
            "bad json": self.make_tar(fresh, names={"index.html": b"x", "404.html": b"y", "data/stock.json": b"{"}),
            "no products": self.make_tar({**fresh, "products": []}),
            "product without status": self.make_tar({**fresh, "products": [{"url": "https://shop.example/x"}]}),
            "stale": self.make_tar(stale),
            "future": self.make_tar(future),
            "just outside the run": self.make_tar(outside),
            "just after the run": self.make_tar(self.stock(
                STARTED + dt.timedelta(minutes=1), UPDATED + guard.SKEW + dt.timedelta(seconds=1))),
        }
        for name, tar_path in cases.items():
            with self.subTest(name):
                out = self.tmp / f"out-{name.replace(' ', '-')}"
                with self.assertRaises(guard.DeployRefused) as caught:
                    self.accept(tar_path, out)
                self.assertIn("refusing deploy", str(caught.exception))
                self.assertFalse(out.exists(), name)
                self.assertFalse(Path(str(out) + ".partial").exists(), name)

    def test_skew_boundary_is_accepted(self):
        self.accept(self.make_tar(self.stock(STARTED - guard.SKEW, UPDATED + guard.SKEW)))

    def test_created_at_covers_a_missing_run_started_at(self):
        self.accept(
            self.make_tar(self.stock(STARTED + dt.timedelta(minutes=1), STARTED + dt.timedelta(minutes=3))),
            run_started_at="", run_created_at=iso(STARTED))

    def test_prefilled_output_directory_is_not_published(self):
        out = self.tmp / "out"
        out.mkdir()
        (out / "index.html").write_text("checked-in snapshot")
        tar_path = self.make_tar(self.stock(STARTED + dt.timedelta(minutes=1), STARTED + dt.timedelta(minutes=2)))
        with self.assertRaises(guard.DeployRefused):
            self.accept(tar_path, out)
        self.assertEqual((out / "index.html").read_text(), "checked-in snapshot")

    def test_traversal_does_not_write_outside_the_deploy_directory(self):
        tar_path = self._traversal_tar()
        outside = self.tmp / "outside.txt"
        with self.assertRaises(guard.DeployRefused) as caught:
            self.accept(tar_path)
        self.assertIn("escapes", str(caught.exception))
        self.assertFalse(outside.exists())

    def test_cli_preflight_and_accept(self):
        script = ROOT / "scripts" / "require_fresh_pages_artifact.py"
        env = os.environ.copy()
        env.update(DEPLOY_EVENT="workflow_dispatch", DEPLOY_CONCLUSION="", DEPLOY_BRANCH="",
                   DEPLOY_RUN_ID="", DEPLOY_HEAD_SHA="", DEPLOY_RUN_STARTED_AT="", DEPLOY_RUN_UPDATED_AT="")
        refused = subprocess.run([sys.executable, str(script), "preflight"], cwd=self.tmp, env=env,
                                 capture_output=True, text=True)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("manual dispatch", refused.stderr)

        stock_finished = STARTED + dt.timedelta(minutes=3)
        tar_path = self.make_tar(self.stock(STARTED + dt.timedelta(minutes=1), stock_finished))
        # A checked-in snapshot beside the command must not become the publish directory.
        snapshot = self.tmp / "site"
        snapshot.mkdir()
        (snapshot / "index.html").write_text("stale site")
        (self.tmp / "data").mkdir()
        (self.tmp / "data" / "stock.json").write_text('{"marker":"checkout"}')
        env.update(DEPLOY_EVENT="workflow_run", DEPLOY_CONCLUSION="success", DEPLOY_BRANCH="main",
                   DEPLOY_RUN_ID=RUN_ID, DEPLOY_HEAD_SHA=HEAD,
                   DEPLOY_RUN_STARTED_AT=iso(STARTED), DEPLOY_RUN_UPDATED_AT=iso(UPDATED))
        accepted = subprocess.run([sys.executable, str(script), "accept", str(tar_path), str(self.tmp / "out")],
                                  cwd=self.tmp, env=env, capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual((snapshot / "index.html").read_text(), "stale site")
        self.assertIn(b"fresh", (self.tmp / "out" / "index.html").read_bytes())
        self.assertEqual(json.loads((self.tmp / "out" / "data" / "stock.json").read_text())["marker"], "artifact")

    def test_workflow_cannot_fall_back_to_checked_in_stock(self):
        workflow = (ROOT / ".github" / "workflows" / "cloudflare-pages.yml").read_text()
        checker = (ROOT / ".github" / "workflows" / "check-and-deploy.yml").read_text()
        self.assertIn("conclusion == 'success'", workflow)
        self.assertNotIn("!= 'cancelled'", workflow)
        self.assertNotIn("build_site.py", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("Build site from main", workflow)
        self.assertNotIn("cp -r site", workflow)
        self.assertNotIn("github.sha", workflow)
        self.assertIn("require_fresh_pages_artifact.py preflight", workflow)
        self.assertIn("require_fresh_pages_artifact.py accept artifact/artifact.tar out", workflow)
        self.assertIn("run-id: ${{ github.event.workflow_run.id }}", workflow)
        self.assertIn('cron: "17,47 * * * *"', checker)
        self.assertIn("python scripts/checker.py", checker)
        self.assertNotIn("data/stock.json", (ROOT / "scripts" / "require_fresh_pages_artifact.py").read_text().split('"""', 2)[2])

    def _bytes_tar(self, payload):
        path = self.tmp / "corrupt.tar"
        path.write_bytes(payload)
        return path

    def _traversal_tar(self):
        path = self.tmp / "slip.tar"
        with tarfile.open(path, "w") as tar:
            payload = b"pwned"
            info = tarfile.TarInfo("../outside.txt")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        return path


if __name__ == "__main__":
    unittest.main()
