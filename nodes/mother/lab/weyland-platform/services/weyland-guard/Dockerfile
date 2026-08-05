FROM python:3.12-slim

WORKDIR /app

# Slimmer than the tool-server: ONLY the guard's needs — no llama-index/qdrant/weaviate/neo4j.
# httpx is explicit (B115): the llama_guard.safety validator calls the Llama Guard classifier svc over HTTP, and its
# module-level `import httpx` runs before the per-builder try/except — a missing httpx would crash the whole builder
# (disabling ALL guards), so we declare it rather than lean on a transitive pull.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    psycopg2-binary \
    prometheus-client \
    sentence-transformers \
    transformers \
    presidio-analyzer \
    spacy

# Pin all model/home caches under /app so the build-time bake (root) and runtime load (appuser) resolve to the SAME
# path, and `chown -R appuser /app` makes them readable offline. HOME=/app is the key (HF_HOME alone misses libs
# that cache to $HOME/.cache) — same fix as the tool-server image.
ENV HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache

# Bake the guard models so verdicts are byte-identical whichever service scores, and the runtime load is offline.
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/nli-deberta-v3-small')"  # grounding.nli (B35)
RUN python -m spacy download en_core_web_sm   # Presidio NLP engine (B34 → B117 pii.presidio)
# B117: bake Llama Prompt Guard 2 (in-process injection classifier — replaced llm_guard.injection) + warm Presidio so
# the analyzer's recognizer registry is cached and instantiating it at runtime is offline + fast.
RUN python -c "from transformers import pipeline; pipeline('text-classification', model='project-free-llama/Llama-Prompt-Guard-2-22M', top_k=None, truncation=True)"
RUN python -c "from presidio_analyzer import AnalyzerEngine; from presidio_analyzer.nlp_engine import NlpEngineProvider; AnalyzerEngine(nlp_engine=NlpEngineProvider(nlp_configuration={'nlp_engine_name':'spacy','models':[{'lang_code':'en','model_name':'en_core_web_sm'}]}).create_engine())"

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
