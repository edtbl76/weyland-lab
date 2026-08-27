# Agentic RAG — the `weyland-agent` service (B70 Part 3)

A self-reflective RAG loop, the sibling to the tool-server's single-shot `/context/ask`. LangGraph owns the control
flow, LlamaIndex owns retrieval, MLflow captures every step as a Trace. It's also the **LangGraph viability spike for
B66**. `agent.weyland.lab` (Keycloak forward-auth) · `weyland-agent.weyland.svc:8080` (ClusterIP).

## The loop
```
retrieve → grade → { generate | reflect → retrieve }     (bounded by max_attempts, default 2)
```
- **retrieve** — a custom LlamaIndex `BaseRetriever` for the current backend fetches top-k chunks.
- **grade** — the LLM judges (prompt-and-parse: `YES`/`NO`) whether the chunks can answer the question.
- **reflect** (only if weak and budget remains) — the LLM rewrites the query and/or picks a different backend; `attempts += 1`.
- **generate** — grounded answer from the chunks, over the shared RAG system prompt.

`POST /agent/ask {query, backend?=pgvector, max_attempts?=2}` → `{answer, sources, attempts, backend_used, backend_history}`.
A well-covered query answers in `attempts=1` (grade relevant); a weak one drives `attempts>1` (reflect fired).

## Architecture decisions (see the B70 design doc)
- **Custom LlamaIndex retrievers, not native stores.** The B-RAG-STREAM collections store chunk text under `content`
  with no `_node_content` blob, so `PGVectorStore`/`QdrantVectorStore` can't read them. `retrievers.py` wraps the
  tool-server's proven per-backend queries in 4 thin `BaseRetriever`s (pgvector/qdrant/weaviate/neo4j).
- **In-process bge query embedding** (`HuggingFaceEmbedding`, bge-base 768 as of B74) — same model the tool-server uses and the
  collections were built with. NOT rogueone's `rag-embed` (that's the *ingestion* embedder); in-process avoids a LAN
  round-trip per retrieval (the loop re-embeds on reflect) and keeps the agent self-contained.
- **Generation** = LangChain `ChatOpenAI` → Ollama `gpt-oss:20b` on rogueone (**Phase A**). **Phase B** repoints
  `OLLAMA_BASE_URL` at LiteLLM → vLLM (throughput for the multi-call loop) — a base_url swap, no code change.
- **Guards** via the shared **weyland-guard** service (INPUT on the query, OUTPUT on the answer+sources), **fail-open**.

## MLflow tracing (the headline)
`mlflow.langchain.autolog()` (LangGraph + LLM spans) + `mlflow.llama_index.autolog()` (retrieval spans) → one Trace
per `/agent/ask` in experiment **`agentic-rag`** at `mlflow.weyland.lab`. `MLFLOW_TRACKING_URI` env.
- ⚠️ **Gotcha:** `mlflow.langchain.autolog()` imports the full **`langchain`** package — `langchain-openai`/`langgraph`
  only pull `langchain-core`, so autolog silently no-ops (`No module named 'langchain'`) unless `langchain` is in the
  image. The two autologs are guarded independently so one failing can't disable the other.
- Verify a trace landed:
  `kubectl -n weyland exec deploy/weyland-agent -- python -c "import mlflow; mlflow.set_tracking_uri('http://mlflow.weyland.svc.cluster.local:5000'); from mlflow import MlflowClient; e=MlflowClient().get_experiment_by_name('agentic-rag'); print(len(mlflow.search_traces(experiment_ids=[e.experiment_id])))"`

## Build & deploy (registry flow)
- Build + push (**rogueone**): `docker build -t registry.weyland.lab/weyland-agent:vN <services/weyland-agent> && docker push registry.weyland.lab/weyland-agent:vN`
- **Registry gotcha (see B101):** the manifest PUT to the MinIO-backed registry often doesn't finalize on the first
  push → pod `ImagePullBackOff: not found`. Confirm `curl -sk https://registry.weyland.lab/v2/weyland-agent/tags/list`
  shows `vN` (watch for the `vN: digest:` line on push), then bump the tag in `k8s/weyland-agent/deployment.yaml` and
  `kubectl -n weyland rollout restart deploy/weyland-agent`.
- Manifests: `k8s/weyland-agent/{deployment,service,servicemonitor,ingress}.yaml`; Argo app in `subdir-apps.yaml`.
  **Meshed** (STRICT-mTLS pgvector + Neo4j Bolt via the existing `neo4j-bolt` DestinationRule). Memory **request kept
  low (512Mi)** — the node runs near its requested-memory ceiling; actual usage is bounded by the 2500Mi limit.

## Verify (on mother)
```
kubectl -n weyland exec deploy/weyland-agent -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/ready').read().decode())"
```
```
kubectl -n weyland exec deploy/weyland-agent -- python -c "import urllib.request,json; r=urllib.request.Request('http://localhost:8080/agent/ask',data=json.dumps({'query':'What is the weyland data mesh?','backend':'pgvector'}).encode(),headers={'Content-Type':'application/json'}); d=json.loads(urllib.request.urlopen(r,timeout=600).read()); print('attempts',d['attempts'],'backend_history',d['backend_history'],'answer_chars',len(d['answer']),'sources',len(d['sources']))"
```
A well-covered query → `attempts 1`; an off-corpus one → `attempts 2` (reflect fired). Guard verdicts tick on
weyland-guard's `/metrics`; a Trace appears in the `agentic-rag` experiment.

## Reference
Design: `../design/agentic-rag-langgraph-design.md`. Guard service: [runbooks/guardrails.md](guardrails.md).
Full MLflow exploitation (eval/prompts/AI-gateway/more integrations) → **B100**. Model gateway Phase B → B26/LiteLLM.
See [[weyland-guard-b70]].
