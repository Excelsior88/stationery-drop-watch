#!/usr/bin/env python3
"""Fail closed unless a Cloudflare deploy is the fresh site artifact from one successful checker run.

The only site that may be published is the artifact uploaded by that run. Checked-in
data/ and site/ are not a deploy source. changes.json is a history log and is not availability.
"""
import json, os, shutil, sys, tarfile, datetime as dt
from pathlib import Path

SKEW = dt.timedelta(minutes=5)


class DeployRefused(Exception):
    """The deploy must not continue."""


def _parse_time(value, label):
    if value is None or not str(value).strip():
        raise DeployRefused(f"refusing deploy: missing {label}")
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        raise DeployRefused(f"refusing deploy: {label} is not a timestamp ({value})") from None
    if parsed.tzinfo is None:
        raise DeployRefused(f"refusing deploy: {label} has no timezone")
    return parsed.astimezone(dt.timezone.utc)


def preflight(event_name, conclusion, branch, run_id, head_sha, run_started_at, run_updated_at, run_created_at=""):
    """Reject every trigger that is not a successful checker run on main.

    The run window starts at run_started_at. created_at is used only when GitHub omits
    run_started_at, and a missing window still refuses the deploy.
    """
    if event_name != "workflow_run":
        raise DeployRefused("refusing deploy: manual dispatch has no checker artifact")
    if branch != "main":
        raise DeployRefused(f"refusing deploy: checker run is on {branch!r}, not main")
    if conclusion != "success":
        raise DeployRefused(f"refusing deploy: checker run concluded {conclusion!r}, not success")
    if run_id is None or not str(run_id).strip():
        raise DeployRefused("refusing deploy: missing checker run id")
    if not head_sha or not str(head_sha).strip():
        raise DeployRefused("refusing deploy: missing checker head sha")
    started = _parse_time(run_started_at or run_created_at, "checker run start")
    updated = _parse_time(run_updated_at, "checker run update")
    if updated < started:
        raise DeployRefused("refusing deploy: checker run update is before its start")
    return started, updated


def _load_stock(stock_path):
    if not stock_path.is_file() or stock_path.stat().st_size == 0:
        raise DeployRefused("refusing deploy: artifact stock.json is missing or corrupt")
    try:
        stock = json.loads(stock_path.read_text())
    except (OSError, json.JSONDecodeError):
        raise DeployRefused("refusing deploy: artifact stock.json is missing or corrupt") from None
    if not isinstance(stock, dict):
        raise DeployRefused("refusing deploy: artifact stock.json is missing or corrupt")
    products = stock.get("products")
    if not isinstance(products, list) or not products:
        raise DeployRefused("refusing deploy: artifact stock.json has no products")
    for product in products:
        if not isinstance(product, dict) or not product.get("url") or not product.get("status"):
            raise DeployRefused("refusing deploy: artifact stock.json has no products")
    started = _parse_time(stock.get("run_started"), "stock run_started")
    finished = _parse_time(stock.get("run_finished"), "stock run_finished")
    if finished < started:
        raise DeployRefused("refusing deploy: stock run_finished is before run_started")
    return started, finished


def _require_site_files(out_dir):
    for name in ("index.html", "404.html"):
        path = out_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            raise DeployRefused(f"refusing deploy: artifact has no {name}")


def accept(tar_path, out_dir, event_name, conclusion, branch, run_id, head_sha, run_started_at, run_updated_at, run_created_at=""):
    """Extract one artifact and require its stock check to have happened during that run.

    out_dir is created only after the archive is valid. A checked-in tree already sitting
    there is refused, not published.
    """
    run_started, run_updated = preflight(
        event_name, conclusion, branch, run_id, head_sha, run_started_at, run_updated_at, run_created_at)
    tar_path, out_dir = Path(tar_path), Path(out_dir)
    if not tar_path.is_file() or tar_path.stat().st_size == 0:
        raise DeployRefused("refusing deploy: artifact is missing")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise DeployRefused("refusing deploy: output directory is not empty")
    staging = out_dir.with_name(out_dir.name + ".partial")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        try:
            with tarfile.open(tar_path) as tar:
                tar.extractall(staging, filter="data")
        except tarfile.FilterError:
            raise DeployRefused("refusing deploy: artifact escapes the deploy directory") from None
        except tarfile.TarError:
            raise DeployRefused("refusing deploy: artifact is corrupt") from None
        _require_site_files(staging)
        stock_started, stock_finished = _load_stock(staging / "data" / "stock.json")
        window_start = run_started - SKEW
        window_end = run_updated + SKEW
        if not (window_start <= stock_started <= window_end and window_start <= stock_finished <= window_end):
            raise DeployRefused(
                "refusing deploy: stock run_finished "
                f"{stock_finished.isoformat()} is outside the checker run "
                f"{run_started.isoformat()}..{run_updated.isoformat()}")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if out_dir.exists():
        out_dir.rmdir()
    staging.rename(out_dir)
    return stock_finished


def _from_env():
    return (
        os.environ.get("DEPLOY_EVENT", ""),
        os.environ.get("DEPLOY_CONCLUSION", ""),
        os.environ.get("DEPLOY_BRANCH", ""),
        os.environ.get("DEPLOY_RUN_ID", ""),
        os.environ.get("DEPLOY_HEAD_SHA", ""),
        os.environ.get("DEPLOY_RUN_STARTED_AT", ""),
        os.environ.get("DEPLOY_RUN_UPDATED_AT", ""),
        os.environ.get("DEPLOY_RUN_CREATED_AT", ""),
    )


def main(argv):
    try:
        command = argv[1] if len(argv) > 1 else ""
        if command == "preflight":
            preflight(*_from_env())
        elif command == "accept":
            if len(argv) != 4:
                raise DeployRefused("refusing deploy: accept needs an artifact tar and an output directory")
            accept(argv[2], argv[3], *_from_env())
        else:
            raise DeployRefused("refusing deploy: unknown command")
    except DeployRefused as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
