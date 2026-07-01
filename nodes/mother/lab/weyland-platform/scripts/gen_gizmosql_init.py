"""Generate GizmoSQL's INIT_SQL_COMMANDS — DuckDB httpfs + a lakeFS S3 secret + one view per CURRENT silver
Parquet file across both domains (music, health). Schema-per-domain (datasets_music / datasets_health),
view name = <dataset> for single-file datasets else <dataset>_<file> — mirrors the Iceberg per-file tables.

WHY a generator: the views live in the imperative `gizmosql-secret` (they carry the lakeFS keys, so they're
not in git). Hand-maintaining ~90 views is how it went stale (frozen at the original 4). Re-run this after
any dataset change instead of hand-editing.

Run in the user-code pod (it has LAKEFS_* env + reaches the gateway); capture stdout locally:
    kubectl -n weyland exec -i deploy/dagster-user-code -- python - < scripts/gen_gizmosql_init.py > /tmp/gizmo-init.sql
Then patch gizmosql-secret's INIT_SQL_COMMANDS with that file and restart gizmosql (see runbooks/gizmosql.md).

NOTE: stdout contains the lakeFS keys (DuckDB CREATE SECRET needs literal values) — pipe it straight into
the Secret; don't paste it around.
"""
import os
import re

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


def main():
    mc = Minio(HOSTPORT, access_key=KEY, secret_key=SECRET, secure=ENDPOINT.startswith("https://"))
    lines = [
        "INSTALL httpfs; LOAD httpfs;",
        (f"CREATE OR REPLACE SECRET lakefs (TYPE S3, KEY_ID '{KEY}', SECRET '{SECRET}', "
         f"ENDPOINT '{HOSTPORT}', URL_STYLE 'path', USE_SSL false, REGION 'us-east-1');"),
    ]
    total = 0
    for repo in REPOS:
        schema = f"datasets_{repo}"
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {schema};")
        prefix = f"{BRANCH}/parquet/"
        seen = set()
        for obj in mc.list_objects(repo, prefix=prefix, recursive=True):
            if not obj.object_name.endswith(".parquet"):
                continue
            rel = obj.object_name[len(prefix):]           # <dataset>/<...>/<file>.parquet
            dataset = rel.split("/")[0]
            name = re.sub(r"\.parquet$", "", rel[len(dataset) + 1:]).replace("/", "_")
            view = _ident(dataset, name)
            if view in seen:
                continue
            seen.add(view)
            lines.append(
                f"CREATE OR REPLACE VIEW {schema}.{view} AS "
                f"SELECT * FROM read_parquet('s3://{repo}/{obj.object_name}');")
            total += 1
    print("\n".join(lines))
    # summary to stderr so it doesn't pollute the SQL on stdout
    import sys
    print(f"-- generated {total} views across {REPOS}", file=sys.stderr)


if __name__ == "__main__":
    main()
