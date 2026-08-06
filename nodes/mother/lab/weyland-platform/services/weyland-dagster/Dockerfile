FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first — the base image's pip 24.0 crashes (TypeError: 'NoneType' object is not iterable, in its
# version parser) while resolving the pinned deps once a malformed version string lands on PyPI (hit 2026-08 around
# pyiceberg). Newer pip parses it fine. Incidental to B82 — just unblocks the build.
RUN pip install --no-cache-dir --upgrade "pip>=25"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so it's baked into the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"

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
# pip>=25 first: the base image's ensurepip pip (24.x) SEGFAULTS mid-resolve on this dep set when the layer cache
# misses (seen 2026-08-06) — the same class of pip bug the main-env install already works around.
RUN python -m venv /opt/soda-venv && /opt/soda-venv/bin/pip install --upgrade "pip>=25" && /opt/soda-venv/bin/pip install --no-cache-dir soda-core-trino
COPY soda/ ./soda/

# Great Expectations (B77 part b — DQ profiling/validation showcase) in its OWN isolated venv: GE 0.18 pins
# sqlalchemy<2 + marshmallow that clash with the dagster+dbt+datahub main env, and acryl-datahub 1.7 dropped the
# native GE action — so GE runs alone (GE 0.18 + trino dialect + SA 1.4), shelled out from ge_validate_op, and the
# MAIN env's emit_ge_assertions() surfaces results to DataHub. pip>=25 first (base pip 24.0 segfaults resolving these).
RUN python -m venv /opt/ge-venv && /opt/ge-venv/bin/pip install --upgrade "pip>=25" && /opt/ge-venv/bin/pip install --no-cache-dir "great-expectations==0.18.*" trino "sqlalchemy<2"
COPY ge/ ./ge/

# Ops scripts (feast_setup.py etc.) — run via `kubectl exec … python /app/scripts/<name>`. Last COPY so it never
# invalidates the cached dbt/deps layer above.
COPY scripts/ ./scripts/

EXPOSE 4000

# ROOT REQUIRED (B47 accepted exception): the embedding model is baked to /root/.cache at build, dbt writes
# /app/dbt/target at runtime, and the K8sRunLauncher spawns every pipeline run-pod FROM this image. Non-root means
# re-validating the whole platform for ~zero LAN-lab gain; the pod securityContext is the real mitigation instead.
# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["dagster", "api", "grpc", "-h", "0.0.0.0", "-p", "4000", "-m", "weyland_pipeline.definitions"]
