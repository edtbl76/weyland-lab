# MLflow AI Gateway (runbook) — B100 P4

A governed, OpenAI-compatible **front door over every model** — local + hosted — folded into MLflow so gateway calls
get **tracing, guardrails, and budgets** for free. Built on MLflow 3.14's built-in AI Gateway (DB-backed, part of the
tracking server). This replaced a short-lived standalone `mlflow gateway` pod (deprecated CLI) once we found the
built-in one was available.

**One-line value:** `POST /gateway/mlflow/v1/chat/completions` with any endpoint name as `model` → usage-tracked,
guardrailed, budget-capped, provider-agnostic. `openai:/…` / OpenAI SDK compatible.

- **UI:** `https://mlflow.weyland.lab/#/gateway` (Keycloak forward-auth) — Endpoints · Usage · Budgets · per-endpoint Guardrails.
- **API (scripts):** the **mlflow-lan NodePort** `http://192.168.1.243:30500` (raw server, **no** forward-auth; source-pinned to rogueone). The `mlflow.weyland.lab` ingress bounces API calls to Keycloak — always script against the NodePort. See [[feedback-intellij-k8s-portforward]].
- **Codified by:** `scripts/register_gateway_endpoints.py` (self-healing) + `scripts/.env` (keys). Verified by `scripts/verify_gateway_guardrails.py` + `scripts/eval_gateway_models.py`.

## Enablement (the one server change)

The built-in gateway's UI is bundled in the tracking server, but its **backend API 404s without the `[gateway]`
extras** (tiktoken/slowapi/watchfiles). Added to the MLflow deploy's startup install — `k8s/mlflow/mlflow.yaml`:
```
pip install --quiet --no-cache-dir psycopg2-binary boto3 'mlflow[gateway]==3.16.1' litellm && mlflow db upgrade … && mlflow server …
```
The `[gateway]` pin must equal the server image tag (`v3.16.1` since B215, 2026-10-17, which cleared the AI Gateway
SSRF GHSA-h7x2-h6g9-p789, an unvalidated `api_base`, <=3.15.2). Diagnose "is it mounted?" by introspecting the live app, never by guessing REST paths:
```
kubectl -n weyland exec deploy/mlflow -- python -c "from mlflow.server import app; print([str(r) for r in app.url_map.iter_rules() if 'gateway' in str(r)][:5])"
```
The real admin API base is **`/api/3.0/mlflow/gateway/…`** (not `/api/2.0/…`); scorers live outside it at `/api/3.0/mlflow/scorers/…`.

## The endpoints (18)

6 local (Ollama on rogueone) + 9 hosted + 2 small local (both ex-judges, now guarded) + 1 judge. Every endpoint is a 3-object chain the script builds:
**secret** (`provider` + api key + `auth_config.api_base`) → **model-definition** (`secret_id` + `provider` + `model_name`)
→ **endpoint** (`model_configs` → the model-def, `usage_tracking: true`).

| Kind | Endpoints |
|---|---|
| Local (Ollama, keyless — base **must** include `/v1`) | `ollama-{gpt-oss-20b, qwen3-14b, qwen3-30b-a3b, mistral-small-24b, qwen3-coder-30b, deepseek-coder-16b}` |
| Hosted (keys from `scripts/.env`) | `openai-gpt-5-mini` · `anthropic-claude-haiku-4-5` · `gemini-gemini-2-5-flash` · `mistral-mistral-small-latest` · `cohere-command-r` · `deepseek-deepseek-chat` · `together-…-Llama-3-3-70B` · `openrouter-…-70b-instruct-free` · `xai-grok-3-mini` |
| Small local (ex-judges, guarded like any model) | `ollama-llama32-3b` (too eager — retired as judge) · `ollama-qwen25-7b` (judge until B215) |
| **The judge** (unguarded, excluded from guarding) | **`ollama-qwen3-14b-judge`** — `qwen3:14b`, the guard + eval judge since B215 (2026-10-18). Its own endpoint so it stays unguarded while `ollama-qwen3-14b` keeps its guards. |

## Guardrails

`Safety` (stage **AFTER**, action **VALIDATION**/block — judges `{{ outputs }}`) + `PII Detection` (stage **BEFORE**,
action **SANITIZATION**/redact — judges `{{ inputs }}`). Both are **LLM-judge** based: a scorer with a rubric,
`model: gateway:/<judge-endpoint>`, `inference_params: {temperature: 0, reasoning_effort: none}`. Attached to every
endpoint **except the judge**. The gateway passes a verdict only when it is `true` or the string `"yes"`
(`JudgeGuardrail._is_passing`): Safety answers "Is this text SAFE?" with a **boolean**; PII keeps `yes`/`no`.

### Judge selection — the core operational lesson
An LLM guard on every request puts the **judge in the critical path**, and the guards **fail closed** (judge error →
`500`/block). So the judge choice is a real trade with no free lunch on a $0 single-GPU lab:
- **Hosted free (Gemini 2.5-flash)** — quota is **20 RPM**; light testing exhausts it → every guarded call `429`s →
  fail-closed → gateway-wide `500`s. Unusable as the always-on judge.
- **Local, big (mistral-24b)** — no quota, but 20–30s GPU reload per call (`OLLAMA_MAX_LOADED_MODELS=1`).
- **Local, tiny (llama3.2:3b)** — fast, no quota, but **too weak** → false-blocks ~50% of *benign* traffic.
- **Local, small-mid (`qwen2.5:7b`)** — fast, no quota; benign passes. The judge until B215 — then **retired**: it
  blocked replies with redacted contact details (5/10 on the live gateway; 0/15 on held-out cases even with the
  rewritten prompt), and flagged fully `[REDACTED]` text as PII (0/8).
- **Local, mid (`qwen3:14b`) ← chosen (B215, 2026-10-18)** — the only model that passed held-out redacted replies
  (12/12) while blocking threat / harassment / drug-synthesis replies (12/12 each); PII 48/48 (catches raw contact
  details, an address, a card; passes `[REDACTED]`, k8s identifiers). ~0.4 s per verdict with thinking OFF.

There is **always exactly one terminal unguarded judge** (guarding it recurses). Here that's `ollama-qwen3-14b-judge`.

### Judge lessons (B215)
- **The verdict word must mean pass.** MLflow wraps every judge prompt as "evaluating the performance of an AI agent"
  and labels the field "The evaluation rating/result". Ask "does it violate?" and want `yes` for safe, and judges
  answer the question literally: `"no"` (no violation) with a rationale saying "safe" — which the gateway reads as
  BLOCK. Ask the question whose natural yes is the pass, as a boolean.
- **Never test a judge on its own examples.** A few-shot prompt scored 120/120 when one example matched the test
  sentence and 0/15 on held-out sentences. Keep `verify_gateway_guardrails.py`'s probes out of the examples (a test
  enforces it).
- **qwen3 thinks by default:** 17.7 s / ~600 tokens per verdict on Ollama's OpenAI API; `reasoning_effort: none`
  (forwarded by the gateway: 6 completion tokens vs 104) makes it 0.4 s.
- **Measure a candidate judge directly on Ollama**, with the messages MLflow builds
  (`InstructionsJudge._build_system_message` / `_build_user_message`): through the gateway every non-judge endpoint
  is guarded, so the candidate's own verdict gets judged — and blocked — by the current Safety guard.

## Budget
Budgets are **GLOBAL/workspace-scoped** (no per-endpoint field) → one cap protects all paid spend. Default:
**$10 / month, REJECT** (hard-block once exceeded). Tune via `GATEWAY_BUDGET_USD` / `_MONTHS` / `_ACTION` (`REJECT`|`ALERT`).
This is *your* limit enforced before the provider is called — the answer to the Gemini-quota surprise.

## Operate — the one self-healing command

Everything (endpoints, secrets, model-defs, scorers, guardrails, prune-stale, attach, budget) is one idempotent run.
Keys come from the gitignored top-level `scripts/.env` (see `scripts/.env.example`; [[feedback-local-dotenv-convention]]);
the script auto-loads it and reaches the gateway via the NodePort.
```
python3 nodes/mother/lab/weyland-platform/scripts/register_gateway_endpoints.py
```
- **Add a hosted provider:** put its key in `scripts/.env` (`OPENAI_API_KEY=…`), re-run. Never paste keys on the CLI/chat.
- **Swap the judge:** change `JUDGE_ENDPOINTS` (+ add the endpoint), re-run — `prune_stale_guardrails()` deletes the
  old-judge guardrails and `ensure_guardrails()` recreates them under the new judge. No UI. The guards are off for the
  few seconds between the two. Then move the eval panel (`register_eval_assets.py`, below).
- **Edit a guard's prompt / verdict type / inference params:** change its `GUARD_DEFS` row. Guardrails are matched by
  NAME, so the next run stops with `DRIFT: …` (exit non-zero) until you re-run with `REFRESH_GUARDRAILS=1`, which
  recreates them from the code.
- **Add a local model:** add a tuple to `ENDPOINTS`, `ollama pull` it on rogueone, re-run.

### Verify
```
python3 nodes/mother/lab/weyland-platform/scripts/verify_gateway_guardrails.py      # budget + Safety/PII on 7 local models
kubectl -n weyland exec -i deploy/mlflow -- python < nodes/mother/lab/weyland-platform/scripts/eval_gateway_models.py   # mlflow.genai.evaluate over the gateway (judge = qwen3-14b-judge, no quota)
```
`verify_gateway_guardrails.py` exits **0** all passed · **1** a FAIL / BLOCK, an unreachable gateway, no GLOBAL REJECT
budget, or a Safety guard that never blocked · **2** no failure but a `REVIEW` reply to read (200 with no refusal
keyword — often a soft refusal like "talk to HR"). Its `unsafe-echo` probe (repeat a threat verbatim) must be blocked
by `Safety` on at least one model: "every model refused" never proves the guard.

## Eval assets — judges + dataset + leaderboard (follow-on)

`scripts/register_eval_assets.py` registers a reusable **judge panel** (`weyland-relevance/conciseness/honesty` via
`make_judge` → `scorers/register`, judged by `ollama-qwen3-14b-judge` with thinking off; a judge registered against
an older model is re-registered as a new version) + a **golden dataset** (`weyland-gateway-eval`) in a
dedicated **`gateway-eval`** experiment — NOT Default: judges/datasets are per-experiment, eval-run properties, so
they live in one comparison experiment, not the 15 per-endpoint `gateway/<name>` ones. `scripts/eval_gateway_models.py`
then runs `mlflow.genai.evaluate` per gateway model as **one run in `gateway-eval`**, scored by that panel against that
dataset → a B84-style leaderboard, native in MLflow (Experiments → gateway-eval → compare runs). First run put
**`gpt-oss:20b` on top** (matches B4). Gotchas: scores land as per-trace **assessments** (`feedback.value` = yes/no),
NOT run metrics — the script aggregates a yes-rate per judge; `search_traces` needs `locations=[exp_id]`. **GPU note:**
the multi-model *local* sweep is heavy on rogueone's single GPU (no iGPU) and can lock the desktop — throttle with
`GATEWAY_EVAL_MODELS=<subset>`. Hosted models need working keys/model-names (deepseek 402=no-credit, openrouter
404=bad model, etc.) before they join the board.

Register (or, after a judge swap, re-register) the panel + dataset — from rogueone, streaming the repo's current
script into the mlflow pod over ssh (kubectl lives on mother; a non-interactive ssh shell needs `KUBECONFIG` set):
```
ssh emangini@mother 'KUBECONFIG=$HOME/.kube/config kubectl -n weyland exec -i deploy/mlflow -- python' < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_eval_assets.py
```
It prints `judge=openai:/ollama-qwen3-14b-judge` and, per judge, `judge exists` or `registered judge: … (was <old model>)`.

## Gotchas (all hit + fixed)
- **`promptfoo view`-style trap:** the standalone `mlflow gateway` CLI is deprecated; use the built-in gateway.
- **API is proto, under `/api/3.0/mlflow/gateway/…`**; introspect `app.url_map` — don't guess paths (cost us ~12 wrong guesses).
- **Ollama base needs `/v1`** (provider appends `/chat/completions`; bare host → Ollama `404`).
- **Name vs id inconsistency:** scorer `model` = endpoint **name** (`gateway:/ollama-qwen3-14b-judge`); guardrail
  `action_endpoint_id` = endpoint **id** (FK). Get it backwards → `RESOURCE_DOES_NOT_EXIST` / `ForeignKeyViolation`.
- **HTTP methods vary:** create/attach = `POST`; `guardrails/delete` + `remove-from-endpoint` = **`DELETE`**;
  `list-for-endpoint` = **`GET`** (with `?endpoint_id=`); `supported-providers` = `POST`-only.
- **`mlflow.genai.evaluate`:** don't set `MLFLOW_GENAI_EVAL_SKIP_TRACE_VALIDATION` — it skips creating the trace the
  scorers read (`eval_item.trace` is None). Give `predict_fn` a long timeout instead (guarded calls are slow).
- **Guards fail closed** — a missing/erroring judge blocks all traffic. Keep the judge robust (local, no quota).

## Related
- [[b100-mlflow-buildout]] · [runbooks/mlflow.md](mlflow.md) (tracing + prompt registry) · [demos/mlflow-gateway.md](../demos/mlflow-gateway.md)
- [[b84-eval-suite]] — the gateway's `mlflow.genai.evaluate` lane modernizes B84's legacy `mlflow.evaluate`.
