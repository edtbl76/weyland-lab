#!/usr/bin/env python3
"""Seed Superset with a Cube SEMANTIC-LAYER dashboard — VIRTUAL datasets over the Cube SQL API (`MEASURE()`), charts,
and a dashboard. Unlike superset_seed.py (physical Trino marts = raw SQL), these consume Cube's GOVERNED metrics:
the measure columns are pre-aggregated by Cube, so Superset just displays them.

Prereq: the Cube DB connection exists in Superset (database_name 'Cube' — see runbooks/cube.md). Run from a box
that reaches superset.weyland.lab (workstation/rogueone), `requests` installed:

    SUPERSET_PASSWORD=<pw> python3 .../scripts/superset_seed_cube.py

Env: SUPERSET_URL (default https://superset.weyland.lab), SUPERSET_USER (admin), SUPERSET_PASSWORD, SUPERSET_CA_BUNDLE.
"""
import json
import os
import sys
import urllib.parse
import uuid

import requests

BASE = os.environ.get("SUPERSET_URL", "https://superset.weyland.lab").rstrip("/")
USER = os.environ.get("SUPERSET_USER", "admin")
PW = os.environ["SUPERSET_PASSWORD"]   # SEC-1: no baked-in fallback — source .env (see .env.example)
_CA = os.environ.get("SUPERSET_CA_BUNDLE") or os.path.expanduser("~/.local/share/mkcert/rootCA.pem")

S = requests.Session()
S.verify = _CA if os.path.exists(_CA) else True
r = S.post(f"{BASE}/api/v1/security/login",
           json={"username": USER, "password": PW, "provider": "db", "refresh": True})
if not r.ok:
    sys.exit(f"login failed {r.status_code}: {r.text[:300]} — need the Superset DB admin (provider=db), not OIDC")
S.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
S.headers.update({"X-CSRFToken": S.get(f"{BASE}/api/v1/security/csrf_token/").json()["result"], "Referer": BASE})


def post(path, body):
    r = S.post(f"{BASE}{path}", json=body)
    if not r.ok:
        sys.exit(f"POST {path} -> {r.status_code}: {r.text[:500]}")
    return r.json()


# --- Cube database connection id ---
dbs = S.get(f"{BASE}/api/v1/database/?q=(page_size:200)").json()["result"]
cube = next((d for d in dbs if d["database_name"].lower() == "cube"), None)
if not cube:
    sys.exit(f"no 'Cube' DB connection among: {[d['database_name'] for d in dbs]}")
cube_id = cube["id"]
print(f"cube db id={cube_id}")

# --- virtual datasets over the cubes (MEASURE() pre-aggregates; each column is one value per group) ---
DATASETS = {
    "cube_genre_audio": "SELECT track_genre, MEASURE(avg_danceability) AS danceability, "
                        "MEASURE(avg_energy) AS energy, MEASURE(avg_valence) AS valence "
                        "FROM spotify_audio GROUP BY track_genre",
    "cube_country_health": "SELECT country, MEASURE(avg_life_expectancy) AS life_expectancy, "
                           "MEASURE(avg_diabetes_prevalence) AS diabetes_prevalence "
                           "FROM country_health GROUP BY country",
    "cube_artist_popularity": "SELECT artist_name, MEASURE(total_plays_sum) AS total_plays "
                              "FROM artist_popularity GROUP BY artist_name",
    "cube_state_health": "SELECT state, MEASURE(avg_diabetes_pct) AS diabetes_pct, "
                         "MEASURE(avg_depression_pct) AS depression_pct FROM state_health_trends GROUP BY state",
    "cube_personality": "SELECT country, MEASURE(avg_openness) AS openness, MEASURE(avg_extraversion) AS extraversion, "
                        "MEASURE(avg_conscientiousness) AS conscientiousness FROM personality_by_country GROUP BY country",
}
def dataset_id_by_name(name):
    q = urllib.parse.quote(f"(filters:!((col:table_name,opr:eq,value:'{name}')),page_size:5)")
    res = S.get(f"{BASE}/api/v1/dataset/?q={q}").json().get("result", [])
    return res[0]["id"] if res else None


ds_id = {}
for name, sql in DATASETS.items():
    did = dataset_id_by_name(name)
    if did:
        ds_id[name] = did
        print(f"  dataset {name} (exists) -> {did}")
        continue
    r = S.post(f"{BASE}/api/v1/dataset/",
               json={"database": cube_id, "schema": "public", "table_name": name, "sql": sql})
    if r.ok:
        ds_id[name] = r.json()["id"]
        print(f"  dataset {name} -> {ds_id[name]}")
    else:  # list-miss race: it exists — look it up rather than die
        did = dataset_id_by_name(name)
        if not did:
            sys.exit(f"dataset {name} -> {r.status_code}: {r.text[:300]}")
        ds_id[name] = did
        print(f"  dataset {name} (found post-422) -> {did}")


def M(col, label=None):
    # measure columns are already aggregated by Cube — AVG of the single per-group value == the value itself.
    return {"expressionType": "SIMPLE", "column": {"column_name": col, "type": "DOUBLE"},
            "aggregate": "AVG", "label": label or col, "optionName": f"m_{col}".lower()}


_charts = {c["slice_name"]: c["id"] for c in S.get(f"{BASE}/api/v1/chart/?q=(page_size:500)").json()["result"]}


def chart(name, ds, x, metrics, limit=25):
    if name in _charts:
        print(f"  chart '{name}' (exists) -> {_charts[name]}")
        return _charts[name]
    params = {"viz_type": "echarts_timeseries_bar", "x_axis": x, "metrics": metrics,
              "groupby": [], "row_limit": limit, "order_desc": True}
    cid = post("/api/v1/chart/", {"slice_name": name, "viz_type": "echarts_timeseries_bar",
                                  "datasource_id": ds_id[ds], "datasource_type": "table",
                                  "params": json.dumps(params)})["id"]
    print(f"  chart '{name}' -> {cid}")
    return cid


print("charts:")
charts = [
    chart("Cube · Danceability & energy by genre", "cube_genre_audio", "track_genre",
          [M("danceability"), M("energy")]),
    chart("Cube · Life expectancy by country", "cube_country_health", "country", [M("life_expectancy")]),
    chart("Cube · Top artists by plays", "cube_artist_popularity", "artist_name", [M("total_plays", "Total plays")]),
    chart("Cube · Diabetes % by US state", "cube_state_health", "state", [M("diabetes_pct")]),
    chart("Cube · OCEAN traits by country", "cube_personality", "country", [M("openness"), M("extraversion")]),
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
            pos[chid] = {"type": "CHART", "id": chid, "children": [],
                         "parents": ["ROOT_ID", "GRID_ID", rid],
                         "meta": {"chartId": cid, "width": 6, "height": 50, "uuid": str(uuid.uuid4())}}
            kids.append(chid)
        pos[rid] = {"type": "ROW", "id": rid, "children": kids, "parents": ["ROOT_ID", "GRID_ID"],
                    "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        rows.append(rid)
    pos["GRID_ID"]["children"] = rows
    body = {"dashboard_title": title, "position_json": json.dumps(pos), "published": True}
    # find-or-update by title (idempotent — don't pile up broken dashboards on re-run)
    dash = next((d for d in S.get(f"{BASE}/api/v1/dashboard/?q=(page_size:200)").json()["result"]
                 if d["dashboard_title"] == title), None)
    if dash:
        did = dash["id"]
        S.put(f"{BASE}/api/v1/dashboard/{did}", json=body)
    else:
        did = post("/api/v1/dashboard/", body)["id"]
    # CRITICAL: set each chart's dashboards relationship — position_json chartId alone doesn't associate them in
    # Superset 6.x, so the frontend renders "no chart definition associated". This is the actual link.
    for cid in chart_ids:
        S.put(f"{BASE}/api/v1/chart/{cid}", json={"dashboards": [did]})
    print(f"dashboard '{title}' -> {did} (linked {len(chart_ids)} charts)")
    return did


dashboard("Weyland — Cube Semantic Layer", charts)
print(f"\nDone: {len(DATASETS)} Cube datasets, {len(charts)} charts, 1 dashboard. Open {BASE} -> Dashboards.")
