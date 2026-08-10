FROM python:3.12-slim

WORKDIR /app

# B111 Option C: PIN the MCP stack. Unpinned installs let a rebuild pull starlette 1.x under the
# old fastapi-mcp 0.4.0, whose streamable-HTTP mount hangs (request.body() → ClientDisconnect) —
# that drift is what broke /mcp. FastMCP 3.x (mcp 1.28-native) replaces fastapi-mcp; the whole set
# is pinned to the versions validated 2026-07-31 so it can't silently drift again.
RUN pip install --no-cache-dir \
    'fastapi==0.139.2' \
    'starlette==1.3.1' \
    'uvicorn==0.51.0' \
    'fastmcp==3.4.5' \
    'mcp==1.28.1' \
    psycopg2-binary \
    httpx \
    llama-index-embeddings-huggingface \
    qdrant-client \
    weaviate-client \
    neo4j \
    prometheus-client \
    sentence-transformers \
    mlflow-skinny \
    langfuse \
    'opentelemetry-sdk==1.44.0' \
    'opentelemetry-exporter-otlp-proto-http==1.44.0' \
    'opentelemetry-instrumentation-fastapi==0.65b0' \
    'opentelemetry-instrumentation-httpx==0.65b0'
# B70 Part 2: `llm-guard` removed — the injection/toxicity/grounding validators (and their models) live in the
# shared weyland-guard service now; this image only POSTs to it over the already-present httpx. sentence-transformers
# stays (llama-index-embeddings-huggingface needs it for the bge query-embedding).

# Pin ALL model/home caches under /app so (a) the build-time bake (as root) and the runtime load (as appuser,
# B47) resolve to the SAME path, and (b) the `chown -R appuser /app` below makes every cached file readable by the
# non-root user. HOME=/app is the key: HF_HOME alone doesn't override libs that cache to $HOME/.cache, and that
# mismatch (root baked to /root/.cache; appuser looked in /home/appuser/.cache) crash-looped the non-root pod
# with "couldn't find them in the cached files" under HF_HUB_OFFLINE.
ENV HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache

# Bake the public embedding model into the image at build time (no HF token needed).
RUN python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='BAAI/bge-base-en-v1.5')"

# B70 Part 2: the guard-model bakes (PromptInjection / Toxicity / nli-deberta-v3-small) moved to the weyland-guard
# image — the tool-server no longer loads them, so its pod is lighter. Only bge (above) is baked here now.

# Models are baked in — force offline at runtime so startup never reaches the HF hub
# (deterministic, airgap-safe). Set AFTER the build-time downloads so the build can
# still fetch the weights.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# B51 — error tracking SDK (GlitchTip/Sentry). Installed AFTER the model bakes so it doesn't invalidate the
# expensive HF/guardrail download layers (this stays a fast incremental rebuild).
RUN pip install --no-cache-dir sentry-sdk

COPY main.py /app/main.py
COPY prompts.py /app/prompts.py
COPY guardrails /app/guardrails

# B47: run as non-root. The HF/guardrail models were baked to /app/.cache as root above; chown /app so appuser can
# read them for the offline load (HF_HUB_OFFLINE=1) and own the workdir. Port 8080 is unprivileged.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

# Runtime config (DB / backend / Dagster URLs + secrets) is supplied by the k8s
# deployment env — see k8s/weyland-tool-server.yaml, the single source of truth.
# main.py keeps in-cluster DNS defaults so the image still runs standalone for dev.
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
