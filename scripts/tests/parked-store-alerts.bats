#!/usr/bin/env bats
# B199 (2026-10-01): stores parked by default (replicas: 0 committed to git) keep a Down alert that compares what is
# RUNNING with what git WANTS — never `== 0`. An `== 0` alert on a parked store fires forever (the noise that buried
# 13 days of no MinIO backup, 2026-09-25); comparing to the desired count stays silent while parked and still pages
# the moment a store git wants running is not. Behaviour proven with promtool unit tests (parked / broken / running)
# — see docs/runbooks/node-capacity.md § Parked stores. Undo the parking with B134 (EMA-195) when hardware lands.

setup() {
  K="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s"
}

# expr_of <file> <alert> -> the alert's PromQL expression
expr_of() {
  python3 - "$1" "$2" <<'PY'
import sys, yaml
for d in yaml.safe_load_all(open(sys.argv[1])):
    if d and d.get("kind") == "PrometheusRule":
        for g in d["spec"]["groups"]:
            for r in g["rules"]:
                if r.get("alert") == sys.argv[2]:
                    print(r["expr"])
PY
}

@test "each parked store's Down alert compares running to DESIRED replicas, never == 0" {
  for pair in "data-mesh/cassandra.yaml:CassandraDown:kube_statefulset_replicas" \
              "data-mesh/mongodb.yaml:MongodbDown:kube_deployment_spec_replicas" \
              "data-mesh/cockroachdb.yaml:CockroachdbDown:kube_deployment_spec_replicas" \
              "data-mesh/superset-alerts.yaml:SupersetWorkerDown:kube_deployment_spec_replicas"; do
    IFS=: read -r f alert desired <<<"$pair"
    run expr_of "$K/$f" "$alert"
    [ "$status" -eq 0 ]
    [ -n "$output" ] || { echo "$alert not found in $f"; return 1; }
    [[ "$output" == *"$desired"* ]] || { echo "$alert does not compare to $desired: $output"; return 1; }
    [[ "$output" != *"== 0"* ]] || { echo "$alert still fires on == 0: $output"; return 1; }
  done
}
