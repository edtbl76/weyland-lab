# Code Quality — runbook (B43, Port category)

Three on-demand scanners → Port. **SonarQube** (server, always-on) + **Trivy** + **Semgrep** (stateless Jobs).
LaunchDarkly-style SaaS avoided; all OSS/$0. Findings surface in Port as `code_quality` + `security_scan` entities.

- SonarQube server: `k8s/sonarqube/sonarqube.yaml` — `sonarqube.weyland.lab`, **meshed** (STRICT Postgres backend,
  db/role `sonarqube`). Auth is **double-login**: a **Keycloak forward-auth gate** (`traefik-forward-auth`) sits
  **in front of** SonarQube's own login (`admin`/`admin` → forced change) — Keycloak SSO first, then SonarQube's
  own login. Stateless-ish: data + extensions on RWO PVCs.
- Scan Jobs (clone → scan → push): `k8s/sonarqube/sonar-scan-job.yaml`, `k8s/code-quality/trivy-scan-job.yaml`,
  `k8s/code-quality/semgrep-scan-job.yaml`. Re-run: `kubectl delete job <name> -n weyland` then re-apply.
- Always-on (NOT KEDA scale-to-zero): the 32GB RAM bump made the cost moot; scale-to-zero would need the KEDA
  HTTP interceptor in front (cross-ns ingress rewire + scan-path-through-interceptor). Revisit only if RAM tightens.

## Host prereq
- `vm.max_map_count=524288` on mother (`/etc/sysctl.d/99-sonarqube.conf`) — SonarQube's embedded Elasticsearch
  refuses to boot otherwise.

## Port wiring (all three → one webhook DS `code-quality`)
- Blueprints: `code_quality` (qualityGate OK/ERROR/WARN/NONE, project, branch), `security_scan` (tool, target,
  critical/high/medium/low/total). Created via MCP. **Webhook DS + its mapping are UI-only** (not MCP-manageable —
  `list_integrations` shows only Ocean exporters).
- **SonarQube → Port:** native webhook (Administration → Configuration → Webhooks → URL = `ingest.getport.io/<key>`).
  Fires after each analysis (the CE processes the report async, then POSTs). Pod is meshed; egress to getport.io
  works (Istio ALLOW_ANY).
- **Trivy/Semgrep → Port:** each Job's `report` container parses the scan JSON → POSTs counts to the same ingest
  URL (Secret `port-ingest-url`, key `url`). Severity map for Semgrep: ERROR→high, WARNING→medium, INFO→low.
- Mapping (paste in the Port webhook DS Mapping tab) is the 2-entry array in this repo's git history / below format;
  `operation` must be **`create`** (Port rejects `upsert`).

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
