# Demo — machine-inventory catalog (B129)

A queryable, diffable inventory of the software installed across the lab machines (rogueone · mother · weyland) —
snaps, flatpaks, apt, pip/npm globals, container images — with a keep/remove disposition + rationale on the
discretionary layer, replacing ad-hoc "what's installed and why" audits. Git SoT + Port catalog. Every step below
is RUN; output is real. Read-only except the SoT (git) and the Port entities.

Runbook: [runbooks/machine-inventory.md](../runbooks/machine-inventory.md) · flow: [flow-machine-inventory](../diagrams/flow-machine-inventory.md).

## #1 — Collect + merge a host (RUN)

```
[rogueone] bash scripts/collect-machine-inventory.sh rogueone | python3 scripts/machine_inventory.py merge rogueone
collecting rogueone locally...
sources: snap flatpak apt pip npm image(docker)          # every collector that ran — an absent tool is named, never a silent 0
merge rogueone: +720 new, 720 total cataloged
  65 item(s) status=unreviewed — curate keep/remove + rationale

[rogueone] bash scripts/collect-machine-inventory.sh weyland | python3 scripts/machine_inventory.py merge weyland
collecting weyland over ssh (root@weyland)...                # per-host user: weyland=root, else emangini
sources: apt
merge weyland: +739 new, 739 total cataloged
```

**UAT:** the SoT (`machine-inventory.yaml`) gains the host; discretionary kinds (snap/flatpak/npm) land
`unreviewed` (the review queue), dep-dominated apt/pip + images land `system` (baseline, no rationale). rogueone
was seeded from the 2026-08-15 audit (7 documented KEEPs); mother (79) + weyland (739) are apt-only baseline.

## #2 — The host-mismatch guard fails CLOSED (RUN — the negative case)

`collect <A> | merge <B>` once mislabeled mother's inventory as weyland (2026-09-14). The collector now tags its
stream with the host; merge refuses a mismatch:

```
[rogueone] bash scripts/collect-machine-inventory.sh rogueone | python3 scripts/machine_inventory.py merge weyland
merge: collected host 'rogueone' != target 'weyland' — refusing to write rogueone's inventory under 'weyland'.
       Re-run: collect-machine-inventory.sh weyland | machine_inventory.py merge weyland
# exit 1
```

**UAT:** exit 1, nothing written — a wrong pipe can no longer silently mislabel one host's inventory as another's.
Merge also refuses empty stdin (`refusing to blank the host`) rather than wiping an entry.

## #3 — Emit to Port (RUN)

Blueprints `host` + `installed_package` are tofu (`tofu/port/machine_inventory.tf`, `tofu apply`); entities are
pushed from the committed SoT (no SSH):

```
[rogueone] set -a && . nodes/mother/lab/weyland-platform/tofu/port/.env && set +a && python3 scripts/machine_inventory.py emit all
emit mother: 1 host + 79 installed_package entities
emit rogueone: 1 host + 720 installed_package entities
emit weyland: 1 host + 739 installed_package entities
emit: 3 host(s), 1538 package entities upserted to Port
```

**UAT:** in Port, the `host` blueprint shows rogueone/mother/weyland; `installed_package` is filterable by
`kind` and `status` (e.g. `status=unreviewed` = the review queue across machines; `status=keep|remove` = the
decisions). Each package relates to its host.

## Cleanup / teardown

Read-only on the machines (the collector only reads package managers). Writes are the git SoT
(`machine-inventory.yaml`) and the Port entities (idempotent upserts — re-emitting overwrites, never duplicates).
No software is installed or removed by this system; it records dispositions, acting on them is manual.

## Onboarding a new client (B169 / EMA-230) — the process + the read-back gate

B169 turned onboarding into a **repeatable process a coding harness can execute**: a role-tagged, numbered
checklist in the runbook (`[harness]` / `[operator]` / `[decision]` steps, a fail-loud preflight, a pass/fail
gate per step) + a thin `onboard-machine` skill that drives it. The new piece worth demoing is the **read-back
verify gate** — proof the catalog actually landed in Port, not an assumption from `emit`'s exit code.

### The verify gate fails CLOSED on a fabricated mismatch (RUN 2026-09-19 — the negative case)

```
[rogueone] MACHINE_INV_VERIFY_ACTUAL=3 python3 scripts/machine_inventory.py verify rogueone
verify rogueone: FAIL — Port has 3 installed_package entities, SoT has 721 (re-run emit; a persistent gap is real drift)
# exit 1
```

The `MACHINE_INV_VERIFY_ACTUAL` seam injects the Port count so the pass/fail decision is testable offline (three
bats cases). A wrong count exits nonzero — `emit` reporting success can no longer stand in for "the entities are
in Port."

### The gate caught a real bug on its FIRST live run (RUN 2026-09-19)

Run live against Port, `verify` immediately found the catalog **undercounting** the SoT:

```
[rogueone] python3 scripts/machine_inventory.py verify all
verify mother: FAIL — Port has 55 installed_package entities, SoT has 79 …
verify rogueone: FAIL — Port has 707 installed_package entities, SoT has 721 …
verify weyland: OK — host entity + 739 installed_package entities in Port (matches SoT)
```

**Root cause:** duplicate SoT rows — `merge` deduped against the on-disk catalog but not within a single run, so a
repo listed once per tag by crictl (`realm-of-agents` ×20) or an apt package printed per multiarch collapsed to
identical `(kind,name)` records that all got appended. Fixed `merge` to dedupe within the run (regression test),
collapsed the existing duplicates one-time (mother 79→55, rogueone 721→708; 111 pure removals, no curated decision
lost), and settled the model: **images are cataloged at repo granularity** (transient baseline; tag churn lives in
B57a provenance / B82 app taxonomy). A gate nobody has watched fail is not a gate — this one failed loud on run one.

### Green after the fix (RUN 2026-09-19)

```
[rogueone] set -a && . nodes/mother/lab/weyland-platform/tofu/port/.env && set +a \
  && python3 scripts/machine_inventory.py emit all && python3 scripts/machine_inventory.py verify all
emit: 3 host(s), 1502 package entities upserted to Port
verify mother: OK — host entity + 55 installed_package entities in Port (matches SoT)
verify rogueone: OK — host entity + 708 installed_package entities in Port (matches SoT)
verify weyland: OK — host entity + 739 installed_package entities in Port (matches SoT)
# exit 0
```

`len(packages)` now equals the unique emitted-identifier count for every host (no hash suffix needed). Onboarding
any real 4th machine is then the same checklist end to end: preflight → (ssh-copy-id) → collect|merge → curate → emit → verify.

## Keeping the catalog fresh — the nightly drift check (B170 / EMA-231)

`scripts/machine-inv-drift.sh` runs on rogueone (user timer, `Persistent=true`): it reconciles each reachable
host into an isolated worktree, opens/updates one inventory PR when the catalog changed, and pushes a Kuma
heartbeat (down → Telegram). Merging the PR is the only human step — no hand data-entry.

### It found real drift on its first dry-run (RUN 2026-09-19)

```
[rogueone] bash scripts/machine-inv-drift.sh --dry-run
collecting rogueone locally...      sources: snap flatpak apt pip npm image(docker)   merge rogueone: +1 new, 709 total
collecting mother over ssh (emangini@mother)...   sources: snap apt image(docker)     merge mother: +0 new, 55 total
collecting weyland over ssh (root@weyland)...     sources: apt                        merge weyland: +0 new, 739 total
── DRY RUN: catalog would change (+3/-0 lines) ──
@@ hosts: (rogueone)
+    - name: maven
+      kind: image
+      status: system
signal: down — machine-inventory drift: +3/-0 lines
```

**UAT:** a `maven` image had been pulled onto rogueone since the last catalog and was never recorded — the check
caught it on the first run (the exact "installed and forgot" case B170 exists for). The dry-run reconciled it
inside a throwaway worktree (your checkout untouched — `git worktree list` shows no leftover), printed the diff,
and signalled `down`. In a real run this becomes an inventory PR + a Telegram ping; merging the PR catalogs the
`maven` row with zero typing.

### Fail-closed behaviour
- **Unreachable host = skipped, never pruned.** merge refuses empty stdin, so a host the scanner can't reach can
  never be blanked; `decide_signal` reports it as `down` ("host(s) unreachable") rather than a false `up`.
- `--prune` removes rows for uninstalled software, but only from a host that was actually scanned.
- The whole plumbing (SSH-collect, worktree isolation, prune, diff, signal) is proven by the dry-run above; the
  `decide_signal` decision (up only when clean AND all reachable) is bats-tested offline (`machine-inv-drift.bats`).
