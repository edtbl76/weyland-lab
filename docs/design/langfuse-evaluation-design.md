# Langfuse Evaluation (B103 final) — design

**Goal:** stand up the Langfuse Evaluation stack (Scores · Evaluators · Human Annotation · Datasets) as the **ONLINE**
eval lane for weyland's AI surfaces — the continuous, on-production-traffic + human-in-the-loop complement to the
**OFFLINE** B84 judge-panel suite. All four are free in self-hosted Langfuse OSS. $0.

## Positioning (don't duplicate B84)

| | Offline — **B84** | Online — **Langfuse eval** (this) |
|---|---|---|
| When | pre-deploy benchmark | continuous, on real production traces |
| Engine | MLflow judge-panel + Promptfoo | Langfuse Evaluators (LLM-as-judge) + Annotation |
| Fixtures | B96 golden set (`golden_questions.json`) | **same** B96 set, mirrored to a Langfuse Dataset |
| Output | MLflow `eval_leaderboard` | Langfuse **Scores** (on traces/sessions) |

The bridge is **shared fixtures**: `langfuse_eval.py` mirrors the 20 golden questions into the Langfuse dataset
`weyland-golden` so both lanes grade the same exam. Prompt-version linkage (from the federation work) means online
scores are comparable across prompt versions — "edit `rag_system` → v2 → compare v1 vs v2 on real traffic + scores."

## Tiered judge (via the existing LiteLLM gateway — $0-first)

One Langfuse **LLM Connection** → LiteLLM (`litellm.weyland.svc:4000/v1`, OpenAI-compatible, master key). Two models:
- **`wl-judge-oss`** (gpt-oss:20b, free local) — the **production evaluators** (high-volume sampled traces). $0.
- **`claude-haiku`** — the **golden-set dataset runs** (quality where it counts; tiny cost, tracked per-VK).

## The four pieces

1. **Scores** — the primitive; where 2–4 land. Numeric/categorical/boolean on traces/observations/sessions.
2. **Evaluators** *(net-new value)* — **native, created programmatically.** Langfuse's eval-config engine IS public
   API — just under the **`/api/public/unstable/`** namespace (`evaluators` + `evaluation-rules`), NOT `/eval-configs`
   (which 404s — the wrong path that misled the first probe; the instance's OpenAPI spec settled it, triple-checked).
   So `langfuse_evaluators.py` (group `registrations`) reconciles **idempotently**: **2 custom evaluators** (`citation`,
   `refusal` — weyland-specific, absent from the managed library) + **9 evaluation-rules** binding evaluators (7 managed:
   Relevance, Helpfulness, Hallucination, Conciseness, Toxicity, Contextrelevance, Faithfulness) to `rag-generate`
   observations. These run **live per-trace on Langfuse's own engine**, scoring into the Scores view. Rules have **no
   per-rule model** — all share the LLM connection's default (`wl-judge-oss`, $0); that's why the tiering below was
   dropped in favour of "all native on wl-judge-oss". Adding a criterion = a `CATALOG` / `CUSTOM_EVALUATORS` entry.
   (The earlier batch-judge-via-LiteLLM approach was superseded once the `/unstable/` API was found.)
3. **Human Annotation** — a queue + a `quality` score config (1–5), route sampled traces for manual review →
   calibrates the auto-evaluators and grows the golden set. UI-configured.
4. **Datasets** — `weyland-golden` seeded from B96 (`langfuse_eval.py`, REST, idempotent). Experiment runner
   (increment 2) runs the RAG over the dataset → dataset-run traces judged by `claude-haiku` → compare prompt
   versions/models in Langfuse.

## Eval-fixture SSOT (git, not Langfuse)

**Single source of truth for eval question sets = git**, fanned out to the tools — the same pattern as prompt
federation (Bifrost = prompt SoT → Langfuse/MLflow mirrors). Langfuse Datasets are a **mirror + browse/run UI**, NOT the
source: Langfuse's data is in Postgres/ClickHouse (lost on a DB reset), and making it the source would couple the *exam*
to a running observability service. A pinned set = **a git commit** — which is the entire point of B96's comparability.

```
git: weyland_pipeline/eval_sets/*.json   (golden.json · regression.json · …)   ← SSOT
        │  langfuse_eval.py (generalized — one Langfuse Dataset per set)
        ├──► Langfuse Datasets   (online lane, experiment runs, UI)
        ├──► eval_testset.py     (offline MLflow judge-panel + mlflow.evaluate leaderboard)
        └──► (optionally) Promptfoo's regression gate
```

Today two sets exist, by intent: **golden** (20 Q — the comparable benchmark, MLflow + Langfuse) and **regression**
(Promptfoo's small assertion-carrying gate). Both become files in the one catalog dir; each set → `weyland-<name>` in
Langfuse. Discovery/lineage can ride on top via DataHub data products (`golden set → feeds → leaderboard + Langfuse`).

## LiteLLM judge aliases (added for this)

- **`wl-judge-oss`** → `ollama_chat/gpt-oss:20b` (free local) — the production/codified judge for the cheap criteria.
- **`claude-haiku`** → Anthropic Haiku — the quality lane (groundedness, golden-set dataset runs).
- (`wl-judge` = qwen2.5:7b stays as the pre-existing general judge alias.)

## SSRF gotcha (UI evaluators only)

Langfuse blocks LLM-connection base URLs that resolve to private IPs ("Blocked IP address detected"). The documented
`LANGFUSE_UNSAFE_TRUSTED_PRIVATE_IPS` is a no-op for LLM connections (langfuse#13097); the working var is
**`LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST`** (= `litellm.weyland.svc.cluster.local`) on web+worker. Only the *UI*
evaluators need this — the codified judge calls LiteLLM from our own egress and is unaffected.

## Durability note

Evaluators, the LLM Connection, and annotation queues are **UI config living in Langfuse Postgres** — a Langfuse DB
reset loses them (same class as the DataHub-UI-secrets gotcha). Datasets + scores are API-reproducible
(`langfuse_eval.py`). Codify what the API allows; document the UI config here + in the runbook so it's rebuildable.

## Build order

1. LiteLLM `wl-judge-oss` alias → deploy. 2. LLM Connection (UI). 3. Evaluators (UI) → online eval live.
4. Datasets (`langfuse_eval.py`, as a `registrations` asset). 5. Human Annotation queue (UI). 6. Experiment runner.
7. DoD: demo · runbook · arch · memory · backlog · Linear.
