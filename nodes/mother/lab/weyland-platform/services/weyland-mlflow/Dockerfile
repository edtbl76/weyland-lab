# weyland-mlflow (B227, 2026-10-24) — the MLflow tracking server + AI Gateway with its drivers BAKED IN.
# Until B227 the pod ran `pip install psycopg2-binary boto3 'mlflow[gateway]==3.16.1' litellm` before the server on
# every start: three unpinned packages (litellm on the gateway's request path; the Postgres and S3 drivers) could move
# on any restart, every boot needed PyPI egress, and no scanner could see what was installed.
#
# requirements.txt is the FULL `pip freeze` of the pod that ran 3.16.1 that way (2026-10-24, 125 packages, `pip check`
# clean), so this image reproduces it exactly — including the base's importlib_metadata 9.0.1 -> 8.9.0 that pip made
# then. Upstream image pinned by digest (the same digest the pod ran). Never change the mlflow version here on its
# own: its DB migrations are forward-only (runbooks/mlflow.md). Runs as the upstream image's user (root), as before.
FROM ghcr.io/mlflow/mlflow:v3.16.1@sha256:06058cc872276873e9759c635e773342aca4731e240f6d20d88ea43774083984

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && pip check && rm /tmp/requirements.txt
