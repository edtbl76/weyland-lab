#!/usr/bin/env python3
"""Seed Superset with Food & Nutrition + Music Catalog dashboards over the ALREADY-REGISTERED ClickHouse datasets
(datasets_health/open_food_facts + usda food, datasets_music/uci_year_prediction + musicbrainz) — the rich raw
datasets that had 0 charts. Complements superset_seed.py (which covers the dbt marts). No dataset registration —
these already exist; this only creates charts + 2 dashboards.

NOTE: open_food_facts stores everything as STRING (incl. nutrients), so numeric metrics use SQL-expression
metrics with the ClickHouse cast `toFloat64OrNull(col)`. Datasets live on the ClickHouse connection.

    SUPERSET_PASSWORD=<pw> python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/superset_seed_extra.py

Env: same as superset_seed.py (SUPERSET_URL/USER/PASSWORD/CA_BUNDLE).
"""
import json
import os
import sys
import uuid

import requests

BASE = os.environ.get("SUPERSET_URL", "https://superset.weyland.lab").rstrip("/")
USER = os.environ.get("SUPERSET_USER", "admin")
PW = os.environ.get("SUPERSET_PASSWORD", "weyland_dev_password")
_CA = os.environ.get("SUPERSET_CA_BUNDLE") or os.path.expanduser("~/.local/share/mkcert/rootCA.pem")

S = requests.Session()
S.verify = _CA if os.path.exists(_CA) else True

r = S.post(f"{BASE}/api/v1/security/login",
           json={"username": USER, "password": PW, "provider": "db", "refresh": True})
if not r.ok:
    sys.exit(f"login failed {r.status_code}: {r.text[:300]}")
S.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
S.headers.update({"X-CSRFToken": S.get(f"{BASE}/api/v1/security/csrf_token/").json()["result"], "Referer": BASE})


def post(path, body):
    r = S.post(f"{BASE}{path}", json=body)
    if not r.ok:
        sys.exit(f"POST {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


# --- resolve existing ClickHouse dataset ids by table_name (page through — Superset caps page_size ~100) ---
allds, _page = [], 0
while True:
    _res = S.get(f"{BASE}/api/v1/dataset/?q=(page:{_page},page_size:100)").json()["result"]
    allds += _res
    if len(_res) < 100:
        break
    _page += 1


def find(tbl, dbhint="click"):
    for d in allds:
        if d["table_name"] == tbl and dbhint.lower() in d["database"]["database_name"].lower():
            return d["id"]
    for d in allds:
        if d["table_name"] == tbl:
            return d["id"]
    sys.exit(f"dataset {tbl!r} not registered in Superset")


OFF = find("open_food_facts")
USDA = find("usda_fooddata_fooddata_central_csv_2024_10_31_food")
UCI = find("uci_year_prediction")
MBA = find("musicbrainz_musicbrainz_artist")
MBR = find("musicbrainz_musicbrainz_release_group")
print(f"datasets: off={OFF} usda={USDA} uci={UCI} mb_artist={MBA} mb_release_group={MBR}")


def COUNT(label="Count"):
    return {"expressionType": "SQL", "sqlExpression": "count(*)", "label": label}


def SQLM(expr, label):
    return {"expressionType": "SQL", "sqlExpression": expr, "label": label}


def chart(name, ds_id, x, metrics, limit=5000, order_desc=False):
    params = {"viz_type": "echarts_timeseries_bar", "x_axis": x, "metrics": metrics, "groupby": [],
              "row_limit": limit}
    if order_desc:
        params["order_desc"] = True
    cid = post("/api/v1/chart/", {"slice_name": name, "viz_type": "echarts_timeseries_bar",
                                  "datasource_id": ds_id, "datasource_type": "table",
                                  "params": json.dumps(params)})["id"]
    print(f"  chart '{name}' -> {cid}")
    return cid


def line(name, ds_id, x, metrics, limit=5000):
    cid = post("/api/v1/chart/", {"slice_name": name, "viz_type": "echarts_timeseries_line",
                                  "datasource_id": ds_id, "datasource_type": "table",
                                  "params": json.dumps({"viz_type": "echarts_timeseries_line", "x_axis": x,
                                                         "metrics": metrics, "groupby": [], "row_limit": limit})})["id"]
    print(f"  chart '{name}' -> {cid}")
    return cid


print("food charts:")
food = [
    chart("Food · Products by Nutri-Score grade", OFF, "nutriscore_grade", [COUNT("Products")], 10),
    chart("Food · Products by NOVA group", OFF, "nova_group", [COUNT("Products")], 10),
    chart("Food · Top 15 food groups", OFF, "pnns_groups_1", [COUNT("Products")], 15, True),
    chart("Food · Avg energy (kcal/100g) by Nutri-Score", OFF, "nutriscore_grade",
          [SQLM("avg(toFloat64OrNull(energy_kcal_100g))", "Avg kcal/100g")], 10),
    chart("Food · Avg sugar & fat by Nutri-Score", OFF, "nutriscore_grade",
          [SQLM("avg(toFloat64OrNull(sugars_100g))", "Avg sugars/100g"),
           SQLM("avg(toFloat64OrNull(fat_100g))", "Avg fat/100g")], 10),
    chart("Food · USDA foods by data type", USDA, "data_type", [COUNT("Foods")], 20, True),
]
print("music catalog charts:")
musiccat = [
    line("Catalog · Songs per year (UCI)", UCI, "year", [COUNT("Songs")]),
    line("Catalog · Avg timbre[0] over year", UCI, "year", [SQLM("avg(timbre_avg_0)", "Avg timbre 0")]),
    chart("Catalog · MusicBrainz artists by type", MBA, "entity_type", [COUNT("Artists")], 20, True),
    chart("Catalog · MusicBrainz release groups by type", MBR, "entity_type", [COUNT("Release groups")], 20, True),
]


def dashboard(title, chart_ids):
    pos = {"DASHBOARD_VERSION_KEY": "v2",
           "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
           "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
           "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": title}}}
    rows = []
    for i in range(0, len(chart_ids), 2):
        rid = f"ROW-{uuid.uuid4().hex[:8]}"
        kids = []
        for cid in chart_ids[i:i + 2]:
            chid = f"CHART-{uuid.uuid4().hex[:8]}"
            pos[chid] = {"type": "CHART", "id": chid, "children": [], "parents": ["ROOT_ID", "GRID_ID", rid],
                         "meta": {"chartId": cid, "width": 6, "height": 50, "uuid": str(uuid.uuid4())}}
            kids.append(chid)
        pos[rid] = {"type": "ROW", "id": rid, "children": kids, "parents": ["ROOT_ID", "GRID_ID"],
                    "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        rows.append(rid)
    pos["GRID_ID"]["children"] = rows
    did = post("/api/v1/dashboard/",
               {"dashboard_title": title, "position_json": json.dumps(pos), "published": True})["id"]
    print(f"dashboard '{title}' -> {did}")


dashboard("Weyland Food & Nutrition", food)
dashboard("Weyland Music Catalog", musiccat)
print(f"\nDone: {len(food) + len(musiccat)} charts, 2 dashboards. Open {BASE} -> Dashboards.")
