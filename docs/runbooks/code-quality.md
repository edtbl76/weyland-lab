# Code Quality — runbook (B43, Port category)

**Two weekly k8s CronJobs → Port** (B69, replacing the old on-demand Jobs). **`code-scan-suite`** runs the **full
scan-suite roster declared in the repo-root [`quality-tools.yaml`](../../quality-tools.yaml)** — the SOURCE OF TRUTH
(`scripts/check-quality-tools.sh` drift-guards scan.py + these docs against it; a hand-copied list is how the old
"9 vs 10" mismatch happened). **22 scan-suite tools**, now **multi-language** (Python + Go for polyglot repos like Stud.io):
secrets · SAST · SCA/deps · IaC/k8s · Dockerfile/shell lint · vuln · HTTP-headers, + **code-maat** change-hotspots;
**`sonar-scan`** runs the always-on **SonarQube** server. All OSS/$0. Findings surface in Port as
`security_scan` (per-tool), `code_hotspot` (churn), and `code_quality` (Sonar gate) → the **Code Health** dashboard.
The suite + B89 triage + B90 dashboard are detailed in the sections below.

- SonarQube server: `k8s/sonarqube/sonarqube.yaml` — `sonarqube.weyland.lab`, **meshed** (STRICT Postgres backend,
  db/role `sonarqube`). Auth is **double-login**: a **Keycloak forward-auth gate** (`traefik-forward-auth`) sits
  **in front of** SonarQube's own login (`admin`/`admin` → forced change) — Keycloak SSO first, then SonarQube's
  own login. Stateless-ish: data + extensions on RWO PVCs.
- Weekly CronJobs (clone → scan → Port): `k8s/code-quality/scan-suite.yaml` (`code-scan-suite`, Sun 04:00 NY) +
  `k8s/sonarqube/sonar-scan.yaml` (`sonar-scan`, Sun 03:00 NY; both moved out of the working day by B228, 2026-10-19). **On-demand — the per-batch DoD Pillar 7 gate:**
  `./scripts/run-scan-suite.sh` (clears any prior adhoc job → launches from `cronjob/code-scan-suite` → waits →
  prints the findings to triage; runs from anywhere with kubectl). **Exit 0 only when the job completed;** a job that
  outlives the wait exits **2**, `NOT a clean scan`, with the partial logs. The default wait is **5400s** (2026-10-16):
  a full run took 43 minutes, and **55 with the B213 image scans** (weyland-lab alone ~31), so the old 900s default
  always timed out and even `3600` was too short. Pass a wait only to shorten it. (It exited 0 on a timeout until
  2026-10-14.) **A scan defect fails the Job (2026-10-16):** every tool still runs and posts, but `scan.py` then exits
  **3** if a tool crashed or `trivy-images` could not scan an image, printing an `!! SCAN DEFECT: …` line for each.
  `scan-all.sh` finishes every repo and exits 3, and the CronJob's `podFailurePolicy` fails the Job on 3 with no retry,
  so `KubeJobFailed` reaches Telegram. Before, those runs exited 0 and Port simply showed smaller numbers. This
  script polls for Complete **or** Failed and, on Failed, prints the defect lines and exits **2** at once instead of
  sitting out its wait. Raw form:
  `kubectl -n weyland create job <name>-smoke --from=cronjob/<code-scan-suite|sonar-scan>`.
  **What it prints** (2026-10-15): per repo, every tool with a critical or high finding plus the run's archive prefix,
  read from the WHOLE job log, which it saves to a file and names. (It printed the last 200 lines until 2026-10-15; a
  full run is ~25,000 lines, so weyland-lab's section never showed.) A completed job whose log is empty or has no
  tool results is exit 2.
- **Triage what is NEW** — a repo's standing totals (hundreds of OSV and kubescape highs on weyland-lab) bury a new
  finding, so diff this run's archive against the previous run for the same repo (the prefixes `run-scan-suite.sh`
  printed; the previous one is the same-size run in `https://s3.weyland.lab/scan-reports/`):
  ```
  python3 /home/edwardmangini/IdeaProjects/weyland/scripts/scan-diff.py <previous-run> <this-run>
  ```
  It compares critical/high findings per tool (trivy, OSV, bandit, semgrep, hadolint, gitleaks, kubescape), keyed on
  file + package/rule/CVE, never on a line number. **Exit 0** nothing new · **1** new findings, listed (fix, or accept
  a phantom with a documented reason) · **2** a report missing or unreadable in either run (not "nothing new").
  B211's DoD run (2026-10-15, `2026-10-14T19-18-00Z` → `2026-10-15T04-17-42Z`): 0 new in every tool.
  **It also lists what is STANDING (2026-10-26):** every OSV finding left in a lockfile outside `golden-paths/`, new or
  not (`osv standing in production lockfiles: N`), and any N > 0 is exit 1. osv applies `osv-scanner.toml` before
  writing `osv.json`, so what remains is unaccepted: fix it, or accept it there with a reason and an expiry. Why: a
  diff never re-raises a finding present in both runs. weyland-dagster's PyJWT and soupsieve (6 advisories, 2 high)
  sat in `osv.json` from 2026-09-04 to 2026-10-26 while every DoD scan read "0 new"; GitHub's Dependabot alerts showed
  them all along (`gh api repos/edtbl76/weyland-lab/dependabot/alerts` lists those).
- **Kubescape C-0236 is accepted (2026-10-22, owner "yes").** "Verify image signature" checks each image against cosign
  public keys set in kubescape's controls-config. None are set, so every workload fails it by construction: the
  `2026-10-21T19-06-15Z` suite showed 123 new C-0236 findings with nothing in the repo changed. Our own key would pass
  only `registry.weyland.lab` images, never the upstream ones. Verification is B88 decision 2 instead: `cosign verify`
  in CI, Gatekeeper's registry-prefix constraint at admission, an in-cluster verifier left as a separate decision.
  `services/scan-suite/kubescape-exceptions.json` (one control, action **`ignore`**; `tests/test_scan.py` pins that) keeps the
  control evaluated but out of the posture counts, and the log prints its size every run:
  `~ kubescape: C-0236 accepted: N workload(s) …`. The first run with it shows C-0236 as **gone** in `scan-diff.py`.
  Accepting another control needs its own dated reason here and in that file.
  **`ignore`, not `alertOnly` (corrected the same day):** on kubescape **v4** (this image since B220) an `alertOnly`
  exception only marks resources `acknowledged`: the control stays `failed` and every finding still counts. The first cut
  used `alertOnly`, was proven on the previous v3 image (where it does exclude), and the 2026-10-22 suite on the shipped
  v4 image moved nothing (`C-0236 accepted: 0`, high 779). Re-proven on the shipped image with `ignore`: `accepted: 124`,
  high 664. `scan.py` now fails the tool loudly if C-0236 is ever left `acknowledged`. Prove a scanner change in the image
  the CronJob runs (`kubectl -n weyland get cronjob code-scan-suite -o jsonpath='{..image}'`), never a cached older tag.
- **The deployed images too** (2026-10-16, `trivy-images`): the source scanners never read a Dockerfile's
  `pip install` line, and 14 Dockerfiles install 103 packages that way (tool-server's `mcp` 1.28.1 sat in one through
  GHSA-84m7-p3x7-pcfv). So the suite also scans every `registry.weyland.lab` image a manifest under `k8s/` deploys (the
  CI-built ones in `scripts/ci/images.tsv` AND the hand-tagged ones it never lists: weyland-agent, ray-head,
  mcp-server-datahub, weyland-jupyter, ranger, …; 23 on 2026-10-16), at the tag the manifest pins, pulled through `https://registry.weyland.lab` (`--insecure`, as CI does), one image at a time with the
  cache cleared between. Results: `trivy-images.json` (`images`, plus `broken` and `missing` — an unscanned image is
  never zero). `scan-diff.py` compares it keyed by image NAME + package + id (never the tag) and counts **MEDIUM** as
  well: trivy rated the mcp advisory MEDIUM. A broken image is exit 2. The first run after the change has no
  previous image scan and prints `trivy-images: baseline (N finding(s))`; every run after that is compared.
- **Accepting an IMAGE finding (2026-10-17, B220): `.trivyignore-images.yaml`.** The image scan (`trivy-images`) used to
  apply NO ignore file, so an image finding accepted with a reason had nowhere to be recorded and came back every run.
  `scan.py` now passes `--ignorefile .trivyignore-images.yaml` to `trivy image` when the repo has one (`.trivyignore`
  stays the SOURCE-scan file). Every entry carries its id, a **purl** (the one package; with a version for a vendored
  copy, e.g. `pkg:pypi/msgpack@1.1.2` inside pip), a **path** when the purl is generic (`stdlib`, `docker/docker` — scope
  it to the one binary, e.g. `**/adbc_driver_flightsql/libadbc_driver_flightsql.so`), a `statement` with the reason, and
  `expired_at` (90 days) so it is re-reviewed. Test an entry by scanning the image with it AND a control image without:
  the accepted finding must vanish and the same id elsewhere must stay reported.
- **osv-scanner v2 grades DECLARED pins (`--no-resolve`, 2026-10-18).** v2 resolves a requirements.txt's transitive
  deps itself (deps.dev) and reports the versions it GUESSES — `requests==2.9.2` for a file that does not list requests
  (177 phantom "new" findings on its first scan). `scan.py` runs it with `--no-resolve`: osv answers "what do the
  lockfiles declare", `trivy-images` answers "what is installed". v1 had the opposite phantom — an UNPINNED requirement
  scored as `0.0.0`, every advisory ever filed (91 on `golden-paths/python/django` alone) — which v2 does not do.
- **gitleaks allowlist: `.gitleaks.toml` (2026-10-17).** gitleaks 8.30 (the scan-suite bump from 8.21) found 111 new
  matches on a clean checkout — 108 SealedSecret ciphertext, 2 Phoenix dev/test `secret_key_base` fixtures, 1 doc dummy
  login. All reviewed (values redacted); the root `.gitleaks.toml` allows exactly those paths with the reason and keeps
  the default rules on. Prove an edit: a planted realistic token outside the allowlist must still be caught.
- **scan-suite's Go tools are built from source (2026-10-18).** Every Go binary bundles its runtime + modules, and release
  builds lag: the image builds osv-scanner/shfmt/staticcheck with `go install` and gitleaks/gosec/govulncheck/kubescape
  from clones with vulnerable modules raised by `go get`, all on one pinned toolchain (`golang:1.27.2` builder stage).
  Re-check after any tool bump: `trivy image` on the built scan-suite → Go-binary HIGH/CRITICAL must be NONE (or accepted
  in `.trivyignore-images.yaml`). Major bumps are contract-tested first — run old and new on this repo with `scan.py`'s
  exact flags and compare the fields it parses (kubescape v3 → v4 and osv-scanner v1 → v2 were, 2026-10-17).
- **Shell scripts inside ConfigMaps are linted** (B230, 2026-10-19): `scripts/check-configmap-shellcheck.sh`, in CI's
  `shellcheck` step, writes every ConfigMap `data` key ending `.sh` under the platform's `k8s/` to a temp file and runs
  `shellcheck --severity=warning` on it — 13 scripts today, 7 of which (pr-staleness, port-pr-reconcile,
  cron-freshness, image-provenance, the scan-suite and sonar-scan-repos runners, feast-ui's launcher) live only in
  their manifest and were never linted before. A finding names `<manifest>:<key>:<line>:<col>` (exit 1); no k8s dir,
  an unparseable manifest, zero scripts or no shellcheck is exit 2. Run it as CI does:
  ```
  cd /home/edwardmangini/IdeaProjects/weyland && docker run --rm -v "$PWD:/repo:ro" -w /repo --entrypoint sh koalaman/shellcheck-alpine:stable -c 'apk add --no-cache python3 py3-yaml bash >/dev/null; bash scripts/check-configmap-shellcheck.sh'
  ```
- **No packages installed straight from a Dockerfile** (2026-10-16): `scripts/check-dockerfile-installs.sh`
  (repo-guards) counts every package a Dockerfile under `nodes/` or `golden-paths/` (the templates, in scope since the
  2026-10-19 DoD audit — 68 Dockerfiles) `pip install`s outside a requirements file, in every stage, and holds
  each Dockerfile to a ceiling in `scripts/ci/dockerfile-installs.baseline` that may only fall. The first count was
  103 packages across 14 Dockerfiles (80 unpinned); all 14 now install from lockfiles, so the ceiling is 0. A new
  direct install fails CI, named. To add a package, put it in the image's requirements file. A lockfile here is the
  FULL frozen set of the image it replaced (`pip freeze` of the deployed image, verified freeze == file == deployed in
  a rebuild). Builder stages that only export ONNX models are pinned at the day's resolution, since nothing deployed
  holds them; conda-based images (ray-head, weyland-jupyter) pin only what their Dockerfile adds over the base.
  **k8s manifests too (B227, 2026-10-24).** The same counter reads every `*.yaml` / `*.yml` under a `k8s/` directory
  (382 that day): a container command, CronJob script or Helm bootstrap that `pip install`s on start is the same
  drift plus PyPI egress on every boot. MLflow did it on every pod start, unseen. Shell redirects (`>/dev/null 2>&1`),
  pipes, and `pip install` inside an `echo`/`printf` message are not counted (each was miscounted on the first pass,
  now pinned by `test_dockerfile_installs.py`). The first count was 13 packages in 5 manifests; **all five are at 0
  since 2026-10-24** (B227 and its follow-on), so the baseline is empty and ANY direct install in a manifest fails CI,
  named: MLflow and Superset install from images of their own (`weyland-mlflow`, CI-built; `weyland-superset`,
  hand-tagged — `superset.md` § The image); api-drift installs its pinned `PyYAML` from a file embedded in its
  ConfigMap (`scripts/lib/api-drift-requirements.txt`); docs-site installs `mkdocs-likec4` from
  `k8s/docs-site/requirements.txt` and `likec4@1.60.0`; sonar-scan and CI's `test-python` step share one frozen
  `scripts/ci/requirements-lang-tests.txt` (CI's step had the same unpinned install, out of this guard's reach).
  ```
  bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dockerfile-installs.sh --list
  ```
- **SonarQube pre-check before handoff** (2026-10-13) — the CI `sonar-gate` step blocks the build and the nightly ship,
  so scan changed files first, on rogueone:
  ```
  set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && cd /home/edwardmangini/IdeaProjects/weyland && python3 scripts/sonar_api.py precheck $(git diff --name-only --diff-filter=d HEAD; git ls-files --others --exclude-standard)
  ```
  It mints a token, runs `sonar-scanner-cli:latest` (the CI image) in Docker as the invoking user over a temp copy of
  the files, waits for Sonar to process the report, lists every issue and hotspot, then deletes the throwaway project
  `weyland-lab-precheck-<pid>` and revokes the token. A scratch project uses the server default profiles and gate,
  which are what `weyland-lab` uses. **Exit 0** `precheck: clean`, or `precheck: nothing for Sonar to analyse` when every
  file is a type Sonar never indexes (`.sh` `.bats` `.md` `.txt` `.tsv` `.csv` `.service` `.timer` `.conf`; no scan) · **1** findings, each named (fix it, or for a hotspot
  that is genuinely fine, `sonar_api.py review-safe <file> "<reason>"` after the push) · **2** could not scan (a missing
  file, a scanner failure, a failed or timed-out analysis, 0 files analysed, or a cleanup that left something behind —
  never read as clean). Two deliberate choices: the verdict is the findings, never the scratch gate (a first analysis
  has no new-code period, so that gate passed with a CRITICAL issue open); and findings `weyland-lab` already has for
  the same file (same rule and message; lines move) are listed but not counted: open issues and TO_REVIEW hotspots as
  `already open`, hotspots reviewed SAFE as `already reviewed`. Without that, a 3-line change to a big file reported
  all 30 of the file's old findings (B207, 2026-10-13), and the rule could never be met. **Except on a line the change
  edits (2026-10-16):** CI's gate counts an edited line as new code, so an already-open finding there fails it. CI #387
  and #388 both failed on an S1192 (a literal duplicated 4×) that the precheck had listed as already open, each time
  because the edit touched a line carrying one copy. The precheck now reads `git diff -U0 origin/main`
  (`SONAR_PRECHECK_BASE` to change it) and counts those as findings, marked `on a line this change edits`; if git cannot
  answer it exits 2, never clean. It also scans only what the
  CI gate scans: files matching `sonar.exclusions` in `sonar-project.properties` (`**/*.yaml`, Dockerfiles, Terraform…)
  are dropped and named (`N excluded by sonar-project.properties`); a k8s manifest change otherwise reported findings
  the real project never sees.
  ~12 s for 3 files. Files Sonar does not analyse (Markdown, YAML) are simply not counted. Flow:
  [flow-sonar-precheck.md](../diagrams/flow-sonar-precheck.md) · demo: [sonar-precheck.md](../demos/sonar-precheck.md).
- Always-on (NOT KEDA scale-to-zero): the 32GB RAM bump made the cost moot; scale-to-zero would need the KEDA
  HTTP interceptor in front (cross-ns ingress rewire + scan-path-through-interceptor). Revisit only if RAM tightens.

## Host prereq
- `vm.max_map_count=524288` on mother (`/etc/sysctl.d/99-sonarqube.conf`) — SonarQube's embedded Elasticsearch
  refuses to boot otherwise.

## Port wiring (all → one webhook DS `code-quality`)
- Blueprints (codified in `tofu/port/blueprints.tf`): `code_quality` (qualityGate OK/ERROR/WARN/NONE, project, branch),
  `security_scan` (tool, target, critical/high/medium/low/total), **`code_hotspot`** (file, revisions, target — code-maat
  churn, B90). **The webhook DS + its mapping are UI-only** (not MCP-manageable — `list_integrations` shows only Ocean exporters).
- **SonarQube → Port:** native webhook (Administration → Configuration → Webhooks → URL = `ingest.getport.io/<key>`).
  Fires after each analysis (the CE processes the report async, then POSTs). Pod is meshed; egress to getport.io
  works (Istio ALLOW_ANY).
- **scan-suite → Port:** `scan.py` POSTs each tool's counts (and code-maat's top-20 hotspots, `kind:"hotspot"`) to the
  same ingest URL (Secret `port-ingest-url`, key `url`). Semgrep severity map: ERROR→high, WARNING→medium, INFO→low.
- Mapping (paste in the Port webhook DS Mapping tab) is now a **3-entry array** (`code_quality` on `.body.qualityGate`,
  `security_scan` on `.body.tool`, `code_hotspot` on `.body.kind=="hotspot"`); `operation` must be **`create`** (Port
  rejects `upsert`). A `202` is queue-acceptance, **not** proof of an entity.

## Gotchas (hit during bring-up)
1. **Port webhook wizard greys out Save until it receives the FIRST event.** Send one to unblock:
   `curl -i -X POST https://ingest.getport.io/<key> -H 'Content-Type: application/json' -d '{...}'` (expect `202`).
   Port does NOT replay past events — after saving the mapping, re-send to create the entity.
2. **Keep mapping JQ lines SHORT.** A long line (the `if/elif` quality-gate expression) **wraps on paste** into the
   Port web editor, injecting a newline mid-string → invalid JSON → "mapping must be array". Same paste-mangling
   class as [[feedback-verify-secret-after-create]] / [[feedback-oneline-commands]]. Store raw `.body.qualityGate.status`
   (short) instead of mapping it inline.
3. **Enum options can't be swapped in place** (`upsert_blueprint` 422 "Option X doesn't exist") — `delete_blueprint`
   + recreate (clean only when no entities exist yet).
4. **Scan Job logs:** the scan runs in **initContainers** (`clone`, then `trivy`/`semgrep`/scanner); `kubectl logs`
   on the main container returns nothing until inits finish. Use `kubectl wait --for=condition=complete job/<name>`
   then read the `report` container (`-c report`) for the `POST 202`.

## Findings (first scan, 2026-06-20) — see triage backlog item
- Trivy: 401 (1 crit / 82 high / 117 med / 201 low) — incl. 3 Dockerfiles missing `USER` (run as root), tool-server
  Deployment misconfig (KSV-0118).
- Semgrep: 48 (2 high / 26 med / 20 low) — dynamic `urllib` in `tool-server/main.py` + `hermes/roadmap-sync.py`,
  H2C smuggling in `hermes/dashboard-nginx.conf`, same Dockerfile-root issue.
- Low-risk on a LAN-only lab, but real hardening. Dockerfile `USER` is the easy win.

## B47 — triage + scanner fixes (2026-07-16)

**Scanner fixes (both were broken):**
- **SonarQube** hard-failed once Flink added `.java` — the Java analyzer needs compiled classes. Fix: a `build-java`
  initContainer (`maven:3.9-eclipse-temurin-17`) `mvn compile`s the Flink modules; scanner passes
  `-Dsonar.java.binaries=…/target/classes`. `k8s/sonarqube/sonar-scan.yaml`.
- **Trivy** `FATAL 429` — the new Flink `pom.xml` made it fetch transitive POMs from Maven Central, rate-limiting
  mother's IP. Fix: `--offline-scan`. `k8s/code-quality/scan-suite.yaml`.
- Both scan jobs' report containers now **print each finding** (`[SEV] file id :: title`) to the pod log, not just
  counts to Port. Pull with `--tail=-1` (a label selector defaults to `--tail=10`!):
  `kubectl -n weyland logs -l job-name=<trivy|semgrep>-scan-weyland -c report --tail=-1 | grep -E '^\[CRITICAL\]'`.

**Semgrep: high 14 → 0.** 4 Dockerfiles made non-root (`rag-index`, `store-scaler`, `genre-trainer`,
`weyland-tool-server` — the last needs `HOME=/app` so HF caches read as the non-root user); `weyland-dagster` +
`ranger` root-required, documented `# nosemgrep` (rule-id only, NOT prose — prose after `nosemgrep:` suppresses
nothing). 8 SQL findings: `_safe_ident()` allowlist on interpolated identifiers + bare `# nosemgrep`. **securityContext
sweep** on ~34 manifests (`allowPrivilegeEscalation:false`+seccomp everywhere; `runAsNonRoot:true` **+ `runAsUser:10001`**
— the numeric uid is REQUIRED, a named USER 401s admission — only on our non-root images).

**Trivy: critical 12 → 0.** All real CVEs were `genre-trainer/requirements.txt`: mlflow (2.18→**3.14**) + ray
(2.37→**2.56** + token auth). ShadowRay (`CVE-2023-48022`, disputed) + public-repo (`GIT-0001`) + gatekeeper/kiali
RBAC (`KSV-0046`) → `/.trivyignore` (each documented). See [[cve-remediation-mlflow3-ray256]], [remote-training.md](remote-training.md).

**Accepted residuals:** `KSV-0118`/`KSV-0014` (readOnlyRootFilesystem, ~195 high) + `run-as-non-root` on root
third-party images — systemic, blanket-applying breaks writers; documented, not per-item fixed.

**2026-10-12 triage (B179 DoD, scan `2026-10-12T20-56-49Z` diff vs `2026-10-12T02-29-39Z`, weyland-lab; critical/high only):**
trivy 88 → 84 (0 new; the `x/net` fix); semgrep, bandit, gitleaks, hadolint, shellcheck 0 new. **osv +92 / -25:**
- **92 are Go stdlib advisories on `golden-paths/go/{echo,gin}`**, a side effect of the `x/net` bump: `go get` raised
  the `go` directive to `1.26.0` (x/net v0.60.0 requires it), and OSV reads that as the stdlib version. CI builds with
  `golang:1.26` = **go1.26.9** (pulled 2026-10-12), which has every fix (the latest fixed version among them is 1.26.9).
  **Fixed by declaring it:** `toolchain go1.26.9` in all four Go samples (also un-hiding `fiber` and `nethttp`, whose
  bare `go 1.26` masked the version). With `GOTOOLCHAIN=local` the line is advisory; the Go lane passes, and OSV then
  reports 0 stdlib findings. A stale cached image older than 1.26.9 would still be exposed to the 13 net/http and
  html/template fixes in 1.26.9.
- **2 are `GO-2026-5932`** (`x/crypto/openpgp` unmaintained, no fix) on echo and gin: **accepted** in `osv-scanner.toml`
  until 2027-04-12. They are module-level only; openpgp is never imported, and govulncheck reports 0.
- The 25 removed are the earlier fixes landing (realm pins, `x/net`, `x/crypto`, `x/text`).

**Pre-existing, not this batch:** `GO-2026-4950`, `fasthttp` 1.51.0 on `golden-paths/go/fiber` (an authorization
bypass via double-encoded paths; fixed in 1.70.0), present since 10-09 and untriaged. **Fixed the same day (owner: "fix fasthttp"):** `fasthttp` 1.51.0 → 1.70.0
(with `brotli` 1.1.0 → 1.2.1), bumped in a scratch copy, OSV clean, fiber tests pass, the Go lane passes. It needed
126k root-owned files in the working tree handed back first (`sudo chown -R`): leftovers of fixture runs as root, the
class AGENTS.md's "Docker runs as you" rule forbids, which also blocked the echo `go.sum` on 10-11.

**2026-10-11 triage (B204 follow-ons + B205 DoD, scan `2026-10-12T02-29-39Z` diff vs `2026-10-09T16-03-18Z`, weyland-lab;
critical/high only):** semgrep, bandit, gitleaks and hadolint **0 new**; trivy 104 → 88 and osv 867 → 813 overall. Every
new one was an advisory published after the baseline against an unchanged pin, none in this batch's files, all **REAL and
fixed**: `realm-of-agents` GitPython 3.1.60 → 3.1.62 (GHSA-59cr-6r3x-644w) and PyJWT 2.14.0 → 2.15.0 (GHSA-42vr-xj54-vc7v,
GHSA-x33g-cr3x-6449, PYSEC-2026-4141/4183), plus multidict 6.9.1 and Werkzeug 3.1.9 that pip-audit named. These were
re-resolved with pip-compile holding the rest, so only those four moved. Proof: 54/54 tests, the app entrypoint imports,
and pip-audit leaves only the accepted cryptography 49 and mlflow. Also: `golang.org/x/net` v0.57.0 → v0.60.0
(CVE-2026-78669, HTTP/2 DoS) in `golden-paths/go/{echo,gin}`; gin's test passes in `golang:1.26`. The batch's own code
was also checked: shellcheck on `ship-images.sh` 0 warnings, the Sonar gate passed (#323), and a scratch Sonar scan of
the operator is clean.

**2026-10-05 triage (B182 DoD, scan `2026-10-05T19-11-32Z` diff vs `2026-10-04T13-34-17Z`, weyland-lab; critical/high
only):** **trivy 0 new.** **kubescape +10** — the two new manifests (`mcp-servers/compositor-memory.yaml`,
`open-webui/backup.yaml`) fail exactly the 5 controls the existing fleet compositor already carries (C-0009/C-0050/C-0270
resource + CPU limits — CPU limits are deliberately absent on mother's single node; C-0211 security context; C-0237 image
signature) — the house pattern, accepted. **osv +2, REAL, fixed:** `pytest==8.4.2` in the new gateway
`requirements-test.txt` (GHSA-6w46-j5rx-g56g / PYSEC-2026-1845, tmpdir handling) → 9.0.3; tests 13/13 + pip-audit clean in
`python:3.12-slim`. In the batch's own files bandit/semgrep/hadolint raised nothing above medium. The weyland-lab gitleaks
critical is `scripts/tests/secret-placeholders.bats:114`, a deliberate fixture of the secret guard's own tests (not this
batch). Method: a diff of (resource, control) / (target, vuln-id)
sets between the two archived reports — a raw total is a repo-wide baseline, never a verdict on a batch.

**2026-10-01 triage (B180 DoD, scan diff vs 2026-09-27, weyland-lab):** kubescape `failedResources` 148 → 151 with the
control set unchanged (137): the new `placement-coverage` (B198) and `datahub-ingestion-watchdog` (B197) CronJobs fail
exactly the controls the existing coverage CronJobs (`servicemonitor-coverage`, `dashboard-coverage`) already carry —
the house CronJob pattern, accepted with them. `C-0012` (credentials in config) on `datahub-ingestion-watchdog-logic` is
a **false positive**: the ConfigMap holds only the variable/argument names (`token`, `DATAHUB_GMS_TOKEN`); the value
comes from the `datahub-token` Secret via `secretKeyRef`. Trivy/osv increases are new lockfiles (angular, vue — first
time scanned) and advisories published since 09-27 against unchanged pins; triaged in B180's close-out.
**Remediated the same day:** PyJWT 2.13.0 → 2.14.0 (1 critical + 5 high: auth bypass / token forgery), GitPython
3.1.59 → 3.1.60 (RCE, ReDoS), urllib3 2.7.0 → 2.8.0 (2 high) in `weyland-dagster`, `genre-trainer` (.in + .txt) and
`rag-index`. Found on the way: **genre-trainer's requirements did not resolve on main** — mlflow 3.15.1 requires
`cryptography<50`, but the 09-25 CVE fix pinned `cryptography==50.0.0`, so its image could not be rebuilt (it builds
on demand, so nothing failed visibly). mlflow / mlflow-skinny / mlflow-tracing → 3.16.1 (`cryptography<51`). Proven in
`python:3.11-slim` (each image's base): full install, `pip check` clean, bumped modules import at the new versions.
The angular golden path moved Angular 19.2 → **20.3.33** (TypeScript 5.9) the same day (owner decision): 7 high → 0 in a
Trivy scan of the new lockfile; clean `npm ci`, tests, selfcheck, `ng build` and the image smoke all pass. Its Dockerfile now
installs with `npm ci` (was `npm install`, which could drift from the lockfile).

**2026-10-02 DoD scan (weyland-lab, vs the 10-01 run):** every critical/high count held or fell (trivy 14C/91H → 13C/79H,
osv 811 → 761, pip-audit 27 → 10 — the operator's pinned requirements), and an identity diff of gitleaks / bandit /
semgrep / hadolint criticals+highs found the SAME findings, not swaps. Ten trivy entries were new — all advisories
published after their files last changed. **Fixed:** `virtualenv` 21.6.1 → 21.7.13 in `genre-trainer` (.in + .txt; it
needs `python-discovery>=1.6`, so 1.4.4 → 1.6.1 too) — proven by building the real image (`python:3.11-slim`), importing
ray/mlflow/virtualenv and creating a venv with it; `devalue` 5.9.2 → 5.9.4 in the astro golden path (lockfile-only
`npm update devalue`) — `npm ci`, 5/5 tests and `astro build` pass in `node:24-alpine`. **Accepted** (no upstream fix —
each package's latest release IS the advisory's `last_affected`): braces 3.0.3, http-cache-semantics 4.2.0, node-forge
1.4.0, golden-path fixtures only — by advisory ID with an expiry (`.trivyignore` `exp:2027-01-02`, `osv-scanner.toml`
`ignoreUntil`), so a new advisory on the same version still fires. Proven with the suite's own scanner versions
(osv-scanner v1.9.1, trivy 0.72.0): zero remaining hits on the five packages outside untracked `node_modules`.

## B69 — weekly CronJobs + the scan-suite (2026-07-18)

The three on-demand Jobs were folded into **two weekly CronJobs** (both `Sun`, `America/New_York` since B228 — 03:00–04:00, out of the working day; see [schedules.md](../schedules.md)):
- **`code-scan-suite`** (`k8s/code-quality/scan-suite.yaml`, Sun 04:00 NY) — ONE `registry.weyland.lab/scan-suite` image
  (`services/scan-suite/`, built via `scripts/build-push-images.sh`) clones the repo once and runs the
  **`quality-tools.yaml`** roster (22 scan-suite tools) best-effort → per-tool severity counts POSTed to the Port
  `code-quality` webhook. The registry is authoritative; the build-suite-home adds (2026-08-07) were **ruff ·
  pip-audit · detect-secrets · headers · gosec · govulncheck · staticcheck · go-vet** (image `scan-suite:v4`).
  **`secret-files`** (B97, 2026-07-22) closes the gap that let the n8n key sit committed for 5 weeks: gitleaks `dir`
  HONORS `.gitignore`, so a file that is BOTH tracked in git AND gitignored (a secret hidden after it was already
  committed) is invisible to it. `secret_files` finds that intersection via `git check-ignore --no-index` over the
  tracked-file list — no entropy heuristics — and marks each hit CRITICAL. Near-zero false positives. Replaces `semgrep-scan-job` + `trivy-scan-job` (deleted).
- **`sonar-scan`** (`k8s/sonarqube/sonar-scan.yaml`, Sun 03:00 NY) — clone → Maven-compile the Flink modules → sonar-scanner
  (kept separate: needs the server + a Java build). Replaces `sonar-scan-job` (deleted).

Image gotchas hit during bring-up (all in the `scan-suite` Dockerfile/`scan.py`): pinned tool download URLs 404 on a
bad version (verify each release's real asset name — trivy was `v0.56.2` → `v0.72.0`); **semgrep needs `setuptools<81`**
(`python:3.12-slim` ships setuptools 83, which removed `pkg_resources`); **code-maat needs `git config --global --add
safe.directory /src`** (clone runs as root, scan as uid 10001 → git "dubious ownership") AND the **`git2` log format**
(`--pretty=format:--%h--%ad--%aN`, NOT the legacy `[%h] %aN %ad %s`).

**A `202` from the ingest URL is NOT proof of an entity** — it's queue-acceptance; the async mapping can still drop it.
Two ways it silently dropped here: the `security_scan.tool` property was a **string enum** locked to `["trivy","semgrep"]`
(any other tool violated it → dropped); fix = drop the enum (`enum = null`) in `tofu/port/blueprints.tf` + re-scan. And a
mapping entry referencing a blueprint that doesn't exist yet → save fails "blueprint not found" (apply the blueprint FIRST).

## B90 — code-maat hotspots → Port (2026-07-18)

code-maat's behavioral analysis (the free CodeScene equivalent) now lands in Port as its own **`code_hotspot`** blueprint
(`tofu/port/blueprints.tf`) — one entity per hot file, `revisions` (churn count), sortable. `scan.py`'s `codemaat()` POSTs
the top-20 rows to the **same** code-quality ingest URL with a `kind:"hotspot"` discriminator; the webhook mapping gained
a **3rd entry** (`filter: .body.kind == "hotspot"`, `identifier: .body.file | gsub("[/. ]"; "-")`). SonarQube *detail*
(issues/measures) is already in Port via the Ocean integration (SonarQube Issues/Projects catalog tables) — separate from
this webhook. See [[project-backlog]] B89 (drive the findings to zero) as the follow-on.

**B91 (dep pinning, 2026-07-19):** the service `requirements.txt` were unpinned, so osv-scanner read them as version
`0.0.0` and matched ~52 phantom CVEs. Fixed with the **pip-tools split**: loose `requirements.in` (human) + pinned
`requirements.txt` (from each service's `pip freeze`). osv now reads real versions → phantoms gone. To re-pin after an
intentional bump: rebuild the image (or exec the running pod) and `pip freeze > requirements.txt`.

**Remediating a pin: edit BOTH files (2026-09-25).** Dependabot treats `requirements.in` as the pip-compile
SOURCE. genre-trainer's `.in` was never updated when `main` hand-remediated `.txt` (cryptography 50.0.0, mlflow
3.15.1, aiohttp 3.14.3), so every dependabot re-cut of weyland-lab #63 regenerated `.txt` from the stale `.in` and
downgraded them again, re-opening 4 CVEs. Only Sourcery's check stopped the merge. `scripts/check-requirements-sync.sh`
(the `repo-guards` CI step) now fails when any exact `==` pin in a `requirements.in` disagrees with, or is missing
from, its `requirements.txt`. Loose `.in` entries (`>=`, bare names) are not compared. Check by hand:
```
[rogueone] bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-requirements-sync.sh
```

**Every requirements directory is watched by Dependabot (B214, 2026-10-16).** `.github/dependabot.yml` says an unlisted
directory is an unwatched one, yet 19 of 23 had no entry, 9 of them lockfiles B213 had just frozen. All 23 now have a
security-only pip entry (`open-pull-requests-limit: 0`, grouped), and `scripts/check-dependabot-coverage.sh`
(`repo-guards`) fails, naming the directory, when a `requirements*.txt` directory has none; it exits 2 when it cannot
read the config. `golden-paths/` (service templates) and `tests/lang/` (fixtures) are excluded with that reason.
```
[rogueone] bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-coverage.sh
```
**An acceptance in `osv-scanner.toml` needs a matching Dependabot `ignore` (2026-10-17).** Dependabot does not read
`osv-scanner.toml`. Within hours of the 19 new entries it opened 8 grouped security PRs (#189–#196), five of them for
versions B214 had accepted because they break the build (pyflink past apache-beam's caps, scan-suite protobuf 5 and
setuptools 83, transformers 5 in the export stages), and they would recur every week. Each of those directories now
carries an `ignore` rule (`dependency-name` + the breaking `versions` range) with the same reason; GitHub documents that
`ignore` applies to security updates too. Lift the rule with the acceptance.

**Every Dependabot `ignore` is backed by a live acceptance (2026-10-22).** An `ignore` silences security updates for that
package in that directory, and nothing expires it; the `osv-scanner.toml` accept behind it is scoped to one version and
has an `effectiveUntil`. `scripts/check-dependabot-ignores.sh` (`repo-guards`) ties them together. Each ignore must be
backed by a `[[PackageOverrides]]` entry at the version the directory pins, or by an `[[IgnoredVulns]]` (advisory-id)
accept whose reason names the package and the directory. The pin must still be below the ignored range. It fails with
`UNBACKED`, `DEAD` (the pin already moved past the cap) or `NOT PINNED`, and exits 2 when it cannot read a config or a
range. A compatibility cap with no advisory needs no ignore, because Dependabot here opens security updates only.
```
[rogueone] bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-ignores.sh
```
Expect `OK — 11 Dependabot ignore(s), each backed by a live osv-scanner.toml accept at the pinned version.`
(2026-10-22). When you lift a cap: bump the pin, delete the accept and the ignore in the same change.

**Remediating a newly visible advisory: the rules B214 learned (2026-10-16).**
- **Read every advisory's range, not the highest fix.** A range can end in `last_affected` with no fix: mlflow 3.15.0
  fixed 5 advisories and still carried an AI Gateway SSRF affecting through 3.15.2. ray-head went to 3.16.1.
- **Find what holds a pin before moving it** (`importlib.metadata` requirements inside the image). scan-suite's urllib3
  sat at 2.0.7 because checkov 3.2.257 pinned `botocore==1.34.25` (<2.1); the smallest move was checkov 3.2.290.
- **Prefer the smallest move, and run the real tool after it.** Moving semgrep would have freed protobuf, but every
  semgrep from about 1.140 pins an mcp version with GHSA-84m7; setuptools 82+ drops `pkg_resources`, which crashed
  semgrep 1.90 at startup. `pip check` passed on both; only running the tool showed it.
- **Accept what has no installable fix, scoped to the exact version.** `osv-scanner.toml` `[[PackageOverrides]]` with
  `name` + `version` + `vulnerability.ignore = true` suppresses that one version only (proven on osv-scanner 1.9.1, and re-checked on the
  v2.7 suite by B220's contract test: the same advisory on another version elsewhere still reports). Since B220 osv runs
  with `--no-resolve`, so it grades the pins a file declares and never versions it guessed for transitive deps. `[[IgnoredVulns]]` by id is repo-wide: use it only when
  the advisory cannot apply anywhere (setuptools' macOS-sdist bypass). Every entry carries its reason and an expiry.
- **Read a Dependabot security PR's whole diff before merging (2026-10-17).** Its grouped PR may REGENERATE the
  lockfile from the `.in`: #194 (oauthlib 3.3.1 → 4.0.0 in weyland-dagster) also renamed packages, dropped the B113/B213
  rationale comments and added packages. Apply the one line yourself (find its dependents in the image first: here only
  `requests-oauthlib` via the kubernetes client, `>=3.0.0`), prove it on the deployed image (`pip check`, the users
  import, `dagster definitions validate`), and close the PR with that reason. A clean one-line PR (#121, #195: GitPython)
  is merged after the requirements-sync guard passes on its head and its file installs on the service's base image.
- **A ray-head bump must be followed by a worker rebuild** ([remote-training.md](remote-training.md) § the worker venv):
  B214's v10 moved mlflow 3.14 → 3.16.1 on the head while the rogueone worker kept 3.14.0 and GitPython 3.1.52.

**B92 (ranger creds, 2026-07-20):** the last real finding — `ranger.yaml`'s ConfigMap shipped 9 plaintext dev passwords —
is fixed: they now live in the `ranger-admin-secret` SealedSecret and a `render-install-props` initContainer substitutes
them into `install.properties` at startup (see [ranger.md](ranger.md)). **`KSV-0109` is now blanket-accepted** in
`.trivyignore` — both remaining hits (ranger `@@TOKEN@@` placeholders, trino `${ENV:...}` refs) are false positives,
since trivy can't distinguish a placeholder from a secret on a password-named key.

**The `Code Health` dashboard** (Port sidebar / Catalog) assembles it all on one page: three number cards (Σ `critical` +
Σ `high` over `security_scan`, count of `sonarQubeIssue`) over a `code_quality` Quality-Gate table + a `code_hotspot`
Top-Hotspots table (sorted by churn). Built via the **Port MCP** (`upsert_dashboard_page`) — **Port dashboards can't be
codified in tofu** ([port.md](port.md): blueprints=code, entities+dashboards=Port/MCP), so this page lives only in Port,
not git. To rebuild it: re-run `upsert_dashboard_page` for `code_health` via the Port MCP.
