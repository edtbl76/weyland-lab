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

# Soda Core (B1.6 L5 Slice C — data quality) in an ISOLATED venv: soda-core pins opentelemetry/click/ruamel at
# versions that clash with dagster+dbt+datahub in the main env, so it lives in its own /opt/soda-venv and is
# invoked as a subprocess by soda_scan_op. soda-core-trino pulls soda-core + the Trino connector. The venv is a
# heavy layer, so it precedes COPY soda/ — editing checks won't rebuild it.
RUN python -m venv /opt/soda-venv && /opt/soda-venv/bin/pip install --no-cache-dir soda-core-trino
COPY soda/ ./soda/

# Ops scripts (feast_setup.py etc.) — run via `kubectl exec … python /app/scripts/<name>`. Last COPY so it never
# invalidates the cached dbt/deps layer above.
COPY scripts/ ./scripts/

EXPOSE 4000

# nosemgrep: dockerfile.security.missing-user.missing-user -- ROOT REQUIRED (B47 accepted exception): the embedding
# model is baked to /root/.cache at build, dbt writes /app/dbt/target at runtime, and the K8sRunLauncher spawns
# every pipeline run-pod FROM this image. Non-root means re-validating the whole platform for ~zero LAN-lab gain;
# the pod securityContext (allowPrivilegeEscalation:false + drop caps) provides the real mitigation instead.
CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-m", "weyland_pipeline.definitions"]
