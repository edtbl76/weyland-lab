# Guardrails — the shared `weyland-guard` service (B14 + B70 Part 2)

The B14 guardrail layer runs as a **standalone service, `weyland-guard`** (extracted from the tool-server in B70
Part 2, 2026-07-22). Every consumer — the tool-server, the coming `weyland-agent`, and the future B66 fleet — calls
it over HTTP instead of loading validator models in-process. The three transformer models load **once**, here.

## Why a service
The validators are **model-backed** (Prompt Guard 2 injection + Presidio PII + a `nli-deberta-v3-small` cross-encoder ≈ 1.5 Gi
RAM). In-process, every consumer pod would duplicate that footprint — on a memory-tight single node that's exactly
the pressure B99 was about. As a shared service the models load once, the consumer pods stay thin, and the guard
layer becomes the **first clean seam of the tool-server decomposition** (related to B31).

## API — three typed routes
`http://weyland-guard.weyland.svc.cluster.local:8080` (ClusterIP, no ingress — internal only).

| Route | Body | Runs |
|---|---|---|
| `POST /guard/input` | `{request_id, query, actor?}` | `prompt_guard.injection` + `llama_guard.safety` |
| `POST /guard/output` | `{request_id, answer, sources:[{content}], actor?}` | `pii.presidio` + `grounding.nli` + `llama_guard.safety` (safety = toxicity) |
| `POST /guard/act` | `{request_id, tool, params?, actor?}` | `policy.audit` (audit) + `policy.gate` (enforcing) |
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
INPUT `prompt_guard.injection` + `llama_guard.safety` · OUTPUT `pii.presidio` + `grounding.nli` + `llama_guard.safety` (safety = toxicity) · ACT `policy.audit` + `policy.gate`.
All SHADOW. Two ways to change a mode:
- **Persistent** — per-validator env on the `weyland-guard` deployment:
```
GUARDRAIL_MODE__prompt_guard__injection=block   # dots in the name → double underscore; values: off|shadow|flag|block
```
- **Live, no restart** — the demo toggle `POST /admin/mode` (see below).
Enforcing FLAG/BLOCK modes are scored inline and returned.

## policy.gate — the enforcing act gate (B17+B19 Phase 2, 2026-07-29)
The MCP gateway now injects a verified `actor` (the Keycloak `client_id` via `X-Forwarded-Consumer`), so the ACT hook
gained `policy.gate` alongside audit-only `policy.audit`. It **BLOCKs**: an act with **no actor** (a caller that
bypassed the gateway), an actor **not in the allowlist**, a tool **not permitted** for that actor, or an actor over its
**per-minute rate cap**. Policy = `_DEFAULT_POLICY` in `validators/policy.py` (one entry per agent, `"*"` = any tool),
env-overridable as JSON via `GUARD_ACT_POLICY`. **ENFORCING (`block`) live 2026-07-29** via
`GUARDRAIL_MODE__policy__gate=block` on the guard deployment — the operator now routes acts through the gateway (verified
`weyland-operator` passes), so NULL-actor / unknown / direct acts are denied for real (proven: `decision:"block"`, reason
*"no actor…"*). Toggle to observe-only for a demo via the live `/admin/mode` toggle rather than editing the manifest.
Full path + the fastapi-mcp header-allowlist gotcha: [runbooks/mcp-gateway.md](mcp-gateway.md).

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

## pii.presidio — calibration (B34 → B117)
Scans the **answer** (OUTPUT hook) with **Microsoft Presidio** called directly (`validators/pii_presidio.py`, B117 —
was `llm_guard.pii`, which already just *wrapped* Presidio). NLP engine = spaCy **`en_core_web_sm`** (for `PERSON`) +
Presidio's built-in regex recognizers (email/SSN/CC/phone/IBAN/bank), baked in the image, loaded offline. Triggers that
justified it: answers **exported off-box** + RAG over **PII-bearing data** (the music mesh has PERSON/artist names).

**Entity set — tuned on real answers, not guessed** (`_PII_ENTITIES` in `validators/pii_presidio.py`):
- **Kept:** `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `US_SSN`, `CREDIT_CARD`, `IBAN_CODE`, `US_BANK_NUMBER` — Presidio's
  regex-backed recognizers are precise (zero misfires in the measurement).
- **Dropped:** `IP_ADDRESS` + `UUID` (every LAN `192.168.x.x` / k8s UUID would fire) and **`CRYPTO`** (the NER tagged a
  markdown table span as a crypto address, score 0.99 — pure FP, no crypto use case).

**Measured FP (golden set, 20 answers):** 3 flagged, **all false positives** — no real PII in the public docs corpus.
Pinned the exact triggers via redact-mode: the NER mislabels **tech nouns as PERSON** ("Traefik" → PERSON, score 1.0)
and (pre-drop) **markdown spans as CRYPTO**. Scores ~1.0, so a threshold won't help — the lever is the entity set.

**Stays SHADOW/advisory.** On the current docs corpus it's pure FP (0 true positives). `PERSON` is kept because it's
the detector the PII-bearing-data path needs, but it's noisy on tech text — so **do not promote to flag/block on
RAG-over-docs**; at promotion, context-gate `PERSON` to the PII-data path (or a tech-term denylist). The regex entities
are the solid core for the export-leak case.

## llama_guard.safety — the Classify layer (B115, 2026-08-03)
The **Classify** path of the guardrails platform (B115): a **model-based content-safety classifier** — Meta's **Llama
Guard** over its full safety taxonomy (S1 violent crime, S9 weapons, S11 self-harm, …) — run as a SECOND opinion
alongside the single-purpose Scan scanners (Prompt Guard 2 injection + Presidio PII). Since B117 it is **also the platform's toxicity signal** (llm_guard.toxicity retired — its S-taxonomy covers hate/harassment/sexual). It is **not** a
baked model: the validator (`validators/llama_guard.py`) POSTs to the always-on **`llama-guard`** svc —
**tier 1** = Llama-Guard-3-1B on **CPU (mother)**, served by **llama.cpp** at temp 0 (`LLAMA_GUARD_URL` on the
deployment; `k8s/llama-guard/`). Runs on **INPUT** (the prompt) and **OUTPUT** (the answer), both **SHADOW**. Reply
`unsafe\n<S-cat>` → BLOCK verdict `unsafe: S<cat>`; `safe` → PASS; unreachable / odd reply → **fail-open** (PASS), per
the caller contract. **Tier 2** (an on-demand Llama-Guard-3-8B on the **rogueone GPU**, same llama.cpp stack) is the
stronger escalation — `scripts/llama-guard-8b.sh {start|smoke|stop}` serves it on `:8003`
([gpu-inference.md](gpu-inference.md)); run the 5-case sweep against it or repoint `LLAMA_GUARD_URL` to
`http://192.168.1.230:8003` while it's up, no rebuild. Design: `../design/guardrails-platform.md`.

## guardrails-structure — the Structure layer (B115, 2026-08-03)
The **Structure** path: Guardrails AI (output-schema validation + re-ask) as a **standalone service** —
`guardrails-structure.weyland.svc:8080` (ClusterIP, no ingress, meshed; `k8s/guardrails-structure/`, Argo). It runs
alone because guardrails-ai pins `click<=8.2.0`, irreconcilable with the Dagster/dbt/huggingface stack that produces the
output (`click>=8.4.2`) — a `ResolutionImpossible` if embedded. Endpoint **`POST /structure/judge-scores`**
`{raw, model, api_base?, num_reasks?}` → validates the judge output against a Pydantic **`JudgeScores`** (three floats
in [0,1]) and, on a schema miss, **re-asks the same judge model** (litellm→Ollama) to repair; returns
`{scores, source, validation_passed}` with source ∈ `guarded | reasked | failed`. `/health` (liveness); `/ready`
imports guardrails+litellm (~1–2 min first boot).

**First consumer:** the RAG eval judge (`weyland-dagster` `eval_scores._judge`) POSTs each judge's raw JSON here via
`weyland_pipeline/structure.py` (a thin HTTP client). **Fail-safe** — if the service is unreachable it best-effort
parses the raw (the pre-B115 behaviour), so a guard outage never sinks an eval. The judge records the `_structure`
source (`guarded`/`reasked`/`fallback`) on its MLflow `eval`-experiment span — the honesty check that the guard actually
ran (all `fallback` = the service isn't answering). Design: `../design/guardrails-platform.md`.

## nemo-guardrails — the Dialog layer (B115, 2026-08-03)
The **Dialog** path (the 4th and final guardrails-platform path): NeMo Guardrails for **conversational / topical**
control — the thing the edge I/O scan does NOT do. It runs as a **standalone service** — `nemo-guardrails.weyland.svc:8080`
(ClusterIP, no ingress, meshed; `k8s/nemo-guardrails/`, Argo; image `registry.weyland.lab/nemo-guardrails:v3`) — in its
own image because NeMo drags a heavy dep tree (langchain, fastembed) that doesn't co-exist cleanly with the rest of the
stack. Meshed so the rails' LLM reaches the rogueone Ollama (the operator brain `gpt-oss:20b`), like the tool-server.

**OpenAI-compat wrapper.** A **FastAPI wraps the NeMo library** (`LLMRails.generate`, `services/nemo-guardrails/app.py`)
behind a plain OpenAI surface — `POST /v1/chat/completions`, `GET /v1/models`, `/health`, `/ready` — rather than NeMo's
own server, because that server wants `config_id` nested under a `guardrails` object a vanilla OpenAI client (Open WebUI)
won't send. So Open WebUI gets a clean OpenAI endpoint; the rails apply transparently. (The endpoint is sync `def` — it
runs in the threadpool because NeMo's `generate` spins its own event loop an `async def` would break; the rails are built
**once** and reused, since the NeMo import is heavy.)

**Open WebUI wiring — the guarded `weyland-operator` lane.** Open WebUI (`chat.weyland.lab`) adds `nemo-guardrails` as an
**OpenAI connection**, so a guarded **`weyland-operator`** chat model appears **alongside** the raw Ollama models — pick it
and every turn runs through the rails; pick a raw Ollama model and general chat is **unguarded** (unaffected). **Gotcha:**
Open WebUI's OpenAI connection is **PersistentConfig** — `ENABLE_OPENAI_API` / `OPENAI_API_BASE_URL` are read only on first
init, then DB-stored, so on an **existing** install the env change is ignored. Add the connection in the **admin UI**
(Settings → Connections → OpenAI; URL `http://nemo-guardrails.weyland.svc:8080/v1`, Auth **None**, empty Model IDs — it
reads `/v1/models`).

**Topical control via `self check input`, not Colang.** The rails config (`config/config.yml`) does topical control with a
**strengthened `self check input` LLM-judge rail** — a single input rail that judges **both** jailbreak/prompt-injection
**and** off-topic (anything that isn't a genuine lab-operations request). The intended NeMo feature — a **Colang
dialog/topical flow** — would **NOT fire** (v1 + v2 both answered off-topic; NeMo's embedding-based dialog matching is its
finickiest feature, and it failed the B32 trial the same way), whereas `self check input` blocks reliably (it caught the
jailbreak first try). So topicality moved into the self-check prompt, and `config/rails.co` overrides the blocked-message
to a **custom operator refusal** ("I'm the weyland lab operator — I only handle lab operations…") instead of NeMo's
generic default. Reliable > elegant.

**Verified 2026-08-03:** off-topic (e.g. "write me a haiku") → the operator refusal; on-topic (a lab-ops question) →
answered through the operator brain; a jailbreak → blocked. Design: `../design/guardrails-platform.md`.

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
POST /admin/mode        {"mode":"block","validators":["pii.presidio"]}   # un-shadow for the demo (omit validators = all)
POST /admin/mode/reset                                                    # revert to committed modes
GET  /admin/mode                                                          # current overrides
```

## Models (baked, offline at runtime)
`services/weyland-guard/Dockerfile` bakes the in-process Scan models (B117): Meta **Llama Prompt Guard 2**
(`project-free-llama/Llama-Prompt-Guard-2-22M`, injection — env `PROMPT_GUARD_MODEL` to swap), **Presidio** + spaCy
`en_core_web_sm` (PII), and `sentence_transformers.CrossEncoder('cross-encoder/nli-deberta-v3-small')` (grounding);
`HF_HUB_OFFLINE=1` at runtime. `llama_guard.safety` is NOT baked (it POSTs to the external `llama-guard` svc).

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
`/ready` should list `grounding.nli`, `prompt_guard.injection`, `pii.presidio`, `llama_guard.safety`, `policy.audit`, `policy.gate`. A
`POST /guard/output` with a hallucinated answer vs a contradicting source should score `grounding.nli` as `flag`
(counter visible on `/metrics`); a jailbreak query on `/guard/input` scores `prompt_guard.injection` as `block` — both
returned as `allow` while SHADOW. **B117 validation (2026-08-05):** direct `.check()` — injection → BLOCK @ 0.998, benign → PASS @ 0.001; email/SSN answer → BLOCK @ 1.0 (EMAIL_ADDRESS), clean text → PASS.

## Tool-server integration (B70 Part 2)
`weyland-tool-server` v0.5.0 dropped `llm-guard` + the guard-model bakes; its `_guard()` now POSTs to this service
(`GUARD_BASE_URL`, fail-open). Its own guardrail ServiceMonitor was retired — verdict metrics come from
`weyland-guard`. The `guardrail_verdicts` Postgres table + `guardrail_verdicts_total` Prometheus series are unchanged,
just emitted here now.

## Records
`guardrail_verdicts` (Postgres) = the durable per-verdict record + the basis for the future B1 data product;
`/metrics` = the live counters. See [[node-oom-forensics]] context for why models-once matters, and the B70 design in
`../design/agentic-rag-langgraph-design.md`.
