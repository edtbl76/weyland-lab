"""Ad-hoc LanceDB query helper — embedded, so it runs in-process (no server to connect to). Opens the domain's
LanceDB (on the lakeFS S3 gateway), lists tables or searches one by a row's own vector (a quick similarity
sanity check). Run in the dagster-user-code pod (has lancedb + lakeFS creds):

  kubectl -n weyland exec -i deploy/dagster-user-code -- python - < scripts/lancedb_query.py <music|health> [table] [row_id] [limit]

  <domain>            list the domain's tables
  <domain> <table>    10 nearest to row 0 of that table
  <domain> <table> <row_id> <limit>   nearest to a specific row
"""
import sys

from weyland_pipeline.assets.datasets_lib.loaders import _lancedb_connect
from weyland_pipeline.assets.datasets_health_transform import HEALTH_CFG
from weyland_pipeline.assets.datasets_music_transform import MUSIC_CFG

CFG = {"music": MUSIC_CFG, "health": HEALTH_CFG}


def main(argv):
    if not argv:
        print("usage: lancedb_query.py <music|health> [table] [row_id] [limit]")
        return
    domain = argv[0]
    db = _lancedb_connect(CFG[domain])
    lt = db.list_tables()
    tables = lt.tables if hasattr(lt, "tables") else list(lt)
    if len(argv) < 2:
        print(f"{domain} tables:", tables)
        return
    table = argv[1]
    limit = int(argv[3]) if len(argv) > 3 else 10
    t = db.open_table(table)
    df = t.to_pandas()
    idx = int(argv[2]) if len(argv) > 2 else 0
    v = df["vector"].iloc[idx]
    cols = [c for c in df.columns if c != "vector"]
    print(t.search(v).limit(limit).select(cols).to_pandas())


if __name__ == "__main__":
    main(sys.argv[1:])
