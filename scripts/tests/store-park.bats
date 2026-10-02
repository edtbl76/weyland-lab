#!/usr/bin/env bats
# store-park.sh — wake / park the B199 default-parked stores by editing the ONE line in git that sets their replica
# count (Argo selfHeal reverts any live scale, so git is the only switch that sticks). Runs against COPIES of the real
# manifests (STORE_PARK_ROOT seam) so the repo is never touched by a test.

setup() {
  REAL="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s"
  T="$(mktemp -d)"
  mkdir -p "$T/data-mesh" "$T/superset"
  cp "$REAL/data-mesh/cassandra.yaml" "$REAL/data-mesh/mongodb.yaml" "$REAL/data-mesh/cockroachdb.yaml" "$T/data-mesh/"
  cp "$REAL/superset/superset-values.yaml" "$T/superset/"
  export STORE_PARK_ROOT="$T" STORE_PARK_NO_KUBECTL=1
  S="${BATS_TEST_DIRNAME}/../store-park.sh"
}
teardown() { rm -rf "$T"; }

replicas_of() {  # replicas_of <store> -> the replica count git sets
  case "$1" in
    superset-worker) python3 -c "import yaml;print(yaml.safe_load(open('$T/superset/superset-values.yaml'))['supersetWorker']['replicas']['replicaCount'])" ;;
    *) python3 -c "import yaml;print([d for d in yaml.safe_load_all(open('$T/data-mesh/$1.yaml')) if d and d.get('kind') in ('Deployment','StatefulSet')][0]['spec']['replicas'])" ;;
  esac
}

@test "every store starts parked (replicas 0) in git" {
  for s in cassandra mongodb cockroachdb superset-worker; do [ "$(replicas_of $s)" = 0 ] || { echo "$s"; return 1; }; done
}

@test "wake sets exactly that store to 1 and leaves the others parked" {
  run bash "$S" wake cockroachdb
  [ "$status" -eq 0 ]
  [ "$(replicas_of cockroachdb)" = 1 ]
  for s in cassandra mongodb superset-worker; do [ "$(replicas_of $s)" = 0 ]; done
  [[ "$output" == *"git"* ]]   # it tells you to push — it never pushes itself
}

@test "wake then park round-trips the file byte-for-byte" {
  cp "$T/data-mesh/mongodb.yaml" "$T/before.yaml"
  run bash "$S" wake mongodb
  [ "$status" -eq 0 ]
  [ "$(replicas_of mongodb)" = 1 ]          # it really woke (a missing script must not pass this test)
  run bash "$S" park mongodb
  [ "$status" -eq 0 ]
  [ "$(replicas_of mongodb)" = 0 ]
  cmp "$T/before.yaml" "$T/data-mesh/mongodb.yaml"
}

@test "the superset worker's nested Helm value is switched, not a stray replicas line" {
  run bash "$S" wake superset-worker
  [ "$status" -eq 0 ]
  [ "$(replicas_of superset-worker)" = 1 ]
  python3 -c "import yaml;d=yaml.safe_load(open('$T/superset/superset-values.yaml'));assert d['supersetWorker']['replicas']['enabled'] is True"
}

@test "wake all wakes every parked store" {
  run bash "$S" wake all
  [ "$status" -eq 0 ]
  for s in cassandra mongodb cockroachdb superset-worker; do [ "$(replicas_of $s)" = 1 ] || { echo "$s"; return 1; }; done
}

@test "waking an already-awake store is a no-op, not an error" {
  bash "$S" wake cassandra
  run bash "$S" wake cassandra
  [ "$status" -eq 0 ]
  [[ "$output" == *"already"* ]]
}

@test "an unknown store is refused with the valid list (exit 2), nothing edited" {
  cp -r "$T" "$T.snap"
  run bash "$S" wake clickhouse
  [ "$status" -eq 2 ]
  [[ "$output" == *"cassandra"* && "$output" == *"superset-worker"* ]]
  diff -r "$T.snap/data-mesh" "$T/data-mesh"; rm -rf "$T.snap"
}

@test "a manifest whose replica line is missing fails closed (exit 2)" {
  sed -i 's/^  replicas: 0$/  replicaz: 0/' "$T/data-mesh/cassandra.yaml"
  run bash "$S" wake cassandra
  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot find"* ]]
}

@test "status lists each store with what git sets" {
  bash "$S" wake mongodb
  run bash "$S" status
  [ "$status" -eq 0 ]
  [[ "$output" == *"mongodb"*"git=1"* ]]
  [[ "$output" == *"cassandra"*"git=0"* ]]
}

@test "wait refuses (exit 2) when it cannot ask the cluster, never a false Ready" {
  run bash "$S" wait cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"cluster"* ]]
}

# wait must SAY what it is waiting for — silent polling read as a hang in the first live drill (2026-10-01).
@test "wait prints progress while the cluster catches up, then reports Ready" {
  mkdir -p "$T/bin"; echo 0 > "$T/n"
  cat > "$T/bin/kubectl" <<'STUB'
#!/usr/bin/env bash
n=$(cat "$STUB_N"); echo $((n+1)) > "$STUB_N"
if [ "$n" -lt 2 ]; then printf '0/'; else printf '1/1'; fi
STUB
  chmod +x "$T/bin/kubectl"
  bash "$S" wake cockroachdb >/dev/null
  run env -u STORE_PARK_NO_KUBECTL PATH="$T/bin:$PATH" STUB_N="$T/n" STORE_PARK_POLL=0 STORE_PARK_PROGRESS_EVERY=1 bash "$S" wait cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"waiting"*"git wants 1"*"desired=0"* ]]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "wake points at the sync that skips Argo's ~3 min poll" {
  run bash "$S" wake cassandra
  [[ "$output" == *"argocd app sync data-mesh"* ]]
  run bash "$S" wake superset-worker
  [[ "$output" == *"argocd app sync superset"* ]]
}
