# Flow — Port PR entity reconciliation (B144): the reaper the integration doesn't have

How closed pull requests get removed from Port's catalog, and why every step refuses to act on an
uncertain answer. Sequence (Mermaid); operations in
[runbooks/pr-lifecycle.md](../runbooks/pr-lifecycle.md) § Reaping stale Port PR entities.
Demo: [demos/port-pr-reconcile.md](../demos/port-pr-reconcile.md).

**The gap in one line:** `github-weyland` fetches **only open PRs**, so a PR that closes stops appearing
in the source data — and an incremental sync **upserts but never deletes**. The entity survives forever
claiming `status: open`.

```mermaid
sequenceDiagram
    autonumber
    participant SHIP as ship-images.sh
    participant GH as GitHub
    participant OCEAN as github-weyland<br/>(Ocean integration)
    participant PORT as Port catalog
    participant JOB as port-pr-reconcile<br/>05:15 NY
    participant SC as DORA scorecards

    rect rgb(255,235,235)
    Note over SHIP,SC: How the lie accumulates
    SHIP->>GH: open a tag-bump PR
    OCEAN->>GH: fetch OPEN pull requests only
    OCEAN->>PORT: upsert githubPullRequest (status=open)
    SHIP->>GH: merge it, or close it as superseded
    Note over OCEAN: the PR stops appearing in the source data.<br/>Incremental sync UPSERTS but never DELETES,<br/>so nothing tells Port it closed.
    PORT->>SC: still status=open, closedAt=null
    Note over SC: cycle time inflates FOREVER.<br/>The scorecard gets WORSE with age<br/>rather than measuring anything.
    end

    rect rgb(245,245,245)
    Note over OCEAN,PORT: Two mechanisms that do NOT fix it — do not re-propose
    Note over OCEAN: POST /integration/.../resync -> {"ok":true} and NOTHING.<br/>No log rows, no resyncState movement, no entity change.
    Note over OCEAN: spec.appSpec.incrementalSyncEnabled=false is NOT DURABLE.<br/>Port-hosted SaaS re-registers and overwrites it.<br/>Set 3 times, reverted 3 times, no human action between.
    end

    rect rgb(235,245,255)
    Note over JOB,PORT: The reconciler
    JOB->>PORT: POST /auth/access_token
    Note over JOB: no accessToken in the reply -> FATAL.<br/>An empty bearer 401s everything downstream,<br/>and a 401-driven empty list reads as "nothing to reap".
    JOB->>PORT: GET githubPullRequest entities, status=open
    JOB->>JOB: emit id / repo / prNumber<br/>missing fields become a literal "-"
    end

    loop every entity Port believes is open
        alt repo or prNumber is "-"
            JOB->>JOB: SKIP — an entity we cannot identify<br/>is one we must not delete
        else
            JOB->>GH: GET /repos/{owner}/{repo}/pulls/{n}
            alt non-200 (incl. 404)
                JOB->>JOB: SKIP — a 404 means the two systems DISAGREE.<br/>Deleting on a disagreement is the guess<br/>this job exists not to make.
            else state == "closed"
                JOB->>PORT: DELETE entities/{id}
            else anything else
                Note over JOB: should_reap is an ALLOW-LIST.<br/>`[ $1 != "open" ]` returns TRUE for the empty<br/>string — an unparseable reply would have<br/>authorised deleting a live entity.
            end
        end
    end

    JOB->>JOB: report "N checked, M reaped"
    alt anything was skipped
        JOB-->>JOB: exit NON-ZERO -> ScheduledJobFailed
        Note over JOB: a run that could not check something<br/>has NOT verified the catalog
    else
        JOB-->>SC: Port now matches GitHub
    end
```

**The invariant:** an entity is deleted only on a **positive** `closed` from a **200** response about a PR
whose repo and number Port could state. Every other path — unreachable API, unparseable body, missing
field, 404, unrecognised state — skips the entity and fails the run.

**Why the failure rule matters more than the freshness rule here.** Because it fails closed, a broken run
exits non-zero having reaped *nothing* while the catalog keeps accumulating stale rows. Freshness alone
would stay quiet as long as some later run succeeded, so `ScheduledJobFailed` is the one that catches it
(`k8s/monitoring/cron-freshness-rules.yaml`).

Covered by 19 bats tests in `scripts/tests/port-pr-reconcile.bats`, the majority of which assert that
**nothing was deleted** — the weighting matches the risk, since this is the only job in `pr-lifecycle/`
whose worst failure destroys data rather than missing a page.
