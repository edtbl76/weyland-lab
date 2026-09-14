# ── builder: export the two DeBERTa classifiers → ONNX (U13). torch lives ONLY here and is thrown away. ──
# grounding.nli = cross-encoder/nli-deberta-v3-small (3-logit NLI); prompt_guard.injection =
# Llama-Prompt-Guard-2-22M (binary DeBERTa classifier). Both export cleanly with a fast tokenizer.json, so the
# runtime stage runs them on raw ONNX Runtime — no torch/transformers/sentence-transformers. (llama_guard.safety
# is a REMOTE httpx client and pii.presidio is spaCy — neither pulled torch, so both are untouched.)
FROM python:3.12-slim AS onnx-export
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir "optimum[onnxruntime]" transformers sentencepiece
RUN python -c "from optimum.onnxruntime import ORTModelForSequenceClassification as M; from transformers import AutoTokenizer as T; \
[(M.from_pretrained(n, export=True).save_pretrained(d), T.from_pretrained(n).save_pretrained(d)) \
 for n, d in [('cross-encoder/nli-deberta-v3-small', '/export/nli_onnx'), \
              ('project-free-llama/Llama-Prompt-Guard-2-22M', '/export/prompt_guard_onnx')]]"

# ── runtime ──────────────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Slimmer than the tool-server: ONLY the guard's needs — no llama-index/qdrant/weaviate/neo4j.
# httpx is explicit (B115): the llama_guard.safety validator calls the Llama Guard classifier svc over HTTP, and its
# module-level `import httpx` runs before the per-builder try/except — a missing httpx would crash the whole builder
# (disabling ALL guards), so we declare it rather than lean on a transitive pull.
#
# U13: the two baked DeBERTa classifiers run on raw ONNX Runtime now — onnxruntime + tokenizers replace
# sentence-transformers + transformers + torch (~1.2 GB). presidio-analyzer + spacy STAY (pii.presidio is spaCy,
# not torch); Presidio does not hard-require transformers, so it installs torch-free.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    psycopg2-binary \
    prometheus-client \
    onnxruntime \
    tokenizers \
    presidio-analyzer \
    spacy

# HOME=/app keeps spaCy/Presidio caches + any onnxruntime/tokenizers cache under the workdir the non-root user owns.
ENV HOME=/app

# Presidio's spaCy NLP engine (B34 → B117 pii.presidio). Baked so the runtime load is offline.
RUN python -m spacy download en_core_web_sm
# Warm Presidio so the analyzer's recognizer registry is cached and instantiating it at runtime is offline + fast.
RUN python -c "from presidio_analyzer import AnalyzerEngine; from presidio_analyzer.nlp_engine import NlpEngineProvider; AnalyzerEngine(nlp_engine=NlpEngineProvider(nlp_configuration={'nlp_engine_name':'spacy','models':[{'lang_code':'en','model_name':'en_core_web_sm'}]}).create_engine())"

# The exported ONNX classifiers (from the builder stage). onnx_runtime.py's OnnxCrossEncoder / OnnxTextClassifier
# load them from these dirs — grounding._MODEL_DIR + prompt_guard._MODEL_DIR default here (ENV makes it explicit).
COPY --from=onnx-export /export/nli_onnx /app/nli_onnx
COPY --from=onnx-export /export/prompt_guard_onnx /app/prompt_guard_onnx
ENV GROUNDING_ONNX_DIR=/app/nli_onnx \
    PROMPT_GUARD_ONNX_DIR=/app/prompt_guard_onnx

COPY app.py /app/app.py
COPY guardrails /app/guardrails

# Non-root (uid 10001, matching the tool-server). chown /app so appuser can read the baked models for the offline load.
RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
