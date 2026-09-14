# Demo — ONNX embedding migration: dropping torch from every mother CPU image (U13)

## The point

Four mother CPU images (`weyland-tool-server`, `weyland-agent`, `weyland-dagster`, `weyland-guard`) each baked
`sentence-transformers` → `torch` (~1.2 GB CPU wheel; dagster pulled the whole CUDA-13 stack) purely to run a bge
embedder or a DeBERTa classifier at inference time. U13 swaps the runtime to **raw ONNX Runtime**
(`onnxruntime` + `tokenizers` + numpy) via a multi-stage Dockerfile — a throwaway builder stage exports the model
→ `model.onnx` + `tokenizer.json` (torch lives ONLY there, discarded), the runtime stage runs it torch-free.

The load-bearing claim is **byte-equivalence**: the ONNX outputs must match sentence-transformers exactly, or every
hydrated vector store (Qdrant/Weaviate/Neo4j/pgvector/LanceDB) would need re-embedding. Every section below is **RUN**;
the output shown is real.

This is a refactor, not a new user-facing workflow, so there is **no UI walkthrough** — the demo is the CLI
equivalence proof + the in-cluster prod verification (the same checks the DoD's "the demo IS the test" requires).

Related: runbook [embedding-model-swap.md](../runbooks/embedding-model-swap.md) (how to swap the model now),
[guardrails.md](../runbooks/guardrails.md) (§ Models); backlog `U13`; memory `u13-onnx-image-slimming`.

---

## #1 — Equivalence proof (why no re-hydration) · in-docker spike

**Proves:** the raw `onnxruntime` + `tokenizers` runtime produces vectors/logits identical to the
`sentence-transformers` originals, so the vectors already in the stores stay valid.

### CLI walkthrough (RUN)

```
[rogueone] # bge bi-encoder (tool-server / agent / dagster): export bge → ONNX, compare vs sentence-transformers
cosine(ST, raw-onnxruntime): [1.0, 1.0, 1.0]  -> RAW RUNTIME EQUIVALENT

[rogueone] # DeBERTa classifiers (guard): grounding cross-encoder + prompt-guard, ORTModelForSequenceClassification
max|ONNX - ST| logits: 0.0 -> LOGIT-EQUIVALENT          # grounding NLI, 3-logit
optimum pipeline output == transformers pipeline output  # prompt-guard, scores match to ~1e-9
```

**UAT:** cosine 1.0 (embedders) and logit diff 0.0 (classifiers) → the hydrated vectors and every calibrated guard
threshold (`GROUNDING_THRESHOLD=0.15`, `PROMPT_GUARD_THRESHOLD=0.5`) remain valid unchanged. **No re-hydration.**

---

## #2 — torch is gone from every runtime image · in-docker

**Proves:** the runtime stage carries no torch/sentence-transformers/transformers — only onnxruntime + tokenizers
(+ Presidio/spaCy for the guard's PII path, which never used torch).

### CLI walkthrough (RUN)

```
[rogueone] docker run --rm registry.weyland.lab/weyland-agent:v8 python -c "import importlib.util as u; \
  print('torch', bool(u.find_spec('torch')), 'onnxruntime', bool(u.find_spec('onnxruntime')))"
torch False onnxruntime True

[rogueone] docker run --rm registry.weyland.lab/weyland-guard:v12 python -c "...find_spec..."
torch: ABSENT   transformers: ABSENT   onnxruntime: PRESENT   presidio_analyzer: PRESENT
```

Sizes: dagster **8.38 → 3.77 GB** (−4.6 GB, CUDA stack pruned) · tool-server 2.57 → 1.38 GB · agent 2.06 GB ·
guard 2.38 GB.

**UAT:** `torch` resolves to absent in all four images; embeddings still come out 768-dim (bge-base) / 384-dim
(bge-small), norm 1.0.

---

## #3 — Prod transaction: tool-server actually retrieves (the byte-equivalence holds in-cluster)

**Proves:** the single most important check — the ONNX query embedding lands in the SAME vector space as the
ST-hydrated index, so retrieval returns relevant results, not junk.

### CLI walkthrough (RUN, in-cluster)

```
[rogueone] kubectl -n weyland exec deploy/weyland-tool-server -- python -c \
  "...POST /context/search {'query':'What is the weyland data mesh?','limit':3}..."
results: 3
top source: tools.md | similarity: 0.7493 | content: ## Data Mesh — Feature & Vector Stores ...
```

**UAT:** non-empty, on-topic results with a healthy similarity (0.7493) → the ONNX embedder loaded, the vector DB
is connected, and the index (built with sentence-transformers) is still queryable with ONNX vectors.

---

## #4 — Prod: dagster code location LOADS with the ONNX resource

**Proves:** the migrated `SentenceTransformerResource` → `OnnxEmbedder` (`resources/onnx_embedder.py`) + the
`datasets_lib/loaders` embedder import cleanly and the definitions load (a pod can be Ready with the gRPC port
bound but definitions broken — this asks the real question).

### CLI walkthrough (RUN, in-cluster)

```
[rogueone] kubectl -n weyland exec deploy/dagster-user-code -- python -c \
  "...GraphQL { workspaceOrError { locationEntries { name loadStatus locationOrLoadError } } }..."
location=weyland_pipeline loadStatus=LOADED type=RepositoryLocation
```

**UAT:** `LOADED` / `RepositoryLocation` (not `PythonError`) → the ONNX embedder resource loaded, no torch.

---

## #5 — Prod: guard's two ONNX classifiers load AND score

**Proves:** both DeBERTa validators are ACTIVE (a validator whose model fails to load is silently skipped from the
set) and a real grounding request scores the cross-encoder without error.

### CLI walkthrough (RUN, in-cluster)

```
[rogueone] kubectl -n weyland exec deploy/weyland-guard -- python -c "...GET /ready..."
validators: ['grounding.nli', 'llama_guard.safety', 'pii.presidio', 'policy.audit', 'policy.gate', 'prompt_guard.injection']
prompt_guard.injection (OnnxTextClassifier): ACTIVE
grounding.nli (OnnxCrossEncoder): ACTIVE

[rogueone] kubectl -n weyland exec deploy/weyland-guard -- python -c "...POST /guard/output (answer+sources)..."
{"request_id": "u13-verify-1", "decision": "allow", "verdict": null}   # SHADOW mode — scored, advisory
```

**UAT:** both `OnnxTextClassifier` (prompt-guard) and `OnnxCrossEncoder` (grounding) present in `/ready`; the
grounding POST is processed by the cross-encoder with no error. `agent /ready` likewise returns `{"status":"ready"}`
(OnnxBge loaded); torch absent in both pods.

---

## #6 — The OnnxBge sync guard (the Pillar-8 cascade) · negative case RUN

**Proves:** `OnnxBge` is byte-duplicated across `weyland-tool-server` (main.py) and `weyland-agent` (retrievers.py)
— a vector-space contract (both must embed identically or the agent retrieves against a space the index was not
built in), the same class DoD Pillar 8 flags for `verdict.py`. `scripts/check-onnx-sync.sh` compares the method
bodies modulo docstring and **fails closed**. A guard nobody has watched fail is not a guard:

### CLI walkthrough (RUN)

```
[rogueone] bash scripts/check-onnx-sync.sh
OK — OnnxBge method bodies are identical across weyland-tool-server and weyland-agent (17 normalized lines).  # exit 0

[rogueone] # bats negative cases (fixtures)
ok 1 identical bodies with DIFFERENT docstrings pass exit 0 (docstring is ignored)
ok 2 a changed method body is DRIFT exit 1, with the reason
ok 3 a missing file is CANNOT-RUN exit 2, never a false pass
ok 4 a file with no OnnxBge class is CANNOT-RUN exit 2, not a false pass
ok 5 the real repo copies are in sync (the live invariant)
```

**UAT:** exit 0 in sync · exit 1 on a changed method body (drift) · exit 2 cannot-run — never a false pass. Wired
into the CI `repo-guards` step beside `check-verdict-sync.sh`.

---

## Cleanup / teardown

**Read-only.** Every check above reads live state; the docker `--rm` runs and the in-cluster `exec`s create nothing.
The local `:u13-verify` build images used during development were removed (`docker rmi`). No data is written.
