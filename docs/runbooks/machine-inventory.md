# Runbook — machine-inventory catalog (B129)

A living, queryable inventory of the software installed across the lab machines (rogueone, mother, weyland) —
snaps, flatpaks, apt, pip/npm globals, AppImages, uv tools, container images — with a **keep/remove disposition + one-line rationale**
per discretionary item, so "what's installed and why" is a catalog we diff over time instead of an ad-hoc audit.

**Pieces:**
- `scripts/collect-machine-inventory.sh <host>` — the collector. Prints the host's inventory normalized to
  `<kind>\t<name>\t<version>`. Read-only; local for this box, SSH (`emangini@<host>`) otherwise. Its `sources:`
  line names every collector that ran, so an absent package manager is visible — never a silent zero.
- `machine-inventory.yaml` (repo root) — the **git SoT**: curated `status` + `rationale` per package.
  `status ∈ keep | remove | system | unreviewed`. **system** = dep-dominated baseline (apt/pip) + transient
  images, captured for completeness with no per-item rationale. **unreviewed** = a new discretionary item
  (snap/flatpak/npm/appimage/uv-tool) awaiting a decision — the review queue and the drift signal.
- `scripts/machine_inventory.py {merge,emit,verify} <host>` — `merge` folds the collector output (stdin) into the
  SoT; `emit` reads the committed SoT plus `placement.yaml` and syncs Port; `verify` reads Port back.
- Port blueprints `host` + `installed_package` — `tofu/port/machine_inventory.tf`.

## Refresh a host (the canonical op)

```
[rogueone] bash scripts/collect-machine-inventory.sh <host> | python3 scripts/machine_inventory.py merge <host>
```

`merge` is **add-only + preserve**: new packages are added (apt/pip/image → `system`, snap/flatpak/npm/appimage/uv-tool →
`unreviewed`), existing curated decisions are never overwritten, and anything cataloged but no longer collected
is **reported to stderr** (never silently dropped — a human decides). It prints the count of `unreviewed` items
still to curate. Then review those items in `machine-inventory.yaml` and set `status` (keep/remove) + a
one-line `rationale`; commit the diff (that diff IS the drift record).

## Publish to Port

Blueprints (once, or after editing the blueprint schema). The provider reads `PORT_CLIENT_ID`/`PORT_CLIENT_SECRET`
from the environment, so source the gitignored `.env` first (without it: "Unable to find client ID"):

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && tofu validate && tofu apply
```
Entities (reads the committed SoT plus `placement.yaml`'s units and host config files — no collect/SSH; creds from
`tofu/port/.env`; one Port request per package, so `all` takes over 10 minutes):

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . nodes/mother/lab/weyland-platform/tofu/port/.env && set +a && python3 scripts/machine_inventory.py emit all && python3 scripts/machine_inventory.py verify all
```
`emit` upserts one `host` entity + one `installed_package` per cataloged package (`kind`/`status`/`rationale`
from the SoT). Baseline (`status: system`) items are emitted too so the Port catalog is complete. Version is not
tracked in the SoT, so it is left blank in Port. It also emits each host's systemd units and host config files from
`placement.yaml` (B180) as kinds `systemd-unit` / `host-config` (status `system`; a guest that is not a cataloged
machine, like whisper, is filed under the host it `runs_on`), and then **deletes** the host's `installed_package`
entities the SoT no longer has — `merge --prune` drops uninstalled packages, and before 2026-09-30 Port kept them
forever (38 stale entities made `verify` fail every night). It refuses to delete when a host's SoT is empty.

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
      `status: unreviewed` item. Only snap/flatpak/npm/appimage/uv-tool are decisions — **do not** curate apt/pip/images (that is
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

Two paths: an **on-demand refresh** (the canonical op above — run it when you've changed a machine) and, since
**B170**, a **nightly drift check** that keeps the catalog current for you.

### Nightly drift check → inventory PR (B170)

`scripts/machine-inv-drift.sh` runs on **rogueone** as a user systemd timer (`nodes/rogueone/systemd/
machine-inv-drift.{service,timer}`, ~03:45 NY, `Persistent=true` so a missed run fires on next boot). It runs
*there* because rogueone is where discretionary installs happen and it already holds the fleet SSH keys, `gh`
auth, and `PR_TOKEN` / Port creds / `KUMA_INVENTORY_PUSH_URL` in `scripts/.env` — no key in the cluster. Each run:

1. **emit + verify** the committed SoT → Port (keeps Port tracking the accepted catalog; the B169 read-back gate).
   A failure no longer only prints: it turns the heartbeat `down` (step 6).
2. For each **reachable** host, `collect | machine_inventory.py merge --prune` **inside an isolated git worktree**
   off `origin/main` (your working checkout is never touched). `--prune` reconciles removals too. An
   **unreachable** host is **skipped, never pruned** — merge refuses empty stdin, so a host it could not scan can
   never be blanked.
3. If the catalog changed → commit on `chore/machine-inventory-drift` and **open or update one inventory PR**.
   **Merging the PR IS the cataloging** — no hand data-entry. Set keep/remove in the PR if you like, or just merge.
4. **Host placement check (B180)** — `placement_check.py --hosts` against the committed `placement.yaml`: every
   inventoried unit and host config file installed and identical to its repo copy, no unlisted unit, no failed
   unit, no stale timer (runbook `observability.md` § Placement inventory).
5. **Kuma push-interval guard (2026-10-13)** — `scripts/kuma_push_check.py` reads every Kuma push monitor
   (read-only: `sqlite3 -readonly` in the Kuma pod, through mother) and compares its heartbeat interval with the
   table in [uptime-kuma.md](uptime-kuma.md) § Push monitors. A mismatch, a paused or missing monitor, or a push
   monitor with no row is a finding. Built because Kuma's 60 s default caught three monitors: each went red a
   minute after every good push.
6. **Kuma heartbeat → Telegram:** `down` when the JOB or the estate failed — an unreachable host, host placement
   drift, a failed Port emit + verify, or a push-interval finding — naming which (same dead-man's-switch channel as
   the restic backup). Otherwise `up`. **Catalog drift alone is `up`**, with the change in the message
   (`catalog drift +3/-0 lines → inventory PR open for review`). Owner decision 2026-10-13: it pushed `down` every
   night 10-05..10-12 while PR #130 waited, so red meant only "a PR is open" and any `docker pull` re-tripped it. The
   PR is where drift is curated, and `pr-staleness` backstops an ignored one. No ping for > the window (rogueone off
   for days) also trips the monitor.

This resolves the old "a blind timer piles up `unreviewed`" worry: the job **doesn't nag you to type anything** —
it writes the change into a PR and you merge it. Dispositions stay yours but never block accuracy. Manual dry-run
for a demo/check (no push/PR/Port/Kuma): `bash scripts/machine-inv-drift.sh --dry-run`.

**Setup (one-time, on rogueone):** create an Uptime-Kuma **push** monitor "machine-inventory-drift", put its URL
in `scripts/.env` as `KUMA_INVENTORY_PUSH_URL`, then
`cp nodes/rogueone/systemd/machine-inv-drift.{service,timer} ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now machine-inv-drift.timer`
(needs `loginctl enable-linger`, already set for the restic backup).

## Notes / gotchas

- **rogueone is fully curated (2026-10-26).** It was seeded from the 2026-08-15 audit (EMA-188, comment of
  2026-08-16; `~/rogueone-snap-cleanup.md`) but only 7 of that audit's KEEPs were transcribed, so 65 approved or
  never-reviewed items sat `unreviewed` for two months. Now: the audit's snap/flatpak KEEPs and the snap runtimes
  (`core*`, `gnome-*`, `gtk-*`, `mesa-*`: "snap platform/runtime") carry its rationale, and the 17 collected only
  after it (npm globals, AppImages, the thunderbird snap) were reviewed one by one with the owner: 10 kept, 7
  uninstalled (thunderbird, LM Studio, NexusMods, and the npm copies of claude-code, opencode-ai, jsdom, node-red).
  A new `unreviewed` item is now genuinely new.
- **mother / weyland** are inventoried by running the collector against them (SSH) — mostly apt + container
  images (`crictl`/`ctr` on the k3s node), far fewer discretionary items than the desktop.
- **Do not curate apt/pip individually** — that is the 578-item baseline the `system` bulk-tag exists to avoid.
  Only snaps/flatpaks/npm-globals/AppImages/uv tools + a flagged app or two are decisions.
- **User-space installs (2026-10-12).** The collector also reads `~/Applications/*.AppImage` (name and version from
  the file name; a `*.part` download is skipped) and `uv tool list` (ANSI escapes stripped: uv bolds names even when
  piped). Emdash, Cursor, LM Studio and `basic-memory` had never been cataloged before this. A tool run with **`uvx`**
  is only cached, not installed, so no collector sees it; install a tool you mean to keep with `uv tool install`.
- **Two npms (2026-10-12).** rogueone has apt's `/usr/bin/npm` (no globals) and nvm's (the real globals: codex,
  cline, opencode-ai, …). The nightly job runs as a systemd unit and saw the first; an interactive shell saw the second;
  so each collection pruned the other's rows. The collector now reads `~/.nvm/versions/node/*/lib/node_modules` directly,
  so both environments give the same answer. Rule: a collector source must not depend on which binary is on `PATH`.
- The collector is **read-only** and the merge/emit write only the SoT + Port — nothing is installed or removed
  by this system; it *records* dispositions, acting on them is manual.
