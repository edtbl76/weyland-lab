# Guardrails — the shared `weyland-guard` service (B14 + B70 Part 2)

The B14 guardrail layer runs as a **standalone service, `weyland-guard`** (extracted from the tool-server in B70
Part 2, 2026-07-22). Every consumer — the tool-server, the coming `weyland-agent`, and the future B66 fleet — calls
it over HTTP instead of loading validator models in-process. The three transformer models load **once**, here.

## Why a service
The validators are **model-backed** (LLM Guard injection + toxicity + a `nli-deberta-v3-small` cross-encoder ≈ 1.5 Gi
RAM). In-process, every consumer pod would duplicate that footprint — on a memory-tight single node that's exactly
the pressure B99 was about. As a shared service the models load once, the consumer pods stay thin, and the guard
layer becomes the **first clean seam of the tool-server decomposition** (related to B31).

## API — three typed routes
`http://weyland-guard.weyland.svc.cluster.local:8080` (ClusterIP, no ingress — internal only).

| Route | Body | Runs |
|---|---|---|
| `POST /guard/input` | `{request_id, query, actor?}` | `llm_guard.injection` |
| `POST /guard/output` | `{request_id, answer, sources:[{content}], actor?}` | `llm_guard.toxicity` + `grounding.nli` |
| `POST /guard/act` | `{request_id, tool, params?, actor?}` | `policy.audit` (audit-only) |
| `GET /health` | — | liveness (200 even if models failed) |
| `GET /ready` | — | 503 until the validator set is built |
| `GET /metrics` | — | `guardrail_verdicts_total` + `guardrail_validator_latency_ms` |

**Response:** `{request_id, decision: "allow"|"block", verdict: {...}|null}`. Three separate routes (not one
`/guard?hook=`) on purpose — typed per-hook schemas (the OUTPUT route *requires* `sources`, which grounding needs),
self-documenting OpenAPI, independent evolution.

## The two contracts that make it safe
- **SHADOW is fast.** All validators default to SHADOW (record-only). The service fire-and-forgets the model scoring
  and answers `allow` immediately, so a caller's synchronous call adds only an in-cluster round-trip (~ms), **not**
  model-inference latency. The caller never needs to know the mode — it 403s iff the service says `block` (which only
  happens in enforcing modes).
- **Callers FAIL OPEN.** A guard outage (unreachable / timeout / error) is treated as `allow` by the client, so it
  degrades to "not guarded", never "no answer". Verified: with `weyland-guard` scaled to 0, `/context/ask` still
  answers.

## Validators & modes
INPUT `llm_guard.injection` · OUTPUT `llm_guard.toxicity` + `grounding.nli` · ACT `policy.audit`. PII
(`llm_guard.pii` → presidio/spaCy) is **coded but deferred** — model not baked, out of the default chain (→ B34).
All SHADOW. Flip one per-validator with an env var on the `weyland-guard` deployment:
```
GUARDRAIL_MODE__llm_guard__injection=block   # dots in the name → double underscore; values: off|shadow|flag|block
```
Enforcing FLAG/BLOCK modes are scored inline and returned; the enforcing policy gate for the ACT hook is B35.

## Models (baked, offline at runtime)
`services/weyland-guard/Dockerfile` bakes the **exact** 3 models the tool-server used (so verdicts are identical):
`llm_guard.input_scanners.PromptInjection`, `llm_guard.output_scanners.Toxicity`,
`sentence_transformers.CrossEncoder('cross-encoder/nli-deberta-v3-small')`; `HF_HUB_OFFLINE=1` at runtime.

## Build & deploy (registry flow)
Image is registry-based (NOT `:local`). Consumers deploy off Argo.
- Build + push (on **rogueone**): `docker build -t registry.weyland.lab/weyland-guard:v1 <services/weyland-guard> && docker push registry.weyland.lab/weyland-guard:v1`
- **Gotcha (hit twice):** large-layer pushes to the MinIO-backed registry can stall and **not finalize the manifest** —
  the pod then `ImagePullBackOff`s with `not found`. Confirm the tag landed before rolling:
  `curl -sk https://registry.weyland.lab/v2/weyland-guard/tags/list`. If missing, re-push and watch for the terminal
  `v1: digest: sha256:…` line (that's the manifest write), then `kubectl -n weyland rollout restart deploy/weyland-guard`.
- Manifests: `k8s/weyland-guard/{deployment,service,servicemonitor}.yaml`; Argo app in
  `k8s/argocd/applications/subdir-apps.yaml`. Meshed (STRICT-mTLS Postgres for `guardrail_verdicts`).

## Verify (on mother)
```
kubectl -n weyland exec deploy/weyland-guard -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/ready').read().decode())"
```
`/ready` should list `grounding.nli`, `llm_guard.injection`, `llm_guard.toxicity`, `policy.audit` (not `pii`). A
`POST /guard/output` with a hallucinated answer vs a contradicting source should score `grounding.nli` as `flag`
(counter visible on `/metrics`); a jailbreak query on `/guard/input` scores `llm_guard.injection` as `block` — both
returned as `allow` while SHADOW.

## Tool-server integration (B70 Part 2)
`weyland-tool-server` v0.5.0 dropped `llm-guard` + the guard-model bakes; its `_guard()` now POSTs to this service
(`GUARD_BASE_URL`, fail-open). Its own guardrail ServiceMonitor was retired — verdict metrics come from
`weyland-guard`. The `guardrail_verdicts` Postgres table + `guardrail_verdicts_total` Prometheus series are unchanged,
just emitted here now.

## Records
`guardrail_verdicts` (Postgres) = the durable per-verdict record + the basis for the future B1 data product;
`/metrics` = the live counters. See [[node-oom-forensics]] context for why models-once matters, and the B70 design in
`aidlc-docs/construction/agentic-rag-langgraph-design.md`.
