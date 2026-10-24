# weyland-mlflow (B227, 2026-10-24) — the MLflow tracking server + AI Gateway with its drivers BAKED IN.
# Until B227 the pod ran `pip install psycopg2-binary boto3 'mlflow[gateway]==3.16.1' litellm` before the server on
# every start: three unpinned packages (litellm on the gateway's request path; the Postgres and S3 drivers) could move
# on any restart, every boot needed PyPI egress, and no scanner could see what was installed.
#
# requirements.txt is a FULL `pip freeze`: first (2026-10-24) the pod that ran 3.16.1 that way, reproduced exactly; then
# (same day, the CVE-2026-115886 follow-on) the 3.17.2 base plus the same drivers and litellm (124 packages, `pip check`
# clean). Upstream image pinned by digest. Never change the mlflow version here on its own: its DB migrations are
# forward-only — move the base tag, the digest and the three mlflow pins together, and prove the migration on a
# restored copy first (scripts/mlflow-upgrade-drill.sh, runbooks/mlflow.md). Runs as the upstream image's user (root).
FROM ghcr.io/mlflow/mlflow:v3.17.2@sha256:2cc40b3208991940d824d04f339833a0b69507569012aa5ec545690608602fc0

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && pip check && rm /tmp/requirements.txt
