# Demo — DoD Pillar 5 reconciliation (backlog ↔ Linear)

The pillar that had no checker, and the checker it has now. **Executed 2026-08-26** (DONE); the guard has
grown from 2 checks to **eight (A–H)** since — most recently **check H** (every project in exactly one
initiative) and **initiative-driven scope** (2026-09-24; see § "Check H" below), after **check G**
(repo↔Linear-project parity, 2026-09-23).

- **Gate:** [definition-of-done.md](../definition-of-done.md) § 5
- **Flow:** [diagrams/flow-linear-sync.md](../diagrams/flow-linear-sync.md)
- **Guard:** `scripts/check-linear-sync.sh` · **Tests:** `scripts/tests/linear-sync.bats` (53 cases)
- **Exit codes:** `0` clean · `1` drift · `2` the guard could not do its job (no key, Linear unreachable/timeout,
  non-200, unparseable/empty response). Both 1 and 2 block — a Linear outage fails the pipeline (fail-closed).
- **CI:** `.woodpecker.yml` step `linear-sync`, **blocking**. Its own step rather than folded into
  `repo-guards` (deliberately secret-free, pure file analysis) or `port-iac-coverage` (different SaaS,
  and a step should hold only the secret it uses). Needs the `linear_api_key` repo secret covering
  **cron + manual** — a secret that does not cover the triggering event is a whole-config PARSE error,
  not a failed step. Unlike `check-secret-placeholders.sh` and `check-servicemonitor-coverage.sh` this
  one *can* run in CI: those need cluster read, this makes one outbound HTTPS call that needs only read
  scope (the CI secret should be a read-only key; the local `scripts/.env` key is write-capable).

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

Expected (current): `OK - 179 backlog item(s) reconciled with Linear (status + priority + coverage), no
project-less open issues, no orphans; 8 active repo(s) mapped 1:1 to live projects.` (exit 0)

**2. Every reference and its verdict**, including closed issues with no project (listed, not failed —
only open work needs to be findable) and the repo→project map (check G):

```
bash scripts/check-linear-sync.sh --list
```

**3. Negative case A — backlog says DONE, Linear says open.** Reproduces the EMA-199 drift against
fixtures, so the guard is seen failing rather than assumed capable of it:

```
cd /tmp && printf '### B143 — woodpecker — **DONE (2026-08-24)**\nLinear: EMA-199.\n' > b.md && printf '{"EMA-199":{"stateType":"backlog","state":"Backlog","project":"Weyland Lab"}}' > s.json && printf '{"Lab & Systems":["Weyland Lab","rogueone Hardware"]}' > ini.json && BACKLOG_FILE=/tmp/b.md LINEAR_SNAPSHOT_JSON=/tmp/s.json LINEAR_INITIATIVES_JSON=/tmp/ini.json bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `B143  EMA-199  is still 'Backlog' in Linear` and **`EXIT=1`**.

**4. Negative case B — an open issue with no project.** The EMA-172 shape:

```
cd /tmp && printf '### B1 — thing — **DONE (2026-08-01)**\nLinear: EMA-10.\n' > b2.md && printf '{"EMA-10":{"stateType":"completed","state":"Done","project":"Weyland Lab"},"EMA-172":{"stateType":"backlog","state":"Backlog","project":null}}' > s2.json && printf '{"Lab & Systems":["Weyland Lab","rogueone Hardware"]}' > ini.json && BACKLOG_FILE=/tmp/b2.md LINEAR_SNAPSHOT_JSON=/tmp/s2.json LINEAR_INITIATIVES_JSON=/tmp/ini.json bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `OPEN ISSUES WITH NO PROJECT` naming `EMA-172`, and **`EXIT=1`**.

**5. It fails CLOSED, and says which kind of failure.** A missing token is exit **2** (guard broken),
never exit 0 (clean backlog) — absence must never stand for success:

```
cd /tmp && BACKLOG_FILE=/tmp/b2.md LINEAR_API_KEY= LINEAR_ENV_FILE=/tmp/no-such.env bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `FATAL: LINEAR_API_KEY is not set` and **`EXIT=2`**.

**6. The test suite** — 53 cases (36 for checks A–F + 8 for check G + 6 for the initiative scope + 3 for check H). `py3-yaml` is required — check G
parses `repos.yaml` with pyyaml, exactly as the CI `linear-sync` step now does:

```
docker run --rm --entrypoint sh -v "$PWD":/w -w /w bats/bats:latest -c "apk add --no-cache python3 py3-yaml >/dev/null 2>&1; bats scripts/tests/linear-sync.bats"
```

Expected: `53 tests, 0 failures`.

## Check G — repo ↔ Linear-project parity (added 2026-09-23)

Every ACTIVE repo in `repos.yaml` maps 1:1 to a live Linear Project (`linear_project:` = the project
NAME). Check G resolves each against a live **projects** query — not the issue snapshot, because an empty
scaffold project has zero issues and never appears there. Live `--list` map (RUN 2026-09-23):

```
--- repos.yaml active-repo -> Linear project (check G) ---
  weyland-lab                            -> Weyland Lab                        [OK]
  stud.io                                -> Stud.IO                            [OK]
  Algopedia                              -> Algopedia                          [OK]
  ServiceTransformation                  -> Service Transformation             [OK]
  emangini-tailwind-nextjs-contentlayer  -> emangini-tailwind-nextjs-contentlayer [OK]
  startme-curator                        -> start.me Curator                   [OK]
  freejack                               -> freejack                           [OK]
  MyBodyGraph                            -> MyBodyGraph                        [OK]
```

**Negative case — a repo added with no project (the onboarding gap), against fixtures:**

```
cd /tmp && printf '### B1 — x — **DONE**\nLinear: EMA-1.\n' > gb.md \
  && printf '{"EMA-1":{"stateType":"completed","state":"Done","project":"Weyland Lab","priority":2,"title":"B1 — x"}}' > gs.json \
  && printf 'repos:\n  - name: NewRepo\n    status: active\n' > grepos.yaml \
  && printf '["Weyland Lab"]' > gp.json \
  && printf '{"Lab & Systems":["Weyland Lab"]}' > gi.json \
  && BACKLOG_FILE=/tmp/gb.md LINEAR_SNAPSHOT_JSON=/tmp/gs.json LINEAR_PROJECTS_JSON=/tmp/gp.json LINEAR_INITIATIVES_JSON=/tmp/gi.json \
     REPOS_FILE=/tmp/grepos.yaml bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `ACTIVE REPOS WITH NO linear_project` naming `NewRepo`, and **`EXIT=1`**. Zero live projects, or
an unreadable `repos.yaml`, is **`EXIT=2`** (fail closed — a token/API failure must not read as "all mapped").
`onboard-repo.sh <repo>` prints the create-project step; automating it is [B159].

## Check H + initiative-driven scope (added 2026-09-24)

Checks E (orphan) and F (unnumbered) apply only to the **weyland scope** = the projects of the Linear
initiative `Lab & Systems` (`LINEAR_SCOPE_INITIATIVE`), read live. It replaced a hard-coded "other products"
denylist that silently treated every new repo project as weyland. Check H: every live project sits in
**exactly one** initiative. Live `--list` tail (RUN 2026-09-24):

```
  --- weyland scope = initiative 'Lab & Systems': Weyland Lab, rogueone Hardware ---
  --- live Linear project -> initiative (check H) ---
  Algopedia                                  -> My Work
  MyBodyGraph                                -> Health and Fitness
  OJay Floyd                                 -> Helper Tools
  Service Transformation                     -> My Work
  Stud.IO                                    -> Music Studio
  Weyland Lab                                -> Lab & Systems
  emangini-tailwind-nextjs-contentlayer      -> My Work
  freejack                                   -> Learning
  rogueone Hardware                          -> Lab & Systems
  start.me Curator                           -> Helper Tools
```

Live verdict: `OK - 182 backlog item(s) reconciled ... weyland scope = 'Lab & Systems' (2 project(s)); 9 active
repo(s) mapped 1:1 to live projects; 10 live project(s) each in exactly one initiative.`

**Negative case — a project filed under no initiative:**

```
cd /tmp && printf '### B1 — x — **DONE**\nLinear: EMA-1.\n' > hb.md \
  && printf '{"EMA-1":{"stateType":"completed","state":"Done","project":"Weyland Lab","priority":2,"title":"B1 — x"}}' > hs.json \
  && printf 'repos:\n  - name: weyland-lab\n    status: active\n    linear_project: "Weyland Lab"\n' > hrepos.yaml \
  && printf '["Weyland Lab","Orphan Project"]' > hp.json \
  && printf '{"Lab & Systems":["Weyland Lab"]}' > hi.json \
  && BACKLOG_FILE=/tmp/hb.md LINEAR_SNAPSHOT_JSON=/tmp/hs.json LINEAR_PROJECTS_JSON=/tmp/hp.json LINEAR_INITIATIVES_JSON=/tmp/hi.json \
     REPOS_FILE=/tmp/hrepos.yaml bash ~/IdeaProjects/weyland/scripts/check-linear-sync.sh; echo "EXIT=$?"
```

Expected: `LIVE PROJECTS IN NO INITIATIVE` naming `Orphan Project`, and **`EXIT=1`**. A missing or EMPTY
`Lab & Systems` initiative is **`EXIT=2`** — an empty scope would check nothing and report OK.

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

Steps 1, 2, 6 and the check-G `--list` are read-only. Steps 3–5 and the check-G negative case write
fixtures under `/tmp`:
`rm -f /tmp/b.md /tmp/s.json /tmp/b2.md /tmp/s2.json /tmp/gb.md /tmp/gs.json /tmp/grepos.yaml /tmp/gp.json`.
Nothing mutates Linear or the backlog — the guard has no write path at all, and the API key needs only
read scope.
