# Demo — MLflow AI Gateway (B100 P4)

One governed OpenAI-compatible front door over **17 models** (6 local + 9 hosted), with **LLM-judge guardrails**
(Safety + PII) and a **global budget cap**, folded into MLflow so every call is usage-tracked. Fully codified — one
self-healing script builds endpoints + scorers + guardrails + budget. Built + validated 2026-07-25.

Grounded in `scripts/register_gateway_endpoints.py` + `scripts/.env` and [runbooks/mlflow-gateway.md](../runbooks/mlflow-gateway.md).

## The surfaces

| Surface | What | Where |
|---|---|---|
| **Gateway UI** | Endpoints · Usage · Budgets · per-endpoint Guardrails | `mlflow.weyland.lab/#/gateway` (Keycloak) |
| **OpenAI-compat API** | `model` = endpoint name, no key | `http://192.168.1.243:30500/gateway/mlflow/v1/chat/completions` (NodePort, rogueone) |
| **Codification** | endpoints/scorers/guardrails/budget in one run | `scripts/register_gateway_endpoints.py` |

## CLI walkthrough

Call any model through the gateway (endpoint name as `model`, no API key — the gateway holds provider keys):
```
[rogueone] python3 -c "import urllib.request as u,json; b='http://192.168.1.243:30500/gateway/mlflow/v1/chat/completions'; print(json.loads(u.urlopen(u.Request(b,data=json.dumps({'model':'ollama-gpt-oss-20b','messages':[{'role':'user','content':'What is a data lakehouse in one sentence?'}]}).encode(),headers={'Content-Type':'application/json'}),timeout=120).read())['choices'][0]['message']['content'])"
```
Rebuild the whole gateway from scratch (idempotent, self-healing):
```
[rogueone] python3 nodes/mother/lab/weyland-platform/scripts/register_gateway_endpoints.py
```

## UAT — eyes-on

1. **Endpoints** — `mlflow.weyland.lab/#/gateway` lists all 17; each has **Usage tracking** on.
2. **Guardrails work** — run `scripts/verify_gateway_guardrails.py`: **benign PASS** on all 6 local models; **PII**
   redacted-before-model (you can see `Contact [REDACTED]…` in the echo) or blocked — never leaked; **unsafe**
   refused/blocked/safely-reframed. (Judge = `ollama-qwen25-7b`, local, no quota.)
3. **Budget** — Gateway → **Budgets** shows the `$10 / 1mo, REJECT` GLOBAL cap + live spend.
4. **Eval lane** — `eval_gateway_models.py` runs `mlflow.genai.evaluate` over the gateway; results land in each
   `gateway/<model>` experiment (MLflow → Evaluation tab).
5. **Tracing** — any gateway call appears as a trace under its `gateway/<model>` experiment.

## Expected result

A provider-agnostic, guardrailed, budget-capped model gateway where a single `chat/completions` call is tracked,
safety/PII-screened by a local judge, and cost-capped — all reproducible from `scripts/register_gateway_endpoints.py`.

## Caveats
- **Guards fail closed** — a missing/erroring judge blocks traffic; the judge (`qwen2.5:7b`) must stay pulled on
  rogueone's Ollama. This is deliberate (fail-safe), but it's why judge robustness matters (see the runbook's
  judge-selection section — Gemini 20-RPM quota → local judge).
- **`openai-gpt-5-mini` may 500** — that model isn't on the account's key; a provider issue, not the gateway.
- Guarded calls to big/cold local models are slow (model + 2 judge round-trips + GPU swap).

## Cleanup / teardown
Read-only demo. The gateway config lives in the MLflow Postgres (durable); re-run the register script to rebuild.
`scripts/.env` holds keys locally (gitignored) — never committed.
