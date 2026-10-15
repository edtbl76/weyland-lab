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
rule, *extra = spec["ingress"]
# A MESHED target's sidecar is scraped by Prometheus on :15020 (envoy-stats-monitor). A policy that forgets it silences
# the pod's mesh metrics at its next restart (B211, 2026-10-14: the Realm's went dark under B209). Unmeshed: no such rule.
meshed = str(deps[target].get("sidecar.istio.io/inject", "")).lower() == "true"
want = [{"from": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "monitoring"}},
                   "podSelector": {"matchLabels": {"app.kubernetes.io/name": "prometheus"}}}],
         "ports": [{"protocol": "TCP", "port": 15020}, {"protocol": "TCP", "port": 15090}]}]
if meshed:
    assert extra == want, f"{target} is meshed: its policy must admit Prometheus on 15020/15090 as a second rule, got {extra}"
else:
    assert extra == [], f"{target} is not meshed, unexpected extra rules {extra}"
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

@test "buildkitd admits only the CI steps that build (build, golden-path-smoke), on 1234 — and both steps exist" {
  run python3 -c "
import yaml
docs=[d for d in yaml.safe_load_all(open('$P/woodpecker/buildkitd.yaml')) if d]
dep=[d for d in docs if d['kind']=='Deployment'][0]
pol=[d for d in docs if d['kind']=='NetworkPolicy'][0]
assert dep['spec']['template']['metadata']['labels'].get('app')=='buildkitd'
s=pol['spec']; assert s['podSelector']['matchLabels']=={'app':'buildkitd'} and s['policyTypes']==['Ingress']
(rule,)=s['ingress']; assert rule['ports']==[{'protocol':'TCP','port':1234}], rule['ports']
(src,)=rule['from']; assert set(src)=={'podSelector'}, src   # same namespace only, no namespaceSelector
(expr,)=src['podSelector']['matchExpressions']
assert expr=={'key':'woodpecker-ci.org/step','operator':'In','values':['build','golden-path-smoke']}, expr
steps={s['name'] for s in yaml.safe_load(open('$BATS_TEST_DIRNAME/../../.woodpecker.yml'))['steps']}
missing={'build','golden-path-smoke'}-steps
assert not missing, f'pipeline has no step named {missing}: the policy would lock CI out of buildkitd'
print('ok')"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "the checker refuses a MESHED target's policy that forgets the sidecar metrics rule" {
  T="$(mktemp -d)"; cp -r "$P" "$T/k8s"
  python3 -c "
import yaml
f='$T/k8s/realm-of-agents/netpol.yaml'; d=yaml.safe_load(open(f)); d['spec']['ingress']=d['spec']['ingress'][:1]
yaml.safe_dump(d, open(f,'w'))"
  P="$T/k8s" run check weyland realm-of-agents-front-door-only realm-of-agents 8080 \
    app=weyland-operator app=dagster-user-code app=a2a-inspector \
    "ns=kube-system,app.kubernetes.io/name=traefik" "ns=monitoring,app.kubernetes.io/name=prometheus" \
    "ns=monitoring,app=api-drift"
  rm -rf "$T"
  [ "$status" -ne 0 ]
  [[ "$output" == *"must admit Prometheus on 15020/15090"* ]]
}

# Every NetworkPolicy in the repo, not just the ones named above: a policy that selects a MESHED workload must admit
# Prometheus on the sidecar's 15020/15090, or the pod's mesh metrics go dark at its next restart (B211, 2026-10-14). A
# workload is meshed when its pod template says sidecar.istio.io/inject "true", or it is in data-mesh (namespace-wide
# injection) and doesn't opt out. Policies on Helm-installed workloads the repo can't see are listed, not guessed.
@test "every NetworkPolicy on a meshed workload admits Prometheus on the sidecar ports" {
  run python3 - "$P" <<'PY'
import sys, glob, yaml
p = sys.argv[1]
docs = [d for f in glob.glob(f"{p}/**/*.yaml", recursive=True) for d in yaml.safe_load_all(open(f)) if isinstance(d, dict)]
def tmpl(d):
    s = d.get("spec") or {}
    if d.get("kind") in ("Deployment", "StatefulSet"):
        return (s.get("template") or {}).get("metadata") or {}
    if d.get("kind") == "FlinkDeployment":
        return ((s.get("podTemplate") or {}).get("metadata")) or {}
    return None
work = []
for d in docs:
    m = tmpl(d)
    if m is not None:
        labels = dict(m.get("labels") or {})
        inj = str(labels.get("sidecar.istio.io/inject") or (m.get("annotations") or {}).get("sidecar.istio.io/inject") or "")
        if d.get("kind") == "FlinkDeployment":
            labels.setdefault("app", d["metadata"]["name"])
        work.append((d["metadata"].get("namespace"), labels, inj))
SIDECAR = {"from": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "monitoring"}},
                     "podSelector": {"matchLabels": {"app.kubernetes.io/name": "prometheus"}}}],
           "ports": [{"protocol": "TCP", "port": 15020}, {"protocol": "TCP", "port": 15090}]}
bad, unknown, checked = [], [], 0
for d in docs:
    if d.get("kind") != "NetworkPolicy" or d["metadata"].get("namespace") == "jupyterhub":
        continue
    ns, sel = d["metadata"].get("namespace"), (d["spec"]["podSelector"].get("matchLabels") or {})
    hits = [w for w in work if w[0] == ns and all(w[1].get(k) == v for k, v in sel.items())]
    if not hits:
        unknown.append(d["metadata"]["name"]); continue
    _, _, inj = hits[0]
    meshed = inj.lower() == "true" or (ns == "data-mesh" and inj.lower() != "false")
    has = SIDECAR in (d["spec"].get("ingress") or [])
    checked += 1
    if meshed and not has: bad.append(f"{d['metadata']['name']}: meshed target, no Prometheus sidecar rule")
    if not meshed and has: bad.append(f"{d['metadata']['name']}: unmeshed target, unexpected sidecar rule")
print(f"checked {checked}; not in the repo (Helm): {sorted(unknown)}")
assert not bad, bad
assert checked >= 10, f"only {checked} policies matched a workload: the scan is not seeing the manifests"
PY
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  echo "$output"
}

# B211 phase 2 (2026-10-14): the registry's pull host is read-only and the pod is reachable only through Traefik (both
# hosts) and registry-ui, so a push has to go through registry-push.weyland.lab's basic auth.
@test "registry: the pull host routes only GET/HEAD (HTTP and HTTPS); the push host needs auth over HTTPS; the pod admits Traefik and registry-ui" {
  run python3 -c "
import yaml
docs=[d for d in yaml.safe_load_all(open('$P/registry/registry.yaml')) if d]
k=lambda kind,name:[d for d in docs if d['kind']==kind and d['metadata']['name']==name]
assert not [d for d in docs if d['kind']=='Ingress' and d['metadata']['name']=='registry'], 'the open pull Ingress is back'
eps=set()
for n in ('registry-pull-https','registry-pull-http'):
    (r,)=k('IngressRoute',n); eps|=set(r['spec']['entryPoints'])
    (route,)=r['spec']['routes']
    assert route['match']=='Host(\`registry.weyland.lab\`) && (Method(\`GET\`) || Method(\`HEAD\`))', route['match']
assert eps=={'web','websecure'}, eps
(push,)=k('Ingress','registry-push'); a=push['metadata']['annotations']
assert a['traefik.ingress.kubernetes.io/router.middlewares']=='weyland-registry-push-auth@kubernetescrd'
assert a['traefik.ingress.kubernetes.io/router.entrypoints']=='websecure'
(mw,)=k('Middleware','registry-push-auth'); assert mw['spec']['basicAuth']['secret']=='registry-push-auth'
env={e['name'] for e in k('Deployment','registry')[0]['spec']['template']['spec']['containers'][0]['env']}
assert 'REGISTRY_HTTP_HOST' not in env, 'REGISTRY_HTTP_HOST pins upload URLs to the read-only host'
print('ok')"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  run check weyland registry-traefik-and-ui-only registry 5000 app=registry-ui "ns=kube-system,app.kubernetes.io/name=traefik"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
