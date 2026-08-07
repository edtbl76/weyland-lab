# Code Quality — runbook (B43, Port category)

**Two weekly k8s CronJobs → Port** (B69, replacing the old on-demand Jobs). **`code-scan-suite`** runs the **full
scan-suite roster declared in the repo-root [`quality-tools.yaml`](../../quality-tools.yaml)** — the SOURCE OF TRUTH
(`scripts/check-quality-tools.sh` drift-guards scan.py + these docs against it; a hand-copied list is how the old
"9 vs 10" mismatch happened). **19 tools**, now **multi-language** (Python + Go for polyglot repos like Stud.io):
secrets · SAST · SCA/deps · IaC/k8s · Dockerfile/shell lint · vuln · HTTP-headers, + **code-maat** change-hotspots;
**`sonar-scan`** runs the always-on **SonarQube** server. All OSS/$0. Findings surface in Port as
`security_scan` (per-tool), `code_hotspot` (churn), and `code_quality` (Sonar gate) → the **Code Health** dashboard.
The suite + B89 triage + B90 dashboard are detailed in the sections below.

- SonarQube server: `k8s/sonarqube/sonarqube.yaml` — `sonarqube.weyland.lab`, **meshed** (STRICT Postgres backend,
  db/role `sonarqube`). Auth is **double-login**: a **Keycloak forward-auth gate** (`traefik-forward-auth`) sits
  **in front of** SonarQube's own login (`admin`/`admin` → forced change) — Keycloak SSO first, then SonarQube's
  own login. Stateless-ish: data + extensions on RWO PVCs.
- Weekly CronJobs (clone → scan → Port): `k8s/code-quality/scan-suite.yaml` (`code-scan-suite`, Sun 13:00 UTC) +
  `k8s/sonarqube/sonar-scan.yaml` (`sonar-scan`, Sun 12:00 UTC). Run on-demand:
  `kubectl -n weyland create job <name>-smoke --from=cronjob/<code-scan-suite|sonar-scan>`.
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
  `-Dsonar.java.binaries=…/target/classes`. `k8s/sonarqube/sonar-scan-job.yaml`.
- **Trivy** `FATAL 429` — the new Flink `pom.xml` made it fetch transitive POMs from Maven Central, rate-limiting
  mother's IP. Fix: `--offline-scan`. `k8s/code-quality/trivy-scan-job.yaml`.
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

## B69 — weekly CronJobs + the scan-suite (2026-07-18)

The three on-demand Jobs were folded into **two weekly CronJobs** (both `Sun`, `Etc/UTC`; see [schedules.md](../schedules.md)):
- **`code-scan-suite`** (`k8s/code-quality/scan-suite.yaml`, 13:00 UTC) — ONE `registry.weyland.lab/scan-suite` image
  (`services/scan-suite/`, built via `scripts/build-push-images.sh`) clones the repo once and runs the
  **`quality-tools.yaml`** roster (19 scan-suite tools) best-effort → per-tool severity counts POSTed to the Port
  `code-quality` webhook. The registry is authoritative; the build-suite-home adds (2026-08-07) were **ruff ·
  pip-audit · detect-secrets · headers · gosec · govulncheck · staticcheck · go-vet** (image `scan-suite:v4`).
  **`secret-files`** (B97, 2026-07-22) closes the gap that let the n8n key sit committed for 5 weeks: gitleaks `dir`
  HONORS `.gitignore`, so a file that is BOTH tracked in git AND gitignored (a secret hidden after it was already
  committed) is invisible to it. `secret_files` finds that intersection via `git check-ignore --no-index` over the
  tracked-file list — no entropy heuristics — and marks each hit CRITICAL. Near-zero false positives. Replaces `semgrep-scan-job` + `trivy-scan-job` (deleted).
- **`sonar-scan`** (`k8s/sonarqube/sonar-scan.yaml`, 12:00 UTC) — clone → Maven-compile the Flink modules → sonar-scanner
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
