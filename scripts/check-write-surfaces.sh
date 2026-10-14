#!/usr/bin/env bash
# Write-surface guard (B209, 2026-10-14) — every deployed service that can CHANGE STATE has a front door.
#
# WHY THIS EXISTS: B207 enforced the act guard on three tool-server endpoints. Around them, the Dagster API (launch any
# job), store-scaler (scale the data stores) and the Realm (paid Haiku, a write-capable Bifrost key) took writes from
# any pod, and nothing in the repo could tell a guarded surface from an open one. This guard makes every deployed
# service DECLARE whether it takes writes, and makes every write surface say what refuses everyone else.
#
# THE CONTRACT (declare and account, like check-onboarding-completeness.sh):
#   every `deployed: true` entry in applications.yaml declares a boolean `writes`. A `writes: true` service passes when
#   ONE of these holds:
#     policy        a NetworkPolicy (podSelector) or Istio AuthorizationPolicy (selector) in k8s/ selects its pods by
#                   `app` or `app.kubernetes.io/name` = <pod_app or key>. Traefik forward-auth on the ingress does
#                   NOT count: a pod can call the ClusterIP directly.
#     front_door    a stated, non-empty reason the app itself authenticates writes (a login, an admin token, S3
#                   signatures, Ranger on the SQL user).
#     accepted_gap  a known open write surface, tracked: it must cite a backlog item (B<n>). Listed every run, so the
#                   debt stays visible until its fix lands.
#
#   usage: scripts/check-write-surfaces.sh [--list]     --list prints every deployed service and its verdict
#
# EXIT CODES: 0 every write surface has a front door or a tracked gap · 1 a defect, named (an open write surface, an
#   undeclared or non-boolean `writes`, a gap with no backlog item) · 2 could not check (registry unreadable or empty,
#   or no NetworkPolicy/AuthorizationPolicy parsed at all — an empty scan is not a clean estate).
#
# INPUTS (fixtures in tests; a set env var overrides): REGISTRY_FILE (applications.yaml), K8S_DIR (the manifests).
# Runbook: docs/runbooks/write-surfaces.md. Tests: scripts/tests/write-surfaces.bats.
set -euo pipefail

if [ -r "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh" ]; then
  # shellcheck source=scripts/lib/common.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
fi
PLATFORM_DIR="${PLATFORM_DIR:-nodes/mother/lab/weyland-platform}"
REGISTRY_FILE="${REGISTRY_FILE:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline/applications.yaml}"
K8S_DIR="${K8S_DIR:-$PLATFORM_DIR/k8s}"

LIST=0
case "${1:-}" in
  "") ;;
  --list) LIST=1 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

python3 - "$REGISTRY_FILE" "$K8S_DIR" "$LIST" <<'PY'
import glob, re, sys
import yaml

reg_f, k8s_dir, listmode = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
try:
    apps = (yaml.safe_load(open(reg_f)) or {}).get("applications")
except Exception as e:
    print(f"CANNOT RUN — registry unreadable ({reg_f}): {str(e)[:120]}", file=sys.stderr); sys.exit(2)
if not apps:
    print(f"CANNOT RUN — no `applications` in registry {reg_f}; refusing to report a clean estate", file=sys.stderr)
    sys.exit(2)

covered = {}   # app label -> [policy names]
for f in glob.glob(f"{k8s_dir}/**/*.yaml", recursive=True):
    try:
        docs = list(yaml.safe_load_all(open(f)))
    except Exception:
        continue   # a manifest this guard can't parse is the yaml-lint lane's finding, not this one's
    for d in docs:
        if not isinstance(d, dict):
            continue
        kind, spec = d.get("kind"), d.get("spec") or {}
        if kind == "NetworkPolicy":
            labels = (spec.get("podSelector") or {}).get("matchLabels") or {}
        elif kind == "AuthorizationPolicy":
            labels = (spec.get("selector") or {}).get("matchLabels") or {}
        else:
            continue
        # `app` (the lab's own manifests) or `app.kubernetes.io/name` (Helm charts, e.g. OpenSearch).
        for name in {labels.get("app"), labels.get("app.kubernetes.io/name")} - {None}:
            covered.setdefault(name, []).append(f"{kind}/{(d.get('metadata') or {}).get('name', '?')}")
if not covered:
    print(f"CANNOT RUN — no NetworkPolicy or AuthorizationPolicy selecting an `app` label found under {k8s_dir}; "
          "an empty scan is not a clean estate", file=sys.stderr)
    sys.exit(2)

bad, rows, gaps = [], [], []
deployed = [a for a in apps if a.get("deployed") is True]
for a in deployed:
    key = a.get("key", "<no-key>")
    w = a.get("writes")
    if "writes" not in a:
        bad.append(f"{key}: does not declare writes (true|false) — every deployed service must say whether it takes writes")
        continue
    if not isinstance(w, bool):
        bad.append(f"{key}: writes must be a boolean, got {w!r}")
        continue
    if not w:
        rows.append((key, "read-only", ""))
        continue
    pols = covered.get(a.get("pod_app") or key)
    door = str(a.get("front_door") or "").strip()
    gap = str(a.get("accepted_gap") or "").strip()
    if pols:
        rows.append((key, "policy", ", ".join(pols)))
    elif door:
        rows.append((key, "front_door", door))
    elif gap:
        if not re.search(r"\bB\d+\b", gap):
            bad.append(f"{key}: accepted_gap must cite the backlog item that fixes it (B<n>): {gap!r}")
            continue
        rows.append((key, "ACCEPTED GAP", gap)); gaps.append((key, gap))
    else:
        bad.append(f"{key}: takes writes and has no front door — add a NetworkPolicy/AuthorizationPolicy selecting "
                   f"app={a.get('pod_app') or key}, a `front_door:` reason, or a tracked `accepted_gap: B<n> …`")

if listmode:
    for key, verdict, detail in sorted(rows):
        print(f"  {key:28} {verdict:13} {detail[:110]}")
for key, gap in gaps:
    print(f"  tracked gap: {key} — {gap}")
if bad:
    print("WRITE SURFACES WITHOUT A FRONT DOOR:")
    for b in bad:
        print(f"  {b}")
    sys.exit(1)
n_w = sum(1 for _, v, _ in rows if v != "read-only")
print(f"OK — {len(deployed)} deployed service(s): {n_w} take writes, each with a policy, a front door or a tracked "
      f"gap ({len(gaps)} gap(s)); {len(deployed) - n_w} read-only.")
PY
