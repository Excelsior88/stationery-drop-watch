#!/usr/bin/env python3
"""Write this run's NEW changes to in_stock (in data/changes.json but not in HEAD's copy).

Every new to=in_stock change is included. There is no product, cover, or Weeks filter.
The webhook body is that list plus the run clock. Run before the data commit.
"""
import datetime
import json
import os
import subprocess
import sys


def key(change):
    return "|".join(str(change.get(k, "")) for k in ("at", "store_id", "label", "to"))


def fresh_in_stock(old, new):
    seen = {key(change) for change in old}
    return [change for change in new if change.get("to") == "in_stock" and key(change) not in seen]


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
    json.dump(fresh, open(argv[0], "w"), indent=1)
    print(len(fresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
