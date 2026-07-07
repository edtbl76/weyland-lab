# B4 — LLM Evaluation Pipeline (runbook)

Persistent, k3s-native evaluation of the tool-server RAG (`/context/ask`) across the local Ollama
models. Reuses existing infra — **no new DB/cache**: Postgres (storage), Dagster (orchestration),
Ollama (generator + judge), bge (embeddings).

**Related:** [model-serving-ollama.md](model-serving-ollama.md) · schema: `scripts/eval-schema.sql` ·
asset: `services/weyland-dagster/weyland_pipeline/assets/eval_testset.py`.

## Architecture (reuse map)
| Need | Reuse |
|---|---|
| Orchestration | **Dagster** — eval = `weyland_eval_job` (asset group `eval`, isolated from the 15-min ingestion schedule); triggered via the tool-server `/pipeline/trigger` path |
| Storage / leaderboard | **weyland-postgres** — `eval_runs / eval_questions / eval_results / eval_scores` + `eval_leaderboard` view (`scripts/eval-schema.sql`) |
| Question generation | **Ollama** (`qwen3:30b-a3b`) over the rag corpus — direct prompt, JSON-constrained |
| Scoring (planned) | **LLM-as-judge** via Ollama — **not Ragas** (see Decision Record) |
| Embeddings | **bge-small** (baked in the Dagster user-code image) |

## Pipeline steps
1. ✅ **Schema** — `eval_*` tables + `eval_leaderboard` view (`scripts/eval-schema.sql`).
2. ✅ **Question generation** — `eval_testset` asset → `eval_questions`. Pulls corpus from
   `rag_chunks` → `qwen3:30b-a3b` writes questions answerable from it (`question_type = direct`).
   10 questions live (grounded in the same corpus the RAG serves).
3. ✅ **Run matrix** — `eval_run_matrix` (job `weyland_eval_job`): each question × 6 models via
   `/context/ask` → `eval_results`. Run 3: 60 results, 0 errors.
4. ✅ **Scoring** — `eval_scores` (job `weyland_eval_score_job`, **separate** so re-scoring needs no
   matrix re-run): LLM-as-judge via Ollama (default judge `deepseek-coder-v2:16b`) → `eval_scores`.
5. ⏳ **Judge-panel scoring** — score each result with **≥3 judges and average** (single-judge
   rankings swing wildly — see Results). The leaderboard should be panel-based.
6. ✅ **/evals endpoints** — tool-server **v0.4.0**: `/evals/run` (single-path trigger), `/evals/score`,
   `/evals/runs`, `/evals/leaderboard` (panel-averaged, `?run_id=`; reports `judges` count). Documented
   in api.md + test.md. **B4 core complete.**

## First results (run 3 — 10 questions, 2026-06-13)
Scored **twice with two different judges** to test judge sensitivity. The result is the headline.

**Judge: deepseek-coder-v2:16b (fast)** — faithful / answer_rel / context_rel
| model | faithful | answer_rel | context_rel |
|---|---|---|---|
| gpt-oss:20b | 0.750 | 0.850 | 0.770 |
| mistral-small3.2:24b | 0.700 | 0.770 | 0.745 |
| qwen3-coder:30b | 0.685 | 0.750 | 0.790 |
| qwen3:14b | 0.625 | 0.655 | 0.740 |
| qwen3:30b-a3b | 0.610 | 0.729 | 0.760 |
| deepseek-coder-v2:16b | 0.565 | 0.695 | 0.770 |

**Judge: mistral-small3.2:24b (slower, more nuanced)**
| model | faithful | answer_rel | context_rel |
|---|---|---|---|
| qwen3:30b-a3b | 0.990 | 1.000 | 0.800 |
| gpt-oss:20b | 0.960 | 0.970 | 0.800 |
| deepseek-coder-v2:16b | 0.920 | 0.780 | 0.770 |
| qwen3-coder:30b | 0.900 | 0.960 | 0.800 |
| mistral-small3.2:24b | 0.790 | 0.870 | 0.710 |
| qwen3:14b | 0.750 | 0.880 | 0.750 |

**KEY FINDING — the ranking is highly judge-dependent.** `qwen3:30b-a3b` went **5th (0.61) → 1st
(0.99)** purely by swapping the judge; `deepseek-coder` went last → 3rd. Mistral also scores higher
and more compressed (0.75–0.99) than deepseek (0.57–0.75) — judges have very different strictness.

**Methodology takeaways:**
- **Single-judge LLM-as-judge is noisy.** A trustworthy ranking needs a **judge panel** (average ≥3
  judges) and/or more questions. One judge × 10 Q is *directional only* — do not over-trust it.
- **No self-bias under either judge:** each judge ranked *itself* low (deepseek last under itself,
  mistral 5th under itself). Reassuring — the judges weren't self-serving.
- **`context_relevancy` stayed ~flat (0.71–0.80) under both** — confirms retrieval is consistent and
  the metric measures the right thing (same chunks for every model).
- **Robust read:** `gpt-oss:20b` is the only model **top-2 under both judges** → the safest RAG-default
  pick. `qwen3:30b-a3b` *might* be best, but its swing makes that judge-dependent.

### Panel results (definitive — 3-judge average, run 3)
Re-scored with a **3-judge panel** (mistral-small3.2 · deepseek-coder-v2 · qwen3-coder); the swing collapses:

| model | faithful | answer_rel | context_rel |
|---|---|---|---|
| mistral-small3.2:24b | 0.823 | 0.903 | 0.822 |
| gpt-oss:20b | 0.820 | 0.882 | 0.807 |
| qwen3:14b | 0.775 | 0.850 | 0.783 |
| deepseek-coder-v2:16b | 0.760 | 0.811 | 0.773 |
| qwen3-coder:30b | 0.756 | 0.836 | 0.843 |
| qwen3:30b-a3b | 0.752 | 0.765 | 0.710 |

**The panel worked:** `qwen3:30b-a3b`'s 5th↔1st whiplash settled to a stable 6th (0.752); the field
tightened to **0.75–0.82** (models are closer than any single judge implied).

**Per-judge faithfulness (why one judge can't be trusted):**
| judge | range | tendency |
|---|---|---|
| deepseek-coder-v2 | 0.47–0.70 | harsh |
| mistral-small3.2 | 0.78–0.97 | generous |
| qwen3-coder | 0.705–0.93 | generous; **ranked *itself* #1 (self-bias)** |

**Defensible conclusion:** **`gpt-oss:20b`** is the best RAG pick — top-2 under *every* configuration
(deepseek-only, mistral-only, panel) **and it is not a judge → zero self-bias.** `mistral` ties it
(0.823) but is itself a panel judge (asterisk). The tight spread says retrieval/corpus matter about as
much as model choice for this RAG.

> **Operational gotchas hit building this** (all fixed, documented in model-serving-ollama.md): Ollama
> OOM under the 48 GB cgroup (host-memory blindness → `OLLAMA_MAX_LOADED_MODELS=1`); thinking models
> returning empty content under `json_object` (→ non-thinking generator/judge); the `num_thread`
> spin-wait fix.

---

## Deploy & schema

**Apply the schema** (once, or after editing `scripts/eval-schema.sql`) — from mother:
```bash
kubectl exec -i -n weyland deploy/weyland-postgres -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' < ~/lab/weyland-platform/scripts/eval-schema.sql
```

**Deploy eval code** (assets live in the Dagster user-code image) — rogueone → mother:
```bash
# rogueone (repo root):
rsync -a nodes/mother/lab/weyland-platform/services/weyland-dagster emangini@mother:~/lab/weyland-platform/services/
# mother:
docker build -t weyland-dagster-user-code:local ~/lab/weyland-platform/services/weyland-dagster/
docker save weyland-dagster-user-code:local | sudo k3s ctr images import -
docker image prune -f
kubectl rollout restart deployment/dagster-user-code deployment/dagster-webserver deployment/dagster-daemon -n weyland
kubectl rollout status deployment/dagster-user-code -n weyland
```
Restart webserver+daemon too when a **new job** is added (so it registers for `/pipeline/trigger`).

## Operating — trigger & query

Postgres queries use this wrapper (substitute the `<SQL>`):
```bash
kubectl exec -n weyland deploy/weyland-postgres -- sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "<SQL>"'
```
Jobs are triggered via the tool-server (reuses `/pipeline/trigger`):
```bash
curl -s -X POST http://localhost:30080/pipeline/trigger -H "Content-Type: application/json" -d '{"job_name":"<job>"}'
```
- **`weyland_eval_job`** — question-gen + run-matrix (fresh run; ~40–60 min on CPU, 10 Q × 6 models).
- **`weyland_eval_score_job`** — LLM-as-judge scoring of the latest run (~15 min w/ deepseek, ~45–60 w/ mistral).

**Progress checks:**
```sql
SELECT id, status, question_count, notes FROM eval_runs ORDER BY id DESC;
SELECT run_id, model, count(*) AS n, round(avg(latency_ms)) AS avg_ms, count(error) AS errs FROM eval_results GROUP BY run_id, model ORDER BY run_id DESC, model;
```

**Leaderboard (model × metric, one run)** — replace `<RUN_ID>`:
```sql
SELECT model,
  round(avg(score) FILTER (WHERE metric='faithfulness')::numeric,3)      AS faithful,
  round(avg(score) FILTER (WHERE metric='answer_relevancy')::numeric,3)  AS answer_rel,
  round(avg(score) FILTER (WHERE metric='context_relevancy')::numeric,3) AS context_rel
FROM eval_results r JOIN eval_scores s ON s.result_id = r.id
WHERE r.run_id = <RUN_ID>
GROUP BY model ORDER BY faithful DESC NULLS LAST;
```
Long-format view: `SELECT * FROM eval_leaderboard WHERE run_id = <RUN_ID> ORDER BY metric, avg_score DESC;`

> **Shell-escaping note:** the `FILTER (WHERE metric='faithfulness')` single-quotes must be escaped
> when passed through the `kubectl exec … -c "…"` wrapper (`'"'"'faithfulness'"'"'`), or just run
> the SQL from a `psql` shell / `kubectl exec -it … psql`.

**Re-score a run with a different judge** (the split-job payoff — no matrix re-run):
```bash
# 1. clear existing scores for the run (scoring skips already-scored rows)
#    DELETE FROM eval_scores WHERE result_id IN (SELECT id FROM eval_results WHERE run_id=<RUN_ID>);
# 2. swap the judge (no rebuild — kubectl set env rolls the pod), then wait
kubectl set env deployment/dagster-user-code -n weyland EVAL_JUDGE_MODEL=mistral-small3.2:24b
kubectl rollout status deployment/dagster-user-code -n weyland
# 3. re-run scoring
curl -s -X POST http://localhost:30080/pipeline/trigger -H "Content-Type: application/json" -d '{"job_name":"weyland_eval_score_job"}'
```
Judges: `deepseek-coder-v2:16b` (default, fast) · `mistral-small3.2:24b` (slower, more nuanced).
`EVAL_TEST_SIZE`, `EVAL_GENERATOR_MODEL`, `EVAL_BACKEND`, `EVAL_ASK_LIMIT` are similarly env-tunable.

## Decision Record — Ragas REJECTED (2026-06-12)

**Decision:** Do **not** use Ragas — neither for test-set generation nor for scoring. Use
**direct-prompt generation + LLM-as-judge scoring** via Ollama instead.

**Context:** B4 originally planned to "use Ragas to auto-generate" questions and use its metrics for
scoring. Before committing, we chose to **validate the cost with evidence instead of assuming it**
(the earlier framing of "slow/heavy" was an unvalidated prior). We tested on rogueone in a throwaway
venv.

**Evidence — measured, not assumed:**

1. **It is broken in the current release.** With the latest resolved versions
   (`ragas 0.4.3`, `langchain 1.3.9`, `langchain-community 0.4.2`, `langchain-core 1.4.7`),
   `import ragas` fails immediately:
   ```
   ragas/llms/base.py", line 12, in <module>
       from langchain_community.chat_models.vertexai import ChatVertexAI
   ModuleNotFoundError: No module named 'langchain_community.chat_models.vertexai'
   ```
   Ragas hard-imports a module path that recent `langchain-community` **deleted** (Vertex AI moved
   to the separate `langchain-google-vertexai` package). So the current Ragas release **cannot even
   import** next to current LangChain. Installing `langchain-google-vertexai` does **not** fix it —
   it provides `langchain_google_vertexai.ChatVertexAI`, not the old `langchain_community...` path
   Ragas demands. The fix sits in **unmerged** PRs (explodinggradients/ragas #2739, #2746; issue
   #2741, ~3 weeks old at time of writing).

2. **It is enormous.** Installing `ragas` (+ the `langchain-google-vertexai` we tried) pulled
   **~100 packages**, including **Google Cloud's entire AI Platform SDK** —
   `google-cloud-aiplatform`, `-bigquery`, `-storage`, `-vectorsearch`, `google-genai` — plus
   `pyarrow`, `datasets`, `langgraph`, `pandas`, `scipy`, `scikit-network`. To generate **text
   questions** in a single-user LAN lab that will never touch Vertex AI. That bloat would land in
   the Dagster user-code image.

3. **Speed: unmeasured** — it never ran (blocked by #1). Getting a speed number would require
   version-archaeology pins or a `sys.modules` monkeypatch hack. Two of three axes (weight +
   fragility) were already conclusive, so we stopped.

**Why the lean path wins here:** LLM-as-judge **is what Ragas does internally** — it's an
LLM-as-judge framework. We get ~the same metrics (faithfulness, answer/context relevancy) from a
few direct, JSON-constrained Ollama prompts: **zero dependency constellation, fully on-LAN,
reproducible, no version roulette.** Ragas earns its keep at *production scale* — standardized,
citable metrics across teams/CI — which is exactly the driver this lab does not have
(see [[feedback-its-a-lab]]). The direct-prompt path already **out-performed** Ragas in practice:
it generated 10 solid, corpus-grounded questions while Ragas couldn't load.

**Cost of this decision:** none. We keep the 10 generated questions; Steps 3–5 need no Ragas; and
we drop `ragas` / `langchain*` from the Dagster image to slim it back to its pre-B4 footprint.

**Revisit if:** the Ragas fix ships (PRs merge) **and** you specifically want canonical, citable
metric definitions for sharing/comparison. Until both are true, the lean path is strictly better
for this lab.
