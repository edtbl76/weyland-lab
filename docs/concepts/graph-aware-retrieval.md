# Graph-aware retrieval (GraphRAG), measured — B38 Phase 0 verdict (2026-11-12)

**Verdict: on this corpus, walking the declared knowledge graph does not improve retrieval — not for single-concept
questions and not for two-entity ones. Plain vector search stays.** Phase 1 (LLM entity/relation extraction) is
shelved: its gate was "only if Phase 0 shows traversal helps", and it did not. The useful next lever the data pointed
to is query decomposition (B247), not more edges.

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

- The two graph modes stay as **experimental**, eval-selectable backends (cost nothing idle; documented in
  `docs/api.md`), for any future traversal design.
- Per-run eval settings (backend, models, depth, question set) and the `multi_entity` exam.
- The Neo4j vector-index fix and the real index health check found on the way (`runbooks/neo4j.md` § Vector index).

**Re-open condition for Phase 1:** a traversal design, or a corpus, that shows a measured gain over plain vector
search on these exams. That would be a new item citing these numbers.
