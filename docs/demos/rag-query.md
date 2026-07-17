# Demo — RAG Query / Retrieval

The tool-server exposes retrieval over the lab's retrieval backends: `/context/search` returns the
top-k chunks from one backend; `/context/ask` runs the full RAG loop (embed → vector/graph search →
local Ollama synthesizes a grounded answer). The valid backends are **`pgvector`**, **`qdrant`**,
**`weaviate`** (vector), and **`neo4j`** (graph). This is a read-only flow — it creates no data.

> **Chain:** prev ← [rag-stream.md](rag-stream.md) (indexes what this retrieves). Full arc: [rag-e2e.md](rag-e2e.md).

## Sequence diagram

Reuse the existing diagram: **[../diagrams/flow-rag-query.md](../diagrams/flow-rag-query.md)**
(client → tool-server `/context/ask` → bge embedding → vector backend → Ollama `/v1` → grounded
answer + sources).

## Prerequisites

- `mother` — hosts the tool-server (`http://mother:30080`, NodePort) and the pgvector / Qdrant /
  Weaviate / Neo4j backends.
- `rogueone` — serves Ollama (`http://ollama.weyland.lab:11434`, `192.168.1.230:11434`) that
  synthesizes the answer for `/context/ask`.
- Retrieval stores populated (the RAG corpus — `weyland_chunks` / `WeylandChunk`, etc.).
- Login for browser UIs: `emangini` / `weyland_dev_password`.

## UI walkthrough

The retrieval API is a code/agent surface, not a Traefik-fronted browser UI, so drive it from the
tool-server's built-in OpenAPI page:

1. Open `http://mother:30080/docs` (FastAPI Swagger UI).
2. Expand **POST `/context/search`**, click **Try it out**. Set the `backend` query param to
   `pgvector` (or `qdrant` / `weaviate` / `neo4j`) and a body like
   `{"query": "How does the mesh enforce mTLS?", "limit": 5}`. **Execute** → the response is the
   top-k chunks.
3. Expand **POST `/context/ask`**, **Try it out**, body
   `{"query": "How does the mesh enforce mTLS?", "backend": "pgvector"}` (optionally a `model`).
   **Execute** → `{answer, model, sources}`.
4. Optionally inspect the graph backend visually at NeoDash (`http://mother:30088`, connect to Bolt
   `neo4j://mother:30086`).

## CLI walkthrough

Top-k retrieval only (swap `backend=` for `qdrant` / `weaviate` / `neo4j`):

[mother] `curl -s -X POST "http://mother:30080/context/search?backend=pgvector" -H 'Content-Type: application/json' -d '{"query":"How does the mesh enforce mTLS?","limit":5}'`

Full RAG answer (retrieve → local LLM synthesize):

[mother] `curl -s -X POST http://mother:30080/context/ask -H 'Content-Type: application/json' -d '{"query":"How does the mesh enforce mTLS?","backend":"pgvector"}'`

Pick a specific Ollama model for the answer (list selectable models first):

[mother] `curl -s http://mother:30080/models`

[mother] `curl -s -X POST http://mother:30080/context/ask -H 'Content-Type: application/json' -d '{"query":"How does the mesh enforce mTLS?","backend":"qdrant","model":"llama3.1:8b"}'`

Check a backend's health before querying (per-backend endpoints):

[mother] `curl -s http://mother:30080/qdrant/health`

> Model names for the `model` field come from the live `/models` list — the `llama3.1:8b` above is
> illustrative; use whatever `/models` returns (`TODO: verify` exact tags on the box).

## Expected result

- `/context/search` returns a JSON array of the top-k chunks (text + metadata) from the chosen
  backend.
- `/context/ask` returns `{"answer": "...", "model": "...", "backend": "...", "sources": [...]}` —
  an answer grounded in the retrieved chunks, with the sources it used.
- An unknown backend returns HTTP 400 with `Valid options: ['neo4j','pgvector','qdrant','weaviate']`.

## Cleanup / teardown

**Read-only** — retrieval and RAG-answer calls query existing stores and the local model; they
create no rows, files, or catalog entries. Nothing to tear down.
