# Demo — open-PR reconcile (B131 resolution half)

**RUN 2026-09-23 (fleet advisory) + 2026-09-22 (`--apply` resolution).** The routine that RESOLVES open managed
PRs instead of only surfacing them — B131's widened acceptance (b) + (c). As of B176 it reconciles **all 8
pr-lane repos** (not just `weyland-lab`) and emits a structured audit trail to **Loki**. The whole point is: a
stale dependabot merge can silently downgrade a hand-remediated CVE, so staleness is resolved by
`@dependabot recreate` (re-cut against current main, cannot regress), superseded PRs are closed, and merges
stay with a human.

- Engine + operator command: `scripts/check-pr-lifecycle.sh` · nightly CronJob:
  `k8s/pr-lifecycle/pr-lifecycle-reconcile.yaml` (03:25 NY, unmeshed, `--apply`, **all 8 pr-lane repos**)
- Runbook: [runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md) § "Resolving open PRs" / "Multi-repo coverage
  + the audit log" · diagram: [diagrams/flow-pr-lifecycle.md](../diagrams/flow-pr-lifecycle.md) · concept:
  [concepts/linear-evaluation.md](../concepts/linear-evaluation.md)

## The run — the whole fleet (2026-09-23)

```
bash scripts/check-pr-lifecycle.sh            # advisory, every lanes.pr repo in repos.yaml
bash scripts/check-pr-lifecycle.sh --apply    # resolve the low-risk ones, all repos
```

One advisory pass fanned out over **8 pr-lane repos** (weyland-lab, stud.io, Algopedia, ServiceTransformation,
emangini-tailwind-nextjs-contentlayer, startme-curator, freejack, MyBodyGraph — each in its own subshell) and
found **14 open managed PRs**, per-repo `pr-lifecycle-audit` lines and a grand-total tail:

```
pr-lifecycle: edtbl76/Algopedia: 0 open (0 stale, 0 superseded, 0 mergeable, 0 needs-human)
pr-lifecycle: edtbl76/ServiceTransformation: 0 open (...)
pr-lifecycle: edtbl76/emangini-tailwind-nextjs-contentlayer: 6 open (0 stale, 0 superseded, 6 mergeable, 0 needs-human)
pr-lifecycle: edtbl76/startme-curator: 0 open (...)         # private — token reaches it, clean sweep not a skip
pr-lifecycle: edtbl76/stud.io: 3 open (0 stale, 0 superseded, 3 mergeable, 0 needs-human)
pr-lifecycle: edtbl76/weyland-lab: 5 open (3 stale, 1 superseded, 1 mergeable, 0 needs-human)
pr-lifecycle: edtbl76/freejack: 0 open (...)                # private — clean sweep
pr-lifecycle: edtbl76/MyBodyGraph: 0 open (...)             # private — clean sweep
pr-lifecycle-audit run=summary ts=2026-09-24T01:58:33Z repos=8 open=14 stale=3 superseded=1 mergeable=10 needs_human=0 failed=0
pr-lifecycle-total: 8 repos, 14 open (3 stale, 1 superseded, 10 mergeable, 0 needs-human)
```

`weyland-lab` is where the interesting classifications live — a fresh image-bump survivor (#100 from the
current HEAD `git-83b30084`) supersedes #99, and the same three stale-dependabot traps recur (#63/#72/#80):

```
#100 [MERGEABLE] ci: image bump ... → git-83b30084 (age 0d, ci=pass)  -> image-bump survivor — merge to ship
#99  [SUPERSEDED] ci: image bump ... → git-fa9c0a5f (age 4d)          -> close (superseded by #100)
#80  [STALE] Bump quic-go 0.59.0→0.59.1 (age 15d, ci=pass)            -> @dependabot recreate
#72  [STALE] Bump soupsieve 2.6→2.9 (age 19d, ci=fail)                -> @dependabot recreate
#63  [STALE] Bump aiohttp 3.14.1→3.14.3 (age 22d, ci=fail)            -> @dependabot recreate
```

Every line above is mirrored to a `pr-lifecycle-audit run=repo …` stdout record; **Alloy ships them to Loki**,
so the fleet's resolution history is queryable in Grafana (LogQL in the runbook). The `run=summary … failed=0`
line is the closed-loop proof every repo was reached — a non-zero `failed` would be a per-repo fail-closed
(exit 2 → Telegram), never a silent skip.

The reading proved out on real data (the deep-dive below is the 2026-09-22 `weyland-lab` `--apply` run that
first exercised the resolution path):

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
- Engine tests: `scripts/tests/pr-lifecycle.bats` **14/14** in `bats/bats:latest` — including the
  load-bearing invariants (**advisory never mutates**, **`--apply` never merges**, **one bad repo never
  shrinks the watch set** — per-repo fail-closed), the **audit-line** shape, and the **no-drift** case
  (the CronJob's embedded ConfigMap copy is byte-identical to the repo script). shellcheck 0.

## Teardown

N/A — repo tooling + a CronJob. The guard is the standing operator command; the `pr-lifecycle-reconcile`
CronJob is the nightly unattended pass. Superseded closes and recreates are GitHub-side and intended to
persist; nothing to tear down.
