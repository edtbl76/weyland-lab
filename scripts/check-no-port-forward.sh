#!/usr/bin/env bash
# check-no-port-forward.sh — repo guard: no port-forward COMMANDS in the repo's instructions or code (2026-10-17).
#
# WHY THIS EXISTS: the lab reaches in-cluster services by LAN NodePort ONLY (AGENTS.md) — never `kubectl port-forward`,
# never IntelliJ's k8s forwarding, never the Python client's portforward. The rule lived in one agent's memory and one
# runbook line, so ~40 docs and four pieces of code (store-park.sh, both trainer entrypoints) kept instructing it, and
# a 2026-09-05 runbook block was copied forward on 2026-10-17 because nothing failed. A port-forward is a background
# process with a teardown burden that silently dies; a NodePort is a standing endpoint the NetworkPolicy can pin.
#
# WHAT COUNTS: `port-forward` followed (before a backtick, `)` or end of line) by a resource (`svc/x`, `pod/x`,
# `deploy/x`, …) or a port mapping (`9090:9090`, `"$3:$4"`), or a call to the Python kubernetes client's
# `portforward(` / `connect_get_namespaced_pod_portforward`. Also an INSTRUCTION in prose with no command spelled out
# ("port-forward the `cassandra` svc", "via the k8s-plugin port-forward", "after port-forwarding the svc") — the query
# cookbooks taught it that way. Prose that names the practice to reject it ("the lab never port-forwards", "no
# `kubectl port-forward` needed") passes.
#
# NOT SCANNED: docs/backlog.md (DONE records describe what was, not what to do), generated/vendored trees, notebooks
# (.ipynb outputs are recorded data — a RAG answer quoting a port-forward is not an instruction), and this guard + its
# test, which must spell the pattern.
#
# Usage: bash scripts/check-no-port-forward.sh        SCAN_ROOT overrides the repo root (tests).
# Exit:  0 none found · 1 port-forward command(s), each as file:line · 2 could not run (no python3, nothing scanned)
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCAN_ROOT="${SCAN_ROOT:-$REPO_ROOT}"

command -v python3 >/dev/null || { echo "check-no-port-forward: python3 not found" >&2; exit 2; }

python3 - "$SCAN_ROOT" <<'PY'
import os, re, sys

root = sys.argv[1]
EXTS = {".md", ".sh", ".bash", ".py", ".yaml", ".yml", ".toml"}
SKIP_DIRS = {".git", "node_modules", "site-techdocs", "aidlc-docs", ".venv", "venv", "__pycache__", ".claude"}
SKIP_FILES = {"docs/backlog.md", "scripts/check-no-port-forward.sh", "scripts/tests/no-port-forward.bats"}

RESOURCE = re.compile(r"^(svc|service|services|pod|pods|po|deploy|deployment|deployments|sts|statefulset|"
                      r"statefulsets|rs|replicaset|replicasets)/\S+")
MAPPING = re.compile(r"^(\d{1,5}|\$\{?\w+\}?)?:(\d{1,5}|\$\{?\w+\}?)$")
PY_CALL = re.compile(r"\bportforward\s*\(|connect_get_namespaced_pod_portforward")
PF = re.compile(r"port-forward")
# An imperative/route in prose: "port-forward(ing) the|a ...", "via|over the [k8s|k8s-plugin|kubectl|IntelliJ] port-forward",
# IntelliJ's "Forward Ports" action as a menu step ("→ Forward Ports"; naming the action to reject it passes).
NEGATED = re.compile(r"\b(not|never|no|without)\s*$", re.I)
INSTRUCTION = re.compile(r"\bport-forward(ing)?\s+(the|a)\b|\b(via|over|through)\s+(the\s+|a\s+)?"
                         r"((k8s|kubectl|intellij)[- ]?(plugin\s+)?|k8s-plugin\s+)?port-forward|→\s*Forward Ports", re.I)

def is_command(line):
    for m in PF.finditer(line):
        tail = re.split(r"[`)]", line[m.end():], maxsplit=1)[0]
        for tok in tail.split():
            tok = tok.strip("\"'")
            if RESOURCE.match(tok) or MAPPING.match(tok):
                return True
    if PY_CALL.search(line):
        return True
    # an instruction counts unless it is negated just before ("NOT via port-forward", "never port-forward the svc")
    return any(not NEGATED.search(line[max(0, m.start() - 12):m.start()]) for m in INSTRUCTION.finditer(line))

scanned, hits = 0, []
for dp, dns, fns in os.walk(root):
    dns[:] = [d for d in dns if d not in SKIP_DIRS]
    for fn in fns:
        path = os.path.join(dp, fn)
        rel = os.path.relpath(path, root)
        if rel in SKIP_FILES:
            continue
        if os.path.splitext(fn)[1] not in EXTS and not fn.startswith("Dockerfile") and fn != "AGENTS.md":
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            continue
        scanned += 1
        for n, line in enumerate(lines, 1):
            if is_command(line):
                hits.append(f"{rel}:{n}: {line.strip()[:160]}")

if scanned == 0:
    print(f"no-port-forward: scanned nothing under {root} — refusing to report clean (exit 2)")
    sys.exit(2)
if hits:
    print("\n".join(hits))
    print(f"FAIL — {len(hits)} port-forward command(s). The lab is NodePorts only: point the client at the service's "
          "LAN NodePort (192.168.1.243:<nodePort>), or run the work in-cluster (a Job, kubectl exec).")
    sys.exit(1)
print(f"no-port-forward: OK — no port-forward commands in {scanned} file(s).")
PY
