# Design — weyland image build pipeline (B57a)

**Goal.** Close out **B57 part (a)**: turn the weyland `.woodpecker.yml` (today a PoC — info · yamllint · notify-port)
into a real **CI→CD handoff** that builds the weyland-built images, pushes a versioned tag to
`registry.weyland.lab`, gets that tag into git, and lets **Argo CD** reconcile + deploy. Replaces the manual
`scripts/build-push-images.sh` + hand-bumped tags loop. Decoupled via **git-as-seam** — CI never calls
`argocd sync` (that bypasses GitOps → drift).

**Scope.** Only the images **we build** (see `build-push-images.sh`): `weyland-tool-server`,
`weyland-dagster-user-code` (+ `-base`), `rag-index`, `feast-server`, `weyland-flink`(+`-py`), `store-scaler`,
`scan-suite`, `guardrails-structure`, `nemo-guardrails`. Third-party/helm apps are Argo-solo (out of scope).
`ranger` is version-pinned (not tag-following) — build explicitly, don't auto-bump.

---

## Current state (what we're replacing)

- **Build:** `scripts/build-push-images.sh` on a host with docker/buildx → `registry.weyland.lab/<img>:$TAG`.
- **Deploy:** manual — bump the tag in the manifest(s) and push; Argo reconciles. `IfNotPresent` + a **new tag** is
  what makes nodes re-pull. Tag-bearing manifests today: `k8s/weyland-tool-server.yaml` (`:v20`),
  `k8s/dagster/user-code.yaml` (`:v44`) and `k8s/dagster/dbt-docs.yaml` (`:v44`, **lockstep** with user-code).
- **Trigger:** none — LAN gets no GitHub push-webhooks.

---

## Decision 1 — build engine: **rootless BuildKit, in-pod, on the existing k8s agents** ✅ DECIDED

Runs on the two existing `kubernetes`-backend agents (`woodpecker-agent-0/-1`, pods on mother) — **no new host
agent**. Chosen over kaniko on the numbers (measured 2026-08-18):

| Builder | Peak RAM | Scratch |
|---|---|---|
| kaniko in-pod | **~8–12 GB** (snapshots the fs *in RAM*) | pod |
| **rootless BuildKit in-pod** | **~1–3 GB** (content store on **disk**, streams layers) | pod disk |
| host buildx (rejected — needs new local agent) | ~1–3 GB | host disk |

Why it matters: `weyland-dagster-user-code` is **8.38 GB**; mother runs at **90% RAM (~7–11 GiB free of ~76 GiB),
no swap** → an OOM is a full-node outage. kaniko's ~8–12 GB peak sits in that fatal range; BuildKit's ~1–3 GB
fits with room to spare, and the heavy 8.38 GB lands on **disk** (mother has **~400 GB free**), not RAM. BuildKit
also gives **warm-cache incremental** rebuilds (only changed layers), so a typical change is seconds, not a full
8.38 GB rebuild.

**Caveat (one-time setup):** rootless BuildKit needs a rootless securityContext on k3s (the standard
`container.apparmor`/`seccomp=Unconfined` + `RUN` mount config) — codified in the pipeline/service, not ad-hoc.
Registry push auth = node-level containerd already trusts `registry.weyland.lab` (no imagePullSecret); the build
step pushes with the registry being no-auth on the LAN.

**IMPLEMENTATION PIVOT (2026-08-18): daemon, not daemonless.** Building BuildKit *inside the Woodpecker step pod*
(daemonless) hit a wall of k3s runtime friction that took the whole afternoon to peel back — in order:
(1) `fs.inotify.max_user_instances=512` on **mother** exhausted → the fsnotify watcher EMFILE'd (fixed: raised to
8192, codified `nodes/mother/host/sysctl.d/99-weyland-buildkit.conf` — note the sysctl must be set on **mother**,
the node the step pods run on, NOT rogueone); (2) rootless BuildKit's nested userns doesn't inherit that raise;
(3) privileged needed AppArmor-unconfined too (EACCES→EPERM); (4) the default `/var/lib/buildkit` on the pod's
nested overlay forced the `runc-native` snapshotter, whose bind-mounts EPERM; (5) even overlayfs-on-a-real-fs-PVC +
`--trusted-security` on the repo, the snapshot bind-mount **still** EPERM'd inside the ephemeral step pod. The fix is
the **standard buildkit-in-k8s pattern**: a long-lived **`buildkitd` Deployment** (`k8s/woodpecker/buildkitd.yaml`,
Argo app `woodpecker-buildkitd`) does its mounts in its own stable mount namespace; the CI `build` step is a thin
`buildctl --addr tcp://buildkitd:1234` client that mounts nothing and needs no privilege. Trade vs the daemonless
ideal: a small always-on pod (request 128Mi, ~150Mi idle; spikes 1-3 GB during a build) + a 40Gi cache PVC — cheap,
and it gives a persistent warm cache. The `--trusted-security` repo flag is no longer needed for the step (kept as a
harmless grant on our own build repo).

## Decision 2 — tag scheme: **`git-<short-sha>`** (recommended)

Content-traceable, no hand-bump, unique per commit → `IfNotPresent` re-pulls cleanly. Replaces the human `vN`.
Keep the **lockstep pair** rule (user-code + dbt-docs move to the SAME tag in one commit). *Alt: auto-increment
`vN` — more human-readable but needs the pipeline to compute "next N"; SHA is simpler and unambiguous.*

## Decision 3 — change detection: **path-scoped per image** (recommended)

`build-push-images.sh` builds all 11 every time; CI should build only images whose **build context changed**
(diff `services/<img>/**` + shared bases). BuildKit's cache makes an over-build cheap, but path-scoping keeps a
routine docs-only commit from rebuilding 8.38 GB. Note the base→user-code dependency (rebuild base ⇒ rebuild
user-code). Log what was skipped (no silent truncation).

## Decision 4 — manifest validation: **kubeconform gate step** (recommended)

Before the deploy handoff, validate the changed k8s manifests against the schemas (`kubeconform -strict
-summary`, CRD schemas via the `-schema-location` catalog). A bad manifest fails the pipeline **before** Argo sees
it. Complements the existing `yamllint` step (syntax) with schema validity.

## Decision 5 — trigger: **manual + nightly pre-dawn cron** (recommended)

No push-webhooks on the LAN → `manual` (Run pipeline / `woodpecker-cli`) + a **cron in the 00:00–06:00 NY off-hours
window** (schedules.md Design Rule #5 — the single node can't absorb a scheduled build stacking on interactive
load mid-day). Proposed ~02:30 NY. The cron rebuilds anything whose source drifted since the last built tag.

## Decision 6 — tag → git handoff: **OPEN — needs your call** ⬅️

How the new tag gets into the git manifests (then Argo reconciles). Options:

| Option | Mechanism | Git-ownership fit | Cost |
|---|---|---|---|
| **A. CI commits to main** | pipeline edits the manifest tag + `git push` to main (needs a write **deploy key/PAT** as a Woodpecker secret) | CI writes your main branch directly | lowest plumbing |
| **B. CI opens a PR** *(recommended)* | pipeline pushes a branch + opens a PR via the GitHub API (outbound works from the LAN); **you merge** → Argo | you stay in the git loop (merge = the gate) | a PR per image change |
| **C. Argo Image Updater** | a controller watches the registry, writes the new tag back to git | automated write-back, but adds a component + per-App annotations | new moving part |
| **D. Manual bump** | CI builds+pushes the image + prints the tag; you bump the manifest | full git control, least automation | manual step remains |

**Recommendation: B (CI opens a PR).** It automates the mechanical tag bump but keeps *you* holding the git
merge — consistent with how you run git in this repo — and it works over the LAN (GitHub API is outbound). If you'd
rather it be zero-touch, A. Everything downstream (Argo reconcile + deploy) is identical regardless.

---

## Pipeline shape (once D6 is settled)

```
weyland .woodpecker.yml (backend: kubernetes)   trigger: manual + cron ~02:30 NY
  1. detect-changes   → which build contexts changed since the last tag
  2. build-<img>      → rootless BuildKit → registry.weyland.lab/<img>:git-<sha>   (only changed; parallel)
  3. kubeconform      → validate the manifests that will carry the new tag
  4. deploy-handoff   → set the new tag in the manifest(s) → (D6: PR / commit) → Argo reconciles
  5. notify-port      → build status → Port ci_pipeline   (existing step, keep)
```

## Acceptance criteria — the 7-pillar DoD (per `docs/definition-of-done.md`)

1. **Docs** — runbooks/woodpecker.md (the build/deploy flow + how to trigger/re-run), arch.md + completeness-audit.md
   line updated (B57a no longer "no real pipeline"), api/hosts unchanged (no new endpoint).
2. **Diagrams** — a `docs/diagrams/flow-*.md` sequence for build→registry→tag→git→Argo→rollout; LikeC4 unchanged
   (no new component — Woodpecker already modeled).
3. **Demo** — `docs/demos/*.md` UI (Woodpecker run + Argo sync eyes-on) + CLI (trigger + verify the new tag deploys),
   **run live**.
4. **Cleanup** — the demo's test build is idempotent (a tag re-push); note any teardown.
5. **Close-out** — EMA-46 → **Done** (this closes the B57 parent); backlog B57(a) → ✅; memory; tier rebalance
   (completing EMA-46 drains a High → promote a Medium).
6. **Operational** — the pipeline itself is GitOps (`.woodpecker.yml` in the repo); the cron is codified (Woodpecker
   cron, not a host crontab); build failures surface via the existing notify-port + a Woodpecker run alert.
7. **Security scan** — the pipeline change touches a k8s manifest/CI config → run-scan-suite triage; the rootless
   BuildKit securityContext gets a deliberate look (privileged-adjacent).

## Open decisions to confirm before build
- **D6 (tag → git handoff)** — A / B / C / D. *(Recommend B.)*
- Everything else (D1–D5) is defaulted above; say the word to change any.
