"""Build GizmoSQL's INIT_SQL_COMMANDS over the lakeFS Parquet, across both domains (music, health).

Two modes (argv[1], default `views`) — BOTH print SQL to stdout for the imperative `gizmosql-secret`:
  views  — `CREATE OR REPLACE VIEW` per Parquet file. LEGACY: views are queryable by name but GizmoSQL's
           Flight SQL GetTables does NOT surface them, so they're invisible in the DataGrip/IntelliJ tree.
  tables — `CREATE TABLE IF NOT EXISTS … AS SELECT` per Parquet file, schema-per-domain. This is the store
           form: base tables ARE surfaced by GetTables → they show up + browse in the IDE tree, and queries
           hit native DuckDB columnar storage instead of re-reading Parquet.

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
    if mode not in ("views", "tables"):
        sys.exit(f"usage: gen_gizmosql_init.py [views|tables]  (got {mode!r})")
    mc = Minio(HOSTPORT, access_key=KEY, secret_key=SECRET, secure=ENDPOINT.startswith("https://"))
    rows = _catalog(mc)
    print("\n".join(build_init_sql(rows, mode)))
    kind = "tables (CREATE TABLE IF NOT EXISTS)" if mode == "tables" else "views"
    print(f"-- generated {len(rows)} {kind} across {REPOS}", file=sys.stderr)


if __name__ == "__main__":
    main()
