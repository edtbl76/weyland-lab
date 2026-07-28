FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx \
    psycopg2-binary \
    qdrant-client \
    weaviate-client \
    neo4j \
    prometheus-client \
    langgraph \
    langchain \
    langchain-openai \
    llama-index-core \
    llama-index-embeddings-huggingface \
    mlflow

# In-process bge query embedding (same model + path convention as the tool-server; torch layer dedupes against it in
# the registry). Pin caches under /app so the build-time bake (root) and runtime load (appuser) resolve identically.
ENV HOME=/app \
    HF_HOME=/app/.cache/huggingface \
    XDG_CACHE_HOME=/app/.cache
RUN python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='BAAI/bge-base-en-v1.5')"
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY retrievers.py graph.py guard.py prompts.py app.py /app/

RUN useradd -u 10001 -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
