#!/usr/bin/env bash
# B82 — Application-registry completeness (drift guard). Every deployed Argo CD Application must be ACCOUNTED FOR in
# the canonical registry (services/weyland-dagster/weyland_pipeline/applications.yaml) — either as an `applications:`
# entry (a component) or an `excluded:` entry (a store / plumbing). An Argo app in neither = drift → fix the registry.
#
# Run from anywhere in the repo. Exit 1 (+ lists the unaccounted apps) on drift, 0 when clean.
set -euo pipefail
here="$(cd "$(dirname "$0")/../nodes/mother/lab/weyland-platform" && pwd)"   # this script lives in repo-root ./scripts; the assets are under the platform dir
argo_dir="$here/k8s/argocd/applications"
registry="$here/services/weyland-dagster/weyland_pipeline/applications.yaml"

python3 - "$argo_dir" "$registry" <<'PY'
import sys, glob, os, re, yaml

argo_dir, registry = sys.argv[1], sys.argv[2]

# Argo app names (metadata.name of every Application manifest)
argo = set()
# glob applications/ AND its parent (k8s/argocd) so the root app-of-apps (weyland-root at k8s/argocd/root-app.yaml,
# NOT under applications/) is COUNTED — the guard was silently ignoring the 74th deployed app.
for f in glob.glob(os.path.join(argo_dir, "*.yaml")) + glob.glob(os.path.join(os.path.dirname(argo_dir), "*.yaml")):
    for doc in yaml.safe_load_all(open(f)):
        if isinstance(doc, dict) and doc.get("kind") == "Application":
            n = doc.get("metadata", {}).get("name")
            if n:
                argo.add(n)

# Everything the registry accounts for: applications[].key + .port_component, and excluded[].key
reg = yaml.safe_load(open(registry))
accounted = set()
for a in reg.get("applications", []):
    accounted.add(a["key"]); accounted.add(a.get("port_component", a["key"]))
for e in reg.get("excluded", []):
    accounted.add(e["key"])

# Known Argo-name -> registry-key aliases (the deliberate renames)
ALIAS = {
    "dagster": "weyland-dagster", "code-quality": "scan-suite", "flink-operator": "flink",
    "kube-prometheus-stack": "grafana", "rag-index-weyland": "rag-index",
}
# GitOps bootstrap Applications — real Argo apps but NOT deployed components, so they carry no registry entry.
INFRA = {"weyland-root"}   # the app-of-apps root (syncs k8s/argocd/applications/)
unaccounted = sorted(a for a in argo if a not in INFRA and a not in accounted and ALIAS.get(a, a) not in accounted)

print(f"Argo apps: {len(argo)} (incl. {len(INFRA & argo)} GitOps bootstrap)  |  registry-accounted keys: {len(accounted)}")
if unaccounted:
    print("❌ UNACCOUNTED Argo apps (add to applications: or excluded: in the registry):")
    for a in unaccounted:
        print(f"   - {a}")
    sys.exit(1)
print("✅ every deployed Argo app is accounted for in the registry")
PY
