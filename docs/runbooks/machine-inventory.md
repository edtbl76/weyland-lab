# Runbook — machine-inventory catalog (B129)

A living, queryable inventory of the software installed across the lab machines (rogueone, mother, weyland) —
snaps, flatpaks, apt, pip/npm globals, container images — with a **keep/remove disposition + one-line rationale**
per discretionary item, so "what's installed and why" is a catalog we diff over time instead of an ad-hoc audit.

**Pieces:**
- `scripts/collect-machine-inventory.sh <host>` — the collector. Prints the host's inventory normalized to
  `<kind>\t<name>\t<version>`. Read-only; local for this box, SSH (`emangini@<host>`) otherwise. Its `sources:`
  line names every collector that ran, so an absent package manager is visible — never a silent zero.
- `machine-inventory.yaml` (repo root) — the **git SoT**: curated `status` + `rationale` per package.
  `status ∈ keep | remove | system | unreviewed`. **system** = dep-dominated baseline (apt/pip) + transient
  images, captured for completeness with no per-item rationale. **unreviewed** = a new discretionary item
  (snap/flatpak/npm) awaiting a decision — the review queue and the drift signal.
- `scripts/machine_inventory.py {merge,emit} <host>` — folds the collector output into the SoT (merge) or
  upserts Port entities (emit). Both read the collector output on stdin.
- Port blueprints `host` + `installed_package` — `tofu/port/machine_inventory.tf`.

## Refresh a host (the canonical op)

```
[rogueone] bash scripts/collect-machine-inventory.sh <host> | python3 scripts/machine_inventory.py merge <host>
```

`merge` is **add-only + preserve**: new packages are added (apt/pip/image → `system`, snap/flatpak/npm →
`unreviewed`), existing curated decisions are never overwritten, and anything cataloged but no longer collected
is **reported to stderr** (never silently dropped — a human decides). It prints the count of `unreviewed` items
still to curate. Then review those items in `machine-inventory.yaml` and set `status` (keep/remove) + a
one-line `rationale`; commit the diff (that diff IS the drift record).

## Publish to Port

Blueprints (once, or after editing the blueprint schema):
```
[mother|rogueone] cd nodes/mother/lab/weyland-platform/tofu/port && tofu validate && tofu apply
```
Entities (reads the committed SoT — no collect/SSH; creds from `tofu/port/.env`):
```
[rogueone] set -a && . nodes/mother/lab/weyland-platform/tofu/port/.env && set +a \
  && python3 scripts/machine_inventory.py emit all      # or a single <host>
```
`emit` upserts one `host` entity + one `installed_package` per cataloged package (`kind`/`status`/`rationale`
from the SoT). Baseline (`status: system`) items are emitted too so the Port catalog is complete. Version is not
tracked in the SoT, so it is left blank in Port.

## Onboarding a new machine (B169 / EMA-230)

The same three steps for any additional client: **collect | merge** → curate its discretionary items in the SoT
→ **emit**. Prereq: the machine is SSH-reachable by **key** (not password — the collector uses `BatchMode`; run
`ssh-copy-id <user>@<host>` once). SSH user per host: **weyland → `root`** (Proxmox host, no `emangini` account),
every other box → `emangini` (the collector encodes this; override a new client with `MACHINE_INV_SSH_USER=<user>`).
Hostnames, not IPs ([feedback-ssh-conventions]). New hosts appear in Port automatically once emitted.

## How it runs (cadence)

**By hand / on-demand**, not a timer — deliberately. A blind scheduled refresh would keep discovering new
discretionary installs and piling them up as `unreviewed` with nobody deciding, and each host needs SSH auth +
human curation anyway. So the refresh is run when you've changed a machine (or periodically by choice), per the
canonical op above. A scheduled **drift check** (a CronJob that re-collects and alerts if the `unreviewed` count
grows) is a reasonable future add — it would need a `docs/schedules.md` row (off-hours, weight, owner) + a
freshness signal, so it's a deliberate follow-on, not a default.

## Notes / gotchas

- **rogueone is seeded** from the 2026-08-15 audit (the documented KEEPs); its remaining `unreviewed` items are
  the review queue. Many are snap platform runtimes (`core*`, `gnome-*`, `gtk-*`, `mesa-*`) — bulk `keep`
  (rationale "snap platform/runtime"); the rest are apps needing a per-item call.
- **mother / weyland** are inventoried by running the collector against them (SSH) — mostly apt + container
  images (`crictl`/`ctr` on the k3s node), far fewer discretionary items than the desktop.
- **Do not curate apt/pip individually** — that is the 578-item baseline the `system` bulk-tag exists to avoid.
  Only snaps/flatpaks/npm-globals + a flagged app or two are decisions.
- The collector is **read-only** and the merge/emit write only the SoT + Port — nothing is installed or removed
  by this system; it *records* dispositions, acting on them is manual.
