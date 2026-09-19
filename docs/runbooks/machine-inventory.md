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

Then **verify by read-back** — `emit`'s own success is not proof the entities landed (the "reads as success"
trap); this reads them back from Port and fails closed on a missing host or a count mismatch:
```
[rogueone] set -a && . nodes/mother/lab/weyland-platform/tofu/port/.env && set +a \
  && python3 scripts/machine_inventory.py verify <host>       # or `all`
# verify <host>: OK — host entity + N installed_package entities in Port (matches SoT)   → exit 0
```
Read-only. Exit nonzero + a diff message (`Port has X, SoT has Y`) means re-run `emit`; a persistent gap is real
drift. This is the canonical verify op — never hand-roll a Port `curl` to check.

## Onboarding a new machine (B169 / EMA-230) — the executable checklist

A repeatable onboarding **process**, written so a coding harness can drive it end to end. Each step is tagged by
**who** runs it — `[harness]` a coding agent (or you) runs autonomously, `[operator]` needs a human at a shell
(a one-time credential step the harness stops and hands off), `[decision]` needs human judgment. Run the steps in
order; each has a pass/fail gate — a step whose gate is not met stops the process (fail closed, never assume a
pass). The `onboard-machine` skill turns this list into tracked steps; this runbook is its source of truth.

Inputs: `<host>` (a **hostname**, never an IP — [feedback-ssh-conventions]) and its SSH `<user>` (**weyland →
`root`**, every other box → `emangini`; the collector encodes this — override a new client with
`MACHINE_INV_SSH_USER=<user>`).

### 0. Preflight — fail loud before touching anything `[harness]`
- [ ] `<host>` is a hostname, not an IP (reject an IP — the SSH conventions require names).
- [ ] SSH key auth works: `ssh -o BatchMode=yes -o ConnectTimeout=10 <user>@<host> true` → exit 0. **BatchMode**
      means it will NOT prompt for a password; a nonzero exit here is the "no key yet" signal → step 1.
- [ ] Port creds present: `nodes/mother/lab/weyland-platform/tofu/port/.env` exists (needed by emit + verify).

  An absent or errored check is **not** a pass — stop and report which precondition failed (fail closed).

### 1. SSH bootstrap — only if preflight's SSH check failed `[operator]`
- [ ] `ssh-copy-id <user>@<host>` (one-time; needs the host password once). The collector uses `BatchMode`, so
      password-only SSH cannot be scripted — the harness **stops here and hands you this command**, then re-runs
      preflight. New account? confirm the user (root for a bare Proxmox host, else emangini).

### 2. Collect + merge into the SoT `[harness]`
- [ ] `bash scripts/collect-machine-inventory.sh <host> | python3 scripts/machine_inventory.py merge <host>`
      (run from rogueone; the collector SSHes to `<host>`). Read-only on the host — it only reads package managers.
- [ ] Gate: the `sources:` line names the collectors that ran (an absent tool is named, never a silent 0), and
      merge prints `+N new … M total` and the count of `status: unreviewed` items to curate. The **host-tag guard**
      refuses `collect A | merge B`, and merge refuses empty stdin — a mislabel or a dead collector fails closed.

### 3. Curate the discretionary items `[decision]`
- [ ] In `machine-inventory.yaml`, set `status` (`keep`/`remove`) + a one-line `rationale` for each new
      `status: unreviewed` item. Only snap/flatpak/npm are decisions — **do not** curate apt/pip/images (that is
      the bulk `system` baseline the tag exists to avoid). A harness should **pre-triage**: bulk-`keep` the obvious
      platform runtimes (snap `core*`/`gnome-*`/`gtk-*`/`mesa-*`, rationale "snap platform/runtime") and surface
      only the genuine per-app calls to the human. The committed diff IS the drift record.

### 4. Emit + verify in Port `[harness]`
- [ ] `set -a && . nodes/mother/lab/weyland-platform/tofu/port/.env && set +a && python3 scripts/machine_inventory.py emit <host>`
- [ ] `… && python3 scripts/machine_inventory.py verify <host>` → `verify <host>: OK …` (exit 0). This reads the
      entities back from Port; a nonzero exit (missing host or count mismatch) means emit did not fully land —
      re-run emit, then verify again. **Do not** treat emit's own success as proof.

Done when `verify <host>` is green: `<host>` and its `installed_package` entities are in the Port catalog, and
future adds/removals surface as `status: unreviewed` drift on the next refresh (the canonical op above).

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
