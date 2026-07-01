"""Build the GizmoSQL silver catalog over the lakeFS Parquet, across both domains (music, health).

Two modes (argv[1], default `views`):
  views  — print CREATE VIEW SQL to stdout. LEGACY path (patched into the imperative gizmosql-secret's
           INIT_SQL_COMMANDS). Kept for reference; NOT how the store is served anymore.
  tables — connect to GizmoSQL over Arrow Flight SQL and MATERIALISE each Parquet file as a *persisted*
           DuckDB TABLE (CREATE OR REPLACE, schema-per-domain). This is the store form, because:
             • GizmoSQL's Flight SQL GetTables surfaces base TABLES but NOT views → tables show up and
               browse in DataGrip / IntelliJ; views are queryable by name yet invisible to the IDE tree.
             • queries hit native DuckDB columnar storage instead of re-reading Parquet each time.
           Requires GizmoSQL to run with a persisted DATABASE_FILENAME on a PVC (k8s/data-mesh/gizmosql.yaml)
           so the tables survive restarts (an in-memory db would re-materialise all of them every boot).

Run in the user-code pod — it has LAKEFS_* (to LIST Parquet) AND GIZMOSQL_* (to connect), and reaches both
the lakeFS gateway and gizmosql.data-mesh.svc:

    # materialise / refresh the store (re-run after any dataset land+transform changes its silver):
    kubectl -n weyland exec -i deploy/dagster-user-code -- python - tables < scripts/gen_gizmosql_init.py

    # or just print the legacy view SQL:
    kubectl -n weyland exec -i deploy/dagster-user-code -- python - < scripts/gen_gizmosql_init.py

NOTE (views mode): stdout carries the lakeFS keys (DuckDB CREATE SECRET needs literals) — pipe it straight
into the Secret, don't paste it around. tables mode keeps the keys in-session (never persisted to the db file).
"""
import os
import re
import sys

from minio import Minio

ENDPOINT = os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000")
HOSTPORT = ENDPOINT.replace("https://", "").replace("http://", "")
KEY = os.environ["LAKEFS_ACCESS_KEY_ID"]
SECRET = os.environ["LAKEFS_SECRET_ACCESS_KEY"]
BRANCH = os.environ.get("LAKEFS_BRANCH", "main")
REPOS = ("music", "health")


def _ident(dataset: str, name: str) -> str:
    base = dataset if name == dataset else f"{dataset}_{name}"
    s = re.sub(r"[^0-9A-Za-z_]+", "_", base).strip("_").lower()
    return s if s and not s[0].isdigit() else f"v_{s}"


def _catalog(mc):
    """List the CURRENT silver Parquet across both repos → [(schema, ident, s3_path)], deduped per schema.
    Mirrors the Iceberg per-file naming: <dataset> for single-file datasets else <dataset>_<file>."""
    out = []
    for repo in REPOS:
        schema = f"datasets_{repo}"
        prefix = f"{BRANCH}/parquet/"
        seen = set()
        for obj in mc.list_objects(repo, prefix=prefix, recursive=True):
            if not obj.object_name.endswith(".parquet"):
                continue
            rel = obj.object_name[len(prefix):]            # <dataset>/<...>/<file>.parquet
            dataset = rel.split("/")[0]
            name = re.sub(r"\.parquet$", "", rel[len(dataset) + 1:]).replace("/", "_")
            ident = _ident(dataset, name)
            if ident in seen:
                continue
            seen.add(ident)
            out.append((schema, ident, f"s3://{repo}/{obj.object_name}"))
    return out


def _secret_sql() -> str:
    return (f"CREATE OR REPLACE SECRET lakefs (TYPE S3, KEY_ID '{KEY}', SECRET '{SECRET}', "
            f"ENDPOINT '{HOSTPORT}', URL_STYLE 'path', USE_SSL false, REGION 'us-east-1');")


def print_views(rows):
    lines = ["INSTALL httpfs; LOAD httpfs;", _secret_sql()]
    for schema in sorted({s for s, _, _ in rows}):
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {schema};")
    for schema, ident, path in rows:
        lines.append(f"CREATE OR REPLACE VIEW {schema}.{ident} AS SELECT * FROM read_parquet('{path}');")
    print("\n".join(lines))
    print(f"-- generated {len(rows)} views across {REPOS}", file=sys.stderr)


def materialize_tables(rows):
    """Connect to GizmoSQL and CREATE OR REPLACE each Parquet file as a persisted DuckDB table. Per-table
    try/except so one bad file logs + is skipped instead of aborting the whole refresh (same discipline as
    the store loaders). Creds come from the pod's own GIZMOSQL_* env (same as datahub_emit.emit_duckdb)."""
    import adbc_driver_flightsql.dbapi as flight_sql

    conn = flight_sql.connect(
        os.environ.get("GIZMOSQL_URI", "grpc+tcp://gizmosql.data-mesh.svc.cluster.local:31337"),
        db_kwargs={
            "username": os.environ.get("GIZMOSQL_USERNAME", "weyland"),
            "password": os.environ["GIZMOSQL_PASSWORD"],
        },
    )
    ok, failed = 0, []
    try:
        cur = conn.cursor()
        cur.execute("INSTALL httpfs")          # one statement per execute — Flight SQL isn't multi-statement
        cur.execute("LOAD httpfs")
        cur.execute(_secret_sql())             # temporary (session) secret — never persisted to the db file
        for schema in sorted({s for s, _, _ in rows}):
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for schema, ident, path in rows:
            try:
                cur.execute(f"CREATE OR REPLACE TABLE {schema}.{ident} AS SELECT * FROM read_parquet('{path}')")
                ok += 1
                print(f"  ✓ {schema}.{ident}", file=sys.stderr)
            except Exception as exc:           # noqa: BLE001 — one bad file must not abort the rest
                failed.append((f"{schema}.{ident}", str(exc).splitlines()[0]))
                print(f"  ✗ {schema}.{ident}: {str(exc).splitlines()[0]}", file=sys.stderr)
    finally:
        conn.close()
    print(f"-- materialised {ok}/{len(rows)} tables across {REPOS}"
          + (f"; {len(failed)} FAILED: {failed}" if failed else ""), file=sys.stderr)


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "views").lower()
    mc = Minio(HOSTPORT, access_key=KEY, secret_key=SECRET, secure=ENDPOINT.startswith("https://"))
    rows = _catalog(mc)
    (materialize_tables if mode == "tables" else print_views)(rows)


if __name__ == "__main__":
    main()
