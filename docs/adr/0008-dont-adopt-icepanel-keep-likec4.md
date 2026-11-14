# Don't adopt IcePanel; keep the architecture model in LikeC4

## Status

accepted

Date: 2026-11-03

## Context and Problem Statement

IcePanel, a hosted C4 tool, was evaluated against LikeC4, the lab's architecture model as code.

## Decision Drivers

* The model lives in git.
* $0.

## Considered Options

* LikeC4
* IcePanel (free plan)

## Decision Outcome

Chosen option: LikeC4, because IcePanel's free plan holds 100 model objects against the lab's 156 elements, cannot sync from git, and puts every useful feature on a paid plan.

### Consequences

* Good, because the model stays reviewable code (`docs/architecture/weyland.likec4`).
* Neutral: none.

## More Information

Concept: [icepanel.md](../concepts/icepanel.md). Backlog B236.
