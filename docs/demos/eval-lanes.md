# The three evaluation lanes — when to use each (B84 P2)

Weyland runs **three complementary LLM-eval passes** over the same RAG (`/context/ask`). They are *not* redundant —
each answers a different question, at a different point in the dev loop, with a different speed/robustness trade-off.
This is the "why would I reach for this one?" reference. Built + validated 2026-07-24/25.

> **Not a bake-off.** P2 was never "pick the winner and delete the rest." All three are kept because each does a job
> the others do badly. Reach for the one that matches the question you're actually asking.

## The one-glance answer

| Lane | The question it answers | Reach for it when… | Verdict | Speed | Judge | Test set |
|---|---|---|---|---|---|---|
| **Judge panel** (B4/B96) | *Which model wins the RAG task — robustly, on which slice, as of when?* | You're **selecting/ranking models** or publishing the canonical leaderboard | per-metric **scores** (0–1), sliceable | ~40–70 min | **≥3 judges, averaged** | golden 20Q (10 conceptual + 10 lexical) × 6 models |
| **mlflow.evaluate** (P2b) | *What do GenAI-standard metrics say, in MLflow's own Evaluation UI, tied to experiment lineage?* | You want the **MLflow-native surface** / standard metric names / to drill per-row in the tracking server | MLflow metrics + Evaluation UI | ~3 min/model | 1 judge (local) | reuses the panel's stored answers |
| **Promptfoo** (P2c) | *Did this prompt or model change **regress** my fixed cases?* | You **edited a prompt** (B100 registry) or swapped a model and want a fast red/green gate | **PASS/FAIL** per assertion (exit 100 on any fail) | ~2 min | deterministic + 1 rubric judge | small hand-authored matrix × 2 models |

**Rule of thumb:** *ranking* → panel · *standard GenAI metrics / MLflow lineage* → mlflow.evaluate · *"did I break it?"* → Promptfoo.

## Where each sits in the loop

```
edit a prompt / swap a model ─▶  Promptfoo   (seconds–minutes, red/green: did I regress?)
                                     │ passes
periodically, to re-rank      ─▶  Judge panel (batch, robust: which model is actually best?)
                                     │ produces answers + the leaderboard
deep-dive / standard surface  ─▶  mlflow.evaluate (re-score those answers in MLflow's UI)
```

Promptfoo is the **fast inner-loop gate** (run it every time you touch a prompt). The panel is the **periodic
authority** (run it to re-decide the model). mlflow.evaluate is the **drill-down surface** over what the panel already
produced. Different cadences, different jobs.

---

## Lane 1 — The judge panel (B4/B96) · the canonical leaderboard

**What it is.** The Dagster eval pipeline: the golden 20-question exam runs × 6 models through the **live**
`/context/ask` (`eval_run_matrix` → `eval_results`), then **every** answer is scored by **≥3 judge models and
averaged** (`eval_scores` → the `eval_leaderboard` view). Metrics: `faithfulness`, `answer_relevancy`,
`context_relevancy`, sliceable by `question_type` (conceptual vs lexical).

**Its unique value — robustness.** A *single* LLM judge is noisy: `qwen3:30b-a3b` swung **5th → 1st** purely by
swapping the judge (see [eval-harness.md](../runbooks/eval-harness.md#first-results-run-3--10-questions-2026-06-13)).
The panel averages that swing away — the field tightened to a stable 0.75–0.82 and `gpt-oss:20b` held top-2 under
*every* configuration. This is the only lane you'd trust to **pick a model**, and the one that's **productized** (a
governed DataHub Data Product + Superset dashboard — see [model-eval-product.md](model-eval-product.md)).

**Reach for it when:** choosing/defending the RAG-default model · reporting "which model, on what slice, as of when" ·
slice analysis (does model X only win on lexical?) · anything that needs a defensible number.

**Don't reach for it when:** you just changed a prompt and want a fast yes/no — it's a 40–70 min batch, wildly overkill
for that.

**Run it** (mother, via the tool-server trigger):
```
[mother] curl -s -X POST http://localhost:30080/pipeline/trigger -H "Content-Type: application/json" -d '{"job_name":"weyland_eval_job"}'
[mother] curl -s -X POST http://localhost:30080/pipeline/trigger -H "Content-Type: application/json" -d '{"job_name":"weyland_eval_score_job"}'
```
Full operating guide: [runbooks/eval-harness.md](../runbooks/eval-harness.md).

---

## Lane 2 — `mlflow.evaluate` (B84 P2b) · the GenAI-native surface

**What it is.** `scripts/eval_mlflow_evaluate.py` reads the **panel's already-stored answers** (latest scored run's
`model, question, context, answer` from Postgres) and re-scores them with **MLflow's GenAI metrics**
(`faithfulness` + `answer_relevance`), one MLflow run per model in the `mlflow_evaluate` experiment. Judge = a local
Ollama model via the OpenAI-compat shim (on-LAN, $0). It does **not** re-run the RAG — it re-*judges* the same outputs.

**Its unique value — the MLflow surface + a standard metric vocabulary.** You get the metrics inside MLflow's
**Evaluation UI**, tied to experiment/run lineage, using metric definitions an outside reader recognizes. Because it
scores the *identical* answers the panel scored, it's also the clean way to **see single-judge noise vs. the panel's
robustness on the same data**.

**Reach for it when:** you want eval results *in MLflow* (next to traces + the prompt registry) · you want
industry-standard GenAI metric names for sharing · you're comparing "one MLflow judge" vs "the 3-judge panel" on the
same answers.

**Don't reach for it when:** you need the trustworthy *ranking* (single judge — noisier than the panel) or a fast gate.

**Caveats.** Uses the **legacy** `mlflow.evaluate` + `mlflow.metrics.genai.*` API, **deprecated since MLflow 3.4** — the
modern path is `mlflow.genai.evaluate`; adoption (not just this spike) would migrate to it. Needs `matplotlib`
(installed inline by the script). ~3 min/model.

**Run it** (mother — no rebuild; the user-code pod already has the deps + env):
```
[mother] kubectl -n weyland exec -i deploy/dagster-user-code -- python < scripts/eval_mlflow_evaluate.py
```
Then compare the `mlflow_evaluate` runs vs the panel's `weyland_rag_eval` at `mlflow.weyland.lab` — same golden set,
different judging mechanism.

---

## Lane 3 — Promptfoo (B84 P2c) · the prompt-regression gate

**What it is.** A self-hosted ($0) declarative eval harness (`k8s/promptfoo/`, always-on web UI at
`promptfoo.weyland.lab`). `promptfooconfig.yaml` defines a **model × prompt matrix** that hits the **live**
`/context/ask` (HTTP provider, `transformResponse: json.answer`) with **assertions**: deterministic (`contains-any`) +
`llm-rubric` (a local Ollama judge). It exits **100 on any failed assertion** — CI-gate semantics — and includes an
**off-corpus honest-negative** test (must decline, not fabricate).

**Its unique value — speed + PASS/FAIL gate semantics.** ~2 min, red/green, declarative. It caught a real regression on
first run: `qwen3:14b` conflated the whole data mesh with just the feature/vector layer → the grounding rubric went
red while `gpt-oss:20b` passed. That's the job — flag a quality drop the moment a prompt or model changes, before it
ships. It's the natural partner to the **B100 prompt registry**: bump a `@production` prompt → re-run Promptfoo → see
if you held the line.

**Reach for it when:** you edited a prompt or swapped a model and want a fast gate · pre-merge regression checks ·
red-team-style assertions · a quick eyes-on matrix in a web UI.

**Don't reach for it when:** you need the full 20Q golden ranking (its set is small + hand-authored, single rubric
judge) — that's the panel's job.

**Run it** (mother — evals write to the same `PROMPTFOO_CONFIG_DIR=/data` the UI reads):
```
[mother] kubectl -n weyland exec deploy/promptfoo -c promptfoo -- promptfoo eval -c /config/promptfooconfig.yaml
```
Then view the run at **https://promptfoo.weyland.lab** (Keycloak forward-auth). Edit the matrix/assertions in the
`promptfoo-config` ConfigMap (`k8s/promptfoo/promptfoo.yaml`); `rollout restart deploy/promptfoo` to pick up changes.

---

## How they overlap (and why that's fine)

- **Panel ∩ mlflow.evaluate:** same golden answers, different judging. The panel is the *robust ranking*; mlflow.evaluate
  is the *standard-metric surface* over the same data. Keeping both makes the single-vs-panel-judge contrast visible.
- **Panel ∩ Promptfoo:** both hit the live RAG. The panel is *breadth* (20Q × 6 models, ≥3 judges, batch); Promptfoo is
  *speed* (small matrix, red/green, seconds). One re-decides the model; the other guards each prompt edit.
- **All three, one corpus:** every lane grades the *same* `/context/ask` RAG, so a change shows up consistently — the
  gate goes red, the panel score dips, the MLflow metric drops.

## Related

- [runbooks/eval-harness.md](../runbooks/eval-harness.md) — the panel pipeline (B4) + golden set + retrieval-depth tuning (B96)
- [demos/model-eval-product.md](model-eval-product.md) — the panel leaderboard **productized** (DataHub product + contract + Superset)
- [runbooks/mlflow.md](../runbooks/mlflow.md) — MLflow tracing (B100 P1) + prompt registry (B100 P2), the surfaces Promptfoo/mlflow.evaluate sit beside
- [demos/mlflow-genai.md](mlflow-genai.md) — GenAI tracing + prompt registry demo
