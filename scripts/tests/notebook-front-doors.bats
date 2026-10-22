#!/usr/bin/env bats
# scripts/check-notebook-front-doors.sh (2026-10-21) — every in-cluster service a JupyterHub notebook dials must admit the
# singleuser servers through any front-door NetworkPolicy that selects it. B211's front doors refused the notebooks for a
# week (Trino, Valkey) and only the owner's end-to-end notebook batch found it. These pin the guard's decisions with fixture
# trees; the first case runs it on the real repo.

setup() {
  T="$BATS_TEST_TMPDIR"
  GUARD="$BATS_TEST_DIRNAME/../check-notebook-front-doors.sh"
  mkdir -p "$T/k8s/data-mesh" "$T/nb"
}

# nb <file> <host> — a notebook whose one code cell dials <host>
nb() {
  printf '{"cells":[{"cell_type":"code","source":["conn = connect(\\"%s\\", 8080)\\n"]}],"metadata":{},"nbformat":4,"nbformat_minor":5}\n' "$2" > "$T/nb/$1"
}
svc() { # svc <name> <ns> <app label>
  printf 'apiVersion: v1\nkind: Service\nmetadata: {name: %s, namespace: %s}\nspec:\n  selector: {app: %s}\n  ports: [{port: 8080}]\n---\n' "$1" "$2" "$3" >> "$T/k8s/data-mesh/svc.yaml"
}
pol() { # pol <name> <ns> <app label> <from-entries yaml (indented 4)>
  printf 'apiVersion: networking.k8s.io/v1\nkind: NetworkPolicy\nmetadata: {name: %s, namespace: %s}\nspec:\n  podSelector: {matchLabels: {app: %s}}\n  policyTypes: [Ingress]\n  ingress:\n  - from:\n%s\n---\n' "$1" "$2" "$3" "$4" >> "$T/k8s/data-mesh/pol.yaml"
}
run_fixture() { CM_K8S_DIR="$T/k8s" NOTEBOOK_DIR="$T/nb" run bash "$GUARD" "$@"; }

SINGLEUSER='    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: jupyterhub}}
      podSelector: {matchLabels: {component: singleuser-server}}'

@test "the real repo passes: every policied service a notebook dials admits the singleuser servers" {
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == "OK — "* ]]
}

@test "a front door that does not admit the notebooks FAILS, naming the notebook, the host and the policy" {
  nb 20_q.ipynb trino.data-mesh.svc.cluster.local
  svc trino data-mesh trino
  pol trino-front-door-only data-mesh trino '    - podSelector: {matchLabels: {app: superset}}'
  run_fixture
  [ "$status" -eq 1 ]
  [[ "$output" == *"20_q.ipynb"* && "$output" == *"trino.data-mesh"* && "$output" == *"trino-front-door-only"* ]]
}

@test "a front door that admits the singleuser servers passes" {
  nb 20_q.ipynb trino.data-mesh.svc.cluster.local
  svc trino data-mesh trino
  pol trino-front-door-only data-mesh trino "$SINGLEUSER"
  run_fixture
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "a policy admitting the whole jupyterhub namespace counts as admitting the notebooks" {
  nb 20_q.ipynb trino.data-mesh.svc
  svc trino data-mesh trino
  pol trino-front-door-only data-mesh trino '    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: jupyterhub}}'
  run_fixture
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "a service with no front-door policy is open, not a failure" {
  nb 30_q.ipynb qdrant.data-mesh.svc.cluster.local
  svc qdrant data-mesh qdrant
  run_fixture
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "a policy that selects a DIFFERENT workload is not this service's front door" {
  nb 20_q.ipynb trino.data-mesh.svc.cluster.local
  svc trino data-mesh trino
  pol other-door data-mesh superset '    - podSelector: {matchLabels: {app: cube}}'
  run_fixture
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "no notebooks found is exit 2, never a clean pass over nothing" {
  svc trino data-mesh trino
  run_fixture
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK"* ]]
}

@test "an unparseable manifest is exit 2, named" {
  nb 20_q.ipynb trino.data-mesh.svc.cluster.local
  printf 'kind: Service\n  bad: [indent\n' > "$T/k8s/data-mesh/broken.yaml"
  run_fixture
  [ "$status" -eq 2 ]
  [[ "$output" == *"broken.yaml"* ]]
}
