#!/usr/bin/env python3
"""Placement inventory guard (B198) — placement.yaml against the architecture model and the live estate.

WHY THIS EXISTS: before the Strix Halo box (B134) lands, every workload needs one answer — where it runs, what state it
holds, whether it can move, where it goes. Kubernetes placement was already guarded (applications.yaml ->
check-onboarding-completeness -> LikeC4), but host-native services were hand-listed and had drifted: a 2026-09-27 spot
check of rogueone found three STUD.io runners, mosquitto and dcgm-exporter running with no model entry, and nothing read
what rogueone ran at all. With one k8s node "which node does this need?" was never asked; with two it must be.

MODES
  --repo       (repo-guards, every push)  schema + enums, known hosts, every LikeC4 node / non-cluster component has a
               row, every row's likec4 exists, a pvc/host-path row is never movable.
  --live       (nightly CronJob)          k8s objects from kube-state-metrics, active systemd units per watched host
               from node-exporter (last 24h — a laptop sleeps), Proxmox guests from pve-exporter; each must match rows.
  --migration  print the Strix Halo migration table (markdown) for B134.

EXIT CODES (the coverage-guard contract): 0 clean · 1 drift, named · 2 a source could not be read — never a pass.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import yaml

ID_PREFIXES = ("k8s:", "systemd:", "pve:", "tool:", "user-systemd:")
DECLARED_ONLY = ("tool:", "user-systemd:")  # not visible to Prometheus: declared, never live-checked
STRIX = {"any", "k3s-worker", "inference-lxc", "stays", "every-node", "tbd"}
NEEDS_WHY = {"k3s-worker", "inference-lxc", "tbd"}
SCOPES = {"lab", "stud.io", "personal", "unused", "unknown"}
MOVE_FIXED = {"movable", "every-node"}
MOVE_REASONED = ("pinned:", "hardware-bound:")
KSM = {"Deployment": "deployment", "StatefulSet": "statefulset", "DaemonSet": "daemonset", "CronJob": "cronjob"}
# A unit is RUNNING when it was active in more than half of the last 24h's samples. Not "active at any moment": D-Bus-
# activated OS helpers (systemd-hostnamed, flatpak-system-helper) run for seconds and exit, and any-moment made each a
# nightly finding (2026-09-28). A sleeping laptop yields no samples, so sleep does not count against a unit.
UNIT_QUERY = 'avg_over_time(node_systemd_unit_state{state="active",instance="%s"}[24h]) > 0.5'
CLUSTER_NODE = "mother"


class CannotRead(Exception):
    """A source could not be read — the guard must exit 2, never report a clean estate it did not see."""


# --- schema -------------------------------------------------------------------------------------------------------

def _row_findings(r, hosts):
    rid = r.get("id", "<no id>")
    out = []
    if not str(rid).startswith(ID_PREFIXES):
        out.append(f"{rid}: id prefix must be one of {', '.join(ID_PREFIXES)}")
    if r.get("host") not in hosts:
        out.append(f"{rid}: unknown host '{r.get('host')}'")
    strix, move, scope = r.get("strix"), str(r.get("move", "")), r.get("scope", "lab")
    if strix not in STRIX:
        out.append(f"{rid}: strix '{strix}' is not one of {sorted(STRIX)}")
    if strix in NEEDS_WHY and not r.get("why"):
        out.append(f"{rid}: strix '{strix}' is a decision and needs a `why`")
    if scope not in SCOPES:
        out.append(f"{rid}: scope '{scope}' is not one of {sorted(SCOPES)}")
    if scope == "unused" and not r.get("why"):
        out.append(f"{rid}: scope 'unused' needs a `why`")
    if move.startswith(MOVE_REASONED):
        if not move.split(":", 1)[1].strip():
            out.append(f"{rid}: move '{move}' needs a reason after the colon")
    elif move not in MOVE_FIXED:
        out.append(f"{rid}: move '{move}' is not movable / every-node / pinned: <reason> / hardware-bound: <reason>")
    state = str(r.get("state", ""))
    if state.startswith(("pvc", "host-path")) and move in MOVE_FIXED and rid.startswith("k8s:"):
        out.append(f"{rid}: state '{state}' is bound to one node, so it cannot be `{move}` (pvc/host-path is pinned)")
    return out


def validate_schema(doc):
    hosts = doc.get("hosts") or {}
    rows = doc.get("workloads") or []
    findings, seen = [], set()
    for r in rows:
        rid = r.get("id")
        if rid in seen:
            findings.append(f"{rid}: duplicate id")
        seen.add(rid)
        findings.extend(_row_findings(r, hosts))
    for host in (doc.get("host_os_units") or {}):
        if host not in hosts:
            findings.append(f"host_os_units: unknown host '{host}'")
    return findings


# --- LikeC4 -------------------------------------------------------------------------------------------------------

_ELEMENT = re.compile(r'^\s*(\w+)\s*=\s*(\w+)\s+"')


def _model_block(text):
    m = re.search(r"^model\s*\{", text, re.M)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[m.end():i - 1]


def likec4_placed_elements(text):
    """Every `node` element, plus every element nested inside a node other than the k3s node (whose components are k8s
    workloads, placed by the live k8s rows and by check-onboarding-completeness)."""
    stack, placed = [], set()
    for line in _model_block(text).splitlines():
        code = line.split("//", 1)[0]
        m = _ELEMENT.match(code)
        if m:
            eid, kind = m.group(1), m.group(2)
            in_node = next((s for s in reversed(stack) if s[1] == "node"), None)
            if kind == "node":
                placed.add(eid)
            elif in_node and in_node[0] != CLUSTER_NODE:
                placed.add(eid)
            if code.count("{") > code.count("}"):
                stack.append((eid, kind))
            continue
        for _ in range(code.count("}") - code.count("{")):
            if stack:
                stack.pop()
        for _ in range(code.count("{") - code.count("}")):
            stack.append(("", ""))
    if not placed:
        raise CannotRead("no node elements parsed from the LikeC4 model")
    return placed


def check_model(doc, model_text):
    placed = likec4_placed_elements(model_text)
    hosts = set((doc.get("hosts") or {}).keys())
    named = {r.get("likec4") for r in doc.get("workloads") or [] if r.get("likec4")}
    out = [f"LikeC4 element '{e}' has no placement row (add a row with likec4: {e})"
           for e in sorted(placed - named - hosts)]
    all_ids = set(re.findall(r'^\s*(\w+)\s*=\s*\w+\s+"', _model_block(model_text), re.M))
    out += [f"row likec4 '{e}' is not an element in the LikeC4 model" for e in sorted(named - all_ids)]
    return out


# --- live ---------------------------------------------------------------------------------------------------------

def _result(resp):
    if not isinstance(resp, dict) or resp.get("status") != "success":
        raise CannotRead(f"Prometheus error: {resp.get('error') if isinstance(resp, dict) else resp}")
    return resp["data"]["result"]


def k8s_objects(query):
    out = set()
    for kind, label in KSM.items():
        res = _result(query(f"kube_{label}_created"))
        if not res:
            raise CannotRead(f"kube_{label}_created returned nothing — kube-state-metrics is not answering")
        out |= {f"k8s:{m['metric']['namespace']}/{kind}/{m['metric'][label]}" for m in res}
    return out


def active_units(query, hosts):
    out = {}
    for host, h in hosts.items():
        inst = (h or {}).get("node_exporter")
        if not inst:
            continue
        res = _result(query(UNIT_QUERY % inst))
        if not res:
            raise CannotRead(f"{host}: no systemd series from {inst} in the last 24h (asleep or exporter down)")
        out[host] = {m["metric"]["name"] for m in res if m["metric"]["name"].endswith((".service", ".timer"))}
    return out


def pve_guests(query):
    res = _result(query("pve_guest_info"))
    if not res:
        raise CannotRead("pve_guest_info returned nothing — pve-exporter is not answering")
    return {f"pve:{m['metric']['id']}" for m in res}


def suggest_row(rid, host="mother"):
    return (f'  - {{id: "{rid}", host: "{host}", state: "stateless", move: "movable", strix: "any", '
            f'managed: "argo"}}   # check state/move before committing')


def _running_set(rid, k8s, units, pve):
    if rid.startswith("k8s:"):
        return k8s
    if rid.startswith("pve:"):
        return pve
    host = rid[len("systemd:"):].split("/", 1)[0]
    return {f"systemd:{host}/{u}" for u in units.get(host, set())} if host in units else None


def check_live(doc, k8s, units, pve):
    rows = doc.get("workloads") or []
    ids = {r["id"] for r in rows}
    os_units = doc.get("host_os_units") or {}
    running = set(k8s) | set(pve)
    for host, us in units.items():
        running |= {f"systemd:{host}/{u}" for u in us if u not in set(os_units.get(host, []))}
    out = []
    for rid in sorted(running - ids):
        host = rid[len("systemd:"):].split("/", 1)[0] if rid.startswith("systemd:") else "mother"
        out.append(f"{rid}: running with no row — add:\n{suggest_row(rid, host)}")
    for r in rows:
        rid = r["id"]
        if rid.startswith(DECLARED_ONLY) or r.get("on_demand"):
            continue
        live = _running_set(rid, k8s, units, pve)
        if live is not None and rid not in live:
            out.append(f"{rid}: row names something that is not running (remove the row, or mark on_demand: true)")
    return out


# --- migration ----------------------------------------------------------------------------------------------------

def migration_table(doc):
    rows = doc.get("workloads") or []
    moves = [r for r in rows if r.get("strix") in NEEDS_WHY]
    lines = ["| Workload | Now on | State | Target | Why |", "|---|---|---|---|---|"]
    lines += [f"| `{r['id']}` | {r['host']} | {r.get('state', '')} | {r['strix']} | {r.get('why', '')} |"
              for r in sorted(moves, key=lambda r: (r["strix"], r["id"]))]
    counts = {}
    for r in rows:
        counts[r.get("strix")] = counts.get(r.get("strix"), 0) + 1
    summary = ", ".join(f"{k}: {counts[k]}" for k in sorted(counts))
    return "\n".join(lines) + f"\n\n## Summary\n\n{len(rows)} rows — {summary}\n"


# --- main ---------------------------------------------------------------------------------------------------------

def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        raise CannotRead(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict) or not doc.get("workloads"):
        raise CannotRead(f"{path} has no workloads — refusing to report OK")
    return doc


def _prom(url):
    def query(q):
        full = f"{url.rstrip('/')}/api/v1/query?" + urllib.parse.urlencode({"query": q})
        try:
            with urllib.request.urlopen(full, timeout=30) as resp:  # noqa: S310  # nosec B310 — in-cluster http URL
                return json.load(resp)
        except (OSError, ValueError) as exc:
            raise CannotRead(f"Prometheus unreachable at {url}: {exc}") from exc
    return query


def _run(args):
    doc = _load(args.file)
    if args.migration:
        print(migration_table(doc))
        return []
    findings = validate_schema(doc)
    if args.live:
        q = _prom(args.prometheus)
        findings += check_live(doc, k8s_objects(q), active_units(q, doc.get("hosts") or {}), pve_guests(q))
    else:
        with open(args.model, encoding="utf-8") as f:
            findings += check_model(doc, f.read())
    return findings


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--repo", action="store_true", help="schema + LikeC4 checks (default)")
    mode.add_argument("--live", action="store_true", help="reconcile against Prometheus")
    mode.add_argument("--migration", action="store_true", help="print the Strix Halo migration table")
    ap.add_argument("--file", default=os.path.join(root, "placement.yaml"))
    ap.add_argument("--model", default=os.path.join(root, "docs/architecture/weyland.likec4"))
    ap.add_argument("--prometheus", default=os.environ.get(
        "PROMETHEUS_URL", "http://monitoring-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090"))
    args = ap.parse_args(argv)
    try:
        findings = _run(args)
    except (CannotRead, OSError) as exc:
        print(f"❌ cannot check placement: {exc}", file=sys.stderr)
        return 2
    if args.migration:
        return 0
    for f in findings:
        print(f"  ❌ {f}", file=sys.stderr)
    if findings:
        print(f"❌ placement drift: {len(findings)} finding(s). Fix placement.yaml (or the model).", file=sys.stderr)
        return 1
    print(f"OK — placement.yaml: {len(_load(args.file)['workloads'])} rows, {'live' if args.live else 'repo'} check clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
