# GizmoSQL browse queries — DataGrip tree workaround

DataGrip / IntelliJ's Arrow Flight SQL introspection **can't expand non-default schemas** in the data-source
tree (it lists `datasets_music` / `datasets_health` but shows no tables under them). This is a **client-side
JDBC-driver limitation**, not a server problem — GizmoSQL's metadata is correct (ADBC `GetObjects` returns
all 109 tables; the JDBC driver DataGrip uses doesn't surface them, confirmed on driver 18.3). Not fixable
from our side.

**Workaround:** `gizmosql_browse.sql` holds one `SELECT * … LIMIT 100` per table, grouped by schema. Open it
in IntelliJ against the **Weyland GizmoSQL** data source and run the statement under the cursor to see a
table's columns + a sample — no tree needed.

## Regenerate (after any dataset land+transform changes the silver)

Run in the user-code pod (has `LAKEFS_*` + reaches the gateway), redirect into this dir:

```
kubectl -n weyland exec -i deploy/dagster-user-code -- python - queries < ~/lab/weyland-platform/scripts/gen_gizmosql_init.py > ~/lab/weyland-platform/sql/gizmosql_browse.sql
```

(or from rogueone, using the repo path to `scripts/gen_gizmosql_init.py`). The list mirrors the persisted
tables 1:1 — same generator, same per-file naming as the `tables` mode that materialises them.
