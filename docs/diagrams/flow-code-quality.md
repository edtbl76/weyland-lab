# Flow — Code quality / security scan (scan-suite → Port)

The weekly **code-health** path (B69 scan-suite + B89 triage + B90 dashboard). Two k8s CronJobs in ns `weyland`
feed Port.io, and a **Code Health** Port dashboard assembles the result. The lab is LAN-only and Port is SaaS, so
everything is **outbound**: each scanner POSTs findings to Port's `code-quality` webhook ingest URL (Secret
`port-ingest-url`), and SonarQube's native webhook POSTs its quality gate the same way.

- **`code-scan-suite`** (Sun **04:00 NY**, B228) — an `initContainer` git-clones the public repo
  (`github.com/edtbl76/weyland-lab`, **full history** for code-maat) into `/src`, then the
  `registry.weyland.lab/scan-suite` image runs the **`quality-tools.yaml`** roster (22 scan-suite tools, multi-language:
  secrets/SAST/SCA/IaC/k8s/lint/vuln/HTTP-headers over Python + Go) best-effort over `/src` — each POSTing severity counts →
  **`security_scan`** blueprint (one entity per tool). code-maat then computes change-hotspots and POSTs the
  **top-20** to the **same** ingest URL with a `kind:"hotspot"` discriminator → **`code_hotspot`** blueprint.
- **`sonar-scan`** (Sun **03:00 NY**, B228) — clone → Maven-compile the Flink modules → `sonar-scanner-cli` against the
  in-cluster SonarQube (`sonarqube.weyland.svc:9000`); SonarQube's **native webhook** POSTs the quality gate →
  **`code_quality`** blueprint (one entity: `weyland-lab`).
- **`sonar-scan-repos`** (Sun **03:15 NY**, B138/B229) — an `alpine/git` initContainer clones the eight active repos
  with no build step (`SONAR_REPOS`); the scanner then runs one SonarQube project per checkout, with source-only Java
  (an empty `sonar.java.binaries`) for a repo holding `.java` files and no build. A failed clone or a failed scan fails
  the Job, named; the rest are still scanned (diagram below).

See [../runbooks/code-quality.md](../runbooks/code-quality.md) and [../schedules.md](../schedules.md).

## Sequence

```mermaid
sequenceDiagram
    participant Cron as CronJobs (ns weyland)<br/>Sun 03:00 + 04:00 NY (B228)
    participant Clone as clone initContainer<br/>(git clone --full-history)
    participant Suite as scan-suite image<br/>(22 tools, code-maat among them)
    participant Maven as maven build + sonar-scanner<br/>(Flink modules)
    participant Sonar as SonarQube<br/>(sonarqube.weyland.svc:9000)
    participant Ingest as Port webhook<br/>(code-quality ingest URL)
    participant BP as Port blueprints<br/>(security_scan / code_hotspot / code_quality)
    participant Dash as Code Health dashboard<br/>(Catalog → Code Health)
    participant Reg as registry.weyland.lab<br/>(the deployed images)
    participant Arch as s3://scan-reports<br/>(per-run archive, 90d)
    participant Op as Operator (DoD Pillar 7)

    Note over Cron,BP: Path 1 — code-scan-suite (Sun 04:00 NY)
    Cron->>Clone: start code-scan-suite
    Clone->>Suite: /src (full git history)
    loop 22 tools best-effort
        Suite->>Ingest: POST per-tool counts {tool, critical/high/medium/low, ...}
        Ingest-->>Suite: 202 (queue-accepted, NOT entity-created)
        Ingest->>BP: map .body.tool!=null → security_scan (one entity per tool)
    end
    Note over Suite: kubescape runs with --exceptions kubescape-exceptions.json (2026-10-22): C-0236 image-signature is accepted with the ignore action (kubescape v4 counts an alertOnly one as acknowledged, still failed), its count printed apart, out of the posture totals, and a C-0236 left acknowledged fails the tool loudly
    Note over Suite,Reg: trivy-images (B213, weyland-lab only) — the images the manifests DEPLOY
    Suite->>Suite: deployed_images — images.tsv refs plus every registry.weyland.lab ref in k8s/ (23)
    loop each deployed image
        Suite->>Reg: trivy image --scanners vuln --ignorefile .trivyignore-images.yaml (B220: purl-scoped accepts, each with expired_at — then trivy clean --scan-cache)
        Reg-->>Suite: a trivy report, or none → recorded BROKEN, never zero
    end
    Suite->>Arch: trivy-images.json {images, broken, missing} with the run's other reports
    Op->>Arch: scan-diff.py previous-run this-run — keyed image NAME + package + id, MEDIUM counted
    Arch-->>Op: new / gone per tool, a baseline line when the old run predates the scan, exit 2 if any image BROKEN
    Note over Suite,Cron: after every tool ran and posted — a crashed tool or a BROKEN image → scan.py exits 3, scan-all.sh finishes the other repos and exits 3, podFailurePolicy fails the Job with no retry, KubeJobFailed → Telegram
    Suite->>Ingest: POST code-maat top-20 {kind:"hotspot", file, revisions, ...}
    Ingest-->>Suite: 202 (queue-accepted)
    Ingest->>BP: map .body.kind=="hotspot" → code_hotspot

    Note over Cron,BP: Path 2 — sonar-scan (Sun 03:00 NY)
    Cron->>Clone: start sonar-scan
    Clone->>Maven: /src (Maven-compile Flink modules)
    Maven->>Sonar: sonar-scanner-cli analysis
    Sonar->>Sonar: CE processes report (async)
    Sonar->>Ingest: native webhook POST quality gate {qualityGate, project, ...}
    Ingest-->>Sonar: 202 (queue-accepted)
    Ingest->>BP: map .body.qualityGate!=null → code_quality (weyland-lab)

    Note over BP,Dash: Code Health assembles it all
    BP->>Dash: 3 number cards (Σ critical/high/medium) + Quality Gate table + Top Hotspots table
```

## sonar-scan-repos: what each repo gets, and when the Job fails (B229)

```mermaid
flowchart TD
    I["initContainer: git clone each repo in SONAR_REPOS"] -->|clone fails| M["append the repo to /src/.clone-failed"]
    I -->|cloned| S["/src/repo"]
    M --> R{"runner: /src/.clone-failed non-empty?"}
    S --> R
    R -->|yes| F1["print: not scanned (clone failed): repo, rc=1"]
    R -->|no| L["for each /src/repo"]
    F1 --> L
    L --> P{"repo has its own sonar-project.properties?"}
    P -->|yes| O["defer to it (projectKey/baseDir/host/token only)"]
    P -->|no| D["-Dsonar.sources=. + default exclusions"]
    O --> J{".java files, no sonar.java.binaries?"}
    D --> J
    J -->|yes| E["-Dsonar.java.binaries=empty dir (source-only Java)"]
    J -->|no| X["no Java setting"]
    E --> SC["sonar-scanner"]
    X --> SC
    SC -->|fails| F2["print: sonar-scanner failed for repo, rc=1, next repo"]
    SC -->|ok| N["next repo"]
    N --> Z["exit rc: 0 only when every repo cloned and scanned"]
    F2 --> Z
```

Tests: `scripts/tests/sonar-scan-repos.bats` runs the real script out of the manifest against fake repos.

## The shell-in-manifests guard: 0 / 1 / 2 (B230)

`scripts/check-configmap-shellcheck.sh` (CI `shellcheck` step) lints the shell that lives inside manifests, which the
`scripts/**` glob never sees.

```mermaid
flowchart TD
    A{"shellcheck on PATH and the k8s dir exists?"} -->|no| C2["exit 2: CANNOT CHECK"]
    A -->|yes| X{"extract every ConfigMap .sh key + every inline sh -c script"}
    X -->|"a manifest does not parse / the extractor fails"| C2
    X -->|"zero scripts found"| C2
    X -->|"N scripts"| S["shellcheck --severity=warning each"]
    S -->|"shellcheck exits 2+ (could not run)"| C2
    S -->|"any exits 1"| C1["exit 1: each finding named manifest:key or manifest:Kind/name/container"]
    S -->|"all exit 0"| C0["exit 0: OK, N scripts (ConfigMap keys + inline)"]
```

Tests: `scripts/tests/configmap-shellcheck.bats` (12). Demo: [demos/code-quality-e2e.md](../demos/code-quality-e2e.md)
§ Shell scripts inside ConfigMaps.

**Gotcha — `202` ≠ entity created.** The ingest URL returns `202` on *queue-acceptance*; the async mapping can
still silently drop the payload. Two ways it did here: the `security_scan.tool` property was a **string enum**
locked to `["trivy","semgrep"]` (any other tool violated it → dropped — fix = `enum = null`), and a
`code_hotspot` mapping entry referenced a **blueprint that didn't exist yet** (apply the blueprint FIRST). Always
confirm the entity in Port, not just the `202`.

**Mapping-filter routing.** The webhook mapping is a **3-entry array** (UI-only, `operation: create`):
`code_quality` on `.body.qualityGate != null` · `security_scan` on `.body.tool != null` · `code_hotspot` on
`.body.kind == "hotspot"`. All three POST to the *same* ingest URL; the filters fan them out to the right
blueprint.

**Dashboard is Port-only.** The **Code Health** dashboard (Catalog → Code Health, built via Port MCP
`upsert_dashboard_page`) can't be codified in tofu — it lives only in Port, not git. Blueprints ARE codified
(`tofu/port/blueprints.tf`); entities + dashboards are Port/MCP.
