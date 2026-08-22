# Port.io — the IDP / software catalog (B43 / B58 / B60)

**What:** Port is the lab's internal developer portal — the **catalog** (every system, component, resource, API,
data store, and their relations), the **scorecards** (production-readiness, etc.), and the **dashboards**. It
replaced Backstage ([[port-catalog-docs-b59]]). Architecturally: **Port = the "see" layer** (catalog, scorecards,
observability); **Hermes = the "do" layer** (acts on the cluster via its tool-server, [[feedback-agent-act-lanes]]).
The *action* execution path (clicking a Port button to change the cluster) is separate — see
[port-agent-easy-button.md](port-agent-easy-button.md).

**Where:**
- UI: **https://app.port.io** (SaaS, EU org `org_KyCTEN4PVUv1D3TM`). Not a `*.weyland.lab` host — Port is cloud.
- Blueprints as code: `tofu/port/` (`catalog.tf`, `blueprints.tf`, `cost.tf`, `actions.tf`) — OpenTofu, state in
  MinIO. See [opentofu.md](opentofu.md).
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
