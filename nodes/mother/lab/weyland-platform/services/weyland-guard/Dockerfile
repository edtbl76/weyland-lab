FROM python:3.12-slim

WORKDIR /app

# Slimmer than the tool-server: ONLY the guard's needs — no llama-index/qdrant/weaviate/neo4j/httpx.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    psycopg2-binary \
    prometheus-client \
    llm-guard \
    sentence-transformers

# Pin all model/home caches under /app so the build-time bake (root) and runtime load (appuser) resolve to the SAME
# path, and `chown -R appuser /app` makes them readable offline. HOME=/app is the key (HF_HOME alone misses libs
# that cache to $HOME/.cache) — same fix as the tool-server image.
ENV HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache

# Bake the EXACT 3 B14 guard models the tool-server bakes, so verdicts are byte-identical whichever service scores.
# PII (llm_guard Sensitive → presidio/spaCy) stays DEFERRED and unbaked — out of the default chain (see roadmap).
RUN python -c "from llm_guard.input_scanners import PromptInjection; PromptInjection()"
RUN python -c "from llm_guard.output_scanners import Toxicity; Toxicity()"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/nli-deberta-v3-small')"

# Models baked → force offline at runtime (deterministic, airgap-safe). Set AFTER the downloads.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY app.py /app/app.py
COPY guardrails /app/guardrails

# Non-root (uid 10001, matching the tool-server). chown /app so appuser can read the baked models for the offline load.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
