# Demo: the lean CI selector (B177, content-aware 2026-10-16)

**What it proves:** `scripts/ci/select-fixtures.sh` skips the fixture-language lanes (`0`) only when a change provably
touched none of them, and runs them (`1`) otherwise. `.woodpecker.yml` is now judged by what changed inside it, not by
its name.

**Why it exists:** pipeline #382 ran the full matrix for hours because one line was added to `repo-guards`, a step
every lean run executes anyway.

Flow: [flow-lean-ci-selector.md](../diagrams/flow-lean-ci-selector.md). Runbook:
[woodpecker.md](../runbooks/woodpecker.md) § Lean language matrix.

## CLI walkthrough (run 2026-10-16)

### 1. The push that tripped #382 now selects lean

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && SELECT_BASE=f9ac9ae1 bash scripts/ci/select-fixtures.sh
```

Expected: `0`. That diff touched `.woodpecker.yml` only inside `repo-guards`.

### 2. Negative cases: a real fixture-lane change still runs everything

Change `test-go`'s image in a copy of the file (outside the repo) and compare:

[rogueone]
```
T=$(mktemp -d) && cd /home/edwardmangini/IdeaProjects/weyland && git show d7ae173b:.woodpecker.yml > $T/base.yml && sed 's|image: golang:1.26$|image: golang:1.27|' $T/base.yml > $T/head.yml && SELECT_CHANGED_FILES=.woodpecker.yml SELECT_WOODPECKER_BASE=$T/base.yml SELECT_WOODPECKER_HEAD=$T/head.yml bash scripts/ci/select-fixtures.sh
```

Expected: `1`.

A base it cannot read is not "nothing changed":

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && SELECT_CHANGED_FILES=.woodpecker.yml SELECT_WOODPECKER_BASE=/nonexistent/base.yml bash scripts/ci/select-fixtures.sh
```

Expected: `1`.

A golden path is still a trigger by name:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && SELECT_CHANGED_FILES=golden-paths/go/gin/main.go bash scripts/ci/select-fixtures.sh
```

Expected: `1`.

### 3. In CI

Pipeline #384 (ce787810, the selector change itself) ran lean, 22 steps instead of 69. `shell-tests` ran the 23
selector cases, including the real f9ac9ae1..d7ae173b push.

## Per-lane: one golden path runs only its lanes (run 2026-10-18, B224)

[rogueone] Replay the Swift 6.4.1 push (#413 ran all 46 fixture lanes for it):
```
cd /home/edwardmangini/IdeaProjects/weyland
git show d4cc9652:.woodpecker.yml > /tmp/wp-base.yml; git show 5999a4d6:.woodpecker.yml > /tmp/wp-head.yml
SELECT_CHANGED_FILES="$(git diff --name-only d4cc9652 5999a4d6)" SELECT_WOODPECKER_BASE=/tmp/wp-base.yml SELECT_WOODPECKER_HEAD=/tmp/wp-head.yml bash scripts/ci/select-fixtures.sh --plan
```
Output (run): `RUN_FIXTURES=1` · `FIXTURE_LANES='swift'` · `GOLDEN_PATH_ONLY='swift/vapor-app'`.

[rogueone] Run a narrowed pipeline:
```
woodpecker-cli pipeline create edtbl76/weyland-lab --branch main --var RUN_FIXTURES=1 --var FIXTURE_LANES=swift --var GOLDEN_PATH_ONLY=swift/vapor-app
```
Result (run, **#416**): **25 steps** (the full matrix is 69) — `test-swift`, `scan-swift`, `golden-path-smoke` (swift/vapor-app
only) plus the production lanes (test-python/shell/java, scan-java, both integration lanes); the other 44 fixture steps are
dropped. **success in 17 min.**

[rogueone] **Negative case — a shared file alongside → the FULL matrix** (run 2026-10-19). The same replay with
`scripts/run-lang-tests.sh` (every lane's runner) added to the changed files:
```
SELECT_CHANGED_FILES="$(git diff --name-only d4cc9652 5999a4d6; echo scripts/run-lang-tests.sh)" SELECT_WOODPECKER_BASE=/tmp/wp-base.yml SELECT_WOODPECKER_HEAD=/tmp/wp-head.yml bash scripts/ci/select-fixtures.sh --plan
```
Output (run): `RUN_FIXTURES=1` · `FIXTURE_LANES=''` · `GOLDEN_PATH_ONLY=''` — empty lanes mean every fixture lane runs. Failed lane discovery also falls back to full (bats-tested).

## UI walkthrough

No UI of its own. The effect shows in **Woodpecker** (<https://woodpecker.weyland.lab> → `edtbl76/weyland-lab` →
pipeline #384): the `test-*` / `scan-*` fixture lanes show as skipped, and `repo-guards`, `build`, `sonar-gate` and
`deploy-handoff` ran.

## Cleanup

Read-only. The scratch copies live in a `mktemp -d` directory outside the repo.
