"""SQL store loaders: MySQL, TimescaleDB and CockroachDB. Each silver Parquet file under parquet/<dataset>/ becomes a
table, written in row batches (pyarrow iter_batches → pandas → to_sql) so big tables (brfss ~3M rows) stay
memory-bounded. to_sql uses the default executemany, NOT method="multi": a multi-row INSERT compiles chunksize ×
columns bind params, which is pathologically slow on wide tables (big_five's 57 cols × 5000 = 285k params hung the
compile until the run was killed).
"""
import io as _io
import os
import urllib.parse

import pyarrow.parquet as pq

from weyland_pipeline._otel import traced_load  # B49(b) Phase 2 - one coarse span per dataset-load

from . import io
from .store_common import _safe_ident, _sql_ident, downloaded, file_table, parquet_objects, record
from .timeseries import hypertable_ts

_MYSQL_BATCH = 50_000
_TO_SQL_CHUNK = 1_000


def _mysql_url(db=""):
    host = os.environ.get("MYSQL_HOST", "mysql.data-mesh.svc.cluster.local")
    port = os.environ.get("MYSQL_PORT", "3306")
    user = os.environ["MYSQL_USER"]
    pw = urllib.parse.quote_plus(os.environ["MYSQL_PASSWORD"])
    return f"mysql+pymysql://{user}:{pw}@{host}:{port}" + (f"/{db}" if db else "")


def _mysql_engine_factory():
    import sqlalchemy

    cache = {}

    def engine_for(db):
        if db not in cache:
            cache[db] = sqlalchemy.create_engine(_mysql_url(db))
        return cache[db]

    return engine_for


def _mysql_ensure_database(dataset):
    """Create the per-dataset database if it does not exist, mirroring the CockroachDB loader. Connecting to a
    non-existent schema fails ("Unknown database"), so the DB must precede ``engine_for(dataset)``. The historical
    trap was that ``weyland`` had a per-database grant only on a hand-maintained allowlist, so a NEW domain hit
    "Access denied to database '<dataset>'". The companion ``--init-file`` grant (mysql.yaml) now gives ``weyland``
    schema-level CREATE across ``*.*`` so this self-provisions for every domain."""
    import sqlalchemy

    eng = sqlalchemy.create_engine(_mysql_url())   # server-level: no default schema, so the db need not exist yet
    try:
        with eng.begin() as conn:
            conn.execute(sqlalchemy.text(f"CREATE DATABASE IF NOT EXISTS `{_safe_ident(dataset)}`"))  # nosemgrep
    finally:
        eng.dispose()


def _write_batches(batches, table, engine):
    """Replace `table` with the first batch, append the rest; return the row count."""
    n, first = 0, True
    for batch in batches:
        df = batch.to_pandas()
        df.to_sql(table, engine, if_exists="replace" if first else "append", index=False, chunksize=_TO_SQL_CHUNK)
        first, n = False, n + len(df)
    return n


@traced_load
def _load_dataset_to_mysql(mc, cfg, dataset, engine_for, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in MySQL db <dataset>."""
    _mysql_ensure_database(dataset)   # self-provision the db (class fix: no per-dataset root grant)
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        table = _sql_ident(stem)

        def load(name=name, table=table):
            data = io.fetch(mc, cfg.repo, name)
            batches = pq.ParquetFile(_io.BytesIO(data)).iter_batches(batch_size=_MYSQL_BATCH)
            n = _write_batches(batches, table, engine_for(dataset))
            log.info(f"mysql {dataset}.{table}: {n:,} rows")
            return n

        record(out, f"{dataset}.{table}", f"mysql {dataset}.{table}", log, load)
    return out


def _tsdb_engine():
    import sqlalchemy

    host = os.environ.get("TIMESCALEDB_HOST", "timescaledb.data-mesh.svc.cluster.local")
    port = os.environ.get("TIMESCALEDB_PORT", "5432")
    db = os.environ.get("TIMESCALEDB_DB", "timeseries")
    user = os.environ.get("TIMESCALEDB_USER", "weyland")
    pw = urllib.parse.quote_plus(os.environ["TIMESCALEDB_PASSWORD"])   # SEC-1: no baked-in fallback
    return sqlalchemy.create_engine(f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}")


# chunk_time_interval = 5 YEARS, NOT the 7-day default: dataset time-series are low-frequency (yearly / monthly /
# quarterly / daily) but can span a CENTURY (FRED fred_macro is 1919→2026). At the default 7 days that is ~3,900 tiny
# chunks, and a GROUP BY over the time dimension builds a ChunkAppend plan large enough to SEGFAULT the backend,
# taking down the whole shared `timeseries` DB (who_gho, eval_scores, ...) into recovery. 5-year chunks keep any
# realistic dataset span to a few dozen chunks. migrate_data moves the just-loaded rows into chunks; if_not_exists
# keeps it idempotent across re-runs.
_HYPERTABLE = ("SELECT create_hypertable('{table}', 'ts', if_not_exists => TRUE, migrate_data => TRUE, "
               "chunk_time_interval => INTERVAL '5 years')")


@traced_load
def _load_dataset_to_timescale(mc, cfg, dataset, time_col, engine, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a TimescaleDB hypertable in db `timeseries`, partitioned
    on a derived `ts` timestamptz. The `ts` coercion is dtype-aware (timeseries.hypertable_ts): a NUMERIC time column
    is a YEAR (WHO GHO's TimeDim → Jan 1 of that year); a date/ISO-string column is a full date (FRED's `date`). Rows
    with no usable timestamp are dropped (a hypertable's time column must be non-null). Table names are
    dataset-prefixed (who_gho_<indicator>) since TimescaleDB is one flat db."""
    import sqlalchemy

    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        table = file_table(dataset, stem)

        def load(name=name, table=table):
            df = pq.ParquetFile(_io.BytesIO(io.fetch(mc, cfg.repo, name))).read().to_pandas()
            if time_col not in df.columns:
                raise KeyError(f"time column {time_col!r} not in {list(df.columns)[:10]}")
            df["ts"] = hypertable_ts(df[time_col])
            df = df[df["ts"].notna()]
            df.to_sql(table, engine, if_exists="replace", index=False, chunksize=5_000)
            # to_sql made a plain table (dropping any prior hypertable); (re)promote it.
            with engine.begin() as conn:
                conn.execute(sqlalchemy.text(_HYPERTABLE.format(table=_safe_ident(table))))  # nosemgrep
            log.info(f"timescaledb {table}: {len(df):,} rows → hypertable on ts (from {time_col})")
            return int(len(df))

        record(out, table, f"timescaledb {table}", log, load)
    return out


def _cockroach_engine_factory():
    import sqlalchemy

    host = os.environ.get("COCKROACH_HOST", "cockroachdb.data-mesh.svc.cluster.local")
    port = os.environ.get("COCKROACH_PORT", "26257")
    user = os.environ.get("COCKROACH_USER", "root")
    cache = {}

    def engine_for(db):
        # the cockroachdb dialect (NOT plain postgres: the pg dialect can't parse Cockroach's version string).
        # Insecure single node → user root, no password, sslmode disabled.
        if db not in cache:
            cache[db] = sqlalchemy.create_engine(f"cockroachdb://{user}@{host}:{port}/{db}?sslmode=disable")
        return cache[db]

    return engine_for


@traced_load
def _load_dataset_to_cockroach(mc, cfg, dataset, engine_for, log) -> dict:
    """Each silver parquet file under parquet/<dataset>/ → a table in CockroachDB db <dataset> (created if absent).
    pg-wire, so pandas.to_sql. MEMORY-SAFE: the parquet is downloaded to a temp FILE and read in batches (brfss
    ~3M rows). Table replaced each run (idempotent)."""
    import sqlalchemy

    with engine_for("defaultdb").connect() as conn:   # CREATE DATABASE from Cockroach's default db
        conn.execute(sqlalchemy.text(f'CREATE DATABASE IF NOT EXISTS "{_safe_ident(dataset)}"'))  # nosemgrep
        conn.commit()
    engine = engine_for(dataset)
    out = {}
    for name, stem in parquet_objects(mc, cfg, dataset):
        table = _sql_ident(stem)

        def load(name=name, table=table):
            with downloaded(mc, cfg, name) as path:
                n = _write_batches(pq.ParquetFile(path).iter_batches(batch_size=_MYSQL_BATCH), table, engine)
            log.info(f"cockroach {dataset}.{table}: {n:,} rows")
            return n

        record(out, f"{dataset}.{table}", f"cockroach {dataset}.{table}", log, load)
    return out
