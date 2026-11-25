# weyland-lab CI — the Woodpecker workflows

Woodpecker reads every `*.yml` in this directory as one **workflow** of the same pipeline (this README is ignored).
Until 2026-11-18 the pipeline was a single file, `.woodpecker.yml`: 70 steps run one after another, ~100 minutes.
B200 split it so independent work runs in parallel. Runbook: [docs/runbooks/woodpecker.md](../docs/runbooks/woodpecker.md).

## What runs where

| Workflow (pool) | What it holds | Waits for |
|---|---|---|
| `platform.yml` (mother) | the lab's own checks: yaml lint, repo guards, Port/Linear sync, shellcheck, shell and Python tests, the Java Flink modules, integration lanes, the SonarQube gate | — |
| `fixtures-haskell.yml` (timberback) | the Haskell sample-app lanes (~17 min, the longest, so alone) | — |
| `fixtures-a.yml` (timberback) | sample-app lanes: ada, swift, elixir | — |
| `fixtures-b.yml` (timberback) | sample-app lanes: node, react-native, flutter, dart, rust, go, c, cpp, lua, php (every lane on the npm, cargo or go cache) | — |
| `fixtures-c.yml` (timberback) | sample-app lanes: swift-tokamak, kotlin, julia, ruby, scala, perl, dotnet, r, clojure, erlang | — |
| `golden-path-1.yml` … `golden-path-3.yml` (timberback) | `golden-path-smoke` on one round-robin third of the golden paths each (`GOLDEN_PATH_SHARD`), plus its own `trunk-upload`. The three files are identical except their shard number (enforced) | — |
| `golden-integration.yml` (timberback) | the golden paths' integration tier (B260): `integration-<ecosystem>` steps against Postgres, Valkey, Redpanda and MinIO started as `services:` sidecars, plus its own `trunk-upload` | — |
| `deliver.yml` (mother) | `detect-changes` → `build` → `kubeconform` → `deploy-handoff` (the image build and tag-bump PR) | all eight work workflows above (platform, the four fixtures-*, the three golden-path shards, golden-integration); **skipped if any failed** |
| `finish.yml` (mother) | `notify-port`, `notify-slack` with the pipeline's true status | everything, `deliver` included, on success **or** failure |

## Rules every workflow follows

1. **Name the agent pool.** `labels: { backend: kubernetes, node: <mother|timberback> }`: `platform`, `deliver` and
   `finish` run on mother; the `fixtures-*` and `golden-path-*` workflows on timberback (B200 steps 3-4). A cache volume
   lives on one node, so `fixtures-b` mounts timberback's `-tb` copies. An agent takes a workflow only if it carries
   every label the workflow lists, and a workflow whose steps mount a node-local volume (`ci-cache-*`) must run on the
   node that holds it (CI #676 hung 3 h on that split). Agent pools: runbook § Agent pools.
2. **Gate on a `--var` at the step, never the workflow.** On v3.18 a workflow-level `when: evaluate` never sees a
   `--var` (re-tested 2026-11-18, #681/#682), while a step-level one sees it in any workflow. So the lean, smoke and
   per-lane modes (`RUN_FIXTURES`, `SMOKE_ONLY`, `FIXTURE_LANES`) gate each step exactly as before. A workflow whose
   steps all skip still clones (~8 s) and succeeds.
3. **No YAML anchors across files.** Each file is self-contained; the old `&skip_on_smoke` / `&junit_env` anchors are
   written out inline.
4. **Workspaces are per workflow.** Files pass step to step only inside one workflow (`deliver` keeps `.ci-build-plan`
   and `.ci-image-bumps` together). JUnit reports are uploaded by a `trunk-upload` step in each workflow that has
   lanes, gated like those lanes, so it runs exactly when one of them ran.
5. **Status across workflows comes from the API.** Inside a workflow, `$CI_PIPELINE_STATUS` and `when: status` see
   only that workflow (#683: another workflow failed while `finish` read success). `finish` asks Woodpecker through
   `scripts/ci/pipeline-status.sh`, and an unknown status is reported as failure.

## History and operating notes (from the single-file header)

- **What it delivers (B57a):** builds the weyland-built images, pushes a `git-<sha>` tag to `registry.weyland.lab`, and
  opens a PR that bumps the tag in the manifests; you merge and Argo CD reconciles. git is the seam: CI never calls
  `argocd sync`. Design: [docs/design/image-build-pipeline-design.md](../docs/design/image-build-pipeline-design.md).
- **Backend:** the kubernetes backend, so steps are pods. Pinned by label so a workflow can't land on STUD.io's
  local-backend agents (B57b). Each workflow's workspace is a local-path RWO volume, so steps inside one workflow run in
  sequence.
- **Build engine:** a persistent `buildkitd` (`k8s/woodpecker/buildkitd.yaml`, on timberback since 2026-11-17); the
  `build` and `golden-path-smoke` steps are thin `buildctl` clients.
- **Triggers:** manual and the nightly cron. No push webhooks on the LAN.
- **The cron is `nightly-images`, id 2, `0 5 * * *` UTC** (01:00 EDT / 00:00 EST; Woodpecker crons are UTC, not
  NY-pinned, docs/schedules.md Design Rule #1). It exists; do not re-create it. **It was created disabled on
  2026-08-18 and never ran** until found on 2026-08-22: `--enabled` is not a default, and nothing warns. After any cron
  change check `enabled` AND that `next_exec` is in the future:
  `curl -sf -H "Authorization: Bearer $WOODPECKER_TOKEN" "$WOODPECKER_SERVER/api/repos/2/cron"`.
- **CLI notes (v3.x, verified 2026-08-22):** `cron` lives under `repo` (`woodpecker-cli repo cron ls|add|update`).
  `repo cron update` and `pipeline last` 404 on a positional repo argument; the REST API works. `--output json` is
  accepted and SILENTLY IGNORED: use `--output 'go-template={{range .}}...{{end}}'` (the payload is a slice). See
  [docs/runbooks/ship-images.md](../docs/runbooks/ship-images.md).
