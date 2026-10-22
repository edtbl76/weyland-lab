#!/usr/bin/env bash
# Every in-cluster service a JupyterHub notebook dials must let the notebooks in (2026-10-21).
#
# WHY THIS EXISTS: B211 (2026-10-14) put NetworkPolicy front doors on the no-auth stores, each admitting the callers its
# author could list. The notebooks were never listed: for a week Trino refused notebooks 20 and 40 and Valkey refused 50,
# and nothing failed until the owner ran the whole notebook library by hand. Each policy's own pin test proved its LISTED
# callers were admitted; nothing asked whether every REAL caller was listed. This asks it for the notebooks.
#
# It reads every code cell of the notebook library for `<service>.<namespace>.svc[.cluster.local]` hosts, finds the
# git Service, and checks every Ingress NetworkPolicy in that namespace whose podSelector selects the Service's pods:
# each must admit the singleuser servers (namespace `jupyterhub`, optionally narrowed to `component: singleuser-server`).
# A service with no such policy is open (listed with --list, not a failure). A host with no Service in git (a Helm-made
# one, e.g. DataHub GMS) is listed as unchecked.
#
#   usage: scripts/check-notebook-front-doors.sh [--list]
# EXIT: 0 every front door admits the notebooks · 1 a front door refuses them, named (notebook, host, policy) · 2 could
#   not check (no notebooks, no k8s dir, a manifest or notebook that does not parse) — never a clean pass over nothing.
# Tests: scripts/tests/notebook-front-doors.bats. Runbook: docs/runbooks/write-surfaces.md.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
K8S_DIR="${CM_K8S_DIR:-$PLATFORM_DIR/k8s}"
NOTEBOOK_DIR="${NOTEBOOK_DIR:-$K8S_DIR/jupyterhub/singleuser/notebooks}"
LIST=0; [ "${1-}" = "--list" ] && LIST=1

[ -d "$K8S_DIR" ] || { echo "CANNOT CHECK: no k8s directory at $K8S_DIR" >&2; exit 2; }

rc=0
python3 - "$K8S_DIR" "$NOTEBOOK_DIR" "$LIST" <<'PY' || rc=$?
import collections, glob, json, os, re, sys

import yaml

k8s, nbdir, list_only = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
HOST = re.compile(r"\b([a-z0-9][a-z0-9-]*)\.([a-z0-9-]+)\.svc(?:\.cluster\.local)?\b")


def cannot(msg):
    print(f"CANNOT CHECK: {msg}", file=sys.stderr)
    raise SystemExit(2)


docs = []
for path in sorted(glob.glob(os.path.join(k8s, "**", "*.y*ml"), recursive=True)):
    try:
        with open(path, encoding="utf-8") as f:
            docs += [d for d in yaml.safe_load_all(f) if isinstance(d, dict)]
    except yaml.YAMLError as e:
        cannot(f"{os.path.relpath(path, k8s)} does not parse: {str(e).splitlines()[0]}")

notebooks = sorted(glob.glob(os.path.join(nbdir, "*.ipynb")))
if not notebooks:
    cannot(f"no notebooks found under {nbdir} — refusing to report a clean library")

uses = collections.defaultdict(set)   # (service, namespace) -> notebooks that dial it
for nb in notebooks:
    try:
        cells = json.load(open(nb, encoding="utf-8"))["cells"]
    except (ValueError, KeyError) as e:
        cannot(f"{os.path.basename(nb)} does not parse as a notebook: {e}")
    for c in cells:
        if c.get("cell_type") == "code":
            for m in HOST.finditer("".join(c.get("source") or [])):
                uses[(m.group(1), m.group(2))].add(os.path.basename(nb))

services = {(d["metadata"]["name"], d["metadata"].get("namespace")): (d.get("spec") or {}).get("selector") or {}
            for d in docs if d.get("kind") == "Service" and d.get("metadata")}
policies = [d for d in docs if d.get("kind") == "NetworkPolicy"]


def selects(policy, ns, selector):
    """True when this Ingress policy's podSelector picks the Service's pods (its labels are a subset of the selector)."""
    spec = policy.get("spec") or {}
    if policy["metadata"].get("namespace") != ns or "Ingress" not in spec.get("policyTypes", ["Ingress"]):
        return False
    want = (spec.get("podSelector") or {}).get("matchLabels") or {}
    return bool(want) and bool(selector) and set(want.items()) <= set(selector.items())


def admits_notebooks(policy):
    for rule in (policy.get("spec") or {}).get("ingress") or []:
        for src in rule.get("from") or []:
            ns = ((src.get("namespaceSelector") or {}).get("matchLabels") or {}).get("kubernetes.io/metadata.name")
            pods = (src.get("podSelector") or {}).get("matchLabels") or {}
            if ns == "jupyterhub" and (not pods or pods.get("component") == "singleuser-server"):
                return True
    return False


refused, counts = [], collections.Counter()
for (svc, ns), nbs in sorted(uses.items()):
    selector = services.get((svc, ns))
    if selector is None:
        counts["unchecked"] += 1
        if list_only:
            print(f"  unchecked  {svc}.{ns}  (no Service in git)  {', '.join(sorted(nbs))}")
        continue
    doors = [p for p in policies if selects(p, ns, selector)]
    blocking = [p["metadata"]["name"] for p in doors if not admits_notebooks(p)]
    verdict = "REFUSED" if blocking else ("admits" if doors else "open")
    counts[verdict] += 1
    if list_only:
        print(f"  {verdict:9s}  {svc}.{ns}  {', '.join(sorted(nbs))}" + (f"  ({', '.join(blocking)})" if blocking else ""))
    if blocking:
        refused.append((svc, ns, sorted(nbs), blocking))

if refused:
    print("NOTEBOOK FRONT DOORS REFUSE THE NOTEBOOKS:")
    for svc, ns, nbs, blocking in refused:
        print(f"  {', '.join(nbs)} dial {svc}.{ns}, but {', '.join(blocking)} does not admit the singleuser servers —"
              f" add a from-entry: namespaceSelector kubernetes.io/metadata.name=jupyterhub +"
              f" podSelector component=singleuser-server (and its pin in write-surface-netpol.bats)")
    raise SystemExit(1)
print(f"OK — {len(notebooks)} notebook(s) dial {len(uses)} in-cluster service(s): {counts['admits']} behind a front door"
      f" that admits them, {counts['open']} with no front door, {counts['unchecked']} not in git (Helm-made).")
PY
# 0 clean, 1 a refusal, anything else (2, a crash, python missing) could not check. `$?` read inside `if ! cmd` is the
# negation's status, not the command's — the first cut did that and reported every finding as exit 2.
case "$rc" in 0|1) exit "$rc" ;; *) exit 2 ;; esac
