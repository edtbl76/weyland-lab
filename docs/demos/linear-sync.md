# Demo — DoD Pillar 5 reconciliation (backlog ↔ Linear)

The pillar that had no checker, and the checker it has now. **Executed 2026-08-26** (DONE).

- **Gate:** [definition-of-done.md](../definition-of-done.md) § 5
- **Flow:** [diagrams/flow-linear-sync.md](../diagrams/flow-linear-sync.md)
- **Guard:** `scripts/check-linear-sync.sh` · **Tests:** `scripts/tests/linear-sync.bats` (23 cases)
- **CI:** `.woodpecker.yml` step `linear-sync`, **blocking**. Its own step rather than folded into
  `repo-guards` (deliberately secret-free, pure file analysis) or `port-iac-coverage` (different SaaS,
  and a step should hold only the secret it uses). Needs the `linear_api_key` repo secret covering
  **cron + manual** — a secret that does not cover the triggering event is a whole-config PARSE error,
  not a failed step. Unlike `check-secret-placeholders.sh` and `check-servicemonitor-coverage.sh` this
  one *can* run in CI: those need cluster read, this makes one outbound HTTPS call with a read-scoped
  token.

## The point

Every DoD pillar has something that can contradict the person filling it in — `check-mermaid.sh`,
`check-doc-counts.sh`, `check-cron-freshness-budgets.sh`, the bats suite, a human looking at a UI.
**Pillar 5 had nothing**, so writing the tick *was* the work: it recorded intent, never outcome.

It failed exactly that way. The B148 close-out recorded *"5 — Linear EMA-207, backlog flipped"* while
**no Linear call had been made at all**. Checking then found four more problems:

| | |
|---|---|
| EMA-207 | B148 closed in the backlog, still `Backlog` in Linear |
| EMA-199 | B143 shipped 2026-08-24, still `Backlog` two days later |
| EMA-186, EMA-172, EMA-101 | open with **no project** — invisible to every filtered view |

## CLI walkthrough (the test — RUN against live infra)

**Prerequisite (once).** Linear → Settings → Security & access → New API key, then append it to the
gitignored `scripts/.env`. Never pasted into a shell, never committed:

```
printf 'LINEAR_API_KEY=lin_api_YOUR_KEY_HERE\n' >> /home/edwardmangini/IdeaProjects/weyland/scripts/.env
```

**1. The gate itself** — run at every close-out:

```
bash scripts/check-linear-sync.sh
```

Expected: `OK - 26 backlog->Linear reference(s) reconciled, no project-less open issues.` (exit 0)

**2. Every reference and its verdict**, including closed issues with no project (listed, not failed —
only open work needs to be findable):

```
bash scripts/check-linear-sync.sh --list
```

**3. Negative case A — backlog says DONE, Linear says open.** Reproduces the EMA-199 drift against
fixtures, so the guard is seen failing rather than assumed capable of it:

```
cd /tmp && printf '### B143 — woodpecker — **DONE (2026-08-24)**\nLinear: EMA-199.\n' > b.md && printf '{"EMA-199":{"stateType":"backlog","state":"Backlog","project":"Weyland Lab"}}' > s.json && BACKLOG_FILE=/tmp/b.md LINEAR_SNAPSHOT_JSON=/tmp/s.json bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `B143  EMA-199  is still 'Backlog' in Linear` and **`EXIT=1`**.

**4. Negative case B — an open issue with no project.** The EMA-172 shape:

```
cd /tmp && printf '### B1 — thing — **DONE (2026-08-01)**\nLinear: EMA-10.\n' > b2.md && printf '{"EMA-10":{"stateType":"completed","state":"Done","project":"Weyland Lab"},"EMA-172":{"stateType":"backlog","state":"Backlog","project":null}}' > s2.json && BACKLOG_FILE=/tmp/b2.md LINEAR_SNAPSHOT_JSON=/tmp/s2.json bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `OPEN ISSUES WITH NO PROJECT` naming `EMA-172`, and **`EXIT=1`**.

**5. It fails CLOSED, and says which kind of failure.** A missing token is exit **2** (guard broken),
never exit 0 (clean backlog) — absence must never stand for success:

```
cd /tmp && BACKLOG_FILE=/tmp/b2.md LINEAR_API_KEY= LINEAR_ENV_FILE=/tmp/no-such.env bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `FATAL: LINEAR_API_KEY is not set` and **`EXIT=2`**.

**6. The test suite** — 23 cases, including the four defects found while building it:

```
docker run --rm --entrypoint sh -v "$PWD":/w -w /w bats/bats:latest -c "apk add --no-cache python3 >/dev/null 2>&1; bats scripts/tests/linear-sync.bats"
```

Expected: `23 tests, 0 failures`.

## What it found on its own first runs

Worth reading as a record of how a guard earns trust — it was wrong three times before it was right:

- **Coverage 19 of 26.** It scanned only the `### B<n>` sections and missed the ordered priority list
  entirely — the exact "supporting one format halves coverage" failure written in its own header.
- **A false positive on B60.** That entry is 1,574 characters and narrates other items' status inside
  itself (`[B63, DONE 2026-08-19]`), which a bare `DONE` search read as B60's own. Fixed to
  first-status-token-wins.
- **A test that was green for an environmental reason.** The "missing API key is fatal" case passed
  only while no key existed on the machine; it went red the moment a real one landed. `LINEAR_ENV_FILE`
  makes that path testable regardless.

## Teardown

Steps 1, 2, 6 are read-only. Steps 3–5 write fixtures under `/tmp`:
`rm -f /tmp/b.md /tmp/s.json /tmp/b2.md /tmp/s2.json`. Nothing mutates Linear or the backlog — the
guard has no write path at all, and the API key needs only read scope.
