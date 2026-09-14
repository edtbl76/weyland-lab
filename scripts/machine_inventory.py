#!/usr/bin/env python3
"""machine_inventory.py — the machine-inventory SoT merger + Port emitter (B129).

Two subcommands, both reading the normalized collector output (`collect-machine-inventory.sh <host>`) on stdin:

    collect-machine-inventory.sh <host> | machine_inventory.py merge <host>
        Fold the collected inventory into machine-inventory.yaml (the git SoT). ADD-ONLY + PRESERVE: new
        packages are added with a default status (apt/pip -> system, else -> unreviewed), existing curated
        decisions (status + rationale) are never overwritten, and packages in the SoT but no longer collected
        are REPORTED to stderr (never silently dropped — a human decides). Decisions are version-independent,
        so version is NOT stored here (no churn); the emitter attaches the live version.

    collect-machine-inventory.sh <host> | machine_inventory.py emit <host>
        Upsert the host + its installed_package entities into Port (REST API + client creds, per
        port-mcp-browser-auth-wedges). Status/rationale come from the SoT; the live version comes from the
        piped collection. Baseline (status: system) packages are emitted too so the catalog is complete.

The discretionary kinds (snap/flatpak/npm/image) default to `unreviewed` so a new install is a visible
review item; the dep-dominated kinds (apt/pip) default to `system` so the catalog is complete without
hundreds of hand-written rationales. See docs/runbooks/machine-inventory.md.
"""
import os
import sys
import json
import urllib.request

import yaml

SOT = os.path.join(os.path.dirname(__file__), "..", "machine-inventory.yaml")
BASELINE_KINDS = {"apt", "pip", "image"}  # captured but not a keep/remove decision: dep-dominated (apt/pip)
#                                          # + transient/regenerable (container images). Curate snap/flatpak/npm.
PORT_API = "https://api.getport.io/v1"


def read_stdin_records():
    """Parse the collector's <kind>\\t<name>\\t<version> lines from stdin into [(kind, name, version)]."""
    recs = []
    for line in sys.stdin:
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2 and parts[0] and parts[1]:
            recs.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return recs


def load_sot():
    if os.path.exists(SOT):
        with open(SOT) as f:
            return yaml.safe_load(f) or {"hosts": {}}
    return {"hosts": {}}


def cmd_merge(host):
    recs = read_stdin_records()
    if not recs:
        sys.exit("merge: no records on stdin — did the collector run? (refusing to blank the host)")
    sot = load_sot()
    hosts = sot.setdefault("hosts", {})
    entry = hosts.setdefault(host, {"role": "", "packages": []})
    existing = {(p["kind"], p["name"]): p for p in entry.get("packages", [])}

    collected = {(k, n) for k, n, _ in recs}
    added = 0
    for kind, name, _ in recs:
        key = (kind, name)
        if key in existing:
            continue  # preserve the curated decision
        status = "system" if kind in BASELINE_KINDS else "unreviewed"
        pkg = {"name": name, "kind": kind, "status": status}
        if status == "unreviewed":
            pkg["rationale"] = ""
        entry.setdefault("packages", []).append(pkg)
        added += 1

    # Report (never auto-drop) anything cataloged but no longer collected — a human decides.
    absent = [f"{k}:{n}" for (k, n) in existing if (k, n) not in collected]
    entry["packages"].sort(key=lambda p: (p["kind"], p["name"].lower()))

    with open(SOT, "w") as f:
        f.write("# Machine-inventory catalog (B129) — curated keep/remove/rationale per host.\n"
                "# status: keep | remove | system (dep baseline) | unreviewed (new, needs a decision).\n"
                "# Maintained by scripts/machine_inventory.py; refresh via docs/runbooks/machine-inventory.md.\n")
        yaml.safe_dump(sot, f, sort_keys=False, default_flow_style=False, allow_unicode=True, width=120)

    print(f"merge {host}: +{added} new, {len(entry['packages'])} total cataloged", file=sys.stderr)
    unreviewed = sum(1 for p in entry["packages"] if p.get("status") == "unreviewed")
    if unreviewed:
        print(f"  {unreviewed} item(s) status=unreviewed — curate keep/remove + rationale", file=sys.stderr)
    if absent:
        print(f"  absent (cataloged but not collected this run — decide): {', '.join(sorted(absent))}", file=sys.stderr)


def port_token():
    cid, sec = os.environ.get("PORT_CLIENT_ID"), os.environ.get("PORT_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("emit: PORT_CLIENT_ID / PORT_CLIENT_SECRET not set (source tofu/port/.env)")
    req = urllib.request.Request(f"{PORT_API}/auth/access_token",
                                 data=json.dumps({"clientId": cid, "clientSecret": sec}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["accessToken"]


def port_upsert(token, blueprint, entity):
    req = urllib.request.Request(
        f"{PORT_API}/blueprints/{blueprint}/entities?upsert=true&merge=true",
        data=json.dumps(entity).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    urllib.request.urlopen(req, timeout=30).read()


def cmd_emit(host):
    recs = read_stdin_records()
    if not recs:
        sys.exit("emit: no records on stdin — refusing to emit an empty inventory")
    sot = load_sot()
    entry = (sot.get("hosts") or {}).get(host, {})
    decided = {(p["kind"], p["name"]): p for p in entry.get("packages", [])}
    ver = {(k, n): v for k, n, v in recs}

    token = port_token()
    port_upsert(token, "host", {"identifier": host, "title": host,
                                "properties": {"role": entry.get("role", "")}})
    n = 0
    for (kind, name), v in ver.items():
        d = decided.get((kind, name), {})
        ident = f"{host}--{kind}--{name}".replace("/", "_").replace(":", "_")[:255]
        port_upsert(token, "installed_package", {
            "identifier": ident, "title": f"{name} ({kind})",
            "properties": {"kind": kind, "package": name, "version": v,
                           "status": d.get("status", "unreviewed"), "rationale": d.get("rationale", "")},
            "relations": {"host": host}})
        n += 1
    print(f"emit {host}: upserted 1 host + {n} installed_package entities to Port", file=sys.stderr)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("merge", "emit"):
        sys.exit("usage: machine_inventory.py {merge|emit} <host>   (reads collector output on stdin)")
    (cmd_merge if sys.argv[1] == "merge" else cmd_emit)(sys.argv[2])


if __name__ == "__main__":
    main()
