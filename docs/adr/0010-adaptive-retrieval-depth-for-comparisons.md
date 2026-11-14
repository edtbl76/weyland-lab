# Search comparison questions at twice the depth; retire the experimental retrieval modes

## Status

accepted

Date: 2026-11-13

## Context and Problem Statement

Vector search at k=3 found both entities in only 5 of 10 two-entity questions. B247 measured four fixes.

## Decision Drivers

* Both-entity coverage on `multi_entity`.
* No harm to ordinary questions on `golden`.
* No added latency or model call.

## Considered Options

* Adaptive depth: a pattern detects a comparison, searched at 2 x limit
* Rule decomposition (one search per entity)
* LLM decomposition (llama3.2:3b)
* Contextual sub-queries ("entity — whole question")

## Decision Outcome

Chosen option: Adaptive depth, on every backend, because it found both entities in 8/10 (as k=6 did), stayed within noise on golden (0.937 vs 0.948), and costs nothing on other questions; on pgvector it took coverage from 5/10 to 7/10.

### Consequences

* Good, because one `retrieve()` serves `/context/search` and `/context/ask`.
* Neutral: all six experimental modes (B38 x2, B247 x4) were retired; their code is in git history.

## More Information

Verdict: [graph-aware-retrieval.md](../concepts/graph-aware-retrieval.md) § B247. Backlog B247.
