# C4 Component — mother VM (k3s)

Level 3: components inside the mother k3s container. See [c4-container.md](c4-container.md) for the container view.

```mermaid
C4Component
    title mother VM — k3s Components

    Container_Ext(hermes, "hermes CT", "MCP client + LiteLLM planning client")
    Container_Ext(rogueone, "rogueone", "Claude Code — MCP client")
    Container_Ext(ollama_ct, "ollama CT", "LLM inference /v1")
    Container_Ext(whisper_ct, "whisper CT", "STT /v1/audio/transcriptions")
    Container_Ext(github, "GitHub", "weyland-lab repo — RAG source")
    System_Ext(hostedmodels, "Gemini / OpenRouter", "hosted LLMs (free tiers)")
    Person_Ext(user, "Edward", "Lab operator — browser UIs")

    Container_Boundary(mother, "mother VM vm-101 (.243) — k3s, ns: weyland") {

        Component(tool_server, "weyland-tool-server", "FastAPI / Python v0.4.0", "Platform HTTP boundary. RAG retrieval (4 backends), /context/ask (RAG gen), /evals/*, /pipeline/trigger, /health, /ready, /status. Exposes /mcp system-view MCP server (fastapi-mcp, Streamable HTTP, read-only). :30080")

        Component(dagster, "Dagster", "Python / Helm", "Pipeline orchestration. RAG: weyland_ingestion_job (git-pull -> chunk -> embed -> 4-backend write), eval, catalog (6h), aidlc_kb (B37). DATASETS LAKEHOUSE (datasets_lib, B72/B75): per-dataset land -> lakeFS raw; brokered transform -> silver (parquet/arrow/avro/lance) + Iceberg gold; asset-check quality gate; build_store_load_assets hydrates Tier-2 stores (MySQL/Timescale/Mongo/Cockroach/Cassandra/ClickHouse/OpenSearch done; ClickHouse via native s3() from lakeFS). dagster.weyland.lab")

        Component(litellm, "LiteLLM", "LiteLLM / k8s", "Hosted-model gateway. Gemini + OpenRouter (wildcard) behind OpenAI /v1. Off-box cut-off valve + spend alerts. mother:30400, litellm.weyland.lab")

        Component(open_webui, "Open WebUI", "Docker / k8s", "Browser voice/chat UI. chat -> Ollama, STT -> whisper shim. chat.weyland.lab")

        Component(n8n, "n8n", "Node.js / k8s", "Workflow automation. Ingestion role retired (-> Dagster). Retained for other automation. n8n.weyland.lab")

        Component(pgvector, "Postgres / pgvector", "PostgreSQL + pgvector", "Primary RAG store: rag_documents + rag_chunks (384-dim bge vectors). Eval tables: eval_runs/questions/results/scores + eval_leaderboard. model_catalog (hosted-model lookup, 6h). In-cluster only :5432")

        Component(qdrant, "Qdrant", "Qdrant", "Vector store. Collection: weyland_chunks. :30083 (HTTP) :30084 (gRPC)")

        Component(weaviate, "Weaviate", "Weaviate", "Vector store. Class: WeylandChunk. :30087")

        Component(neo4j, "Neo4j", "Neo4j + APOC", "Graph + vector index. GraphRAG: Document/Chunk nodes, BELONGS_TO + NEXT edges; B37 AIDLC :Entry graph (RELATED_TO/SURFACES_AT/TAGGED/IN_VERTICAL from frontmatter). GDS plugin (PageRank/Louvain). :30085 (HTTP) :30086 (Bolt)")

        Component(minio, "MinIO", "MinIO", "S3-compatible object storage. 8TB USB passthrough. s3.weyland.lab (API) files.weyland.lab (Filestash UI)")

        Component(prometheus, "Prometheus + Grafana", "kube-prometheus-stack", "Observability: cluster/node/pod dashboards, ServiceMonitors (Qdrant/Weaviate/APISIX/CoreDNS), Alertmanager -> Telegram. grafana.weyland.lab")

        Component(traefik, "Traefik", "k3s built-in ingress", "TLS termination for *.weyland.lab. mkcert wildcard cert.")

        Component(coredns, "CoreDNS", "CoreDNS", "LAN DNS. *.weyland.lab wildcard -> mother (Traefik). CT-specific zones: ollama.weyland.lab -> .244, whisper.weyland.lab -> .246. :53")

        Component(apisix, "APISIX", "APISIX / etcd", "Active API/data-plane gateway. Routes front tool-server /context + /pipeline and the qdrant/weaviate/neo4j backends. :30090 (data plane) apisix.weyland.lab (dashboard, Keycloak SSO)")

        Component(headlamp, "Headlamp", "React / k8s", "Kubernetes UI. Permanent cluster-admin SA token. headlamp.weyland.lab")

        Component(neodash, "NeoDash", "neo4jlabs/neodash / k8s", "Neo4j dashboard/viz UI (free Bloom-alternative). Browser-side Bolt to Neo4j. mother:30088")

        Component(docs_site, "Platform Docs (B59)", "MkDocs Material / nginx / k8s", "Standalone docs site — runbooks/architecture/concepts; browsable + searchable + Mermaid. initContainer builds from the repo, nginx serves. Replaced the retired Backstage IDP/TechDocs. docs.weyland.lab")
        Component(mlflow, "MLflow (B10+B16)", "MLflow / k8s", "Experiment tracking + model registry. Postgres backend store + MinIO artifact store (proxied via --serve-artifacts). Meshed (STRICT Postgres). Keycloak SSO (forward-auth). mlflow.weyland.lab")
    }

    Container_Boundary(istiosystem, "mother VM — k3s, ns: istio-system (Istio service mesh, B8)") {

        Component(istiod, "istiod", "Istio 1.30 / minimal profile", "Mesh control plane. Per-pod sidecar injection (LABEL sidecar.istio.io/inject). Meshed: tool-server + 4 backends + Dagster, PERMISSIVE mTLS; Postgres STRICT.")

        Component(kiali, "Kiali", "Kiali / k8s", "Mesh observability UI: topology graph, mTLS lock status, traces (Tempo). Read-only + RBAC-tightened. Keycloak SSO (forward-auth). kiali.weyland.lab")
    }

    Container_Boundary(datamesh, "mother VM — k3s, ns: data-mesh (B1.2 storage + B65 Tier-2 stores)") {

        Component(nessie, "Nessie", "Nessie / k8s", "Iceberg catalog + git-branch table versioning. Postgres version store, MinIO warehouse, Iceberg REST /iceberg. Meshed (STRICT Postgres). Keycloak SSO (forward-auth). nessie.weyland.lab :19120")

        Component(lakefs, "lakeFS", "lakeFS / k8s", "Git-style versioning for file/dataset products. The datasets lakehouse writes silver THROUGH its S3 gateway (versioned, per-run commits). Postgres metadata + MinIO blockstore. lakefs.weyland.lab :8000")

        Component(trino, "Trino", "Trino / k8s", "Federation query engine — iceberg (native Nessie) + postgresql catalogs. Superset/dbt ride on it. trino.weyland.lab")

        Component(gizmosql, "GizmoSQL (DuckDB)", "Arrow Flight SQL / k8s", "DuckDB served over Flight SQL; PERSISTED tables materialised from lakeFS Parquet (schema-per-domain). mother:31337")

        Component(superset, "Superset", "Superset / k8s", "BI/SQL exploration over Trino + Postgres + TimescaleDB + ClickHouse. superset.weyland.lab")

        Component(timescaledb, "TimescaleDB", "TimescaleDB / k8s", "Time-series hypertables (operational metrics + who_gho dataset series); Dagster feed. lastfm skipped (no per-listen timestamps). :5432")

        Component(mysql, "MySQL", "MySQL 8.4 / k8s", "Health datasets — 6 DBs / 32 tables, hydrated from silver Parquet by datasets_health_mysql_load. :3306")

        Component(tier2, "Tier-2 dataset stores", "k8s (data-mesh + opensearch ns)", "Hydrated from silver Parquet by build_store_load_assets: MongoDB (docs) · CockroachDB (distributed SQL) · Cassandra (wide-column) · ClickHouse (columnar OLAP, native s3() ingest) · OpenSearch (search, ns opensearch) · MusicBrainz-Postgres (full native mbdump). Valkey = shared cache.")

        Component(datahub, "DataHub", "DataHub / k8s", "Metadata catalog + lineage. Native ingestion sources (Mongo/Cockroach/ClickHouse/Cassandra/MusicBrainz) + custom emitters (MySQL/Timescale/DuckDB/OpenSearch) via the 6h catalog job. OpenSearch + Kafka backend.")

        Component(portaction, "Port actions → cluster", "port-agent (ns port-agent) + store-scaler", "Port self-service action → outbound-polling port-agent → in-cluster store-scaler → k8s deployments/scale (wake/sleep the idle data stores).")
    }

    Rel(hermes, tool_server, "MCP /mcp — status, context_search, context_ask, list_models")
    Rel(rogueone, tool_server, "MCP /mcp (Claude Code)")
    Rel(user, open_webui, "browser voice/chat")
    Rel(user, dagster, "pipeline UI")
    Rel(user, prometheus, "observability dashboards")
    Rel(user, headlamp, "k8s management")
    Rel(user, neodash, "graph dashboards / viz")
    Rel(neodash, neo4j, "Bolt :30086 (browser-side)")
    Rel(user, docs_site, "browse platform docs")
    Rel(user, mlflow, "experiments + model registry UI")
    Rel(mlflow, pgvector, "backend store: runs/params/metrics (mTLS, STRICT)")
    Rel(mlflow, minio, "artifact store (S3, mlflow bucket)")
    Rel(tool_server, pgvector, "embed + retrieve rag_chunks (mTLS, STRICT)")
    Rel(tool_server, qdrant, "retrieve (mTLS)")
    Rel(tool_server, weaviate, "retrieve (mTLS)")
    Rel(tool_server, neo4j, "retrieve (mTLS)")
    Rel(tool_server, ollama_ct, "RAG generate + eval judge /v1")
    Rel(tool_server, dagster, "POST /pipeline/trigger launchRun")
    Rel(dagster, github, "git-pull docs/ + nodes/ (B25b — replaced Obsidian SSH)")
    Rel(dagster, hostedmodels, "model_catalog: fetch OpenRouter/Gemini model lists")
    Rel(dagster, pgvector, "write rag_documents + rag_chunks + model_catalog (mTLS, STRICT)")
    Rel(dagster, qdrant, "write weyland_chunks (mTLS)")
    Rel(dagster, weaviate, "write WeylandChunk (mTLS)")
    Rel(dagster, neo4j, "write nodes + edges (mTLS)")
    Rel(dagster, minio, "publish TechDocs site, hourly (B41 -> techdocs bucket)")
    Rel(dagster, ollama_ct, "eval: generate questions + judge responses")
    Rel(open_webui, ollama_ct, "chat completions /v1")
    Rel(open_webui, whisper_ct, "STT /v1/audio/transcriptions")
    Rel(prometheus, tool_server, "scrape /metrics + ServiceMonitors")
    Rel(prometheus, litellm, "scrape /metrics (request/spend)")
    Rel(hermes, litellm, "planning turns /v1 (Gemini-free)")
    Rel(litellm, hostedmodels, "egress: Gemini / OpenRouter")
    Rel(coredns, traefik, "*.weyland.lab wildcard resolution")
    Rel(apisix, tool_server, "API/data-plane gateway routes: /context, /pipeline")
    Rel(apisix, qdrant, "gateway route")
    Rel(apisix, weaviate, "gateway route")
    Rel(apisix, neo4j, "gateway route")
    Rel(user, kiali, "mesh graph + mTLS status (Keycloak SSO)")
    Rel(istiod, tool_server, "injects + configures Envoy sidecars")
    Rel(kiali, prometheus, "Envoy mesh metrics (consolidated onto kube-prometheus-stack)")
    Rel(prometheus, tool_server, "scrape Envoy /stats (PodMonitor)")
    Rel(user, nessie, "Iceberg catalog UI (Keycloak SSO)")
    Rel(user, lakefs, "file/dataset versioning UI (Keycloak SSO)")
    Rel(nessie, pgvector, "version store (mTLS, STRICT)")
    Rel(nessie, minio, "Iceberg warehouse s3://warehouse")
    Rel(lakefs, pgvector, "metadata (mTLS, STRICT)")
    Rel(lakefs, minio, "blockstore s3://lakefs")
    Rel(dagster, lakefs, "datasets: write silver (parquet/arrow/avro/lance) + commit, via S3 gateway")
    Rel(dagster, nessie, "datasets: hydrate Iceberg gold (per-file tables)")
    Rel(dagster, mysql, "hydrate health datasets: silver Parquet -> tables")
    Rel(dagster, timescaledb, "weyland_timeseries_job -> hypertables (hourly)")
    Rel(superset, trino, "primary query engine")
    Rel(trino, nessie, "iceberg catalog (native Nessie)")
    Rel(gizmosql, lakefs, "materialises tables from the lakeFS Parquet")
    Rel(dagster, tier2, "hydrate Tier-2 stores: silver Parquet -> store (ClickHouse via native s3)")
    Rel(dagster, datahub, "catalog emit (6h) + native ingestion sources")
    Rel(superset, tier2, "ClickHouse OLAP queries")
```
