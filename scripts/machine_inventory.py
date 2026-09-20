#!/usr/bin/env python3
"""machine_inventory.py — the machine-inventory SoT merger + Port emitter (B129).

Two subcommands, both reading the normalized collector output (`collect-machine-inventory.sh <host>`) on stdin:

    collect-machine-inventory.sh <host> | machine_inventory.py merge <host>
        Fold the collected inventory into machine-inventory.yaml (the git SoT). ADD-ONLY + PRESERVE: new
        packages are added with a default status (apt/pip -> system, else -> unreviewed), existing curated
        decisions (status + rationale) are never overwritten, and packages in the SoT but no longer collected
        are REPORTED to stderr (never silently dropped — a human decides). Decisions are version-independent,
        so version is NOT stored here (no churn); the emitter attaches the live version.

    machine_inventory.py emit <host|all>
        Upsert the host + its installed_package entities into Port (REST API + client creds, per
        port-mcp-browser-auth-wedges). Reads the committed SoT (no stdin/SSH). Status/rationale come from the
        SoT; version is not tracked in the SoT, so it is left blank in Port. Baseline (status: system)
        packages are emitted too so the catalog is complete.

    machine_inventory.py verify <host|all>
        The fail-CLOSED onboarding gate (B169): READ BACK from Port and assert the `host` entity exists and
        its installed_package entity count matches the SoT — so `emit` is verified, never assumed from its own
        exit code (the "reads as success" bug class). Read-only. Exits nonzero on a missing host or a count
        mismatch. Test seam: MACHINE_INV_VERIFY_ACTUAL injects the Port count so the pass/fail decision is
        exercisable offline.

The discretionary kinds (snap/flatpak/npm/image) default to `unreviewed` so a new install is a visible
review item; the dep-dominated kinds (apt/pip) default to `system` so the catalog is complete without
hundreds of hand-written rationales. See docs/runbooks/machine-inventory.md.
"""
import os
import sys
import json
import urllib.request
import urllib.error

import yaml

SOT = os.environ.get("MACHINE_INV_SOT", os.path.join(os.path.dirname(__file__), "..", "machine-inventory.yaml"))
BASELINE_KINDS = {"apt", "pip", "image"}  # captured but not a keep/remove decision: dep-dominated (apt/pip)
#                                          # + transient/regenerable (container images). Curate snap/flatpak/npm.
PORT_API = "https://api.getport.io/v1"


def read_stdin_records():
    """Parse the collector's stream: a leading `host:<name>` tag then `<kind>\\t<name>\\t<version>` lines.
    Returns (collected_host, [(kind, name, version)]). collected_host is None only for a pre-tag collector."""
    collected_host, recs = None, []
    for line in sys.stdin:
        line = line.rstrip("\n")
        if collected_host is None and line.startswith("host:"):
            collected_host = line[len("host:"):].strip()
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] and parts[1]:
            recs.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return collected_host, recs


def stdin_for(cmd, host):
    """read_stdin_records + the host-mismatch guard: fail CLOSED if the collected host is not the target,
    so `collect <A> | <cmd> <B>` never mislabels A's inventory as B (the 2026-09-14 weyland/mother mixup)."""
    collected_host, recs = read_stdin_records()
    if collected_host is not None and collected_host != host:
        sys.exit(f"{cmd}: collected host '{collected_host}' != target '{host}' — refusing to write "
                 f"{collected_host}'s inventory under '{host}'. Re-run: "
                 f"collect-machine-inventory.sh {host} | machine_inventory.py {cmd} {host}")
    if collected_host is None:
        print(f"{cmd}: warning — collector output carried no host: tag (old collector?); "
              f"cannot verify it is really {host}", file=sys.stderr)
    return recs


def load_sot():
    if os.path.exists(SOT):
        with open(SOT) as f:
            return yaml.safe_load(f) or {"hosts": {}}
    return {"hosts": {}}


def cmd_merge(host, prune=False):
    recs = stdin_for("merge", host)
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
        existing[key] = pkg  # dedupe WITHIN this run too: a repo listed once per tag (crictl) or an apt
        #                      package printed per arch (multiarch) arrives as identical (kind,name) records;
        #                      without this the 2nd..Nth would all append (the mother realm-of-agents x20 bug).
        added += 1

    # Anything cataloged but no longer collected. Default (by-hand path): REPORT only, a human decides.
    # --prune (the B170 reconcile): REMOVE it too, so the catalog tracks uninstalls. Safe because merge
    # already refuses empty stdin above — an unreachable host yields no records and never reaches here, so
    # prune can never wipe a host it simply couldn't scan.
    absent_keys = [(k, n) for (k, n) in existing if (k, n) not in collected]
    pruned = 0
    if prune and absent_keys:
        drop = set(absent_keys)
        entry["packages"] = [p for p in entry["packages"] if (p["kind"], p["name"]) not in drop]
        pruned = len(absent_keys)
    absent = [f"{k}:{n}" for (k, n) in absent_keys]
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
    if prune and pruned:
        print(f"  pruned {pruned} no longer installed: {', '.join(sorted(absent))}", file=sys.stderr)
    elif absent:
        print(f"  absent (cataloged but not collected this run — decide): {', '.join(sorted(absent))}", file=sys.stderr)


def port_token():
    cid, sec = os.environ.get("PORT_CLIENT_ID"), os.environ.get("PORT_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("emit: PORT_CLIENT_ID / PORT_CLIENT_SECRET not set (source tofu/port/.env)")
    req = urllib.request.Request(f"{PORT_API}/auth/access_token",
                                 data=json.dumps({"clientId": cid, "clientSecret": sec}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["accessToken"]  # nosec B310 — fixed https Port API URL, not a user scheme


def port_upsert(token, blueprint, entity):
    req = urllib.request.Request(
        f"{PORT_API}/blueprints/{blueprint}/entities?upsert=true&merge=true",
        data=json.dumps(entity).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    urllib.request.urlopen(req, timeout=30).read()  # nosec B310 — fixed https Port API URL, not a user scheme


def cmd_emit(host):
    """Push the committed SoT to Port (no collect/SSH needed — the SoT is the source). `host` is a single
    host or `all`. Emits one `host` entity + one `installed_package` per cataloged package (kind/status/
    rationale from the SoT; version is not tracked in the SoT, so it is left blank in Port)."""
    sot = load_sot()
    hosts = sot.get("hosts") or {}
    targets = sorted(hosts) if host == "all" else [host]
    token = port_token()
    total = 0
    for h in targets:
        entry = hosts.get(h)
        if not entry:
            sys.exit(f"emit: host '{h}' is not in the SoT (have: {', '.join(sorted(hosts)) or 'none'})")
        port_upsert(token, "host", {"identifier": h, "title": h,
                                    "properties": {"role": entry.get("role", "")}})
        n = 0
        for p in entry.get("packages", []):
            ident = f"{h}--{p['kind']}--{p['name']}".replace("/", "_").replace(":", "_")[:255]
            port_upsert(token, "installed_package", {
                "identifier": ident, "title": f"{p['name']} ({p['kind']})",
                "properties": {"kind": p["kind"], "package": p["name"],
                               "status": p.get("status", "unreviewed"), "rationale": p.get("rationale", "")},
                "relations": {"host": h}})
            n += 1
        total += n
        print(f"emit {h}: 1 host + {n} installed_package entities", file=sys.stderr)
    print(f"emit: {len(targets)} host(s), {total} package entities upserted to Port", file=sys.stderr)


def port_get(token, path):
    req = urllib.request.Request(f"{PORT_API}{path}",
                                 headers={"Authorization": f"Bearer {token}"})
    return json.load(urllib.request.urlopen(req, timeout=30))  # nosec B310 — fixed https Port API URL, not a user scheme


def port_counts(host):
    """Return (host_exists, installed_package_count) for `host` from Port. installed_package identifiers are
    `<host>--<kind>--<name>`, so the host's packages are exactly those whose identifier has the `<host>--`
    prefix. Test seam: MACHINE_INV_VERIFY_ACTUAL injects the count (host assumed present) so the pass/fail
    decision in cmd_verify is exercisable without the network."""
    seam = os.environ.get("MACHINE_INV_VERIFY_ACTUAL")
    if seam is not None:
        return True, int(seam)
    token = port_token()
    try:
        port_get(token, f"/blueprints/host/entities/{host}")
        host_exists = True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            host_exists = False
        else:
            raise
    data = port_get(token, "/blueprints/installed_package/entities")
    prefix = f"{host}--"
    count = sum(1 for e in data.get("entities", []) if str(e.get("identifier", "")).startswith(prefix))
    return host_exists, count


def cmd_verify(host):
    """Fail-CLOSED onboarding gate (B169): confirm the committed SoT actually landed in Port by READING IT
    BACK — the `host` entity must exist and its installed_package count must match the SoT. `host` is a single
    host or `all`. Read-only; exits nonzero on any missing host or count mismatch (never a silent green)."""
    sot = load_sot()
    hosts = sot.get("hosts") or {}
    targets = sorted(hosts) if host == "all" else [host]
    rc = 0
    for h in targets:
        entry = hosts.get(h)
        if not entry:
            sys.exit(f"verify: host '{h}' is not in the SoT (have: {', '.join(sorted(hosts)) or 'none'})")
        expected = len(entry.get("packages", []))
        host_exists, actual = port_counts(h)
        if not host_exists:
            print(f"verify {h}: FAIL — no `host` entity in Port (run: machine_inventory.py emit {h})", file=sys.stderr)
            rc = 1
            continue
        if actual != expected:
            print(f"verify {h}: FAIL — Port has {actual} installed_package entities, SoT has {expected} "
                  f"(re-run emit; a persistent gap is real drift)", file=sys.stderr)
            rc = 1
            continue
        print(f"verify {h}: OK — host entity + {actual} installed_package entities in Port (matches SoT)",
              file=sys.stderr)
    if rc:
        sys.exit(rc)


def main():
    usage = ("usage: machine_inventory.py merge  [--prune] <host>  (reads collector output on stdin;\n"
             "                                                      --prune also removes uninstalled rows)\n"
             "       machine_inventory.py emit   <host|all>        (reads the committed SoT; no stdin)\n"
             "       machine_inventory.py verify <host|all>        (read-back gate: SoT landed in Port)")
    args = sys.argv[1:]
    prune = "--prune" in args
    args = [a for a in args if a != "--prune"]
    if len(args) != 2 or args[0] not in ("merge", "emit", "verify"):
        sys.exit(usage)
    cmd, target = args
    if prune and cmd != "merge":
        sys.exit(f"{cmd}: --prune is only valid for merge\n{usage}")
    if cmd == "merge":
        cmd_merge(target, prune=prune)
    elif cmd == "emit":
        cmd_emit(target)
    else:
        cmd_verify(target)


if __name__ == "__main__":
    main()
