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

## Onboarding a new client (B169 / EMA-230)

Same three steps for any additional machine: `collect | merge` (SSH by key) → curate → `emit`. See the runbook.
