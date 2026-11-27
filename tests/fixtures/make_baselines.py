"""Freeze the stock rows a few older tests were written against.

Those tests check what the checker saved on the run that first added a set of
listings (a quiet first observation, exact row counts, the first status). Live
data keeps moving: later status changes are real and logged, and some shops have
since become link-only and have no rows at all. So the first-run facts are read
from the data as it was committed on that run, kept here, and the live data is
tested separately with checks that stay true as it grows.

Run from the repo root to rebuild:  python3 tests/fixtures/make_baselines.py
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "baselines"

# name: (commit whose data/stock.json and data/changes.json are the baseline, canonical ids, extra urls)
BASELINES = {
    # 76c89c2e5 (Nov 20, 2026, 12:07 AM ET): first check run with the beautiful people covers.
    "beautiful_people": ("76c89c2e5", {"cover-a6-beautiful-people-green", "cover-a5-beautiful-people-pink",
                                        "weeks-beautiful-people-yellow"}, set()),
    # 87eb8c2f6 (Nov 23, 2026, 2:54 AM ET): last data commit where the apex-URL rows still had their first status.
    "checker_politeness": ("87eb8c2f6", set(), {
        "https://milligram.com/products/hobonichi-2027-techo-original-book-a6-japanese",
        "https://milligram.com/products/hobonichi-2027-techo-original-planner-book",
        "https://cultpens.com/products/leuchtturm1917-bullet-journal-edition-2-black",
        "https://goldspot.com/products/leuchtturm-1917-black-hardcover-medium-dotted",
    }),
}


def show(commit, path):
    return json.loads(subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT))


def main():
    OUT.mkdir(exist_ok=True)
    for name, (commit, canon, urls) in BASELINES.items():
        stock = show(commit, "data/stock.json")
        changes = show(commit, "data/changes.json")
        rows = [r for r in stock["products"] if r.get("canonical") in canon or r["url"] in urls]
        keep = {r["url"] for r in rows}
        snap = {
            "commit": subprocess.check_output(["git", "rev-parse", commit], cwd=ROOT, text=True).strip(),
            "products": sorted(rows, key=lambda r: r["url"]),
            "changes": [c for c in changes if c.get("url") in keep],
        }
        (OUT / f"{name}.json").write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n")
        print(name, len(rows), "rows", len(snap["changes"]), "changes")


if __name__ == "__main__":
    main()
