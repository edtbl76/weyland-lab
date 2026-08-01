# Platform Maps

Interactive, at-a-glance maps of the Weyland R&D data & AI platform — the systems, how they fit
together, and what each layer does. Each opens full-screen; best viewed on a wide display.

!!! abstract "Platform Map"
    The application platform end-to-end: ingress and the authenticated **MCP gateway**, the agent /
    RAG stack, the shared **guardrails** service, the read-only **MCP server mesh**, model serving and
    evaluation, observability, and the governance & policy layer — every service and how a request
    flows through them.

    → **[Open the Platform Map](https://edtbl76.github.io/weyland-lab/platform-map.html)** (public)

!!! abstract "Data-Mesh Map"
    The data mesh end-to-end: storage and table formats, the **Nessie / Iceberg / Trino** lakehouse,
    the tiered stores (vector · graph · relational · columnar), the **dbt** transform and **Cube**
    semantic layers, streaming, feature and ML tiers, and the catalog / lineage / data-quality
    governance planes.

    → **[Open the Data-Mesh Map](https://edtbl76.github.io/weyland-lab/data-mesh-map.html)** (public)

!!! abstract "LLM Routing Map"
    The agentic egress plane: each **use-case alias** (`wl-coding`, `wl-rag`, …) and the **provider
    fallback chain** LiteLLM resolves it to — primary → always-on-free → paid escalation, colour-coded
    by cost tier. The transparent failover the OSS gateway couldn't give us, drawn end-to-end.

    → **[Open the LLM Routing Map](llm-routing-map.html)** — **internal only** (not published to Pages)
    &nbsp;·&nbsp; **[Copyable diagram](llm-routing.md)** — the same chains as a portable Mermaid flowchart

---

*The platform and data-mesh maps are generated from the platform's own architecture model and kept in
step with the running system. For the layered architecture diagrams and sequence flows, see the
Architecture section.*
