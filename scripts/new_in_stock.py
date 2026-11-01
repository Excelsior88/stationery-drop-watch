#!/usr/bin/env python3
"""Write this run's NEW changes to in_stock (in data/changes.json but not in HEAD's copy) to the
path given as argv[1], as a JSON list. Prints the count. Run before the data commit."""
import json, subprocess, sys
def key(c): return "|".join(str(c.get(k, "")) for k in ("at", "store_id", "label", "to"))
new = json.load(open("data/changes.json"))
try:
    old = json.loads(subprocess.run(["git", "show", "HEAD:data/changes.json"], capture_output=True, text=True, check=True).stdout)
except subprocess.CalledProcessError:
    old = []
seen = {key(c) for c in old}
fresh = [c for c in new if c.get("to") == "in_stock" and key(c) not in seen]
json.dump(fresh, open(sys.argv[1], "w"), indent=1)
print(len(fresh))
