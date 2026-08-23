# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
- When the code-knowledge-base rerun guard reports NO_STORE, no scan-breadth question is presented at all — on a large repository choose the breadth deliberately, brief it explicitly, and record in the `## Scope of Analysis` block exactly what was analyzed deeply versus skimmed, so a later workflow rescans its own area instead of trusting a narrow store (learned 2026-08-21) <!-- cid:reverse-engineering:c1 -->
- Settle architectural decisions before starting an `express` run and brief them in as inputs — `express` runs no design pass, so a decision left open there is never made by the workflow (learned 2026-08-21) <!-- cid:reverse-engineering:c3 -->
- An absent or failed result must NEVER stand for success. `cmd 2>/dev/null` inside a boolean, an empty list, a pipeline whose exit status comes from the last command — each turns an error into a positive answer. This class appeared FIVE times on 2026-08-22 (woodpecker `--output json` silently ignored; `curl -sf` collapsing every non-2xx to exit 0; `NOERROR` matching /error/; a shallow-clone `git diff` failure read as "changed"; a deleted diff file yielding an empty image list that passed a verification gate) — twice inside the very gate built to prevent it. Fail closed: verifying nothing is not verifying successfully (learned 2026-08-22) <!-- cid:code-generation:c14 -->
- Stubbed tests verify the DECISIONS code makes, never its CONTRACT with an external system — the stub author decides what the command returns, so the test confirms the author's assumption. Before encoding any external command's output in a stub, observe the real thing once. Seven defects in `ship-images.sh` survived 47 green tests and were found in three live runs (learned 2026-08-22) <!-- cid:code-generation:c4 -->
- Read the governing document BEFORE choosing a value, not after — `docs/schedules.md` Design Rules, `docs/definition-of-done.md`, the runbook for the system being touched. An undocumented existing exception (e.g. a CronJob absent from the schedules table) is evidence of a GAP, never permission to add another (learned 2026-08-22) <!-- cid:code-generation:c8 -->
- After creating a Kubernetes Secret, verify the STORED value before relying on it — `b64len` should equal ceil(chars/3)*4. An empty or truncated value is accepted silently (DATA 1, pod starts) and fails only at runtime. Credentials come from the gitignored `scripts/.env`, never a paste and never a silent `read` (learned 2026-08-22) <!-- cid:code-generation:c11 -->
- Every Argo Application runs `selfHeal: true`, so `argocd app rollback` and `kubectl rollout undo` are TRAPS, not procedures — both report success (108 Argo revisions / 10 Deployment revisions are retained) and are then silently reverted to `main` HEAD within ~3 minutes. Nothing fails loudly, so under pressure you believe you rolled back, watch it return, and lose minutes. The ONLY durable rollback is reverting the commit in git and syncing the affected apps. Same mechanism that reverts `replicas: 0` and is why store sleep is parked (learned 2026-08-22) <!-- cid:deployment-pipeline:c2 -->
- `Ready` is only evidence when a probe measured something. A Kubernetes workload with no `readinessProbe` reports `1/1 Ready` the instant PID 1 is alive, and that status is byte-identical to a genuinely healthy one — so asserting readiness without asserting that a probe EXISTS verifies nothing. Found 2026-08-23 on `dagster-user-code`, which had no probe at all: it is the gRPC code server every Dagster run executes inside, deploys `Recreate`, and could have come up unable to load its definitions while `ship-images.sh` printed `✓ shipped`. Stacked under a tag check like FR1.5 — a fact about bytes on a node — the result is a green deploy report backed by nothing that asked the application a question. Same nothing-verified class as the five silent-failure defects; the absence here was the check itself (learned 2026-08-23) (learned 2026-08-23) <!-- cid:deployment-execution:c5 -->
- A test that asserts only a non-zero exit cannot distinguish a correct failure from a missing implementation — `[ "$status" -ne 0 ]` passes on exit 127 (command not found). Assert the failure REASON, not just the status. Found 2026-08-23 when a bats test written specifically to prove the SMOKE gate fails closed passed in the Red run against a function that did not exist yet. This is the second time in this effort a defect appeared inside the guard built to prevent it (learned 2026-08-23) (learned 2026-08-23) <!-- cid:deployment-execution:c6 -->
- A tool's exit code is not its verdict — read what it PRINTED. `promtool check rules` exits 0 while printing `FAILED` and naming a real lint error (found 2026-08-23: four `ScheduledJobStale` rules sharing one label set; trusting the status alone would have shipped it). This is the third tool in this effort whose exit status disagreed with its own finding, after `woodpecker-cli --output json` silently ignoring the flag and `curl -sf` collapsing every non-2xx to 0. Distinct from the absent-result rule: here the result is present and looks successful while the tool is reporting a failure. Gate on the output text, and never read `$?` at the end of a pipeline — it is the LAST command's status, which is how `cmd | head; echo $?` reported `head`'s success three separate times in one session (learned 2026-08-23) (learned 2026-08-23) <!-- cid:observability-setup:c5 -->
- NEVER assert a sibling manifest's pattern without opening it. Writing `k8s/pr-lifecycle/cron-freshness.yaml` "on the pr-staleness pattern" produced a container image that does not exist (`ghcr.io/edtbl76/alpine-curl-jq:latest` — the real one is `alpine:latest` plus `apk add --no-cache curl jq ca-certificates`) and `sidecar.istio.io/inject: "false"` annotated as mirroring pr-staleness when that job does the OPPOSITE: it injects the sidecar and handles Job completion with `/quitquitquit` plus an `activeDeadlineSeconds` backstop. Both would have deployed and failed — ImagePullBackOff, and broken mTLS to the in-cluster Woodpecker server. Same class as the stubbed-test rule: an assumption about another system encoded instead of an observation of it. Read the file you are claiming to copy (learned 2026-08-23) (learned 2026-08-23) <!-- cid:observability-setup:c6 -->
