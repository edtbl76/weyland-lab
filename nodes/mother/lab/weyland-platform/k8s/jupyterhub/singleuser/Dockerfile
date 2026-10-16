# B1.8 singleuser image — the datasets-lake toolkit on top of the standard scientific notebook: polars over the 4
# lakeFS silver formats (Parquet/Arrow/Avro/Lance) + DuckDB SQL, all reading the lakeFS S3 gateway via s3fs.
# Built + `ctr import`ed into k3s (single node → no registry); referenced by singleuser.image with pullPolicy Never.
#
# NOTEBOOK DISTRIBUTION (B81): the notebooks under `notebooks/` are baked here at /opt/examples ONLY as a
# cold-start fallback. The LIVE library is git-synced from the public repo into ~/notebooks on every spawn by
# the singleuser postStart hook (see jupyterhub-values.yaml) — git is already in the scipy base, so growing the
# library is a `git push`, NOT an image rebuild. Rebuild this image only to refresh the offline fallback or the
# pinned deps below.
FROM quay.io/jupyter/scipy-notebook:latest
USER root
# 2026-10-16: the additions are pinned (requirements-lake.txt, the versions weyland-jupyter:v1 runs).
COPY requirements-lake.txt /tmp/requirements-lake.txt
RUN pip install --no-cache-dir -r /tmp/requirements-lake.txt \
    && mkdir -p /opt/examples
COPY notebooks/ /opt/examples/
RUN chmod -R a+rX /opt/examples
USER ${NB_UID}
