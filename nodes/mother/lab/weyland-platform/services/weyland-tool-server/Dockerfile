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
    neo4j \
    prometheus-client \
    llm-guard \
    sentence-transformers

# Pin the Hugging Face cache so the build-time download and the runtime load
# resolve to the same path (default would be /root/.cache/huggingface).
ENV HF_HOME=/app/.cache/huggingface

# Bake the public embedding model into the image at build time (no HF token needed).
RUN python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='BAAI/bge-small-en-v1.5')"

# Bake the B14 guardrail models so they load offline at runtime (airgap-safe), same as bge.
# PII (llm_guard Sensitive -> presidio/spaCy) is DEFERRED and intentionally NOT baked here;
# it stays out of the default chain until a future eval promotes it (see roadmap).
RUN python -c "from llm_guard.input_scanners import PromptInjection; PromptInjection()"
RUN python -c "from llm_guard.output_scanners import Toxicity; Toxicity()"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/nli-deberta-v3-small')"

# Models are baked in — force offline at runtime so startup never reaches the HF hub
# (deterministic, airgap-safe). Set AFTER the build-time downloads so the build can
# still fetch the weights.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# B51 — error tracking SDK (GlitchTip/Sentry). Installed AFTER the model bakes so it doesn't invalidate the
# expensive HF/guardrail download layers (this stays a fast incremental rebuild).
RUN pip install --no-cache-dir sentry-sdk

COPY main.py /app/main.py
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
