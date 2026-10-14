#!/usr/bin/env bats
# B209 (2026-10-14) — the write surfaces' front doors. NetworkPolicies, enforced by k3s's built-in controller (an Istio
# AuthorizationPolicy can't see the unmeshed callers involved: Traefik, port-agent, store-scaler itself).
#   - dagster-webserver (GraphQL launches ANY job): only dagster-user-code, weyland-tool-server and Traefik (the UI).
#   - store-scaler (/scale scales the data stores): only the port-agent namespace.
#   - realm-of-agents (spends paid Haiku; holds a Bifrost key): the operator, dagster-user-code, the a2a-inspector,
#     Traefik (now behind Keycloak forward-auth), Prometheus and the api-drift job.
# A NetworkPolicy fails SILENTLY on a label typo (it selects nothing, so the surface stays open, or it locks a
# legitimate caller out), so each policy's target and same-namespace sources are cross-checked against the real
# Deployments' pod-template labels, and the exact allowed set is pinned: adding a caller is a deliberate change here.

setup() {
  P="$BATS_TEST_DIRNAME/../../nodes/mother/lab/weyland-platform/k8s"
}

# check <namespace> <policy> <target app label> <port> <expected sources...>
# A source is `app=<label>` (same namespace, must match a Deployment in git) or `ns=<namespace>[,<k>=<v>]` (another
# namespace, optionally narrowed to pods with one label; those workloads are Helm-installed, not in this repo).
check() {
  python3 - "$P" "$@" <<'PY'
import sys, yaml, glob
p, ns, name, target, port, *expected = sys.argv[1:]
docs = [d for f in glob.glob(f"{p}/**/*.yaml", recursive=True) for d in yaml.safe_load_all(open(f)) if isinstance(d, dict)]
pol = next((d for d in docs if d.get("kind") == "NetworkPolicy" and d["metadata"]["name"] == name
            and d["metadata"].get("namespace") == ns), None)
assert pol, f"no NetworkPolicy {ns}/{name}"
deps = {d["metadata"]["name"]: d["spec"]["template"]["metadata"]["labels"] for d in docs
        if d.get("kind") == "Deployment" and d["metadata"].get("namespace") == ns}
spec = pol["spec"]
assert spec["podSelector"]["matchLabels"] == {"app": target}, spec["podSelector"]
assert deps.get(target, {}).get("app") == target, f"no {ns} Deployment {target} with pod label app={target}"
assert spec["policyTypes"] == ["Ingress"], f"policyTypes {spec['policyTypes']}"
(rule,) = spec["ingress"]
assert rule["ports"] == [{"protocol": "TCP", "port": int(port)}], rule["ports"]
got = []
for f in rule["from"]:
    nsel = (f.get("namespaceSelector") or {}).get("matchLabels")
    psel = (f.get("podSelector") or {}).get("matchLabels") or {}
    assert set(f) <= {"namespaceSelector", "podSelector"} and (nsel or psel), f"unexpected from-entry {f}"
    if nsel is None:
        assert list(psel) == ["app"], f"same-namespace sources select on app= only: {psel}"
        a = psel["app"]
        assert deps.get(a, {}).get("app") == a, f"allowed source {a} has no {ns} Deployment with pod label app={a}"
        got.append(f"app={a}")
    else:
        assert list(nsel) == ["kubernetes.io/metadata.name"], f"namespaces are selected by name only: {nsel}"
        got.append(",".join([f"ns={nsel['kubernetes.io/metadata.name']}"] + [f"{k}={v}" for k, v in psel.items()]))
assert sorted(got) == sorted(expected), f"allowed {sorted(got)}, expected {sorted(expected)}"
print("ok")
PY
}

@test "the Dagster API admits only dagster-user-code, the tool-server and Traefik, on 3000" {
  run check weyland dagster-webserver-front-door-only dagster-webserver 3000 \
    app=dagster-user-code app=weyland-tool-server "ns=kube-system,app.kubernetes.io/name=traefik"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "store-scaler admits only the port-agent namespace, on 8080" {
  run check data-mesh store-scaler-port-agent-only store-scaler 8080 ns=port-agent
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "the Dagster webserver stays meshed in git (the label was a live-only patch until B209)" {
  run python3 -c "
import yaml,sys
d=[x for x in yaml.safe_load_all(open('$P/dagster/webserver.yaml')) if x and x.get('kind')=='Deployment'][0]
assert d['spec']['template']['metadata']['labels'].get('sidecar.istio.io/inject')=='true', 'inject label missing'
print('ok')"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "the checker fails on a policy that admits a caller nobody listed (it is not a rubber stamp)" {
  run check weyland dagster-webserver-front-door-only dagster-webserver 3000 app=dagster-user-code
  [ "$status" -ne 0 ]
  [[ "$output" == *"expected"* ]]
}

@test "the Realm admits only its six callers, on 8080" {
  run check weyland realm-of-agents-front-door-only realm-of-agents 8080 \
    app=weyland-operator app=dagster-user-code app=a2a-inspector \
    "ns=kube-system,app.kubernetes.io/name=traefik" "ns=monitoring,app.kubernetes.io/name=prometheus" \
    "ns=monitoring,app=api-drift"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "the api-drift job's pods carry the label the Realm's policy admits" {
  run python3 -c "
import yaml
d=[x for x in yaml.safe_load_all(open('$P/monitoring/api-drift.yaml')) if x and x.get('kind')=='CronJob'][0]
assert d['spec']['jobTemplate']['spec']['template']['metadata']['labels'].get('app')=='api-drift'
print('ok')"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "realm.weyland.lab sits behind Keycloak forward-auth (it was open to the LAN until B209)" {
  run python3 -c "
import yaml
d=[x for x in yaml.safe_load_all(open('$P/realm-of-agents/ingress.yaml')) if x and x.get('kind')=='Ingress'][0]
mw=(d['metadata'].get('annotations') or {}).get('traefik.ingress.kubernetes.io/router.middlewares','')
assert 'weyland-traefik-forward-auth@kubernetescrd' in mw, mw
print('ok')"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "the A2A Inspector admits only Traefik (its forward-auth'd UI), on 8080" {
  run check weyland a2a-inspector-front-door-only a2a-inspector 8080 "ns=kube-system,app.kubernetes.io/name=traefik"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
