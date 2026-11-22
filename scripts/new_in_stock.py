#!/usr/bin/env python3
"""Write this run's NEW changes to in_stock (in data/changes.json but not in HEAD's copy).

Every new to=in_stock change is included (limited-edition inks too, from data/inks/changes.json, tagged tracker=inks), except Traveler's Company and MIDORI (removed Nov 19, 2026).
There is no product, cover, or Weeks filter.
The webhook body is that list plus the run clock. Run before the data commit.
"""
import datetime
import json
import os
import subprocess
import sys


def key(change):
    return "|".join(str(change.get(k, "")) for k in ("at", "store_id", "label", "to"))


# Removed at TRAVELER'S COMPANY USA's request on Nov 19, 2026: never alert or email for these, even if a row comes back.
TAKEDOWN_SECTIONS = ("travelers", "midori")
TAKEDOWN_STORES = {"travelerscompanyusa", "mdproductusa"}  # the two brands' own stores


def taken_down(change):
    return change.get("section") in TAKEDOWN_SECTIONS or change.get("store_id") in TAKEDOWN_STORES


def fresh_in_stock(old, new):
    seen = {key(change) for change in old}
    return [change for change in new
            if change.get("to") == "in_stock" and key(change) not in seen and not taken_down(change)]


def fresh_ink_in_stock(old, new):
    """New ink changes to in_stock, tagged tracker=inks (and section=inks so the email step picks the inks tag).

    Same rule as fresh_in_stock: only changes that are not already in HEAD's copy. ink_tracker.check only writes a change
    when a listing it already had a status for flips, so a newly tracked ink never produces an event. Hidden rows
    (ink_tracker marks them hidden) never alert."""
    seen = {key(change) for change in old}
    out = []
    for change in new:
        if change.get("to") != "in_stock" or change.get("hidden") or key(change) in seen or taken_down(change):
            continue
        out.append(dict(change, tracker="inks", section="inks"))
    return out


def webhook_body(changes, run_at, test=False):
    body = {"source": "stationery-drop-watch", "run_at": run_at, "changes": changes}
    if test:
        body["test"] = True
    return body


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--webhook":
        changes = json.load(open(argv[1]))
        run_at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        body = webhook_body(changes, run_at, test=os.environ.get("TEST_PING") == "true")
        json.dump(body, open(argv[2], "w"))
        return 0
    new = json.load(open("data/changes.json"))
    try:
        old = json.loads(subprocess.run(["git", "show", "HEAD:data/changes.json"], capture_output=True, text=True, check=True).stdout)
    except subprocess.CalledProcessError:
        old = []
    fresh = fresh_in_stock(old, new)
    ink_path = "data/inks/changes.json"
    if os.path.exists(ink_path):
        ink_new = json.load(open(ink_path))
        try:
            ink_old = json.loads(subprocess.run(["git", "show", "HEAD:" + ink_path], capture_output=True, text=True, check=True).stdout)
        except subprocess.CalledProcessError:
            ink_old = ink_new  # file not in HEAD yet: everything in it is history, nothing is new
        fresh += fresh_ink_in_stock(ink_old, ink_new)
    json.dump(fresh, open(argv[0], "w"), indent=1)
    print(len(fresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
