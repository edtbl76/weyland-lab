#!/usr/bin/env bats
# No port-forward guard (2026-10-17) — the lab reaches in-cluster services by LAN NodePort ONLY (AGENTS.md).
#
# WHY THIS EXISTS: the rule lived in one agent's memory and one runbook line, so 40-odd docs and four pieces of code kept
# telling people (and agents) to `kubectl port-forward` — a runbook written a week before the rule became absolute was
# copied forward as recently as 2026-10-17. The guard fails any port-forward COMMAND in the repo's instructions and
# code. Prose that names the practice in order to reject it ("the lab never port-forwards") is not a command and must
# pass, or the guard would punish the rule's own statement.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-no-port-forward.sh"
  ROOT="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$ROOT/docs/runbooks" "$ROOT/scripts" "$ROOT/nodes/k8s"
  echo "# clean" >"$ROOT/docs/runbooks/clean.md"
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

@test "a clean tree passes and says how much it scanned" {
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
  [[ "$output" == *"file(s)"* ]]
}

@test "a kubectl port-forward to a service in a runbook fails and names file:line" {
  printf 'line one\nkubectl -n monitoring port-forward svc/prometheus 9090:9090\n' >"$ROOT/docs/runbooks/obs.md"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"docs/runbooks/obs.md:2"* ]]
}

@test "a port-forward in a shell script fails (code, not only docs)" {
  printf '#!/bin/sh\nkubectl port-forward -n "$1" "svc/$2" "$3:$4" &\n' >"$ROOT/scripts/entry.sh"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"scripts/entry.sh:2"* ]]
}

@test "a port-forward with only a port mapping (no resource) still fails" {
  printf 'kubectl port-forward 8080:443\n' >"$ROOT/docs/runbooks/argo.md"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"docs/runbooks/argo.md:1"* ]]
}

@test "the python kubernetes client's portforward call fails" {
  printf 'from kubernetes.stream import portforward\npf = portforward(api.connect_get_namespaced_pod_portforward, "p", "ns", ports="5432")\n' >"$ROOT/scripts/pf.py"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"scripts/pf.py"* ]]
}

@test "an instruction in prose to port-forward fails, even with no command spelled out" {
  printf 'IntelliJ → Cassandra driver, port-forward the `cassandra` svc `9042`.\n' >"$ROOT/docs/runbooks/q1.md"
  printf 'Most are reachable from IntelliJ via the k8s-plugin port-forward.\n' >"$ROOT/docs/runbooks/q2.md"
  printf 'against 127.0.0.1:5432 after **port-forwarding the svc via the k8s plugin**\n' >"$ROOT/docs/runbooks/q3.md"
  printf 'IntelliJ Kubernetes plugin → Services → timescaledb → Forward Ports → 5432\n' >"$ROOT/docs/runbooks/q4.md"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"docs/runbooks/q1.md:1"* ]]
  [[ "$output" == *"docs/runbooks/q2.md:1"* ]]
  [[ "$output" == *"docs/runbooks/q3.md:1"* ]]
  [[ "$output" == *"docs/runbooks/q4.md:1"* ]]
}

@test "prose that rejects port-forwarding is not a command and passes" {
  printf 'The lab never port-forwards (NodePorts only).\nNo `kubectl port-forward` needed: use 192.168.1.243:30980.\nReach it at the NodePort and NOT via port-forward.\nnever port-forward the svc; use its NodePort\nNo `kubectl port-forward`, no IntelliJ k8s "Forward Ports", no Python client\n' >"$ROOT/docs/runbooks/rule.md"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "a manifest comment that quotes a port-forward command fails too" {
  printf '# replaces the ad-hoc `kubectl port-forward svc/woodpecker-server 8000:80`\nkind: Service\n' >"$ROOT/nodes/k8s/lan.yaml"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"nodes/k8s/lan.yaml:1"* ]]
}

@test "vendored dependency trees are not scanned (SwiftPM .build, node_modules)" {
  mkdir -p "$ROOT/golden-paths/swift/app/.build/checkouts/dep" "$ROOT/node_modules/x"
  printf 'kubectl port-forward deployment/http-server 8080:8080\n' >"$ROOT/golden-paths/swift/app/.build/checkouts/dep/README.md"
  printf 'kubectl port-forward svc/x 80:80\n' >"$ROOT/node_modules/x/README.md"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "the backlog's history is not scanned (DONE records describe what was, not what to do)" {
  printf -- '- **B57** — DONE: replaced `kubectl port-forward svc/woodpecker-server 8000:80` with a NodePort\n' >"$ROOT/docs/backlog.md"
  SCAN_ROOT="$ROOT" run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "scanning nothing is a could-not-run (exit 2), not a clean pass" {
  SCAN_ROOT="$BATS_TEST_TMPDIR/empty" run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"nothing"* ]]
}
