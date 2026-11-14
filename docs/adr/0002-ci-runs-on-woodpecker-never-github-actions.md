# CI runs on Woodpecker, never GitHub Actions

## Status

accepted

Date: 2026-11-12

## Context and Problem Statement

Every repo the lab manages needs CI that reports to the lab's own tooling (Trunk, Port, the Sonar gate), on the lab's agents, at $0. GitHub Actions was proposed for repos that had no pipeline.

## Decision Drivers

* One CI system for every managed repo, with the same gates and reporting.
* Runs on the lab's own agents (rogueone, mother).
* $0.

## Considered Options

* Woodpecker CI for every repo
* GitHub Actions for the repos without a pipeline

## Decision Outcome

Chosen option: Woodpecker for every repo (owner, 2026-11-12: "We use woodpecker").

### Consequences

* Good, because every repo shares the org secret, the Trunk upload and the Port notification already wired in Woodpecker.
* Bad, because a repo with an existing GitHub Actions workflow must be moved, not merely supplemented (MyBodyGraph and grkit were, B245).

## More Information

Runbook: [woodpecker.md](../runbooks/woodpecker.md) (repos table). Backlog B245.
