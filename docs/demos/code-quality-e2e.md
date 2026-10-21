# Demo — Code quality / security scan (scan-suite → Port)

The weekly **code-health** capability (B69 scan-suite + B89 triage + B90 dashboard). Two k8s CronJobs in ns
`weyland` feed Port.io: **`code-scan-suite`** runs 9 security tools + code-maat hotspots over the cloned repo
(→ `security_scan` + `code_hotspot` blueprints), and **`sonar-scan`** Maven-compiles + runs sonar-scanner against
the in-cluster SonarQube (→ `code_quality` quality-gate). A **Code Health** Port dashboard assembles all three.
Grounded in [../runbooks/code-quality.md](../runbooks/code-quality.md), [../diagrams/flow-code-quality.md](../diagrams/flow-code-quality.md),
and [../schedules.md](../schedules.md).

> **✅ Validated — RUN live 2026-07-18.** Both smokes executed straight through: **9** `security_scan` entities
> confirmed in Port, code-maat **posted 20 hotspots**, `sonar-scan` returned **ANALYSIS SUCCESSFUL**, and the
> **Code Health** dashboard renders (Open Critical **1**, Open High **276**).

## Sequence diagram

```mermaid
sequenceDiagram
    participant Cron as CronJobs (ns weyland)<br/>Sun 12:00 + 13:00 UTC
    participant Clone as clone initContainer<br/>(git clone --full-history)
    participant Suite as scan-suite image<br/>(22 tools, code-maat among them)
    participant Sonar as SonarQube<br/>(sonarqube.weyland.svc:9000)
    participant Ingest as Port webhook<br/>(code-quality ingest URL)
    participant BP as Port blueprints<br/>(security_scan / code_hotspot / code_quality)
    participant Dash as Code Health dashboard

    Cron->>Clone: start code-scan-suite (Sun 04:00 NY)
    Clone->>Suite: /src (full git history)
    loop 9 tools best-effort
        Suite->>Ingest: POST per-tool counts
        Ingest-->>Suite: 202 (queue-accepted, NOT entity-created)
        Ingest->>BP: .body.tool!=null → security_scan
    end
    Suite->>Ingest: POST code-maat top-20 {kind:"hotspot"}
    Ingest->>BP: .body.kind=="hotspot" → code_hotspot
    Cron->>Clone: start sonar-scan (Sun 03:00 NY)
    Clone->>Sonar: Maven-compile + sonar-scanner
    Sonar->>Ingest: native webhook POST quality gate
    Ingest->>BP: .body.qualityGate!=null → code_quality (weyland-lab)
    BP->>Dash: 3 cards + Quality Gate table + Top Hotspots table
```

## Prerequisites

- **Port** — `https://app.port.io`; blueprints `security_scan`, `code_hotspot`, `code_quality`
  (`tofu/port/blueprints.tf`); webhook DS `code-quality` with a **3-entry mapping array** (UI-only, `operation: create`).
- **CronJobs** (both `Sun`, `America/New_York` since B228): `code-scan-suite` (`k8s/code-quality/scan-suite.yaml`, 04:00),
  `sonar-scan` (`k8s/sonarqube/sonar-scan.yaml`, 03:00).
- **scan-suite image** — `registry.weyland.lab/scan-suite` (`services/scan-suite/`); ingest URL in Secret
  `port-ingest-url` (key `url`).
- **SonarQube** — `https://sonarqube.weyland.lab`, in-cluster `sonarqube.weyland.svc:9000`, native webhook → Port.
- **Code Health dashboard** — Port Catalog → **Code Health** (built via Port MCP `upsert_dashboard_page`, Port-only, not codified).
- `kubectl` runs on **mother** (`emangini@mother`).

## UI walkthrough

1. Open `https://app.port.io` → **Catalog** → **Code Health** dashboard. Confirm the assembled page:
   - **3 number cards** — Σ `critical`, Σ `high`, Σ `medium` over `security_scan` (live values: Open Critical **1**, Open High **276**).
   - **Quality Gate table** — from `code_quality` (one row: `weyland-lab`, gate = **ERROR**).
   - **Top Hotspots table** — from `code_hotspot`, sorted by churn (`revisions`).
2. Drill into the individual catalog tables (sidebar / Catalog):
   - **Security Scans** (`security_scan`) — **9 tool entities**: gitleaks, checkov, kubescape, hadolint, bandit, osv-scanner, shellcheck, semgrep, trivy — each with its critical/high/medium/low/total and `scannedAt`.
   - **Code Hotspot** (`code_hotspot`) — top-20 hot files ranked by `revisions` (churn).
   - **Code Quality** (`code_quality`) — `weyland-lab`, `qualityGate = ERROR`, with `project` / `branch` / `analyzedAt` / `url`.
3. Cross-check the source detail in the **SonarQube UI** at `https://sonarqube.weyland.lab/dashboard?id=weyland-lab`
   (double-login: Keycloak forward-auth gate, then SonarQube's own login).

## CLI walkthrough

The canonical trigger is the weekly Sunday CronJob. To kick each on-demand instead of waiting, create a Job
`--from` the CronJob on **mother**.

[rogueone] Kick the scan-suite (22 tools, code-maat among them) and read its findings, with the canonical command
(`kubectl wait --for=condition=complete` never returns for a FAILED Job, and since 2026-10-16 a scan defect fails it):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/run-scan-suite.sh
```
Expect `✓ scan complete`, per repo every tool with a critical or high finding plus its archive path, and the full log's
path. Each tool prints `= <tool>: …C / …H / …M / …L` then `POST 202`, and `= code-maat: posted 20 hotspots to Port`.

[mother] Kick the sonar path (clone → Maven-compile → sonar-scanner):
```
kubectl -n weyland create job sonar-scan-smoke --from=cronjob/sonar-scan && kubectl -n weyland wait --for=condition=complete job/sonar-scan-smoke --timeout=900s && kubectl -n weyland logs job/sonar-scan-smoke --tail=5
```
Expect `ANALYSIS SUCCESSFUL` and `EXECUTION SUCCESS`.

The Port entities appear within seconds of each `202` (Sonar lags a few seconds while the SonarQube CE processes
the report before its native webhook fires). Remember: a `202` is queue-acceptance, **not** proof an entity was
created — confirm in the Port catalog tables above.

### Shell scripts inside ConfigMaps (B230, RUN 2026-10-19)

CI's `shellcheck` step used to see only `scripts/**`; 7 scripts that live only in a ConfigMap were never linted. The
guard, in CI's own image:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && docker run --rm -v "$PWD:/repo:ro" -w /repo --entrypoint sh koalaman/shellcheck-alpine:stable -c 'apk add --no-cache python3 py3-yaml bash >/dev/null; bash scripts/check-configmap-shellcheck.sh'
```
Output (RUN 2026-10-21, after the B230 re-audit widened it to inline `sh -c` scripts): `OK — 50 shell script(s) (13
ConfigMap key(s), 37 inline sh -c) under weyland-platform/k8s pass shellcheck --severity=warning.`, exit 0. (2026-10-19:
13 ConfigMap scripts only.)

**Negative case, runnable** — a scratch copy of the k8s tree with a bare `cd $dir` planted in the `sonar-scan-repos`
runner (the repo is untouched):

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && docker run --rm -v "$PWD:/repo:ro" -w /repo --entrypoint sh koalaman/shellcheck-alpine:stable -c 'apk add --no-cache python3 py3-yaml bash >/dev/null; T=$(mktemp -d); cp -r nodes/mother/lab/weyland-platform/k8s "$T/k8s"; sed -i "s|^    rc=0\$|    rc=0\n    cd \$dir|" "$T/k8s/sonarqube/sonar-scan-repos.yaml"; CM_SHELLCHECK_K8S_DIR="$T/k8s" bash scripts/check-configmap-shellcheck.sh; echo "exit=$?"; rm -rf "$T"'
```
Output (RUN 2026-10-21):
```
sonarqube/sonar-scan-repos.yaml:sonar-all.sh:8:1: warning: Use 'cd ... || exit' or 'cd ... || return' in case cd fails. [SC2164]
CONFIGMAP SHELLCHECK: 1 of 50 shell script(s) have findings at --severity=warning.
exit=1
```
The finding is named by manifest and data key (an inline script is named `<manifest>:<Kind>/<name>/<container>`). The
fail-closed cases (no k8s dir, an unparseable manifest, the extractor failing, zero scripts, no shellcheck, shellcheck
itself erroring → exit 2) are in `scripts/tests/configmap-shellcheck.bats` (12 cases).

## Expected result

- **9** `security_scan` entities in Port (one per tool), each with severity counts; **20** `code_hotspot` entities
  ranked by churn; **1** `code_quality` entity (`weyland-lab`, gate `ERROR`).
- The **Code Health** dashboard renders the 3 cards + 2 tables (Open Critical **1**, Open High **276** as of 2026-07-18).
- `scan-suite-smoke` log ends with `= code-maat: posted 20 hotspots to Port`; `sonar-scan-smoke` ends with `ANALYSIS SUCCESSFUL` / `EXECUTION SUCCESS`.

## Cleanup / teardown

[mother] Delete the smoke Jobs:
```
kubectl -n weyland delete job scan-suite-smoke sonar-scan-smoke --ignore-not-found
```
> The demo re-creates data, but it's **idempotent Port upserts** — the webhook mapping's `operation: create` is
> keyed by identifier (`tool` for `security_scan`, `file`-slug for `code_hotspot`, `weyland-lab` for `code_quality`),
> so re-running overwrites rather than duplicating. No teardown of Port entities is needed beyond the smoke Jobs.
