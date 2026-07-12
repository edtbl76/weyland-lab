# B1.8 singleuser image — the datasets-lake toolkit on top of the standard scientific notebook: polars over the 4
# lakeFS silver formats (Parquet/Arrow/Avro/Lance) + DuckDB SQL, all reading the lakeFS S3 gateway via s3fs.
# Built + `ctr import`ed into k3s (single node → no registry); referenced by singleuser.image with pullPolicy Never.
FROM quay.io/jupyter/scipy-notebook:latest
USER root
RUN pip install --no-cache-dir polars s3fs pylance duckdb fastavro \
    && mkdir -p /opt/examples
COPY datasets_lake.ipynb /opt/examples/datasets_lake.ipynb
RUN chmod -R a+rX /opt/examples
USER ${NB_UID}
