# Woodpecker step menu — weyland CI

A "café menu" of every step in [`.woodpecker.yml`](../../.woodpecker.yml): what each does, its image, and
when you'd want it. The operational runbook (deploy, triggers, gotchas, secrets) is
[woodpecker.md](woodpecker.md); this page is the **step catalog**.

## How the kitchen runs (read first)

- **One workflow, `backend: kubernetes`.** Every step is a pod on mother's `woodpecker-agent-0/-1`. The
  workflow is deliberately pinned to the k8s backend so it can't land on the rogueone **local-backend**
  agents (those are STUD.io's, B57b). A step that needs the host (privileged, eBPF, docker-in-docker) can
  therefore NOT run here — see "Off-menu" below.
- **Trigger:** `when: event: [manual, cron]` — no push webhooks on the LAN. The `nightly-images` cron
  (`0 5 * * *` UTC) is the full-regression run; manual is everything else.
- **Sequential, in file order.** No `depends_on` — single-node k3s → local-path RWO, so steps run one at a
  time and pass workspace files (`.ci-build-plan`, `.ci-image-bumps`) cleanly step→step.
- **Blocking by default.** A failing step fails the pipeline (and the nightly ship). Add `failure: ignore`
  to a step to keep it reporting without blocking — do not silently delete a guard.

## Gates & guards (run every pipeline, blocking)

| Step | Image | What it does |
|---|---|---|
| `yaml-syntax` | pipelinecomponents/yamllint | yamllint the k8s manifests |
| `repo-guards` | node:24-alpine | mermaid parse · doc-counts · app-registry · quality-tools · SA-automount · cron-freshness · pip-audit · ODCS · verdict-sync (5+ guards; fail-closed) |
| `port-iac-coverage` | alpine | Port blueprints/entities ↔ OpenTofu coverage |
| `linear-sync` | alpine | **DoD Pillar 5** — full backlog ↔ Linear reconciliation (status · project · priority · missing · orphan) |
| `shellcheck` | koalaman/shellcheck-alpine | `--severity=warning` over `scripts/*.sh` + `scripts/{lib,ci,integration,perf}` + `eval/coding-agents/tasks/*/grade.sh` |
| `shell-tests` | bats/bats | the whole `scripts/tests/` bats suite (+apk python3/py3-yaml/jq/git) |
| `rego-policies` | python:3.12-slim | compile + test the Gatekeeper Rego policies |

## Per-language test lanes (golden-path lane verification)

Each runs that language's golden-path tests + the deliberate-fail selfcheck + coverage baseline. Add a new
lane when a new ecosystem lands under `golden-paths/` (mirror the pattern; see `scripts/run-lang-tests.sh`).

| Step | Image | Step | Image |
|---|---|---|---|
| `test-python` | python:3.12-slim | `test-ruby` | ruby:3.3 |
| `test-shell` | bats/bats | `test-elixir` | elixir:1.17 |
| `test-java` | maven:3.9-temurin-21 | `test-clojure` | clojure:temurin-21-lein |
| `test-go` | golang:1.26 | `test-cpp` | gcc:14 (trixie) |
| `test-rust` | rust:1-slim | `test-c` | gcc:14 |
| `test-dotnet` | dotnet/sdk:8.0 | `test-node` | node:24-alpine |
| `test-kotlin` | gradle:8.10-jdk21 | `test-scala` | sbtscala/scala-sbt:temurin-21 |
| `test-php` | composer:2.7 | | |

## Per-language scan lanes (static analysis / lint)

One `scan-<lang>` per ecosystem (`scripts/run-lang-scan.sh`; scanners registered in `quality-tools.yaml`).
Notable: `scan-clojure` = `cljkondo/clj-kondo` (static, no lein), others reuse the test image.

`scan-rust · scan-java · scan-dotnet · scan-kotlin · scan-scala · scan-php · scan-ruby · scan-elixir · scan-clojure · scan-cpp · scan-c · scan-node`

## Golden-path + integration

| Step | Image | What it does |
|---|---|---|
| `golden-path-smoke` | moby/buildkit | builds every golden path via buildkitd → serves each as a run-to-completion k8s Job (SA `golden-path-runner`) → curls the contract → tears down. **Selector:** `--var GOLDEN_PATH_ONLY='python/fastapi go/echo'` scopes it (unset = all) |
| `test-integration-guard` | alpine | black-box the guard service's decision path |
| `test-integration-datahub` | redpanda | DataHub MAE/MCE black-box against a throwaway Redpanda |
| `keploy-api-tests` | python:3.12-slim | **on-demand** (`--var KEPLOY=true`) privileged, **native-mode** keploy replay of `keploy/keploy/<test-set>/` against the golden app. Gated off normal runs; first run confirms eBPF uprobe-attach works in a step pod (see below) |

## Build → deploy → notify (the ship half, B57a)

| Step | Image | When | What it does |
|---|---|---|---|
| `detect-changes` | alpine/git | always | compute which images changed → `.ci-build-plan` |
| `build` | moby/buildkit | always | thin buildctl → buildkitd; push `git-<sha>`; per-image syft SBOM + trivy vuln + cosign sign (1Gi/4Gi mem) |
| `kubeconform` | kubeconform | always | schema-validate the manifests that will carry the new tag |
| `deploy-handoff` | alpine | `status: success` | bump tags → branch → open the deploy PR (**you** merge → Argo reconciles) |
| `notify-port` | curlimages/curl | `status: [success, failure]` | build outcome → Port `ci_pipeline` (B63 reliability signal) |

## Ordering from the menu (how to run a subset)

The pipeline runs *all* steps in file order; there is no per-step "run just this one" toggle. The levers:

- **`--var GOLDEN_PATH_ONLY=…`** — scope `golden-path-smoke` to specific paths (the one built-in selector).
- **`when:` conditions** — pin a step to `status`, `branch`, `event`, or a `path:` changeset so it only
  fires when relevant (today only `deploy-handoff`/`notify-port` use `when`).
- **`failure: ignore`** — keep a step advisory instead of blocking.
- **Comment a step out** for a one-off local experiment (never commit that).
- A true per-step menu (pick-and-run) would need either per-step `when` guards or a `.woodpecker/`
  **multi-workflow** split — see below.

## Off-menu / on-demand steps you can add

**Keploy is now wired** as the on-demand `keploy-api-tests` step above (var-gated, privileged, native-mode
— it does NOT need docker or a local agent; k3s has no docker daemon, so it runs the app as a plain
`uvicorn` child and instruments it with eBPF in a privileged pod, which this cluster allows). Two ways to
run it:

- **In CI, on-demand:** `woodpecker-cli pipeline create --branch main --var KEPLOY=true edtbl76/weyland-lab`.
  The **first** such run is the experiment — it proves whether keploy's eBPF uprobe-attach works inside a
  Woodpecker step pod (it works on the bare rogueone host, 7/7).
- **On the host, any time:** `bash scripts/keploy-verify.sh` on rogueone (docker mode, the proven path).

**Fallback if the in-pod eBPF attach fails:** convert this file to a `.woodpecker/` directory (verified: a
`.woodpecker/` dir shadows the single `.woodpecker.yml`, so the main pipeline moves into
`.woodpecker/build.yml` unchanged) and add `.woodpecker/keploy.yml` with `labels: {backend: local}` +
`when: event: manual`, landing on the rogueone local-backend agent where keploy is proven. (Keploy's own
`keploy ci scaffold` emits **GitHub Actions**, which the LAN can't webhook — the hand-written step is right.)

**Adding a new step:** copy the closest existing step (image + `commands`), keep it in file order at the
right phase, decide blocking vs `failure: ignore`, and — per the DoD cascade — add its runbook/menu row
here in the same change. New per-language lanes also touch `run-lang-tests.sh` / `run-lang-scan.sh` /
`quality-tools.yaml`.
