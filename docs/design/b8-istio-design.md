# B8 — Istio service mesh: first slice (sidecar) — design

**Status:** DESIGN (approved 2026-06-17). **Type:** evaluate-for-build-now → this *is* the build of slice 1.
**Depends on:** running k3s on mother (B-platform), B5 Prometheus (reuse), Traefik ingress (keep).
**Drivers (all four, confirmed):** mTLS/zero-trust · mesh observability · traffic management · hands-on
learning of a production-grade mesh. Learning is an explicit driver → the goal is **maximal real value on a
contained slice with minimal blast radius**, not mesh-everything.

## Decision: Approach 1 — sidecar, contained slice, bookinfo warm-up
Rejected: **B** (mesh whole `weyland` ns now — too much blast radius on the single load-bearing node) and
**C** (sandbox-only — gives no real mTLS/observability). Ambient (Approach 2) is the **fallback if step 0
shows mother is tight** (lighter: ztunnel, no sidecars, no pod restarts).

## Step 0 — Headroom gate (go vs pivot to ambient)
Before installing, measure mother's headroom against the added cost:
- **Cost added:** `istiod` ~0.3–0.5 GB · ~5 sidecars (tool-server + 4 backends) @ ~50–100 MB each · Kiali +
  Jaeger (bounded retention) ~0.3–0.5 GB. Rough total ~1–1.5 GB + CPU.
- **Measure:** `kubectl top nodes`, `free -h` on mother, current pod count / requests-vs-allocatable.
- **Gate:** if free headroom is comfortably above ~2 GB → proceed sidecar. If tight → **pivot to ambient**
  (Approach 2) or descope (fewer meshed backends, Jaeger sampling). Record the decision in the runbook.

## Install — minimal, Traefik-preserving
- `istioctl install --set profile=minimal` → **`istiod` only**. **No Istio ingress/egress gateway** —
  **Traefik stays the front door** (an ingress swap is high blast radius and not needed for slice 1).
- **Observability add-ons:** Kiali + Jaeger, wired into the **existing B5 kube-prometheus-stack** (do NOT
  stand up a second Prometheus — add Istio's scrape config / ServiceMonitors so the existing Prometheus
  collects Envoy metrics; Kiali reads from it). Expose Kiali at **`kiali.weyland.lab`** via Traefik.
- k3s compatibility: confirm the Istio version supports the running k3s/Kubernetes version (verification item).

## The slice — precise, per-workload injection
Mesh **only** the tool-server + its 4 vector backends (pgvector, qdrant, weaviate, neo4j) — **per-workload
injection via the pod-template annotation `sidecar.istio.io/inject: "true"`**, *not* namespace-label
injection (which would mesh all of `weyland` ns). Everything else in the namespace stays untouched.
- Each slice workload restarts once to get its sidecar. These are RWO single-instance Deployments with
  `strategy: Recreate` (see [[k8s-rwo-recreate-strategy]]) → brief per-pod downtime; **do them one at a time**
  and validate health between each.

## mTLS posture — slice 1 is all-PERMISSIVE (two un-meshed clients force it)
The slice has **two distinct un-meshed in-cluster/external clients**, so STRICT is not achievable in slice 1:
- **tool-server edge:** Hermes (CT 104) + Claude Code (rogueone) call `/mcp` over **NodePort 30080 from
  outside the cluster** (no mesh identity). STRICT here → MCP breaks.
- **the 4 vector backends:** **Dagster** (un-meshed, not in slice 1) writes `rag_*` / `weyland_chunks` / nodes
  to pgvector/qdrant/weaviate/neo4j on every ingestion + eval run, **plaintext**. STRICT on the backends →
  **ingestion + evals break.**

**Therefore slice 1 = PERMISSIVE everywhere** (`PeerAuthentication` PERMISSIVE, scoped by selector to the
slice workloads — never mesh-wide). mTLS still *happens automatically* on the tool-server↔backend hops (both
meshed → Kiali shows the lock) and is *observable*; it just isn't *enforced* yet. Nothing breaks.

**STRICT enforcement is the slice-2 "expand" step:** mesh **Dagster** (its writes become mTLS), confirm no
other un-meshed client remains, then flip the backends to **STRICT**. That's where enforced zero-trust is
earned — deliberately deferred to keep slice 1 contained (the Approach-A call).

## Observability
Kiali (live traffic graph of the slice), Jaeger (distributed traces across tool-server→backend hops), Envoy
metrics into the existing Prometheus/Grafana. Bounded Jaeger retention / sampling for the lab.

## Traffic-management experiment (learning, reversible)
One `VirtualService` + `DestinationRule` on a single tool-server→backend hop demonstrating: a **retry** +
**timeout** + a **fault injection** (delay then abort), observed in Kiali/Jaeger, then removed.

## Traefik interaction
Traefik is **not** in the mesh and stays the ingress. It routes the `*.weyland.lab` UIs (grafana/dagster/n8n/
kiali…), none of which are in the slice except Kiali — Kiali stays un-meshed (or PERMISSIVE) so Traefik can
reach it. The tool-server's external surface is NodePort (not Traefik), already handled by PERMISSIVE above.

## Reversibility
Per-workload: remove the inject annotation + restart → sidecar gone. CRDs (PeerAuthentication / VirtualService
/ DestinationRule) deletable. `istioctl uninstall` removes the control plane. Rollback is bounded to the slice.

## Success criteria (= build-now validated for slice 1)
1. tool-server↔backend hops show mTLS **observed** under PERMISSIVE (Kiali lock / `istioctl … tls-check`).
2. Kiali renders the slice traffic graph; a Jaeger trace spans tool-server→backend. 3. The traffic-policy
experiment behaves (retry/fault visible). 4. **No regression — all un-meshed clients still work: the MCP
(Hermes + Claude Code via NodePort) AND Dagster ingestion/eval writes to the backends.** Then decide
**expand to slice 2 (mesh Dagster → STRICT backends)** vs **hold**.

## Phasing
0. **Headroom gate** (go / pivot-to-ambient).
1. **Install** istiod (minimal) + Kiali/Jaeger on existing Prometheus; Kiali ingress.
2. **Bookinfo warm-up** — deploy the canonical sample in a throwaway ns; learn injection, mTLS, VS/DR, Kiali
   risk-free; then tear down.
3. **Mesh the real slice** — inject tool-server + 4 backends one at a time; **PERMISSIVE everywhere**.
4. **Validate** success criteria (esp. **MCP *and* Dagster-ingestion** no-regression).
5. **Traffic experiment**, then decide expand vs hold.
6. **Slice 2 (later) — STRICT enforcement:** mesh Dagster → confirm no other un-meshed backend client → flip
   backends to STRICT. (Out of scope for the slice-1 plan; noted here so the path is explicit.)

## Artifacts
`k8s/istio/` (install values, PeerAuthentication, VS/DR, Kiali ingress) · runbook
`docs/runbooks/service-mesh-istio.md` (all commands + the headroom decision) · backlog B8 update ·
arch.md / api.md (kiali.weyland.lab) on completion.

## Open / verification items
- Istio version vs running k3s version compatibility.
- Exact mother headroom (step 0) — decides sidecar vs ambient pivot.
- Confirm no *other* external/NodePort consumer of a slice backend that PERMISSIVE must cover.
- Whether Kiali should be dev-password-gated (LAN) like the other UIs.
