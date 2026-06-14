FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    fastapi-mcp \
    uvicorn \
    psycopg2-binary \
    httpx \
    llama-index-embeddings-huggingface \
    qdrant-client \
    weaviate-client \
    neo4j

# Pin the Hugging Face cache so the build-time download and the runtime load
# resolve to the same path (default would be /root/.cache/huggingface).
ENV HF_HOME=/app/.cache/huggingface

# Bake the public embedding model into the image at build time (no HF token needed).
RUN python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# Model is baked in — force offline at runtime so startup never reaches the HF hub
# (deterministic, airgap-safe). Set AFTER the build-time download so the build can
# still fetch the weights.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY main.py /app/main.py

# Runtime config (DB / backend / Dagster URLs + secrets) is supplied by the k8s
# deployment env — see k8s/weyland-tool-server.yaml, the single source of truth.
# main.py keeps in-cluster DNS defaults so the image still runs standalone for dev.
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
