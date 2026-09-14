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

# U13 (2026-09-13): the in-process bge query-embedder is raw ONNX Runtime now. torch (~1.2 GB CPU wheel) +
# sentence-transformers + llama-index-embeddings-huggingface are GONE — replaced by onnxruntime + tokenizers
# (~70 MB). Embeddings are byte-equivalent to the old HuggingFaceEmbedding (verified cosine 1.0 vs
# sentence-transformers), so the hydrated pgvector/Qdrant/Weaviate/Neo4j vectors need NO re-embedding.
# llama-index-core STAYS — retrievers.py wraps each backend in a BaseRetriever so the LangGraph nodes get a
# standard retriever interface (NodeWithScore/QueryBundle/TextNode); only the -embeddings-huggingface extra left.
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    psycopg2-binary \
    onnxruntime \
    tokenizers \
    qdrant-client \
    weaviate-client \
    neo4j \
    prometheus-client \
    langgraph \
    langchain \
    langchain-openai \
    llama-index-core \
    mlflow \
    langfuse

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
