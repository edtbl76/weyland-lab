# Langfuse evaluation — grading the RAG on live traffic (B103)

Prompt federation + sessions told us *what ran*. Evaluation tells us *how good it was* — continuously, on real
production traces, without a human in the loop for every answer. This is the **online** eval lane; it complements the
**offline** B84 MLflow judge-panel (the pre-deploy benchmark) and shares the same B96 fixtures.

## The four pieces (all self-hosted OSS, $0)

| Piece | What it is |
|---|---|
| **Scores** | the primitive — a numeric/categorical value on a trace/observation/session |
| **Evaluators** | 9 **native** LLM-as-judge criteria running live per-trace on `rag-generate` |
| **Datasets** | the git eval-fixture SSOT mirrored into Langfuse (`weyland-golden`, `weyland-regression`) |
| **Human Annotation** | the `weyland-rag-review` queue + a `human_quality` label, for manual spot-checks |

## The 9 evaluators

Created programmatically via Langfuse's `/api/public/unstable/evaluation-rules` API (they run on Langfuse's own engine,
scoring every `rag-generate` observation, judged by `wl-judge-oss` = local gpt-oss:20b, $0):

- **7 managed** (from Langfuse's library): Relevance, Helpfulness, Hallucination, Conciseness, Toxicity,
  Contextrelevance, Faithfulness
- **2 custom** (weyland-specific, absent from the library): **`citation`** (does the answer cite its sources, as the
  `rag_system` prompt requires?) and **`refusal`** (when the context lacks the answer, does it say so rather than guess?)

## See it yourself

Fire a RAG call, wait ~1–3 min (9 judge calls run async in `langfuse-worker`), then check the scores landed:

```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "import os,httpx; print(httpx.post('http://weyland-tool-server.weyland.svc.cluster.local:8080/context/ask', json={'query':'what NodePort does GizmoSQL listen on','backend':'pgvector'}, timeout=180).status_code)"
```
```
kubectl -n weyland exec deploy/dagster-user-code -- python -c "
import os,httpx
from collections import Counter
h=os.environ['LANGFUSE_HOST'].rstrip('/'); a=(os.environ['LANGFUSE_PUBLIC_KEY'],os.environ['LANGFUSE_SECRET_KEY'])
s=httpx.get(h+'/api/public/v2/scores',auth=a,params={'limit':40},timeout=20).json().get('data',[])
print(dict(Counter(x.get('name') for x in s)))
"
```

Or in the UI: **Langfuse → Tracing →** open a `rag-generate` trace → the 9 scores sit on the generation; **Evaluation →
Scores** trends them over time; **Datasets → weyland-golden** is the 20-question benchmark; **Human Annotation →
weyland-rag-review** is the manual queue.

## Who owns what (source vs mirror)

- **git owns the exam** — `weyland_pipeline/eval_sets/*.json` (golden = B96 20, regression = Promptfoo gate). A pinned
  set is a git commit. `langfuse_eval.py` mirrors it → Langfuse Datasets (a **copy**, never the source).
- **Langfuse owns online scoring** — the native evaluators + the Scores/Sessions views.
- **MLflow owns the offline leaderboard** (B84); **LiteLLM owns the judge model** (`wl-judge-oss`); **Promptfoo owns the
  CI regression gate**.
- All of it is **codified** as Dagster `registrations` assets (`langfuse_golden_dataset`, `langfuse_codified_evals`), so
  a Langfuse DB reset rebuilds every evaluator + dataset by re-materializing.

## Gotchas (so you don't re-learn them)

- Langfuse blocks private-IP LLM connections ("Blocked IP address detected") — fix is
  `LANGFUSE_LLM_CONNECTION_WHITELISTED_HOST`, **not** the no-op `LANGFUSE_UNSAFE_TRUSTED_PRIVATE_IPS` (langfuse#13097).
- The eval-config API is under `/api/public/unstable/`, **not** `/eval-configs` (which 404s). Native rules have **no
  per-rule model** — they all use the connection's default, so we run everything on `wl-judge-oss`.

Runbook: [runbooks/langfuse.md](../runbooks/langfuse.md) § Evaluation. Design: `../design/langfuse-evaluation-design.md`.
Memory: `langfuse-evaluation-b103`.
