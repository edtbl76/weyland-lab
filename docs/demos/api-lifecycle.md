# Demo — API lifecycle management (B155)

The estate's APIs are governed across design → published → deprecated → retired from one catalog
(`apis.yaml`), with a PR-time lifecycle guard, a nightly drift cron, and a breaking-change engine over
committed contract snapshots. Concept: [api-lifecycle.md](../concepts/api-lifecycle.md); flow:
[flow-api-lifecycle.md](../diagrams/flow-api-lifecycle.md).

Repo tooling — the **CLI walkthrough IS the demo**, with the **negative cases** (each guard/engine shown
failing with its exit code).

## CLI walkthrough (RUN 2026-09-07)

**1. The catalog is well-governed (PR-time lifecycle guard):**

```
bash scripts/check-api-lifecycle.sh
# OK — 12 API(s) well-governed: all declare owner/kind/status/version, owners resolve, every published
#      typed contract is snapshotted (6 snapshots), deprecations + retirements consistent. (12 published)
bash scripts/check-api-lifecycle.sh --list    # the per-API lifecycle catalog (owner/kind/status/version/spec)
```

Negative cases RUN (bats fixtures): an owner that isn't a service → **exit 1** (`OWNER …`); a published
openapi API with no snapshot → **exit 1** (`SPEC …`); a `deprecated` API with no `retire_by`/`successor`
→ **exit 1** (`DEPRECATION …`); a `retired` API that still has consumers → **exit 1** (`RETIRED …`);
an unreadable catalog → **exit 2** (never a clean pass).

**2. The breaking-change engine (`api_spec_diff.py`):**

```
python3 scripts/lib/api_spec_diff.py docs/api/specs/weyland-tool-server.openapi.json <same>   # OK — 0 breaking (exit 0)
# a spec with an operation removed →
#   BREAKING    operation removed: POST /context/ask
#   BREAKING — 1 breaking / 1 total change(s)   (exit 1)
```

Classifies removed operation / removed response field / removed enum value / new required field as
BREAKING; additive changes COMPATIBLE; OpenAPI-vs-A2A → **CANNOT COMPARE (exit 2)**, never silent.

**3. PR-time breaking-change enforcement (the contract lock) — RUN 2026-09-07:**

The lock (`docs/api/specs/contract-lock.json`) records each API's approved baseline + version. Proven
end-to-end by removing an operation from a snapshot:

```
# 1. the guard catches the changed contract at PR time
bash scripts/check-api-lifecycle.sh
#   LOCK — 1 API(s): weyland-guard: snapshot changed vs the locked baseline — re-lock (…)   → exit 1
# 2. re-locking REFUSES the breaking change without a major bump
bash scripts/gen-api-contract-lock.sh
#   REFUSED — breaking contract change(s) without a MAJOR version bump:
#     - weyland-guard: v1.0 -> v1.0 is a MAJOR change but the version did not increase its major:
#         operation removed: GET /admin/mode   → exit 1
```

Bumping the major version in `apis.yaml` lets the re-lock succeed (an *additive* change re-locks freely).
So a breaking change to a published API cannot merge without a deliberate major bump — the enforcement is
a **merge gate**, not just the nightly drift cron. (Git-independent: the baseline lives in the lock.)

**4. The live drift cron (`api-drift`) — RUN live 2026-09-07:**

```
# fetches the tool-server's LIVE /openapi.json (NodePort) and diffs vs the committed snapshot
python3 scripts/lib/api_drift.py <apis.yaml> docs/api/specs
# OK — 1 reachable API(s) match their committed contract; 0 skipped (unreachable).   (exit 0)
```

Negative/edge cases RUN: an operation removed on the live spec → **BREAKING DRIFT exit 1** (named + the
fix: re-capture, bump MAJOR, migrate); an unreachable source → **SKIP** (not drift, listed); a missing
snapshot → **exit 2**. In-cluster it fetches every API's `.svc` `/openapi.json` + the realm A2A card.

**Tests + wiring:** `api-spec-diff.bats` **10** · `api-lifecycle.bats` **14** · `api-drift.bats` **6**
(incl. the embedded-ConfigMap byte-identity) · `api-contract-lock.bats` **6** (generator refusal + guard
LOCK). shellcheck 0. `check-api-lifecycle.sh` in `repo-guards`;
`api-drift` CronJob at 03:20 (freshness-budgeted, ScheduledJobFailed→Telegram). Contract snapshots
captured live: tool-server (17 paths), realm-http (14), guard (7), agent (4), operator (4), realm A2A (24 skills).

## UI walkthrough

N/A — repo tooling + a CronJob. A drift failure surfaces as a red Job → `ScheduledJobFailed` → Telegram,
like the coverage crons; the human-readable inventory stays at [api.md](../api.md).

## Teardown

Read-only. The guard + engine read repo files; the cron makes HTTP GETs and writes nothing. Snapshots
are committed git artifacts (the governed baseline), re-captured deliberately when an API version bumps.
