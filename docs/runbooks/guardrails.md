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
INPUT `llm_guard.injection` · OUTPUT `llm_guard.pii` + `llm_guard.toxicity` + `grounding.nli` · ACT `policy.audit`.
All SHADOW. Two ways to change a mode:
- **Persistent** — per-validator env on the `weyland-guard` deployment:
```
GUARDRAIL_MODE__llm_guard__injection=block   # dots in the name → double underscore; values: off|shadow|flag|block
```
- **Live, no restart** — the demo toggle `POST /admin/mode` (see below).
Enforcing FLAG/BLOCK modes are scored inline and returned. The enforcing **act** policy gate for the ACT hook is
deferred — it needs the gateway-injected `actor` for per-actor allowlist/rate-limit, so it's blocked on **B17+B19**
(today `actor` is always `None`). B35 covered the *grounding* half of that original bundle (below).

## grounding.nli — calibration (B35, 2026-07-28)
`grounding.nli` scores answer-vs-sources by **sentence-level NLI**: split the answer into claims (markdown/citation-
normalized, newline-aware — RAG answers are markdown lists), score each claim's best-supporting chunk with the
`nli-deberta-v3-small` cross-encoder, and **average** them (`grounded_mean`, shown in the verdict `reason` alongside
the weakest claim). The NLI is bounded + serialized (cap **12** claims, `batch_size=8`, a `threading.Lock`) so it
can't OOM the pod — the earlier whole-answer scorer, then the unbounded sentence-level one, `exit 137`'d it; the pod
limit is **3072Mi** (raised again in B34 for the 4th/PII model).

**What it measures — read this before trusting the number:** chunk-**attributability** ("is the answer traceable to
the retrieved chunks"), **NOT faithfulness/truth.** Good *conceptual* answers legitimately synthesize *beyond* sparse
chunks → they score mid-low even when correct; short *lexical/factual* answers that sit verbatim in a chunk score
high. Labeled golden-set shadow data (n≈40, tagged by type via `X-Forwarded-Consumer`) put the genuinely-
unattributable tail (retrieval misses + heavy elaboration) below ~0.15.

**Threshold `0.15`** (was a guessed `0.5` that flagged ~50%, including attributable answers). Override with
`GROUNDING_THRESHOLD` on the deployment to retune as shadow data accrues. **Stays SHADOW/advisory** — NLI can't tell
"synthesized-but-true" from "hallucinated," so real faithfulness gating is the **LLM-judge lane (B84)**, not this
guard. grounding.nli is a useful "answer exceeded its retrieved sources" signal, not a blocking gate.

## llm_guard.pii — calibration (B34, 2026-07-29)
Baked + active (SHADOW) as of B34 (was coded-but-unbaked). Scans the **answer** (OUTPUT hook) with llm_guard's
`Sensitive` → presidio; NER = `Isotonic/deberta-v3-base_finetuned_ai4privacy_v2` + a spaCy `en_core_web_sm` engine,
both baked in the image. Triggers that justified it: answers **exported off-box** + RAG over **PII-bearing data** (the
music mesh has PERSON/artist names).

**Entity set — tuned on real answers, not guessed** (`_PII_ENTITIES` in `validators/llm_guard.py`):
- **Kept:** `PERSON`, `EMAIL_ADDRESS(+_RE)`, `PHONE_NUMBER`, `US_SSN(+_RE)`, `CREDIT_CARD(+_RE)`, `IBAN_CODE`,
  `US_BANK_NUMBER` — the regex-backed ones are precise (zero misfires in the measurement).
- **Dropped:** `IP_ADDRESS` + `UUID` (every LAN `192.168.x.x` / k8s UUID would fire) and **`CRYPTO`** (the NER tagged a
  markdown table span as a crypto address, score 0.99 — pure FP, no crypto use case).

**Measured FP (golden set, 20 answers):** 3 flagged, **all false positives** — no real PII in the public docs corpus.
Pinned the exact triggers via redact-mode: the NER mislabels **tech nouns as PERSON** ("Traefik" → PERSON, score 1.0)
and (pre-drop) **markdown spans as CRYPTO**. Scores ~1.0, so a threshold won't help — the lever is the entity set.

**Stays SHADOW/advisory.** On the current docs corpus it's pure FP (0 true positives). `PERSON` is kept because it's
the detector the PII-bearing-data path needs, but it's noisy on tech text — so **do not promote to flag/block on
RAG-over-docs**; at promotion, context-gate `PERSON` to the PII-data path (or a tech-term denylist). The regex entities
are the solid core for the export-leak case.

## Demo toggle — `POST /admin/mode` (live, no restart)
Flip validators shadow↔flag/block **live** for a demo, then revert. In-process override: a pod restart drops back to
the committed modes (a demo can't be left on by accident) and there's no manifest drift for Argo to fight — chosen over
a `kubectl set env` flip precisely because Argo self-heal would revert that mid-demo.

**Auth:** `/admin/*` is Bearer-gated (it can DISABLE the guards, unlike the scoring routes) — `GUARD_ADMIN_TOKEN` from
Secret `weyland-guard-admin` (key `token`), constant-time compared, **fail-closed** (503 if unset). Create once
(out-of-band, NOT committed):
`kubectl -n weyland create secret generic weyland-guard-admin --from-literal=token=$(openssl rand -hex 24)`.
```
# in-cluster; -H "Authorization: Bearer <token>", or exec the pod which has GUARD_ADMIN_TOKEN in env
POST /admin/mode        {"mode":"block","validators":["llm_guard.pii"]}   # un-shadow for the demo (omit validators = all)
POST /admin/mode/reset                                                    # revert to committed modes
GET  /admin/mode                                                          # current overrides
```

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
