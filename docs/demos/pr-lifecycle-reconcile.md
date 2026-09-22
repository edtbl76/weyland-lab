# Demo — open-PR reconcile (B131 resolution half)

**RUN 2026-09-22.** The routine that RESOLVES open managed PRs instead of only surfacing them — B131's
widened acceptance (b) + (c), unbuilt until now. Length-vs-structure aside, the whole point is: a stale
dependabot merge can silently downgrade a hand-remediated CVE, so staleness is resolved by
`@dependabot recreate` (re-cut against current main, cannot regress), superseded PRs are closed, and merges
stay with a human.

- Engine + operator command: `scripts/check-pr-lifecycle.sh` · nightly CronJob:
  `k8s/pr-lifecycle/pr-lifecycle-reconcile.yaml` (03:25 NY, unmeshed, `--apply`)
- Runbook: [runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md) § "Resolving open PRs" · diagram:
  [diagrams/flow-pr-lifecycle.md](../diagrams/flow-pr-lifecycle.md) · concept:
  [concepts/linear-evaluation.md](../concepts/linear-evaluation.md)

## The run

```
bash scripts/check-pr-lifecycle.sh            # advisory
bash scripts/check-pr-lifecycle.sh --apply    # resolve the low-risk ones
```

First advisory pass over `edtbl76/weyland-lab` found **8 open managed PRs** — including a **4-deep
`ci:image-bump` superseded stack** (#95→96→97→98, survivor #99) that the Linear inbox never surfaced, and 3
stale dependabot PRs (#63/#72/#80):

```
#99 [MERGEABLE]  ci: image bump ...          -> image-bump survivor, CI green — merge to ship
#98 [SUPERSEDED] ci: image bump ...          -> close (superseded by #99)
#97 [SUPERSEDED] ...                          -> close (superseded by #98)
#96 [SUPERSEDED] ...                          -> close (superseded by #97)
#95 [SUPERSEDED] ...                          -> close (superseded by #96)
#80 [STALE]      Bump quic-go 0.59.0->0.59.1  -> @dependabot recreate
#72 [STALE]      Bump soupsieve 2.6->2.9      -> @dependabot recreate
#63 [STALE]      Bump aiohttp 3.14.1->3.14.3  -> @dependabot recreate
pr-lifecycle: 8 open (3 stale, 4 superseded, 1 mergeable, 0 needs-human)
```

The reading proved out on real data:

- **The regression trap, caught.** #63 was already satisfied on main (aiohttp 3.14.3) yet its stale branch
  carried `cryptography` 48.0.1 / `mlflow` 3.14.0 — merging it would have **downgraded** main's remediated
  50.0.0 / 3.15.1 (reintroducing CVE-2026-69247/69249). GitHub reported it `MERGEABLE` (main unprotected);
  the reconciler classified it `STALE` from the `compare` API and refused to merge.
- **The #12-after-#13 trap, caught.** The 4-deep image-bump stack: merging any of #95–98 after #99 rolls the
  image tags backwards. The reconciler kept only the newest (#99) and marked the rest `SUPERSEDED`.
- **Class-aware.** `@dependabot recreate` fires only on dependabot PRs; the image-bump survivor is `MERGEABLE`
  (the ship loop), never "recreated".

## Eyes-on: the resolution, verified

`--apply` (2026-09-22) then acted — recreate on the 3 stale, close on the 4 superseded, **never a merge**:

```
#80: requested @dependabot recreate
#72: requested @dependabot recreate
#63: requested @dependabot recreate
#98: closed (superseded by #99)   #97: closed (superseded by #98)
#96: closed (superseded by #97)   #95: closed (superseded by #96)
```

Verified against GitHub after: **#95–98 CLOSED** (8 open → 4). And the recreates worked end-to-end — a later
advisory run showed **#80/#72/#63 no longer STALE**: dependabot re-cut them against current main, so #80 is
now `MERGEABLE` and #72/#63 are `NEEDS-HUMAN` (their recreated CI is red — exactly the residual a human should
see, which `pr-staleness-check` will keep nagging). The stale-downgrade hazard is gone by construction.

## Toolchain-verified (the way the CronJob runs it)

- **The in-cluster toolchain, proven before push:** `alpine:latest` + `apk add bash github-cli python3
  ca-certificates` runs `check-pr-lifecycle.sh` cleanly (bash 5.3.9 / gh 2.97.0 / python 3.14.7), advisory
  exit 0 — so the CronJob's `apk add` line is confirmed, not discovered in-cluster.
- Engine tests: `scripts/tests/pr-lifecycle.bats` **12/12** in `bats/bats:latest` — including the two
  load-bearing invariants (**advisory never mutates**, **`--apply` never merges**) and the **no-drift** case
  (the CronJob's embedded ConfigMap copy is byte-identical to the repo script). shellcheck 0.

## Teardown

N/A — repo tooling + a CronJob. The guard is the standing operator command; the `pr-lifecycle-reconcile`
CronJob is the nightly unattended pass. Superseded closes and recreates are GitHub-side and intended to
persist; nothing to tear down.
