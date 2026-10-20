# ── builder: export bge-base-en-v1.5 → ONNX (U13). torch lives ONLY here and is thrown away. ──
# We export the model once (transformer graph → model.onnx) + save its tokenizer.json, then the runtime
# stage below runs it on raw ONNX Runtime — no torch/transformers/sentence-transformers at runtime.
FROM python:3.12-slim AS bge-export
# 2026-10-16: pinned (requirements-bge-export.txt, today's resolution; torch from the PyTorch CPU index).
COPY requirements-bge-export.txt /tmp/requirements-bge-export.txt
RUN pip install --no-cache-dir -r /tmp/requirements-bge-export.txt
# B216: export at the PINNED Hugging Face commits in onnx_models.json, then prove the export reproduces the deployed
# model's recorded output (a mismatch fails this build, naming the model). onnx_export.py is byte-identical to
# scripts/onnx_export.py (scripts/tests/onnx-export.bats). Runbook: docs/runbooks/onnx-models.md.
COPY onnx_export.py onnx_models.json /tmp/onnx/
ARG ONNX_EXPORT_RECORD=
RUN python /tmp/onnx/onnx_export.py build /tmp/onnx/onnx_models.json

# ── runtime ──────────────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

# U13 (2026-09-13): the in-process bge query-embedder is raw ONNX Runtime now. torch (~1.2 GB CPU wheel) +
# sentence-transformers + llama-index-embeddings-huggingface are GONE — replaced by onnxruntime + tokenizers
# (~70 MB). Embeddings are byte-equivalent to the old HuggingFaceEmbedding (verified cosine 1.0 vs
# sentence-transformers), so the hydrated pgvector/Qdrant/Weaviate/Neo4j vectors need NO re-embedding.
# llama-index-core STAYS — retrievers.py wraps each backend in a BaseRetriever so the LangGraph nodes get a
# standard retriever interface (NodeWithScore/QueryBundle/TextNode); only the -embeddings-huggingface extra left.
# 2026-10-16: pinned. requirements.txt is v8's full frozen runtime set (four packages raised past advisories).
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# The exported ONNX model + tokenizer.json (from the builder stage). retrievers.py's OnnxBge loads them from
# BGE_ONNX_DIR. HOME=/app keeps any onnxruntime/tokenizers cache under the workdir the non-root user owns.
COPY --from=bge-export /export/bge_onnx /app/bge_onnx
ENV HOME=/app \
    BGE_ONNX_DIR=/app/bge_onnx

COPY retrievers.py graph.py guard.py prompts.py app.py /app/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
