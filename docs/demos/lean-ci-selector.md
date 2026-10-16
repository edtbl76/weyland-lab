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

## UI walkthrough

No UI of its own. The effect shows in **Woodpecker** (<https://woodpecker.weyland.lab> → `edtbl76/weyland-lab` →
pipeline #384): the `test-*` / `scan-*` fixture lanes show as skipped, and `repo-guards`, `build`, `sonar-gate` and
`deploy-handoff` ran.

## Cleanup

Read-only. The scratch copies live in a `mktemp -d` directory outside the repo.
