# Graph-aware retrieval (GraphRAG), measured — B38 Phase 0 verdict (2026-11-12)

**Verdict: on this corpus, walking the declared knowledge graph does not improve retrieval — not for single-concept
questions and not for two-entity ones. Plain vector search stays.** Phase 1 (LLM entity/relation extraction) is
shelved: its gate was "only if Phase 0 shows traversal helps", and it did not. The useful next lever the data pointed
to was the two-entity question, not more edges; B247 measured four fixes for it (below) and **adaptive depth** won:
a comparison question is searched at twice the depth, on every backend.

## What was tested

The B37 frontmatter graph links the AI-DLC knowledge base: 510 `:Entry` documents, 2,311 declared `RELATED_TO`
edges (about 4.5 per entry). Before B38 nothing traversed it at answer time. Two retrieval modes were added to the
tool-server beside plain `neo4j` (vector only), and measured on pinned exams with one answer model
(`qwen3:30b-a3b`), the existing 3-judge panel, and per-run eval settings (`docs/runbooks/eval-harness.md`):

| Mode | How it works |
|---|---|
| `neo4j` | vector top-k on `Chunk.embedding` |
| `neo4j_graph_rerank` | vector top-10 plus each hit's best `RELATED_TO` neighbour chunk, scored by similarity + 0.1 × the share of the pool's documents linked to the candidate's; returns k |
| `neo4j_graph_expand` | vector top-k, then append the best chunk of each hit's best related document (up to 2k) |

`GRAPH_BONUS` (0.1) and `GRAPH_CANDIDATES` (10) were fixed before the runs, not tuned on the exam.

## Results

**Golden set, conceptual half** (eval runs 36–39; the lexical half is weyland docs with no `RELATED_TO` edges, a
control: `expand` retrieved exactly the baseline's chunks there, so its lexical score spread, about ±0.035 context
relevancy, is the judge-plus-generation noise floor):

| Run | Context relevancy | Answer relevancy | Faithfulness |
|---|---|---|---|
| `neo4j` k=3 | **0.948** | 0.947 | 0.863 |
| `neo4j_graph_rerank` k=3 | 0.860 | 0.897 | 0.843 |
| `neo4j` k=6 (volume control) | 0.938 | 0.953 | 0.920 |
| `neo4j_graph_expand` (≤6) | 0.852 | 0.853 | 0.825 |

**Two-entity set** (`eval_sets/multi_entity.json`, runs 40–41; 6 questions on linked pairs, 4 on unlinked pairs):
did retrieval find BOTH entities the question names?

| Pairs | `neo4j` | `neo4j_graph_rerank` |
|---|---|---|
| linked (6) | **3/6** | 1/6 |
| unlinked (4) | **2/4** | 0/4 |

Context relevancy: linked 0.811 vs 0.783, unlinked 0.675 vs 0.667 — flat to worse, inside the noise.

## Why it fails here (the learning)

1. **The bonus rewards hubs, not answers.** A candidate scores higher the more retrieved documents it links to, so the
   graph promotes documents central to the neighbourhood over the specific one the question names. "What role do
   direct managers play (ADKAR)?" lost all three ADKAR chunks to McKinsey 7S / organizational design / Kotter
   (context relevancy 0.90 → 0.17). "MoSCoW vs RICE" lost RICE to `decision-matrix`, the hub linked to both.
2. **Rerank swaps entities instead of adding the missing one.** Tech Radar vs Wardley: vector found Tech Radar only,
   rerank Wardley only. The single win in the first run (ADKAR vs Kotter, 0.867 → 0.967) was that same swap landing well.
3. **Declared links connect neighbouring topics, not answers.** `RELATED_TO` says "a practitioner would also look at",
   which is the wrong relation for "which chunk answers this question".
4. **Approximate vector search changes with k.** Asking the HNSW index for 10 candidates returns a different top 3
   than asking for 3 (rerank changed 5 of 10 lexical questions with no graph edges involved). Any reranking
   experiment must hold k constant, or use exact search, before crediting the reranker.
5. **Vector search's real two-entity failure is one-sidedness:** in 5 of 10 two-entity questions it retrieved only
   one of the two entities (the stronger term dominates the query embedding). That is what query decomposition
   targets — B247.

## What stays

- **Adaptive depth** (B247): `/context/search` and `/context/ask` search a comparison question at 2 x `limit` on every
  backend (`is_comparison` / `retrieve` in the tool-server).
- All six experimental modes were **retired 2026-11-13** (B247 close): measured, lost, recorded here. The code is in git
  history (`c04080e6`) if a future design wants to start from it.
- Per-run eval settings (backend, models, depth, question set) and the `multi_entity` exam.
- The Neo4j vector-index fix and the real index health check found on the way (`runbooks/neo4j.md` § Vector index).

**Re-open condition for Phase 1:** a traversal design, or a corpus, that shows a measured gain over plain vector
search on these exams. That would be a new item citing these numbers.

## B247: fixing the two-entity question (2026-11-13)

Vector search found both entities in only 5 of 10 two-entity questions. Four fixes were built as tool-server backends
and measured with the same model and judges, on `multi_entity` (does retrieval find both?) and on `golden` (does it
hurt ordinary questions?). Baselines: `neo4j` k=3 (run 40, golden 36) and k=6 (run 42).

| Design | How it works | Both entities | Golden conceptual ctx | Verdict |
|---|---|---|---|---|
| `neo4j` k=3 | plain vector top 3 | 5/10 | 0.948 | baseline |
| `neo4j` k=6 | plain vector top 6, every question | **8/10** | 0.938 | depth alone fixes most of it |
| rule decomposition (43 / 45) | a pattern splits "X vs Y"; one search per entity, merged | 7/10 | 0.870 | lost: linked ctx 0.811 → 0.567 |
| LLM decomposition (44 / 46) | `llama3.2:3b` on CPU names the entities | 7/10 | **0.410** | lost badly; 127 s per question |
| contextual sub-queries (47 / 49) | per entity, "<entity> — <whole question>" | 6/10 | 0.972 | lost: unlinked ctx 0.517 |
| **adaptive depth** (48 / 50) | the pattern only DETECTS a comparison; those get 2 x k | **8/10** | 0.937 | **adopted** |

**Confirmed on `pgvector`** (the default backend) after adoption, same exam, live before/after (runs 51 → 52): both entities 5/10 → 7/10 (RACI and Git workflow recovered; Service Blueprinting still missed), linked context relevancy flat (0.769), linked faithfulness 0.831 → 0.861. Unlinked answer scores fell on two questions: feature store (the corpus gap — more chunks, still no right one) and Kafka vs Spark, where the extra slot went to the stale `test_main.py` chunk holding the exam's wording (the corpus still had it at run time; see learning 5).

Adaptive depth also had the best linked faithfulness (0.914) and the best golden lexical context relevancy (0.838), at no
extra latency or model call. The other two misses (feature store vs RAG retrieval; Tech Radar vs Wardley Map) are a
corpus gap: no entry covers the second entity.

**The learning:**

1. **A bare entity name is a bad query for an opaque term.** "RACI matrix", "Kano model", "ADKAR model" alone
   retrieved junk (`anthropic-model-watch.yaml`, `revenue-management.md`): the embedder does not know the acronym and
   keys on generic words like "model". The question's other words were what found them.
2. **Putting the question back into each sub-query undoes the split.** "<entity> — <whole question>" embeds close to the
   whole question, so both sub-queries collapse toward the dominant entity again.
3. **The answer chunks were already ranked 4-6.** Depth recovered them; splitting threw away the context that ranked
   them. Spend the result budget, do not re-ask the question.
4. **A small local model is the wrong tool on the retrieval path.** It was slower than the answer model's generation
   and its entity lists hurt ordinary questions.
5. **Eval contamination:** the RAG corpus indexes this repository, and the tool-server's test file held the exam's
   exact questions, so it was retrieved as "relevant context" (Kafka vs Spark, ctx 0.87 → 0.33). Fixed at the root:
   test code no longer enters the corpus, and a CI audit fails if any pinned-exam question appears verbatim in an
   indexed document (`docs/runbooks/rag-stream.md` § What goes into the corpus).
