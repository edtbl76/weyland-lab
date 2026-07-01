"""Build GizmoSQL's INIT_SQL_COMMANDS over the lakeFS Parquet, across both domains (music, health).

Three modes (argv[1], default `views`) — all print to stdout:
  tables  — `CREATE TABLE IF NOT EXISTS … AS SELECT` per Parquet file, schema-per-domain → INIT_SQL for the
            persisted store. Fast native columnar storage vs re-reading Parquet. THE current form.
  views   — `CREATE OR REPLACE VIEW` per file. Legacy always-live form (no PVC); kept as a fallback.
  queries — a `SELECT * … LIMIT 100` per table for a local `sql/` file. Browse workaround: DataGrip's Flight
            SQL introspection can't expand non-default schemas in the tree (server metadata is fine — proven
            via ADBC GetObjects; it's a DataGrip/JDBC-driver limitation, NOT the object type), so you open the
            file and run the statement under the cursor to see a table's columns.

WHY INIT_SQL (not driving the DDL over a client): GizmoSQL runs each Flight SQL statement in an ISOLATED
session, so a client's `CREATE SCHEMA`/`CREATE SECRET` isn't visible to the next `CREATE TABLE` (fails with
"Schema … does not exist"). INIT_SQL runs the whole block in ONE session at server startup — the only place
schema + secret + table DDL coexist. On a PERSISTED DuckDB (DATABASE_FILENAME on a PVC — see gizmosql.yaml),
`IF NOT EXISTS` materialises the tables once on first boot and skips on every restart after (no re-read).

Run in the user-code pod (it has LAKEFS_* to LIST Parquet + reaches the gateway); capture stdout locally:
    kubectl -n weyland exec -i deploy/dagster-user-code -- python - tables < scripts/gen_gizmosql_init.py > /tmp/gizmo-init.sql
Then patch gizmosql-secret's INIT_SQL_COMMANDS with that file and restart gizmosql (see runbooks/gizmosql.md).

NOTE: stdout carries the lakeFS keys (DuckDB CREATE SECRET needs literals) — pipe it straight into the Secret,
don't paste it around.
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


def build_queries(rows):
    """Browse-workaround: a `SELECT *` per table, grouped by schema. DataGrip's Flight SQL introspection
    can't expand non-default schemas in the tree (server metadata is fine — proven via ADBC GetObjects),
    so this is how you eyeball a table's columns: open the file, run the statement under the cursor."""
    lines = ["-- GizmoSQL browse workaround — run the statement under your cursor to see a table's columns.",
             "-- Regenerate after dataset changes: gen_gizmosql_init.py queries > sql/gizmosql_browse.sql", ""]
    last = None
    for schema, ident, _ in rows:
        if schema != last:
            lines += ["", f"-- {schema}"]
            last = schema
        lines.append(f"SELECT * FROM {schema}.{ident} LIMIT 100;")
    return lines


def build_init_sql(rows, mode):
    lines = []
    if mode == "tables":
        # cap DuckDB (defaults to node-RAM-sized → OOMs the container) BEFORE the CTAS materialise runs.
        lines.append("SET memory_limit='3GB';")
    lines += ["INSTALL httpfs; LOAD httpfs;", _secret_sql()]
    for schema in sorted({s for s, _, _ in rows}):
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {schema};")
    for schema, ident, path in rows:
        if mode == "tables":
            # IF NOT EXISTS: materialise once on first boot, skip on restart (persisted DB survives it).
            lines.append(
                f"CREATE TABLE IF NOT EXISTS {schema}.{ident} AS SELECT * FROM read_parquet('{path}');")
        else:
            lines.append(
                f"CREATE OR REPLACE VIEW {schema}.{ident} AS SELECT * FROM read_parquet('{path}');")
    return lines


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "views").lower()
    if mode not in ("views", "tables", "queries"):
        sys.exit(f"usage: gen_gizmosql_init.py [views|tables|queries]  (got {mode!r})")
    mc = Minio(HOSTPORT, access_key=KEY, secret_key=SECRET, secure=ENDPOINT.startswith("https://"))
    rows = _catalog(mc)
    lines = build_queries(rows) if mode == "queries" else build_init_sql(rows, mode)
    print("\n".join(lines))
    kind = {"tables": "tables (CREATE TABLE IF NOT EXISTS)", "views": "views",
            "queries": "SELECT * browse queries"}[mode]
    print(f"-- generated {len(rows)} {kind} across {REPOS}", file=sys.stderr)


if __name__ == "__main__":
    main()
