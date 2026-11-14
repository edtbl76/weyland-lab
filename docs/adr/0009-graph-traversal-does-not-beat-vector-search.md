# Graph-aware retrieval does not beat vector search on this corpus

## Status

accepted

Date: 2026-11-12

## Context and Problem Statement

B38 asked whether walking the declared knowledge graph (B37 `RELATED_TO` edges) improves RAG retrieval over plain vector search.

## Decision Drivers

* Measured on pinned exams (golden, multi_entity) with one model and the 3-judge panel.

## Considered Options

* Plain vector search
* Graph rerank (`neo4j_graph_rerank`)
* Graph expand (`neo4j_graph_expand`)

## Decision Outcome

Chosen option: Plain vector search, because golden conceptual context relevancy was 0.948 against 0.860 (rerank) and 0.852 (expand), and on two-entity questions rerank found both entities 1/10 against vector's 5/10.

### Consequences

* Good, because no graph traversal sits on the retrieval path.
* Neutral: Phase 1 of B38 (LLM entity extraction) is shelved; re-open only with a design that measures better.

## More Information

Verdict: [graph-aware-retrieval.md](../concepts/graph-aware-retrieval.md). Backlog B38.
