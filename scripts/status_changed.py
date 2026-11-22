#!/usr/bin/env python3
"""Exit 0 if data/ differs from HEAD in anything besides check timestamps (so it's worth a commit), else 1.
Ink tracker files count too (data/inks/: written by ink_tracker.py check). A file that wasn't written this run is skipped."""
import json, os, subprocess, sys
VOLATILE = {"checked_at", "run_started", "run_finished"}
FILES = ("data/stock.json", "data/changes.json", "data/inks/stock.json", "data/inks/changes.json", "data/inks/retired.json")
def strip(o):
    if isinstance(o, dict): return {k: strip(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list): return [strip(v) for v in o]
    return o
for f in FILES:
    if not os.path.exists(f):
        continue
    try: old = json.loads(subprocess.run(["git", "show", f"HEAD:{f}"], capture_output=True, text=True, check=True).stdout)
    except subprocess.CalledProcessError: sys.exit(0)
    if strip(old) != strip(json.load(open(f))): sys.exit(0)
sys.exit(1)
