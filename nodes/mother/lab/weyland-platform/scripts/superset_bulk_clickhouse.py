#!/usr/bin/env python3
"""Bulk-register every ClickHouse datasets_* table as a Superset dataset (the UI only adds one at a time).

Runs IN-CLUSTER (reaches superset + clickhouse svcs directly, bypassing the ingress OIDC via the /security/login
DB provider). Pipe it into the Dagster user-code pod (it has requests + clickhouse-connect + cross-ns svc DNS):

    [rogueone] scp .../scripts/superset_bulk_clickhouse.py emangini@mother:~/superset_bulk_clickhouse.py
    [mother]   kubectl -n weyland exec -i deploy/dagster-user-code -- python - < ~/superset_bulk_clickhouse.py

Override creds via env if the defaults are wrong: SUPERSET_USER / SUPERSET_PASSWORD.
"""
import os

import requests
import clickhouse_connect

SUP = os.environ.get("SUPERSET_URL", "http://superset.data-mesh.svc.cluster.local:8088").rstrip("/")
USER = os.environ.get("SUPERSET_USER", "admin")
PW = os.environ.get("SUPERSET_PASSWORD", "weyland_dev_password")
CH_HOST = os.environ.get("CLICKHOUSE_HOST", "clickhouse.data-mesh.svc.cluster.local")
CH_PW = os.environ.get("CLICKHOUSE_PASSWORD", "weyland_dev_password")

s = requests.Session()

# 1. auth (DB provider = the FAB admin user; bypasses Keycloak OIDC which is browser-only)
r = s.post(f"{SUP}/api/v1/security/login",
           json={"username": USER, "password": PW, "provider": "db", "refresh": True})
r.raise_for_status()
s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
r = s.get(f"{SUP}/api/v1/security/csrf_token/")
r.raise_for_status()
s.headers.update({"X-CSRFToken": r.json()["result"], "Referer": SUP})

# 2. find the ClickHouse connection Superset already has
dbs = s.get(f"{SUP}/api/v1/database/?q=(page_size:100)").json()["result"]
ch = [d for d in dbs if "clickhouse" in (d.get("backend") or "").lower()]
if not ch:
    raise SystemExit(f"No ClickHouse connection in Superset. Found: "
                     f"{[(d['id'], d['database_name'], d.get('backend')) for d in dbs]}")
db_id = ch[0]["id"]
print(f"ClickHouse Superset DB id={db_id} ({ch[0]['database_name']})")

# 3. every datasets_* table from ClickHouse itself
client = clickhouse_connect.get_client(host=CH_HOST, port=8123, username="default", password=CH_PW)
tables = client.query(
    "SELECT database, name FROM system.tables WHERE database LIKE 'datasets_%' ORDER BY database, name"
).result_rows

created = skipped = failed = 0
for schema, table in tables:
    r = s.post(f"{SUP}/api/v1/dataset/", json={"database": db_id, "schema": schema, "table_name": table})
    if r.status_code in (200, 201):
        created += 1
        print(f"+ {schema}.{table}")
    elif r.status_code == 422 and "exist" in r.text.lower():
        skipped += 1
    else:
        failed += 1
        print(f"! {schema}.{table}: {r.status_code} {r.text[:140]}")

print(f"\ncreated={created}  skipped(existing)={skipped}  failed={failed}  total={len(tables)}")
