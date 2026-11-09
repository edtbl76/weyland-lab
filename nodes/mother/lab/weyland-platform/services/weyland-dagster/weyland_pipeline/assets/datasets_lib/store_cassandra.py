"""Cassandra store loader: each silver Parquet file under parquet/<dataset>/ becomes a table in keyspace
datasets_<domain>. Idempotent (drop + recreate), with a row_id uuid clustering key so nothing upserts away on a
shared key."""
import os

import pyarrow.parquet as pq

from weyland_pipeline._otel import traced_load  # B49(b) Phase 2 - one coarse span per dataset-load

from .store_common import _q, _safe_ident, _sql_ident, downloaded, file_table, parquet_objects, record

_CQL_BATCH = 5_000
_CASS_LOG_EVERY = 200_000   # B121: heartbeat every N rows so big writes (lastfm ~17M) aren't silent for 15-40 min
_UNKNOWN = "__UNKNOWN__"


def _cassandra_cluster():
    from cassandra.cluster import Cluster

    hosts = os.environ.get("CASSANDRA_HOSTS", "cassandra.data-mesh.svc.cluster.local").split(",")
    port = int(os.environ.get("CASSANDRA_PORT", "9042"))
    return Cluster(hosts, port=port)


def _cql_col(dtype):
    """Map a pandas dtype → (CQL type, value caster to a Cassandra-safe python native: NaN → None, numpy scalars →
    int/float/str so the driver's type codecs accept them)."""
    import pandas as pd

    if pd.api.types.is_bool_dtype(dtype):
        return "boolean", lambda v: None if pd.isna(v) else bool(v)
    if pd.api.types.is_integer_dtype(dtype):
        return "bigint", lambda v: None if pd.isna(v) else int(v)
    if pd.api.types.is_float_dtype(dtype):
        return "double", lambda v: None if pd.isna(v) else float(v)
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "timestamp", lambda v: None if pd.isna(v) else v.to_pydatetime()
    return "text", lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)


def _partition_value(v):
    """A partition key may not be null or empty ("Key may not be empty": one blank fails the batch), so null / NaN /
    NaT / "" all collapse to a queryable sentinel."""
    import pandas as pd

    return _UNKNOWN if (v is None or pd.isna(v) or str(v) == "") else str(v)


def _cql_schema(pf, partition_raw, label, log):
    """(cols, cql_types, casters, partition) for one parquet file. The partition column is used only when present in
    the data (else row_id-only key), and is forced to text with the sentinel caster."""
    peek = next(pf.iter_batches(batch_size=256)).to_pandas()   # dtypes + column order
    cols = [_sql_ident(c) for c in peek.columns]
    cql_types, casters = map(list, zip(*[_cql_col(peek[c].dtype) for c in peek.columns]))
    partition = _sql_ident(partition_raw) if partition_raw else None
    if partition and partition not in cols:
        log.warning(f"cassandra {label}: partition col {partition!r} not present in "
                    f"{cols[:12]} — falling back to row_id-only key (plain dump)")
        partition = None
    if partition:
        pi = cols.index(partition)
        cql_types[pi], casters[pi] = "text", _partition_value
    return cols, cql_types, casters, partition


def _create_table(session, ks, table, cols, cql_types, partition):
    pk = f'PRIMARY KEY (("{_q(partition)}"), row_id)' if partition else "PRIMARY KEY (row_id)"
    col_defs = ", ".join(f'"{_q(c)}" {t}' for c, t in zip(cols, cql_types))
    session.execute(f"DROP TABLE IF EXISTS {_safe_ident(ks)}.{_safe_ident(table)}")  # nosemgrep
    session.execute(f'CREATE TABLE {_safe_ident(ks)}.{_safe_ident(table)} ({col_defs}, row_id uuid, {pk})')  # nosemgrep
    quoted = ", ".join(f'"{_q(c)}"' for c in cols)
    marks = ", ".join(["?"] * (len(cols) + 1))
    return session.prepare(f'INSERT INTO {ks}.{table} ({quoted}, row_id) VALUES ({marks})')


def _stream_rows(session, ins, pf, casters, label, log):
    """Fan the rows out with a prepared INSERT + execute_concurrent, in row batches (memory-safe)."""
    import uuid

    from cassandra.concurrent import execute_concurrent_with_args

    total = pf.metadata.num_rows
    log.info(f"cassandra {label}: writing {total:,} rows…")
    n, next_mark = 0, _CASS_LOG_EVERY
    for batch in pf.iter_batches(batch_size=_CQL_BATCH):
        params = [tuple(casters[i](v) for i, v in enumerate(rec)) + (uuid.uuid4(),)
                  for rec in batch.to_pandas().itertuples(index=False, name=None)]
        execute_concurrent_with_args(session, ins, params, concurrency=64)
        n += len(params)
        if n >= next_mark:   # B121: per-N-rows heartbeat so long writes aren't a silent block
            log.info(f"cassandra {label}: {n:,}/{total:,} rows…")
            next_mark += _CASS_LOG_EVERY
    return n


@traced_load
def _cassandra_write_file(session, ks, table, path, partition_raw, log):
    """Create <ks>.<table> from one silver parquet file and stream its rows in. Returns the rows written (0 for an
    empty file)."""
    pf = pq.ParquetFile(path)
    if pf.metadata.num_rows == 0:
        return 0
    label = f"{ks}.{table}"
    cols, cql_types, casters, partition = _cql_schema(pf, partition_raw, label, log)
    ins = _create_table(session, ks, table, cols, cql_types, partition)
    n = _stream_rows(session, ins, pf, casters, label, log)
    log.info(f"cassandra {label}: {n:,} rows" + (f" (partition={partition})" if partition else " (row_id key)"))
    return n


def _load_dataset_to_cassandra(session, mc, cfg, dataset, partition_raw, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in keyspace datasets_<domain> (per-table
    resilience: one file's failure is recorded, never fatal)."""
    ks = f"datasets_{cfg.domain}"
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        table = file_table(dataset, stem)

        def load(name=name, table=table):
            with downloaded(mc, cfg, name) as path:
                return _cassandra_write_file(session, ks, table, path, partition_raw, log)

        record(out, f"{ks}.{table}", f"cassandra {table}", log, load)
    return out
