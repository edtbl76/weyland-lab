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
RUN pip install --no-cache-dir polars s3fs pylance duckdb fastavro \
    && mkdir -p /opt/examples
COPY notebooks/ /opt/examples/
RUN chmod -R a+rX /opt/examples
USER ${NB_UID}
