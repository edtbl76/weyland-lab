"""Document, search and columnar store loaders: MongoDB, OpenSearch and ClickHouse. Each silver Parquet file under
parquet/<dataset>/ becomes one collection / index / table, dropped and reloaded each run (idempotent)."""
import os
import urllib.parse

import pyarrow.parquet as pq

from weyland_pipeline._otel import traced_load  # B49(b) Phase 2 - one coarse span per dataset-load

from .mongo_encode import to_bson_encodable
from .store_common import downloaded, file_table, lakefs_base, parquet_objects, record

# Mongo docs are Python dicts (heavy: OFF is 211 all-string cols), so a smaller batch than MySQL's, and the parquet
# is read from a temp FILE (not held in RAM): the 50k + whole-file approach OOMKilled user-code.
_MONGO_BATCH = 20_000
_OS_BATCH = 5_000


def _mongo_client():
    from pymongo import MongoClient

    host = os.environ.get("MONGO_HOST", "mongodb.data-mesh.svc.cluster.local")
    port = os.environ.get("MONGO_PORT", "27017")
    user = urllib.parse.quote_plus(os.environ.get("MONGO_USER", "weyland"))
    pw = urllib.parse.quote_plus(os.environ["MONGO_PASSWORD"])   # SEC-1: no baked-in fallback
    return MongoClient(f"mongodb://{user}:{pw}@{host}:{port}/?authSource=admin")


def _insert_batches(collection, path):
    n = 0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=_MONGO_BATCH):
        docs = to_bson_encodable(batch).to_pylist()
        if docs:
            collection.insert_many(docs, ordered=False)
            n += len(docs)
    return n


@traced_load
def _load_dataset_to_mongo(mc, cfg, dataset, client, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a Mongo collection in db datasets_<domain>, doc per row.
    MEMORY-SAFE: the parquet is downloaded to a temp file and read in row batches → insert_many."""
    db = client[f"datasets_{cfg.domain}"]
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        coll = file_table(dataset, stem)

        def load(name=name, coll=coll):
            db[coll].drop()
            with downloaded(mc, cfg, name) as path:
                n = _insert_batches(db[coll], path)
            log.info(f"mongo datasets_{cfg.domain}.{coll}: {n:,} docs")
            return n

        record(out, coll, f"mongo {coll}", log, load)
    return out


def _opensearch_client():
    from opensearchpy import OpenSearch

    host = os.environ.get("OPENSEARCH_HOST", "opensearch-cluster-master.opensearch.svc.cluster.local")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
    # standalone playground has the security plugin OFF → plain HTTP, no auth.
    return OpenSearch(hosts=[{"host": host, "port": port}], use_ssl=False, verify_certs=False, http_compress=True)


def _bulk_index(client, index, path):
    from opensearchpy import helpers

    n = 0
    for batch in pq.ParquetFile(path).iter_batches(batch_size=_OS_BATCH):
        actions = ({"_index": index, "_source": doc} for doc in batch.to_pylist())
        ok, _errs = helpers.bulk(client, actions, chunk_size=_OS_BATCH, raise_on_error=False)
        n += ok
    return n


@traced_load
def _load_dataset_to_opensearch(client, mc, cfg, dataset, log) -> dict:
    """Each silver parquet file → an OpenSearch index (doc per row). MEMORY-SAFE: temp file + row batches →
    helpers.bulk. Index name = the sanitized file name (OpenSearch requires lowercase, no special chars)."""
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        index = file_table(dataset, stem)

        def load(name=name, index=index):
            client.indices.delete(index=index, ignore=[404])
            with downloaded(mc, cfg, name) as path:
                n = _bulk_index(client, index, path)
            client.indices.refresh(index=index)
            log.info(f"opensearch {index}: {n:,} docs")
            return n

        record(out, index, f"opensearch {index}", log, load)
    return out


def _clickhouse_client(database="default"):
    import clickhouse_connect

    host = os.environ.get("CLICKHOUSE_HOST", "clickhouse.data-mesh.svc.cluster.local")
    port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
    user = os.environ.get("CLICKHOUSE_USER", "default")
    # ClickHouse requires a password (set via the users.d Secret: DataHub's clickhouse-sqlalchemy can't do no-auth).
    # It comes from CLICKHOUSE_PASSWORD (secretKeyRef → clickhouse-secret), NOT a hardcoded default: an empty
    # fallback fails auth loudly rather than embedding the real secret in code.
    pw = os.environ.get("CLICKHOUSE_PASSWORD", "")
    return clickhouse_connect.get_client(host=host, port=port, username=user, password=pw, database=database)


# Skip all-null parquet columns (Parquet 'null' type → ClickHouse can't schema-infer it); they carry no data, so
# dropping them is lossless (3 usda tables had one each).
_CH_CREATE = ("CREATE TABLE `{db}`.`{table}` ENGINE = MergeTree ORDER BY tuple() AS "
              "SELECT * FROM s3({{url:String}}, {{k:String}}, {{s:String}}, 'Parquet') "
              "SETTINGS input_format_parquet_skip_columns_with_unsupported_types_in_schema_inference = 1")


@traced_load
def _load_dataset_to_clickhouse(client, mc, cfg, dataset, log) -> dict:
    """Each silver parquet file → a MergeTree table in db datasets_<domain>. NATIVE ingest: ClickHouse reads the
    parquet straight from the lakeFS S3 gateway via the s3() table function (schema inferred, columnar, memory-bounded
    server-side), so no Python row loop. lakeFS creds are bound params, so the secret stays out of query text/logs."""
    db = f"datasets_{cfg.domain}"
    _scheme, base = lakefs_base()
    creds = {"k": os.environ["LAKEFS_ACCESS_KEY_ID"], "s": os.environ["LAKEFS_SECRET_ACCESS_KEY"]}
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        table = file_table(dataset, stem)

        def load(name=name, table=table):
            client.command(f"DROP TABLE IF EXISTS `{db}`.`{table}`")
            client.command(_CH_CREATE.format(db=db, table=table),
                           parameters={"url": f"{base}/{cfg.repo}/{name}", **creds})
            n = int(client.command(f"SELECT count() FROM `{db}`.`{table}`"))
            log.info(f"clickhouse {db}.{table}: {n:,} rows (native s3 ingest)")
            return n

        record(out, f"{db}.{table}", f"clickhouse {table}", log, load)
    return out
