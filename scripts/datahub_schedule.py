#!/usr/bin/env python3
"""datahub_schedule.py — pause / resume a DataHub managed-ingestion source's schedule (B199 store parking, 2026-10-01).

When a store is parked (replicas: 0), its DataHub ingestion would still start on schedule, fail against the parked
store, and cost memory in mother's overnight stall window. `store-park.sh` calls this to pause the schedule on park and
restore it on wake, so one command does both. Called directly:

    datahub_schedule.py status <source name>...
    datahub_schedule.py pause  <source name>
    datahub_schedule.py resume <source name> <cron interval> <timezone>

Env: DATAHUB_GMS_URL, DATAHUB_GMS_TOKEN (store-park.sh supplies both — a local port-forward and the cluster Secret
`weyland/datahub-token`, read at runtime and never printed). Exit 0 ok · 2 cannot read / did not land.

Safety: the source is matched by its EXACT name; the update resends every field it read (name, type, config incl.
recipe, source) so only the schedule changes; and every change is verified by reading the source back.
"""
import hashlib
import json
import os
import sys

from datahub_ingestion_check import CannotRead, _gms

FIELDS = ("urn name type schedule { interval timezone } "
          "config { recipe version executorId debugMode extraArgs { key value } } source { type }")
LIST = ("query($q:String!){ listIngestionSources(input:{start:0,count:50,query:$q}) "
        f"{{ total ingestionSources {{ {FIELDS} }} }} }}")
GET = f"query($urn:String!){{ ingestionSource(urn:$urn) {{ {FIELDS} }} }}"
UPDATE = "mutation($urn:String!,$input:UpdateIngestionSourceInput!){ updateIngestionSource(urn:$urn,input:$input) }"


def _data(resp, key):
    if resp.get("errors"):
        raise CannotRead(f"GraphQL errors: {resp['errors']}")
    data = (resp.get("data") or {}).get(key)
    if data is None:
        raise CannotRead(f"no `{key}` in the GMS response")
    return data


def find_source(gql, name):
    hits = [s for s in _data(gql(LIST, {"q": name}), "listIngestionSources")["ingestionSources"] if s["name"] == name]
    if len(hits) != 1:
        raise CannotRead(f"expected exactly one ingestion source named {name!r}, found {len(hits)}")
    return hits[0]


def _schedule(src):
    s = src.get("schedule")
    return {"interval": s["interval"], "timezone": s["timezone"]} if s else None


def describe(src):
    s = _schedule(src)
    return f"{s['interval']} {s['timezone']}" if s else "paused"


def fingerprint(src):
    """A short hash of everything the update resends except the schedule — compare it before and after a park/wake
    to prove the recipe and config came through untouched."""
    body = json.dumps({"name": src["name"], "type": src["type"], "config": src["config"], "source": src.get("source")},
                      sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def update_input(src, schedule):
    """The full UpdateIngestionSourceInput for `src` with only its schedule replaced."""
    inp = {"name": src["name"], "type": src["type"], "config": src["config"], "schedule": schedule}
    if src.get("source"):
        inp["source"] = src["source"]
    return inp


def set_schedule(gql, name, schedule):
    """Set (or with None, remove) the schedule of the source named `name`; verified by reading it back."""
    src = find_source(gql, name)
    if _schedule(src) == schedule:
        return "unchanged"
    _data(gql(UPDATE, {"urn": src["urn"], "input": update_input(src, schedule)}), "updateIngestionSource")
    after = _data(gql(GET, {"urn": src["urn"]}), "ingestionSource")
    if _schedule(after) != schedule:
        raise CannotRead(f"{name}: the schedule change did not land (now: {describe(after)})")
    return "changed"


def main(argv):
    url, token = os.environ.get("DATAHUB_GMS_URL"), os.environ.get("DATAHUB_GMS_TOKEN")
    if not url or not token or not argv:
        print("usage: datahub_schedule.py status|pause|resume ... (needs DATAHUB_GMS_URL + DATAHUB_GMS_TOKEN)",
              file=sys.stderr)
        return 2
    gql = _gms(url, token)
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "status":
            for name in args:
                src = find_source(gql, name)
                print(f"{name}: {describe(src)}  (config {fingerprint(src)})")
        elif cmd == "pause" and len(args) == 1:
            print(f"{args[0]}: schedule {set_schedule(gql, args[0], None)} -> paused")
        elif cmd == "resume" and len(args) == 3:
            sched = {"interval": args[1], "timezone": args[2]}
            print(f"{args[0]}: schedule {set_schedule(gql, args[0], sched)} -> {args[1]} {args[2]}")
        else:
            print(f"bad command: {json.dumps(argv)}", file=sys.stderr)
            return 2
    except CannotRead as exc:
        print(f"DataHub: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
