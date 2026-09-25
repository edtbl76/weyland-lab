# Runbook — repo coverage parity (B138)

The lab's repo-watching lanes (CI, scanning, PR-lifecycle, Port catalog, backup, IaC) each grew their own repo
list and diverged silently — they ranged 1→6 repos, a stale repo stayed cataloged, and two active repos were
watched nowhere. `repos.yaml` (repo root) is the ONE canonical list every lane reconciles to; a guard fails when
an enforced lane drifts, and an onboarding helper walks a new repo to parity.

## Pieces

- **`repos.yaml`** (repo root) — the SoT. Each repo has `visibility` (public/private), `status` (active/stale),
  and per-lane `lanes` (iac/ci/scan/pr/catalog/backup); a `false` lane must carry a reasoned `except:` note.
  Top-level **`enforce:`** lists the lanes the guard hard-fails CI on — it starts small and grows as each lane
  reaches parity, so the guard ships incrementally without redding the pipeline.
- **`scripts/check-repo-coverage.sh`** — the drift guard (in the `repo-guards` CI step; pure file analysis).
  Reads `repos.yaml`, extracts each lane's actual set from its central config, and compares. Enforced-lane drift
  (a repo missing OR an unexpected/stale repo present) = **exit 1**; unreadable SoT or unparseable lane = **exit 2**
  (fail-closed); pending lanes are reported, not enforced.
- **`scripts/onboard-repo.sh <repo>`** — prints the exact ordered steps to bring one repo (already in `repos.yaml`)
  to its declared coverage: the central edits, the per-repo files that live inside the target repo, and the manual
  grants. A guide, not an auto-editor (central files are reviewed tofu/k8s config). The repo slice of B154's paved path.

## The lanes (what "covered" means)

| Lane | Central config the guard reads | Notes |
|---|---|---|
| `pr` | `k8s/pr-lifecycle/pr-staleness.yaml` `REPOS` (surface) **+** `scripts/check-pr-lifecycle.sh` `REPOS` (reconcile) | **enforced** — two consumers, guarded as `pr` + `pr(recon)`; keep both lists identical. Reconcile `--apply` needs a **write** PAT (staleness only reads). |
| `catalog` | `tofu/port/b137_integrations.tf` `.name \| IN(...)` selector | **enforced** |
| `iac` | `tofu/github/*.tf` `github_repository` resources | **enforced** (since 2026-09-15) — `tofu import` per repo, then codify the imported state |
| `scan` | `k8s/code-quality/scan-suite.yaml` `SCAN_REPOS` env | **enforced** — the vuln suite's `scan-all.sh` loops the 21 tools over every repo in `SCAN_REPOS` (clones public+private with the pr-lifecycle `Contents:read` token). SonarQube multi-repo is a follow-on (its Java analyzer needs per-repo compiled binaries). |
| `backup` | `nodes/rogueone/backup/backup-repos.conf` (local paths) | **enforced** — matched by each repo's SoT `backup_path` (a checkout folder can differ from the repo name; freejack is under `~/Documents/Education`), and an allow-list path claimed by no repo is flagged as an orphan |
| `ci` | **Woodpecker activation**, read by an anonymous `GET /api/repos/lookup/<owner>/<repo>` (in-cluster `woodpecker-server`, else `http://mother:30980`; override `WOODPECKER_URL`) | **enforced** (2026-09-24) — `lanes.ci: true` ⇔ activated. Before this `ci: true` was an unchecked claim (7 of 9 repos said it with no pipeline); those are now `ci: false` + `except.ci`. No secret needed (repo-guards stays secret-free). **Private-repo limit:** anonymously a private repo answers `401` whether activated or not, so `ci: true` on a PRIVATE repo is unverifiable and the guard exits 2 — the first private repo to get CI needs an authenticated lookup added to the guard (a read token in the step) at that time. Unreachable Woodpecker = exit 2. |

## Check coverage (the canonical op)

```
[rogueone] bash scripts/check-repo-coverage.sh
```

Prints per-lane parity. Enforced lanes must show `✓ parity`; pending lanes list their onboarding gaps. Exit 0 =
enforced lanes green, 1 = an enforced lane drifted, 2 = guard broken.

## Onboard a new repo

1. **Add it to `repos.yaml`** — name, `visibility`, `status: active`, and `lanes` (the target coverage). This is
   the source of truth; nothing is "onboarded" until it is here.
2. **Get the checklist:**
   ```
   [rogueone] bash scripts/onboard-repo.sh <repo-name>
   ```
   It prints, per lane the repo should join, the exact step — and, for a **private** repo, the access grants
   required first (Port github-ocean token, pr-lifecycle PAT, scan/CI tokens) or the lane silently skips it.
3. **Do the central edits** (pr-staleness `REPOS` + its bats, the reconcile `REPOS` in `scripts/check-pr-lifecycle.sh`
   then `bash scripts/embed-pr-lifecycle.sh` to re-embed, Port `IN(...)` selectors, backup path, `tofu import`
   for iac), the **per-repo files** in the target repo (`.woodpecker.yml`, scan configs), and the **manual** steps
   (Woodpecker activation, private-repo access).
4. **CI lane — start at `ci: false`, flip to `true` on activation.** A new repo has no pipeline yet, so add it
   with `ci: false` + `except: { ci: "no pipeline yet ..." }`. When the repo gets its `.woodpecker.yml` **and** is
   activated (`woodpecker-cli repo add <owner>/<repo>`), flip `lanes.ci: true` and drop the `except.ci` note **in
   the same change**. The guard fails either way round — `ci: true` before activation ("missing"), or activated
   while still `ci: false` ("unexpected") — so the flip cannot be forgotten or done early. `onboard-repo.sh` prints
   this step even while `ci` is false. The same rule applies when **updating** an existing repo (adding or removing
   its pipeline, or deactivating it in Woodpecker): change `lanes.ci` in the same change.
5. **Verify:** `bash scripts/check-repo-coverage.sh` — the lanes you brought to parity now show `✓`. Promote a lane
   into `enforce:` once it is at full parity so future drift blocks CI.

## Reconcile drift (guard went red)

The guard names the lane and the repos: `missing` = expected but absent (add it to that lane's config); `unexpected`
= present but not expected (a stale/retired repo lingering, or one dropped from the SoT — remove it or restore the
SoT entry). Fix the config, or fix `repos.yaml` if the SoT itself is wrong — never silence the guard.
