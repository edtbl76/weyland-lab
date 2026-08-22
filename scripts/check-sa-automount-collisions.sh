#!/usr/bin/env bash
# B95 — guard against the security-hardening collision that silently broke lancedb-sync (2026-07-20): a workload's
# RBAC was bound to a `default` ServiceAccount, then automount was disabled on that same `default` SA → the pod held
# the RBAC permissions with NO token to authenticate (ConfigException: Service token file does not exist), undetected
# for weeks because the op only ran on a sensor. This FAILS if ANY (Cluster)RoleBinding in the repo binds a `default`
# ServiceAccount — the anti-pattern. A workload that calls the k8s API must use a DEDICATED SA (automount on), never
# `default`. Cheap static tripwire; catches the whole class before it ships. Mirrors scripts/check-app-registry.sh.
# Run from anywhere; script is in the repo-root ./scripts. See k8s/rbac-default-sa-noautomount.yaml.
set -euo pipefail
. "$(dirname "$0")/lib/common.sh"
here="$REPO_ROOT"
python3 - "$here" <<'PY'
import sys, os, yaml
root = sys.argv[1]
findings = []
for dirpath, dirs, files in os.walk(root):
    if "/.git" in dirpath or "/node_modules" in dirpath:
        continue
    for fn in files:
        if not fn.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(dirpath, fn)
        try:
            with open(path) as fh:
                docs = list(yaml.safe_load_all(fh))
        except Exception:
            continue   # unparseable (Helm template / non-strict yaml) — not our concern
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") not in ("RoleBinding", "ClusterRoleBinding"):
                continue
            meta = doc.get("metadata") or {}
            for subj in (doc.get("subjects") or []):
                if isinstance(subj, dict) and subj.get("kind") == "ServiceAccount" and subj.get("name") == "default":
                    ns = subj.get("namespace") or meta.get("namespace") or "?"
                    findings.append((os.path.relpath(path, root), doc.get("kind"), meta.get("name"), ns))
if findings:
    print("SA-automount COLLISION RISK — a (Cluster)RoleBinding binds a `default` ServiceAccount (B95 anti-pattern):")
    for f, kind, name, ns in findings:
        print(f"  {f}: {kind}/{name} -> ServiceAccount/{ns}/default")
    print("Fix: give the workload a DEDICATED ServiceAccount (automountServiceAccountToken: true) + repoint the")
    print("binding's subject. NEVER re-enable automount on `default`. See k8s/rbac-default-sa-noautomount.yaml.")
    sys.exit(1)
print("OK — no (Cluster)RoleBinding binds a `default` ServiceAccount (no automount-hardening collision).")
PY
