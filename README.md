# Weyland

A self-hosted, $0-budget, single-operator **AI homelab** — Minisforum MS-A2 bare-metal → Proxmox → k3s → a full RAG + agent + observability platform, managed as code.

## What's here

- **`nodes/<name>/`** — each node is a system deployed *onto* the lab (see [docs/arch.md](docs/arch.md)).
- **`nodes/mother/lab/weyland-platform/`** — the core k3s platform: the MCP tool-server, four vector backends (pgvector / Qdrant / Weaviate / Neo4j), Dagster pipelines, the LiteLLM model gateway, an Istio service mesh, the full LGTM observability stack, **Argo CD** (GitOps), **OpenTofu** (non-k8s IaC), and the **Port.io** IDP catalog.
- **`docs/`** — architecture, runbooks, API + host inventories, and the ordered roadmap. Browse it rendered at **[docs.weyland.lab](https://docs.weyland.lab)**.

## Operating model

- **Deploy = push to git.** The k8s layer reconciles via **Argo CD**; non-k8s infra (Port, Proxmox, GitHub) is **OpenTofu**.
- **LAN-only**, self-hosted over SaaS, free tiers + owned hardware. It's a lab for **learning and experimentation**, not production — high latency tolerance, deliberately over-built in places.

## Docs

| Topic | Where |
|---|---|
| Architecture + C4 diagrams | [docs/arch.md](docs/arch.md) |
| Host inventory | [docs/hosts.md](docs/hosts.md) |
| Endpoints | [docs/api.md](docs/api.md) |
| Runbooks | [docs/runbooks/](docs/runbooks/) |
| Roadmap (ordered source of truth) | [docs/backlog.md](docs/backlog.md) |
