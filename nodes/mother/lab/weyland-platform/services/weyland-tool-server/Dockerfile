# ── builder: export bge-base-en-v1.5 → ONNX (U13). torch lives ONLY here and is thrown away. ──
# We export the model once (transformer graph → model.onnx) + save its tokenizer.json, then the runtime
# stage below runs it on raw ONNX Runtime — no torch/transformers/sentence-transformers at runtime.
FROM python:3.12-slim AS bge-export
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "optimum[onnxruntime]" transformers
RUN python -c "from optimum.onnxruntime import ORTModelForFeatureExtraction as M; from transformers import AutoTokenizer as T; M.from_pretrained('BAAI/bge-base-en-v1.5', export=True).save_pretrained('/export/bge_onnx'); T.from_pretrained('BAAI/bge-base-en-v1.5').save_pretrained('/export/bge_onnx')"

# ── runtime ──────────────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# B111 Option C: PIN the MCP stack. Unpinned installs let a rebuild pull starlette 1.x under the old
# fastapi-mcp 0.4.0, whose streamable-HTTP mount hangs (request.body() → ClientDisconnect) — that drift is
# what broke /mcp. FastMCP 3.x (mcp 1.28-native) replaces fastapi-mcp; the set is pinned to the versions
# validated 2026-07-31 so it can't silently drift again.
#
# U13 (2026-09-13): the bge query-embedder is raw ONNX Runtime now. torch (~1.2 GB CPU wheel) +
# sentence-transformers + llama-index-embeddings-huggingface are GONE — replaced by onnxruntime + tokenizers
# (~70 MB). Embeddings are byte-equivalent to the old HuggingFaceEmbedding (verified cosine 1.0 vs
# sentence-transformers), so the hydrated Qdrant/Weaviate/Neo4j vectors need NO re-embedding.
RUN pip install --no-cache-dir \
    'fastapi==0.139.2' \
    'starlette==1.3.1' \
    'uvicorn==0.51.0' \
    'fastmcp==3.4.5' \
    'mcp==1.28.1' \
    psycopg2-binary \
    httpx \
    onnxruntime \
    tokenizers \
    qdrant-client \
    weaviate-client \
    neo4j \
    prometheus-client \
    mlflow-skinny \
    langfuse \
    'opentelemetry-sdk==1.44.0' \
    'opentelemetry-exporter-otlp-proto-http==1.44.0' \
    'opentelemetry-instrumentation-fastapi==0.65b0' \
    'opentelemetry-instrumentation-httpx==0.65b0' \
    sentry-sdk

# The exported ONNX model + tokenizer.json (from the builder stage). main.py's OnnxBge loads them from
# BGE_ONNX_DIR. HOME=/app keeps any onnxruntime/tokenizers cache under the workdir the non-root user owns.
COPY --from=bge-export /export/bge_onnx /app/bge_onnx
ENV HOME=/app \
    BGE_ONNX_DIR=/app/bge_onnx

COPY main.py /app/main.py
COPY prompts.py /app/prompts.py
COPY guardrails /app/guardrails

# B47: run as non-root; chown so appuser owns the workdir + can read the baked ONNX model. Port 8080 unprivileged.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

# Runtime config (DB / backend / Dagster URLs + secrets) is supplied by the k8s deployment env —
# see k8s/weyland-tool-server.yaml, the single source of truth. main.py keeps in-cluster DNS defaults.
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
