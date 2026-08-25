# Port.io — the IDP / software catalog (B43 / B58 / B60)

**What:** Port is the lab's internal developer portal — the **catalog** (every system, component, resource, API,
data store, and their relations), the **scorecards** (production-readiness, etc.), and the **dashboards**. It
replaced Backstage ([[port-catalog-docs-b59]]). Architecturally: **Port = the "see" layer** (catalog, scorecards,
observability); **Hermes = the "do" layer** (acts on the cluster via its tool-server, [[feedback-agent-act-lanes]]).
The *action* execution path (clicking a Port button to change the cluster) is separate — see
[port-agent-easy-button.md](port-agent-easy-button.md).

**Where:**
- UI: **https://app.port.io** (SaaS, EU org `org_KyCTEN4PVUv1D3TM`). Not a `*.weyland.lab` host — Port is cloud.
- Schema as code: `tofu/port/` (`catalog.tf`, `blueprints.tf`, `cost.tf`, `actions.tf`, plus `b137_blueprints.tf`,
  `b137_scorecards.tf`, `b137_integrations.tf`) — OpenTofu, state in MinIO. See [opentofu.md](opentofu.md).
  Coverage is asserted by `scripts/check-port-iac-coverage.sh`; see
  [What is deliberately UI-managed](#what-is-deliberately-ui-managed-and-why-b137).
- Action agent (LAN relay): `k8s/port-agent/port-agent-values.yaml` — covered separately in
  [port-agent-easy-button.md](port-agent-easy-button.md).

## How the catalog is built + kept in sync

> **CORRECTED 2026-08-22.** This section previously claimed there is "no self-hosted k8s exporter / Ocean
> integration running." **That is false**, and was verified false against the live Port API. FOUR integrations
> are connected:
>
> | Integration | Type | Version | Mapped kinds |
> |---|---|---|---|
> | `weyland-cluster` | OnPrem — K8S EXPORTER | 0.7.4 | 11: deployments, daemonsets, replicasets, statefulsets, pods, nodes, namespaces, Istio gateways + virtualservices |
> | `github-weyland` | SaasOAuth2 — github-ocean | 6.8.1 | **1: `repository` only** |
> | `linear` | Saas | 0.3.97 | 3: issue, label, team |
> | `sonarqube-direct` | Saas | 0.1.439 | 2: issues, projects_ga |
>
> The k8s exporter runs **on-prem and pushes outbound**, which is why the LAN-only topology never blocked it —
> the original inference (cloud cannot reach in ⇒ no exporter) was wrong about the direction of travel.
>
> Live counts at correction time: **51 blueprints** (only 13 in OpenTofu), **8 scorecards** (none in OpenTofu),
> `githubRepository` 6 entities, `service` 6, `environment` 3, `ci_pipeline` 13, and
> **`githubPullRequest` 0 / `githubWorkflowRun` 0 / `deployment` 0** — those blueprints exist but nothing feeds
> them. `deployment: 0` is exactly the gap EMA-172 (DORA) is open for, and the `service/dora_lead_time`,
> `service/dora_deploy_freq` and `service/delivery_performance` scorecards are built and starved.
>
> **Consequence worth knowing:** ingesting pull requests is NOT a build — it is adding the `pull-request` kind to
> `github-weyland`'s existing mapping.
>
> **RESOLVED 2026-08-24 (B137).** The table above is kept as written because it is the record of what was found;
> here is what is true now. All 4 integrations, all 8 scorecards and the 8 missing hand-authored blueprints are
> codified in `tofu/port/` and `tofu plan` is clean. `github-weyland` maps `repository` **+ `pull-request`** and
> holds 7 PR entities matching `gh pr list`; `weyland-cluster` gained `batch/v1/jobs` + `batch/v1/cronjobs`
> (13 kinds), which ended ~40 audit-log failures/hour. The **versions in that table have already moved** —
> github-ocean 6.8.1 → **6.9.4**, sonarqube 0.1.439 → **0.1.442**, linear 0.3.97 → **0.4.3**, all without human
> action, which is exactly why `version` is left unmanaged in `b137_integrations.tf`. `deployment` still has
> **0 entities**: that is EMA-172's DORA gap, untouched here.

Port is SaaS and the lab is LAN-only, so **Port's cloud cannot reach inbound** to scrape the cluster — anything
Port learns about in-cluster state is **pushed outbound** to it. The catalog is maintained two ways, split by
what the thing *is*:

- **Blueprints (the schema) = OpenTofu, drift-checked.** The blueprint definitions live in `tofu/port/` and are
  the codified source of truth:
  - `catalog.tf` — the 5 **Software Catalog** blueprints that mirror the old Backstage model:
    `domain`, `system`, `resource`, `api`, `component` (component also relates to `k8s_workload`, `service`,
    APIs, and resources).
  - `blueprints.tf` — 7 webhook/integration blueprints fed by the observability tools:
    `security_scan` (9-tool scan-suite), `code_hotspot` (code-maat churn), `glitchtip_issue`, `feature_flag` (Unleash),
    `code_quality` (SonarQube), `endpoint`, `ci_pipeline` (Woodpecker).
  - `cost.tf` — the `cost` (Recurring Cost) blueprint.
  - `b137_blueprints.tf` — the 8 hand-authored blueprints that had only ever existed in the UI:
    `service`, `workload`, `deployment`, `environment`, `organization`, `backup`, `ai_session`, `ai_user`.
    `service` is the one that mattered most: `component`'s "Repo / Service (DORA)" relation targets it, so
    reading the IaC alone made that relation look broken.
  - `b137_scorecards.tf` — all **8 scorecards** (44 rules): `service/delivery_performance` (14),
    `service/production_readiness` (10), `service/quality_maturity` (5), `service/reliability_health` (5),
    `service/dora_lead_time` (3), `service/dora_deploy_freq` (3), `workload/availability` (3),
    `sonarQubeProject/services_connected` (1).
  - `b137_integrations.tf` — all **4 integrations** and their resource mappings: `github-weyland`,
    `weyland-cluster`, `linear`, `sonarqube-direct`.
- **Entities (the data) = MCP / integration-managed, NOT in tofu.** B60 deliberately decoupled the lanes:
  codifying actively-edited entity data caused constant sync friction (every ownership/relation/scorecard tweak
  forced a tofu reconcile). Entities (1 domain · 3 systems · 11 components · 6 resources · 5 APIs · service repos)
  are rebuilt from the docs (`arch.md` / `api.md`) via MCP in minutes. The `component → k8s_workload` **live links**
  (logical service ↔ running pod) were likewise built via MCP — the upgrade Backstage couldn't do. Webhook-fed
  entities (`security_scan`, `glitchtip_issue`, `feature_flag`, `code_quality`, `ci_pipeline`) are **pushed** by
  the source tools' Port webhooks ([code-quality.md](code-quality.md), [glitchtip.md](glitchtip.md),
  [unleash.md](unleash.md), [uptime-kuma.md](uptime-kuma.md), [woodpecker.md](woodpecker.md)).

To rebuild the catalog after a change: re-emit entities from the docs via MCP; reconcile blueprint schema with
`tofu -chdir=tofu/port plan && tofu … apply` (on **rogueone**, creds via env — see below).

## What is deliberately UI-managed, and why (B137)

51 blueprints are live; **21 are codified**. The other 30 are UI-managed on purpose. The rule is
**codify what cannot recreate itself; document what does** — and the decision is not prose only, it is
executable: `scripts/check-port-iac-coverage.sh` fails on anything live that is neither codified nor excused
by one of the three reasons below.

| Group | Count | Why it stays out of `tofu/port/` |
|---|---|---|
| Port **system** blueprints (`_`-prefixed) | 11 | Port owns them and ships them with every org. The provider even models them as a different resource type (`port_system_blueprint`), precisely because they are not ours to create or destroy. Codifying them hands tofu a `destroy` it must never perform. |
| **Integration-owned** (`githubRepository`, `githubPullRequest`, the 6 `k8s_*`, 2 `istio_*`, 3 `linear*`, 2 `sonarQube*`) | 15 | An Ocean integration creates its blueprints on install and **revises them on upgrade** — github-ocean moved 6.8.1 → 6.9.4 in two days here. If tofu owned `githubRepository`, every upgrade would read as drift and an apply would revert the integration's own schema. That is the permanently-dirty plan B137 exists to cure, so codifying them would reintroduce the disease in the name of curing it. |
| **Dormant** — `githubOrganization`, `githubUser`, `githubWorkflow`, `githubWorkflowRun` | 4 | Same owner (github-ocean created them on install) but nothing maps them today, so they cannot be *derived* from the live mappings. They are named explicitly in the guard's `DORMANT_UI_MANAGED` list, each with its reason, rather than silently tolerated. |

**The consequence, stated rather than rediscovered: rebuild order.** Six relations on codified blueprints point at
integration-owned targets, so a from-scratch restore must **install the integrations first, then `tofu apply`**:

```
component.k8sWorkload           -> k8s_workload
workload.k8s_workload           -> k8s_workload
environment.k8s_cluster         -> k8s_cluster
service.github_repository       -> githubRepository
service.sonar_project           -> sonarQubeProject
deployment.github_pull_request  -> githubPullRequest
```

The guard prints that list on every run, so it stays a stated fact instead of something someone works out
mid-restore.

### The IaC coverage guard

```bash
bash scripts/check-port-iac-coverage.sh           # assert; non-zero on any live-only schema
bash scripts/check-port-iac-coverage.sh --list    # the full decision table, always exit 0
```

**Why it exists and why `tofu plan` is not enough:** plan compares the code to the resources **tofu knows about**.
A blueprint created in the UI is not one of them, so "no changes" and "half the catalog is unversioned" are
byte-identical outputs. That is how the org reached 51/13 blueprints, 8/0 scorecards and 4/0 integrations over two
months with a clean plan the whole time — found by accident, from an unrelated scan. The guard asks the inverse
question and is the only thing that can catch the disease recurring.

It reads the **`.tf` files**, not `tofu state`: state answers "what does tofu know about", and a resource can sit
in state with no code behind it — exactly the condition B60's unexecuted `state rm` left the component entities in
for weeks. It fails closed on an unreachable API, an empty live list, or an unparseable `.tf`. Covered by 18 bats
tests in `scripts/tests/port-iac-coverage.bats`, each mutation-verified.

**CI wiring:** step `port-iac-coverage` in `.woodpecker.yml`. It is `failure: ignore` **only until** the repo
secrets `port_client_id` / `port_client_secret` exist on `edtbl76/weyland-lab` — it is the one guard here that
needs credentials, which is why it is a separate step from `repo-guards` (pure file analysis, no secrets). Once
the secrets are set, delete the `failure: ignore` line. An advisory guard left advisory is how fifteen diagrams
rotted.

## OpenTofu port-provider gotchas

Codifying the blueprints hit the port-labs provider's central trap — read this before running `tofu` in
`tofu/port/` ([[opentofu-iac-gotchas]]):

- **Provider source type `port-labs` ≠ resource prefix `port_`.** `tofu plan -generate-config-out` writes a bare
  `provider = port-labs` into every generated resource — an unmapped local name → OpenTofu resolves it to
  `hashicorp/port-labs` → "provider does not have a provider named…" + "Inconsistent lock file". One leftover
  generated file poisons every `init`. **Fix:** write plain resource blocks (the `port_` prefix anchors the `port`
  provider mapped in `main.tf`), **strip the `provider = port-labs` lines**
  (`sed -i -E '/^[[:space:]]*provider[[:space:]]*=[[:space:]]*port-labs[[:space:]]*$/d'`), and bring resources into
  state with **CLI `tofu import <addr> <id>`** — NOT `import` blocks (which hit the same phantom). `cost.tf` is the
  hand-written example with no `provider =` line.
- **`port_entity` generate-config also emits read-only fields** (`id`, `created_at`, `updated_at`, `updated_by`) →
  sed-strip those too, or you get a perpetual "N to change" (part of why entities are MCP-managed, not codified).
- **Creds via env, never committed:** `PORT_CLIENT_ID` / `PORT_CLIENT_SECRET` (the tofu provider uses **Personal**
  creds — Client ID = your email — which authenticate + manage the catalog fine) plus the MinIO state creds
  (`AWS_ACCESS_KEY_ID=admin` / `AWS_SECRET_ACCESS_KEY=…`). EU org → the provider defaults to `api.getport.io`,
  which routes catalog ops cross-region; adjust `base_url` in `main.tf` only if auth fails.

## The action path (cross-reference)

Clicking a Port self-service **action** to do something in the cluster is a different mechanism (the port-agent
polling relay → an in-cluster receiver). The full gotcha chain (POLLING not KAFKA, EU `api.port.io`, **Organization**
creds not Personal for run-claiming, the templated action `body`) is documented in
**[port-agent-easy-button.md](port-agent-easy-button.md)**. Note the split: the **tofu provider** uses Personal
creds; the **port-agent** must use **Organization** creds (Personal 403 on `/v1/actions/runs/claim-pending`).

## Gotchas

- **No inbound = no cloud scraper.** Don't expect a Port managed k8s integration to populate the catalog; it's
  MCP + tofu + tool-pushed webhooks. ([[lan-no-github-webhooks]] is the same wall.)
- **Blueprints codified, entities not.** Editing entity data via tofu re-introduces the sync friction B60 removed —
  keep entities in MCP/Port, keep only schema in `tofu/port/`.
- **The setup-wizard "3 of 4" nag is unfixable** for a self-hosted LAN lab (it wants SaaS connectors) — dismiss the ✕.

## Links
- [port-agent-easy-button.md](port-agent-easy-button.md) · [opentofu.md](opentofu.md) ·
  [[port-catalog-docs-b59]] · [[opentofu-iac-gotchas]] · [[port-agent-lan-gotchas]] · [[feedback-agent-act-lanes]] ·
  [code-quality.md](code-quality.md) · [glitchtip.md](glitchtip.md) · [unleash.md](unleash.md) ·
  [uptime-kuma.md](uptime-kuma.md) · [woodpecker.md](woodpecker.md)
