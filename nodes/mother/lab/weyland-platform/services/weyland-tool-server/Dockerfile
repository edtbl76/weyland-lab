FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    psycopg2-binary \
    httpx \
    llama-index-embeddings-huggingface \
    qdrant-client \
    weaviate-client \
    neo4j

RUN python -c "from llama_index.embeddings.huggingface import HuggingFaceEmbedding; HuggingFaceEmbedding(model_name='BAAI/bge-small-en-v1.5')"

COPY main.py /app/main.py

ENV WEYLAND_DB_HOST=weyland-postgres.weyland.svc.cluster.local
ENV WEYLAND_DB_PORT=5432
ENV WEYLAND_DB_NAME=weyland
ENV WEYLAND_DB_USER=weyland
ENV QDRANT_HOST=qdrant.weyland.svc.cluster.local
ENV QDRANT_PORT=6333
ENV WEAVIATE_HOST=weaviate.weyland.svc.cluster.local
ENV WEAVIATE_PORT=8080
ENV WEAVIATE_GRPC_PORT=50051
ENV NEO4J_URI=bolt://neo4j.weyland.svc.cluster.local:7687
ENV NEO4J_USER=neo4j
ENV DAGSTER_URL=http://dagster-webserver.weyland.svc.cluster.local:3000

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
