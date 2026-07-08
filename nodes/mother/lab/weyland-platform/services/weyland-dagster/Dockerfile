FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so it's baked into the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

COPY weyland_pipeline/ ./weyland_pipeline/
COPY feast_repo/ ./feast_repo/

# dbt project — parse at build → dbt/target/manifest.json (required by @dbt_assets at import time). `deps` pulls
# dbt_utils/dbt_expectations from the dbt hub; `parse` builds the manifest but does NOT connect (no Trino needed
# at build). DBT_PROFILES_DIR points at the in-project profiles.yml (env-var defaults render offline).
COPY dbt/ ./dbt/
RUN cd /app/dbt && DBT_PROFILES_DIR=/app/dbt dbt deps && DBT_PROFILES_DIR=/app/dbt dbt parse

# Ops scripts (feast_setup.py etc.) — run via `kubectl exec … python /app/scripts/<name>`. Last COPY so it never
# invalidates the cached dbt/deps layer above.
COPY scripts/ ./scripts/

EXPOSE 4000

CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-m", "weyland_pipeline.definitions"]
