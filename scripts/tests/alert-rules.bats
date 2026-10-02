#!/usr/bin/env bats
# promtool unit tests for alert rules — the REAL rule text, extracted from the PrometheusRule manifests, against
# scenarios built from measured data (B199, 2026-10-02). `promtool check rules` proves syntax; only `promtool test rules`
# proves an alert fires when it should and stays silent when it should not. promtool comes from Alpine's `prometheus`
# package (CI's apk line); if it is missing the test FAILS — a skipped behaviour test is a pass that proved nothing.
#
# Expected alerts carry their annotations so promtool compares them too; the bats wrapper copies each rule's real
# annotations into the expectations, so editing an alert's wording never breaks this test, while changing its
# condition or labels does. A TEMPLATED annotation ({{ $value }}, {{ $labels.x }}) is compared rendered, so the
# scenario states its rendered text (exp_annotations in the fixture) and that wins over the copied template.

setup() {
  K="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s"
  T="$(mktemp -d)"
}
teardown() { rm -rf "$T"; }

@test "promtool is available (fail, never skip, when it is not)" {
  run command -v promtool
  [ "$status" -eq 0 ] || { echo "promtool missing: apk add prometheus"; return 1; }
}

# promtool_test <fixture> <manifest under k8s/>... — extract the real rules from the manifests, run the fixture.
promtool_test() {
  local fixture="$1"; shift
  python3 - "$K" "$T" "${BATS_TEST_DIRNAME}/fixtures/alert-rules/$fixture" "$@" <<'PY' || return 1
import sys, yaml
K, T, test_path = sys.argv[1:4]
files = sys.argv[4:]
groups, ann = [], {}
for f in files:
    for d in yaml.safe_load_all(open(f"{K}/{f}")):
        if d and d.get("kind") == "PrometheusRule":
            for g in d["spec"]["groups"]:
                g = dict(g, name=f"{f}/{g['name']}")
                groups.append(g)
                for r in g["rules"]:
                    if "alert" in r:
                        ann[r["alert"]] = r.get("annotations", {})
yaml.safe_dump({"groups": groups}, open(f"{T}/rules.yaml", "w"))
t = yaml.safe_load(open(test_path))
for case in t["tests"]:
    for art in case["alert_rule_test"]:
        if art["alertname"] not in ann:
            sys.exit(f"alert {art['alertname']} not found in the manifests")
        for ea in art["exp_alerts"]:
            # live rule annotations, overridden by any RENDERED values the scenario states (templated fields)
            ea["exp_annotations"] = {**ann[art["alertname"]], **ea.get("exp_annotations", {})}
yaml.safe_dump(t, open(f"{T}/test.yaml", "w"), sort_keys=False)
PY
  run promtool check rules "$T/rules.yaml"
  [ "$status" -eq 0 ] && [[ "$output" == *SUCCESS* ]] || { echo "$output"; return 1; }
  run promtool test rules "$T/test.yaml"
  [ "$status" -eq 0 ] && [[ "$output" == *SUCCESS* ]] || { echo "$output" | tail -30; return 1; }
}

@test "the node-memory and parked-store alerts behave as measured (promtool test rules)" {
  promtool_test node-and-parked.test.yaml monitoring/node-memory-alerts.yaml data-mesh/cassandra.yaml \
    data-mesh/mongodb.yaml data-mesh/cockroachdb.yaml data-mesh/superset-alerts.yaml
}

@test "the operator sweep alerts only when deferral outlasts an eval run (promtool test rules)" {
  promtool_test operator-sweep.test.yaml weyland-operator/prometheusrule.yaml
}

@test "the two spend alerts partition paid egress without double-counting (promtool test rules)" {
  promtool_test spend.test.yaml litellm/prometheusrule.yaml bifrost/prometheusrule.yaml
}
