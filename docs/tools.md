# Tools

The launchpad for every running tool in the lab. All `*.weyland.lab` UIs are **LAN-only** and sit
behind **Keycloak SSO** (OIDC or forward-auth) — sign in once, then click through. This page is the hub
the rest of the documentation mesh points at: a DataHub dataset links to its runbook, and the runbook (or
this page) links to the live tool.

!!! note "Reverse of the catalog links"
    In DataHub, a dataset's **Links** sidebar points *out* to its runbook here. This page closes the loop
    by pointing *back* to the tools. Retired tools (Backstage/IDP, Jaeger) are intentionally omitted.

## Catalog & Governance

| Tool | Link | What it's for |
|---|---|---|
| **DataHub** | <https://datahub.weyland.lab> | Metadata catalog — datasets, lineage, glossary, domains, data products, structured properties |
| **LikeC4** | <https://likec4.weyland.lab> | Interactive architecture (C4) explorer — pan/zoom/drill the whole platform model (B64) |
| **Ranger** | <https://ranger.weyland.lab> | Data-plane authz — Trino column/row masking, tag policies, access audit |
| **Gatekeeper Policy Manager** | <https://gatekeeper.weyland.lab> | Control-plane authz — OPA/Gatekeeper constraints + per-resource violation report |
| **Port** | <https://app.port.io> | Internal Developer Platform / catalog + self-service actions (SaaS, EU org) |
| **Keycloak** | <https://keycloak.weyland.lab> | Central IdP / SSO admin (the `weyland` realm behind every UI) |

## BI & Analytics

| Tool | Link | What it's for |
|---|---|---|
| **Superset** | <https://superset.weyland.lab> | BI + ad-hoc SQL exploration over Trino + the Postgres DBs |
| **Lightdash** | <https://lightdash.weyland.lab> | dbt-native BI over the marts (metrics-as-code) |
| **dbt Docs** | <https://dbt-docs.weyland.lab> | dbt model DAG, lineage, and test results |

## Data Mesh — Query & Streaming

| Tool | Link | What it's for |
|---|---|---|
| **Trino** | <https://trino.weyland.lab> | Federation query engine (`iceberg` + `postgresql` catalogs); query via CLI/IntelliJ/Superset |
| **GizmoSQL** | <https://gizmosql.weyland.lab> | DuckDB Flight SQL — single-node OLAP over persisted silver tables |
| **ClickHouse** | <https://clickhouse.weyland.lab> | Columnar OLAP (`/play` UI) |
| **CockroachDB** | <https://cockroachdb.weyland.lab> | Distributed SQL admin UI |
| **Redpanda Console** | <https://redpanda.weyland.lab> | Kafka-wire streaming + schema registry browser |
| **OpenSearch** | <https://opensearch.weyland.lab> | Search index / playground |

## Data Mesh — Storage, Versioning & Registry

| Tool | Link | What it's for |
|---|---|---|
| **MinIO Console** | <https://minio.weyland.lab> | Object storage console (buckets, browse) |
| **MinIO S3 API** | <https://s3.weyland.lab> | S3 endpoint for clients |
| **Nessie** | <https://nessie.weyland.lab> | Iceberg catalog + table (branch/commit) versioning |
| **lakeFS** | <https://lakefs.weyland.lab> | Data/file versioning (git-for-data) |
| **Container Registry** | <https://registry.weyland.lab> | MinIO-backed OCI image registry |
| **Registry UI** | <https://registry-ui.weyland.lab> | Registry browser |

## Data Mesh — Feature & Vector Stores

| Tool | Link | What it's for |
|---|---|---|
| **Feast (REST)** | <https://feast.weyland.lab> | Feature store — online features by entity key (`/docs` Swagger) |
| **Feast UI** | <https://feast-ui.weyland.lab> | Feature registry browser |
| **LanceDB Viewer** | <https://lancedb.weyland.lab> | Embedded vector store browser |

## Orchestration, Training & Automation

| Tool | Link | What it's for |
|---|---|---|
| **Dagster** | <https://dagster.weyland.lab> | Pipeline orchestration (assets, jobs, schedules, sensors) |
| **Ray** | <https://ray.weyland.lab> | Persistent training / HP-sweep cluster |
| **MLflow** | <https://mlflow.weyland.lab> | Experiment tracking + model registry |
| **n8n** | <https://n8n.weyland.lab> | Workflow automation |

## Models & AI

| Tool | Link | What it's for |
|---|---|---|
| **OpenWebUI (Chat)** | <https://chat.weyland.lab> | LLM chat front end |
| **LiteLLM** | <https://litellm.weyland.lab> | Model gateway (unified LLM API) |
| **Ollama** | <https://ollama.weyland.lab> | Local model serving API |
| **Whisper** | <https://whisper.weyland.lab> | Speech-to-text transcription API |

## Observability & Cost

| Tool | Link | What it's for |
|---|---|---|
| **Grafana** | <https://grafana.weyland.lab> | LGTM dashboards — metrics, logs, traces |
| **Uptime Kuma** | <https://kuma.weyland.lab> | Uptime status board (Telegram paging) |
| **GlitchTip** | <https://glitchtip.weyland.lab> | Error tracking (Sentry-compatible) |
| **OpenCost** | <https://opencost.weyland.lab> | Kubernetes cost allocation |
| **Kiali** | <https://kiali.weyland.lab> | Istio service-mesh topology |

## Platform, CI/CD & Files

| Tool | Link | What it's for |
|---|---|---|
| **Argo CD** | <https://argocd.weyland.lab> | GitOps CD for the k8s layer |
| **Woodpecker CI** | <https://woodpecker.weyland.lab> | CI pipelines |
| **SonarQube** | <https://sonarqube.weyland.lab> | Code quality + SAST (part of the weekly scan-suite → Port Code Health) |
| **Unleash** | <https://unleash.weyland.lab> | Feature flags |
| **Headlamp** | <https://headlamp.weyland.lab> | Kubernetes UI |
| **APISIX** | <https://apisix.weyland.lab> | API gateway dashboard |
| **Filestash** | <https://files.weyland.lab> | File browser |
