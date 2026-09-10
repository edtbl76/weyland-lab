# Dify — evaluation & positioning (B161 Phase 1)

> Phase 1 of B161 (investigate → implement). This is the **positioning call** that gates the Phase 2
> deployment shape: *where Dify fits*, not keep/skip. Method per the reverse-engineering rule — map
> Dify's real capabilities (current open-source self-hosted edition, verified against the official docs,
> 2026-09) onto what the estate already runs, and find the actual delta.

## Verdict

**Adopt as a COMPLEMENT — the low-code LLM-app front door — deployed thin.** Dify's one genuinely new
capability is a **visual, non-code authoring canvas for LLM apps / agents / workflows**; nothing in the
estate offers that (LangGraph is code-first, n8n is a generic automation canvas that is not LLM-native,
Dagster is data orchestration). Everything *else* Dify bundles — model providers, vector/knowledge,
prompt IDE, tools, tracing, eval — overlaps a plane the estate already runs well, and Dify can be wired
to **reuse each of those planes rather than duplicate them**. So it is neither a *replace* (it replaces
nothing the estate does well) nor a *skip* (the canvas is a real gap-filler), but a **thin control plane
mounted on top of the existing AI plane**. Its cost is its own multi-container runtime, which lands
squarely against the node-capacity wall — the central Phase 2 constraint (below).

## Per-capability overlap

| Dify capability | Estate already runs | Delta | Wire-up in Phase 2 |
|---|---|---|---|
| **Visual workflow / agent builder (low-code canvas)** | LangGraph (code); n8n (generic, not LLM-native); Dagster (data) | **REAL — the reason to adopt.** A non-code LLM-app authoring surface exists nowhere else. | Dify owns this; it is the point. |
| **Model / provider management** | Bifrost + LiteLLM gateway plane ([[gateway-lane-separation]]) | Duplicate | Configure ONE OpenAI-compatible provider → **LiteLLM/Bifrost base URL**; no direct vendor keys in Dify. Caveat: embeddings/rerank/vision/tool-calling need the gateway to expose compatible endpoints (LiteLLM does). |
| **Tools / plugins** | MCP gateway + fleet (6 read-only + compositor), tool-server | Overlap — BUT Dify is an **MCP client (HTTP transport)** | Point Dify at the **MCP gateway** so its canvas uses the estate's existing tools; do not build a parallel Dify-plugin tool ecosystem. Bonus: Dify can also **publish an app AS an MCP server**, so a Dify-authored flow can become a tool the Realm/operator agents consume. |
| **RAG / knowledge / datasets** | Qdrant + Weaviate + LanceDB + bge-base(768) + the streaming indexer ([[vector-store-hydration-b1]]) | Mostly duplicate | Set `VECTOR_STORE` to an **external existing Qdrant (or Weaviate)** — never let Dify stand up a redundant 4th store. Dify still needs an embedding model → route via the gateway. Its dataset UI overlaps the hydration pipelines; use it only for canvas-local knowledge, not as the estate's ingestion path. |
| **Tracing / observability** | Langfuse (B103) + MLflow Traces + Tempo (OTel) | Duplicate (Dify's built-in is weaker) | Dify **exports to Langfuse** (documented LLMOps provider) and to **OTLP** (`ENABLE_OTEL` → Tempo). Route traces out; don't rely on Dify's built-in log view. |
| **Prompt IDE** | Bifrost prompt repo + skills; Langfuse prompt mgmt ([[prompt-federation-b103]]) | Duplicate | Additive only as the canvas's authoring surface; the Bifrost repo stays the prompt SoT. |
| **Eval** | promptfoo (B84), MLflow gateway eval, golden-set (B96) | Dify has ~none | Keep the existing eval plane; Dify does not compete here. |
| **Identity / SSO** | Keycloak (forward-auth everywhere) | **Gap** — Dify OSS has no first-class OIDC (Enterprise only) | Keycloak **forward-auth at the edge** (`dify.weyland.lab`) for LAN access control + Dify's own login for in-app identity. Single-tenant lab ⇒ acceptable; note it is not per-user SSO. |

## Recommended Phase 2 deployment shape

The heavy part is **Dify's own runtime**, not models or vectors. Reuse everything reusable; run only the
Dify-specific pieces.

- **Reuse (no new footprint):** providers → LiteLLM/Bifrost · knowledge → external Qdrant · tools → MCP
  gateway · traces → Langfuse + Tempo · (optionally) app DB → a new database on the in-cluster Postgres
  server · cache/queue → the existing Valkey/Redis.
- **Must run (Dify-specific, ~cannot reuse):** `api` · `worker` (+ `worker_beat`) · `web` · `plugin_daemon`
  · `sandbox` (code-execution security boundary — not optional if flows run code) · `ssrf_proxy`. That is
  the irreducible core even after externalizing Postgres/Redis/vector.
- **GitOps:** Argo app; mirror `langgenius/dify-*` images to `registry.weyland.lab` (pinned tags, no
  `:latest`); Istio STRICT mesh; `dify.weyland.lab` ingress + `/etc/hosts` + blackbox probe.
- **Packaging reality:** the OSS project ships **Docker-Compose**, not an official K8s/Helm chart (K8s HA
  is documented only for Enterprise). Phase 2 must either adopt a **community Helm chart** (evaluate one)
  or **hand-author manifests** from the compose topology — a real authoring cost to budget.

## Risks & the central constraint

1. **Node capacity — and it BLOCKS Phase 2 (see B134/EMA-195, re-measured 2026-08-27).** On `mother`
   **memory is now the binding constraint**: ~66.7Gi requested / ~67.4Gi 7-day peak against 72Gi
   allocatable — **~4.6Gi headroom at peak**, swapless ([[mother-ram-ceiling-hydrate-reliability]]).
   Dify's core (several always-on containers even with Postgres/Redis/vector externalized; realistically
   8–16Gi resident) **does not fit always-on** — it would blow the peak headroom. The obvious mitigation,
   **run Dify on-demand / parkable**, is exactly what **B134 deferred**: there is *no robust on-demand
   workload manager* — ceding `/spec/replicas` to an external actor (store-scaler / KEDA) was rejected on
   mechanism (Argo self-heal reverts `replicas:0`; a sleeping pod reports Synced/Healthy so the
   accidental-scale-to-zero safety net vanishes; sleep state lives only in the cluster), and KEDA was
   retired for it. So Dify can go **neither always-on (no memory) nor cleanly on-demand (no robust
   manager)** today. **Phase 2 is therefore blocked on B134** delivering an on-demand workload manager
   that doesn't require that carve-out (or otherwise freeing steady memory). This is a hard gate, not a
   preference.
2. **Gateway compatibility surface.** Embeddings, rerank, vision, tool-calling and structured output must
   each work through the OpenAI-compatible gateway, not just chat — verify per model on LiteLLM.
3. **Version-coupled vector client.** Dify pins vector-client versions (e.g. a recent release forced
   Weaviate 1.24 + v4 client); reusing the estate's Qdrant/Weaviate ties Dify upgrades to those versions.
4. **Runtime duplication is the real cost**, not models/vectors — accept that Dify adds an app/runtime
   layer (workers, sandbox, plugin daemon, its own state) in exchange for the canvas.

## Open decisions for Phase 2 (need a call before building)

> **Phase 2 is PARKED — blocked by B134 (EMA-195).** Dify has no viable footprint on `mother` today
> (can't fit always-on, and the on-demand path is what B134 has deferred pending a robust workload
> manager). These decisions are pre-staged for when B134 unblocks it; do not build Phase 2 until then.

- **On-demand vs always-on?** (recommend on-demand / store-scaler-parkable, given the node ceiling.)
- **Community Helm chart vs hand-authored manifests?** (spike a chart first; fall back to manifests.)
- **Externalize app Postgres/Redis onto the shared servers, or run Dify-local?** (recommend external to
  cut the footprint; a dedicated DB on the in-cluster Postgres.)
- **Knowledge store: Qdrant or Weaviate?** (recommend Qdrant — the estate's primary vector service.)

## Sources

Official Dify docs (self-host deploy overview, docker-compose topology, environment/configuration, MCP
publish + tools, external-ops tracing) verified 2026-09; cross-referenced against the estate's AI plane
(gateways, agents, RAG, eval, observability). See [design/golden-paths.md] neighbors under `docs/concepts/`
for the audit-doc pattern this follows ([data-platform-capabilities-audit.md](data-platform-capabilities-audit.md),
[ci-test-categories-audit.md](ci-test-categories-audit.md)).
