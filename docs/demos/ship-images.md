# Demo — the ship loop + delivery watchdogs (B135 / B131)

Extends [weyland-image-ci](weyland-image-ci.md), which ends at "CI opens a tag-bump PR." This demo covers the
four steps that used to be manual — merge under gates, sync, verify a pod carries the tag — plus the two
watchdogs that make a *missing* run visible.

**Execution status: 🟡 partial — see [What has actually been run](#what-has-actually-been-run).** The ship loop
and `pr-staleness-check` have been run end-to-end against live infra with recorded evidence. Two paths have
**not** fired live yet and are marked inline: the `SMOKE` gate (no image has changed since it was added) and
`cron-freshness-check`'s first scheduled run.

## Sequence diagram

[flow-ship-loop.md](../diagrams/flow-ship-loop.md) — the gated loop, and [the watchdogs](../diagrams/flow-ship-loop.md#watchdogs).

## Prerequisites

- Everything [weyland-image-ci](weyland-image-ci.md) requires (buildkitd, repo activated, `github_token`).
- **`argocd` CLI** on rogueone, logged in via the LAN NodePort `mother:30880` — `argocd.weyland.lab` sits behind
  Keycloak forward-auth and answers a CLI login with HTTP 400. See [runbooks/ship-images.md](../runbooks/ship-images.md).
- **`woodpecker-cli`** configured; `gh` authenticated.
- `scripts/.env` provides `WOODPECKER_SERVER`, `WOODPECKER_TOKEN`, `PORT_CLIENT_ID`/`SECRET`. **Sourced, never
  pasted** — `set -a; . ./scripts/.env; set +a`.
- Secrets `pr-lifecycle-github` and `cron-freshness-woodpecker` present in ns `weyland` (both sealed; see
  [runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md)).

## UI walkthrough (eyes-on UAT)

1. **Woodpecker** — `https://woodpecker.weyland.lab` → `edtbl76/weyland-lab` → latest run.
   **UAT — confirm:** the run's **event is `cron`** for a nightly (not `manual`), and the `detect-changes` log
   shows `shallow clone — deepening so the old shas are reachable` followed by a per-image decision line.
   *If every image says "changed" on a quiet day, change detection has regressed — that exact bug shipped once.*
2. **GitHub** — the repo's PRs. **UAT:** a `ci: bump … → git-<sha>` PR exists on branch `ci/image-bump-<sha>`,
   and its **Files changed** tab shows **only** image-tag lines. Do **not** merge by hand; the script's gates are
   the point of the demo.
3. **Argo CD** — `https://argocd.weyland.lab` → the affected app(s). **UAT:** after the merge they go
   **Synced / Healthy** and the workload rolls. Only the *affected* apps should sync — a full `--all` sync is a
   CPU spike on a node already at its request ceiling.
4. **Grafana → Alerting → Alert rules.** **UAT:** the group **`scheduled-work-freshness`** is present with
   **5 rules**, each `Normal` / health `ok`, and the four `ScheduledJobStale` rules carry distinct `cadence`
   labels (`30m` / `6h` / `daily` / `weekly`). *Two rules sharing a label set is a real lint error — `promtool`
   exits 0 while printing `FAILED`, so the UI is the honest check.*
5. **Telegram.** **UAT:** when a watchdog fires, the message renders with a summary and description through the
   existing template — no routing change was made, so a blank or malformed alert means the payload shape drifted.

## CLI walkthrough

**[rogueone]** Run the loop. It short-circuits and exits 0 without triggering a pipeline when no image build
context has changed:

```
cd /home/edwardmangini/IdeaProjects/weyland && ./scripts/ship-images.sh
```

**[rogueone]** Read change detection on its own, without building anything:

```
cd /home/edwardmangini/IdeaProjects/weyland && PLAN=/tmp/plan.tsv sh scripts/ci/detect-changes.sh
```

**[rogueone]** Confirm the nightly cron is alive — `enabled` true **and** `next_exec` in the future:

```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && curl -s -o /tmp/cron.json -w 'HTTP %{http_code}\n' -H "Authorization: Bearer $WOODPECKER_TOKEN" "$WOODPECKER_SERVER/api/repos/2/cron" && cat /tmp/cron.json
```

**[rogueone]** Find the last cron-triggered build and its duration:

```
cd /home/edwardmangini/IdeaProjects/weyland/scripts && set -a && . ./.env && set +a && woodpecker-cli pipeline ls edtbl76/weyland-lab
```

**[mother]** Verify every bumped image is live (the FR1.5 assertion, by hand):

```
kubectl get pods -A -o jsonpath='{..image}' | tr ' ' '\n' | grep 'registry.weyland.lab/' | sort -u
```

**[mother]** Verify the SMOKE precondition — every workload for a bumped image declares a `readinessProbe`:

```
kubectl get deploy,statefulset -A -o go-template='{{range .items}}{{$n:=.metadata.name}}{{range .spec.template.spec.containers}}{{if .readinessProbe}}probe  {{else}}NOPROBE{{end}}{{$n}}{{"\t"}}{{.image}}{{"\n"}}{{end}}{{end}}' | grep registry.weyland.lab
```

**[mother]** Run either watchdog on demand:

```
kubectl -n weyland create job cron-freshness-adhoc --from=cronjob/cron-freshness-check && kubectl -n weyland wait --for=condition=complete job/cron-freshness-adhoc --timeout=180s && kubectl -n weyland logs job/cron-freshness-adhoc
```

```
kubectl -n weyland create job pr-staleness-adhoc --from=cronjob/pr-staleness-check && kubectl -n weyland wait --for=condition=complete job/pr-staleness-adhoc --timeout=180s && kubectl -n weyland logs job/pr-staleness-adhoc
```

**[rogueone]** Run the shell suite (the gates' real test — every external binary is stubbed):

```
cd /home/edwardmangini/IdeaProjects/weyland && docker run --rm -v "$PWD:/code:ro" -w /code bats/bats:latest scripts/tests/
```

## Expected result

- **Nothing to ship:** `✓ nothing to ship — no image build context changed since its deployed tag.`, exit 0, no
  pipeline triggered.
- **Full ship:** pipeline → PR → three gates pass → merge → scoped `argocd app sync` → `✓ shipped — git-<sha> is
  live and smoke-verified.`
- **Gate refusal:** the run names the gate that stopped it and **leaves the PR open**. A refusal is a success of
  the gate, not a failure of the loop.
- **Watchdogs:** `done - N cron(s) checked, M alert(s) fired`. **Zero checked exits non-zero** — a watchdog that
  finds nothing and reports success is emitting a green signal.
- **Tests:** `62 tests, 0 failures`.

## What has actually been run

Recorded honestly, because "the demo IS the test" and a written-but-unrun step proves nothing.

| Step | Status | Evidence |
|---|---|---|
| Full ship (gates → merge → sync → verify) | ✅ RUN 2026-08-22 | pipeline #24 → PR #35 merged → three affected Argo applications synced → 5 workloads on `git-36c4d3e0` |
| Gate refusal path | ✅ RUN 2026-08-22 | PR #34 — aborted at FR2.1, no merge attempted, branch preserved |
| "Nothing to ship" short-circuit | ✅ RUN 2026-08-22 / 2026-08-23 | clean exit 0, no pipeline triggered |
| FR2.3 close superseded PR | ✅ RUN 2026-08-22 | #34 closed before #35 merged |
| Change detection in CI | ✅ RUN 2026-08-23 | pipeline #25 — `shallow clone — deepening…` + 11 correct `unchanged` decisions |
| Nightly cron fires on schedule | ✅ RUN 2026-08-23 | pipeline #25, `event: cron`, 05:00:21Z, 82s |
| `pr-staleness-check` | ✅ RUN ×3, 2026-08-22 | run 3: six repos fetched, 4 real alerts → Telegram + Alertmanager |
| bats suite | ✅ RUN 2026-08-23 | 62 passed, 0 failed |
| Freshness rules loaded | ✅ VERIFIED 2026-08-23 | group `scheduled-work-freshness`, 5 rules, `health: ok` |
| **`SMOKE` gate, live** | 🟡 **NOT YET RUN** | added after the last real ship; needs a night where an image context actually changes |
| **`cron-freshness-check` scheduled run** | 🟡 **NOT YET RUN** | CronJob created ~4 min after its 04:30 slot; first firing is the following day |
| **A cron-produced bump PR** | 🟡 **NOT YET RUN** | pipeline #25 built 0 images, so it opened no PR — B139 item 5 |

The three 🟡 rows are why this demo is **🟡, not ✅**. They are not defects; they need a day on which an image
build context genuinely changes, which cannot be forced without manufacturing a change.

**Deferred by decision to Linear EMA-77** ("B87 — Vet + live-validate all E2E demos"). B135/B131 closed with DoD
Pillar 3's live-execution requirement carried there rather than holding both issues open on a condition that
arrives by itself. Closing them here: run `scripts/ship-images.sh` on a day `detect-changes.sh` reports a
non-empty plan — that single run exercises the SMOKE gate and the cron-produced PR together. For
`cron-freshness-check`, confirm `kube_cronjob_status_last_successful_time{cronjob="cron-freshness-check"}` has a
value and the run appears in the CronJob's history; an ad-hoc Job succeeding does **not** prove the schedule.

## Cleanup / teardown

- **Ad-hoc watchdog Jobs** created above are the only data this demo creates. Remove them:

```
kubectl -n weyland delete job cron-freshness-adhoc pr-staleness-adhoc --ignore-not-found
```

- **Alerts** fired by a watchdog auto-resolve after Alertmanager's 5-minute `resolve_timeout` — synthetic alerts
  carry no `endsAt`. Nothing to clean.
- **A real ship run is not undoable by cleanup** — it merges a PR and rolls workloads. To reverse one, follow
  [the rollback runbook](../runbooks/ship-images.md): **revert the bump commit in git**. `argocd app rollback`
  and `kubectl rollout undo` are **traps** — both report success and are silently reverted by `selfHeal` within
  ~3 minutes.
- Registry `git-<sha>` tags ARE the deploy history — keep. `weyland-image-prune` (Sun 11:00) handles node-side
  pressure.
- `/tmp/plan.tsv` and `/tmp/cron.json` from the CLI walkthrough are throwaway.

## Related

- [weyland-image-ci.md](weyland-image-ci.md) — the build half this extends
- [runbooks/ship-images.md](../runbooks/ship-images.md) · [runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md)
- `arch.md` §10b — decision matrix and the bug class
