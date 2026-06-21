# Code Quality — runbook (B43, Port category)

Three on-demand scanners → Port. **SonarQube** (server, always-on) + **Trivy** + **Semgrep** (stateless Jobs).
LaunchDarkly-style SaaS avoided; all OSS/$0. Findings surface in Port as `code_quality` + `security_scan` entities.

- SonarQube server: `k8s/sonarqube/sonarqube.yaml` — `sonarqube.weyland.lab`, **meshed** (STRICT Postgres backend,
  db/role `sonarqube`), own login (`admin`/`admin` → forced change). Stateless-ish: data + extensions on RWO PVCs.
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
