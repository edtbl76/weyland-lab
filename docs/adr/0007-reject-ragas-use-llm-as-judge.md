# Reject Ragas; generate and score evals with direct prompts and an LLM judge

## Status

accepted

Date: 2026-06-12

## Context and Problem Statement

B4 planned to use Ragas to generate eval questions and score answers.

## Decision Drivers

* It must run on the lab's local models.
* Measured, not assumed.

## Considered Options

* Direct-prompt generation plus an LLM-as-judge panel via Ollama
* Ragas

## Decision Outcome

Chosen option: Direct prompts plus an LLM judge, because Ragas was broken in its current release (`import ragas` failed against the resolved langchain) when tested on rogueone.

### Consequences

* Good, because the eval stack has no langchain dependency to break.
* Bad, because metrics are the lab's own definitions, not a library's (they are pinned in the eval harness).

## More Information

Decision Record: [eval-harness.md](../runbooks/eval-harness.md) § Decision Record — Ragas REJECTED.
