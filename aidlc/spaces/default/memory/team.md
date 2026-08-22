# Team-Level Rules

> This team's affirmed practices and corrections. Loaded after `org.md` as
> strict-additive guidance; contradictions with broader policy are rejected.
> Populated by the practices-discovery affirmation gate. Edit at the gate,
> not directly.

## Way of Working

<!-- Affirmed during practices-discovery. Example: -->
<!-- We use GitHub Flow with feature branches. Branches live 3-5 days max. -->
<!-- Hotfixes branch from main and merge back via expedited review. -->

## Walking Skeleton

<!-- Affirmed during practices-discovery. Example: -->
<!-- We don't run a walking skeleton — our deployment pipeline is mature -->
<!-- and the slice cost outweighs the value at our maturity stage. -->

## Testing Posture

**Methodology**: tdd
**Ordering**: For each applicable testable layer, write the failing test first (Red), implement the minimum that passes it (Green), then refactor while green.

Affirmed 2026-08-22. This replaces reliance on the org-level `test-after` default, which applied only
because no posture had been recorded here. Where a slice is better described as an observable
user-facing scenario, express the test as a scenario — that is a BDD-flavoured way of writing the
Red step, not a different methodology, and it does not change the Red/Green/Refactor ordering above.

**Shell is included.** This repository carries 17 shell scripts and, as of 2026-08-22, no shell test
harness at all — the largest untested surface in the tree. Shell that makes decisions (gate checks,
exit-code logic, argument handling) gets tests like any other layer; `bats` is the harness. Shell
that is purely a sequence of external commands with no branching does not need a test for its own
sake.

## Deployment

<!-- Affirmed during practices-discovery. -->

## Code Style

<!-- Team-specific conventions beyond the linter. Example: -->
<!-- - Prefer named exports over default exports -->
<!-- - All async functions return Result<T, E>, never throw -->

## Forbidden

<!-- Team-specific forbidden patterns -->

## Mandated

<!-- Team-specific mandates -->

## Corrections

<!-- Self-learning loop appends here. -->
