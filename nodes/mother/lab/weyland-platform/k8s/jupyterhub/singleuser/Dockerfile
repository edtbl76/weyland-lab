# B1.8 singleuser image — the datasets-lake toolkit on top of the standard scientific notebook: polars over the 4
# lakeFS silver formats (Parquet/Arrow/Avro/Lance) + DuckDB SQL, all reading the lakeFS S3 gateway via s3fs.
# Built + `ctr import`ed into k3s (single node → no registry); referenced by singleuser.image with pullPolicy Never.
#
# NOTEBOOK DISTRIBUTION (B81): the notebooks under `notebooks/` are baked here at /opt/examples ONLY as a
# cold-start fallback. The LIVE library is git-synced from the public repo into ~/notebooks on every spawn by
# the singleuser postStart hook (see jupyterhub-values.yaml) — git is already in the scipy base, so growing the
# library is a `git push`, NOT an image rebuild. Rebuild this image only to refresh the offline fallback or the
# pinned deps below.
# Pinned by digest (2026-10-17, B220): `:latest` silently jumped ubuntu-24.04 → 26.04 and JupyterHub 5 → 6 between
# rebuilds. This digest = lab-4.6.4 / python-3.13.16 / ubuntu-26.04 (2026-10-12), the one tested. Bump it on purpose.
FROM quay.io/jupyter/scipy-notebook:lab-4.6.4@sha256:8f8a5763d9a01e7f488eff8d9379654788e9cc08286dbcbc6bcda129c1b0edcd
USER root
# 2026-10-18 (B220): `apt-get upgrade` picks up the Ubuntu fixes published after the pinned base digest (curl/libcurl
# 8.18.0-1ubuntu2.8 for CVE-2026-92392), and /usr/bin/pebble is removed: Canonical's service manager ships in the
# ubuntu-26.04 base, nothing here uses it (entrypoint = tini → start.sh → start-notebook.py; /var/lib/pebble/default/layers
# is empty), and its go1.26.7 build carried 3 HIGH Go-stdlib advisories.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -f /usr/bin/pebble && rm -rf /var/lib/pebble /var/lib/apt/lists/*
# 2026-10-16: the additions are pinned (requirements-lake.txt, the versions weyland-jupyter:v1 runs).
COPY requirements-lake.txt /tmp/requirements-lake.txt
RUN pip install --no-cache-dir -r /tmp/requirements-lake.txt \
    && mkdir -p /opt/examples
COPY notebooks/ /opt/examples/
RUN chmod -R a+rX /opt/examples
USER ${NB_UID}
