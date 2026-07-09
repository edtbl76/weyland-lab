#!/usr/bin/env python3
"""Seed Superset with Music + Health dashboards over the dbt MARTS (`iceberg.dbt.mart_*`) via the REST API:
registers the 7 marts as Trino datasets, then creates bar/line charts + two dashboards. Brings Superset's data
side level with Lightdash — ad-hoc BI over the curated/tested marts instead of only raw gold.

Prereq: a Superset DB-admin login (the helm-bootstrapped `admin`, separate from Keycloak OIDC). Run from a box
that reaches superset.weyland.lab (workstation/rogueone), `requests` installed:

    SUPERSET_PASSWORD=<pw> python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/superset_seed.py

Env: SUPERSET_URL (default https://superset.weyland.lab), SUPERSET_USER (default admin), SUPERSET_PASSWORD
(default weyland_dev_password), SUPERSET_CA_BUNDLE (default ~/.local/share/mkcert/rootCA.pem), TRINO_DB_NAME
(substring matching the Trino DB connection name, default 'trino').

The 7 marts must exist in `iceberg.dbt` (dbt build) and the Trino connection must reach the `dbt` schema.
Chart `params` mirror the live Superset 6.1.0 schema (echarts_timeseries_bar/line, SIMPLE adhoc metrics).
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

# --- auth: DB login (JWT) + CSRF token (+ session cookie) ---
r = S.post(f"{BASE}/api/v1/security/login",
           json={"username": USER, "password": PW, "provider": "db", "refresh": True})
if not r.ok:
    sys.exit(f"login failed {r.status_code}: {r.text[:300]} — need the Superset DB admin (provider=db), not OIDC")
S.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
r = S.get(f"{BASE}/api/v1/security/csrf_token/")
if not r.ok:
    sys.exit(f"csrf failed {r.status_code}: {r.text[:300]}")
S.headers.update({"X-CSRFToken": r.json()["result"], "Referer": BASE})


def post(path, body):
    r = S.post(f"{BASE}{path}", json=body)
    if not r.ok:
        sys.exit(f"POST {path} -> {r.status_code}: {r.text[:400]}")
    return r.json()


# --- Trino database connection id ---
dbs = S.get(f"{BASE}/api/v1/database/?q=(page_size:200)").json()["result"]
want = os.environ.get("TRINO_DB_NAME", "trino").lower()
trino = next((d for d in dbs if want in d["database_name"].lower()), None)
if not trino:
    sys.exit(f"no Trino DB connection matching {want!r} among: {[d['database_name'] for d in dbs]}")
trino_id = trino["id"]
print(f"trino db id={trino_id} ({trino['database_name']})")

# --- register the 7 marts as datasets (schema dbt), reusing any that already exist ---
MARTS = ["mart_spotify_audio", "mart_genre_audio_profile", "mart_fma_genre_tree", "mart_artist_popularity",
         "mart_state_health_trends", "mart_country_health", "mart_personality_by_country"]
existing = {d["table_name"]: d["id"] for d in S.get(f"{BASE}/api/v1/dataset/?q=(page_size:500)").json()["result"]
            if d.get("schema") == "dbt"}
ds_id = {}
for m in MARTS:
    if m in existing:
        ds_id[m] = existing[m]
        print(f"  dataset {m} (exists) -> {ds_id[m]}")
    else:
        ds_id[m] = post("/api/v1/dataset/", {"database": trino_id, "schema": "dbt", "table_name": m})["id"]
        print(f"  dataset {m} -> {ds_id[m]}")


def M(col, agg, label=None, ctype="DOUBLE"):
    return {"expressionType": "SIMPLE", "column": {"column_name": col, "type": ctype},
            "aggregate": agg, "label": label or f"{agg}({col})", "optionName": f"m_{col}_{agg}".lower()}


def chart(name, mart, viz, x, metrics, limit=5000, order_desc=False):
    params = {"viz_type": viz, "x_axis": x, "metrics": metrics, "groupby": [], "row_limit": limit}
    if order_desc:
        params["order_desc"] = True
    cid = post("/api/v1/chart/", {"slice_name": name, "viz_type": viz, "datasource_id": ds_id[mart],
                                  "datasource_type": "table", "params": json.dumps(params)})["id"]
    print(f"  chart '{name}' -> {cid}")
    return cid


BAR, LINE = "echarts_timeseries_bar", "echarts_timeseries_line"
print("music charts:")
music = [
    chart("Marts · Top 20 artists by plays", "mart_artist_popularity", BAR, "artist_name",
          [M("total_plays", "SUM", "Total plays", "BIGINT")], 20, True),
    chart("Marts · Tracks per genre (top 20)", "mart_spotify_audio", BAR, "track_genre",
          [M("track_id", "COUNT", "Tracks", "VARCHAR")], 20, True),
    chart("Marts · Genre energy vs danceability", "mart_spotify_audio", BAR, "track_genre",
          [M("energy", "AVG"), M("danceability", "AVG")], 20, True),
    chart("Marts · Genre acousticness vs valence", "mart_spotify_audio", BAR, "track_genre",
          [M("acousticness", "AVG"), M("valence", "AVG")], 20, True),
]
print("health charts:")
health = [
    chart("Marts · US chronic conditions over time", "mart_state_health_trends", LINE, "year",
          [M("diabetes_pct", "AVG"), M("asthma_pct", "AVG"), M("copd_pct", "AVG"), M("depression_pct", "AVG")]),
    chart("Marts · Diabetes prevalence by state (top 20)", "mart_state_health_trends", BAR, "state",
          [M("diabetes_pct", "AVG")], 20, True),
    chart("Marts · Life expectancy over time", "mart_country_health", LINE, "year",
          [M("life_expectancy", "AVG"), M("healthy_life_expectancy", "AVG")]),
    chart("Marts · Top 20 countries by life expectancy", "mart_country_health", BAR, "country",
          [M("life_expectancy", "AVG")], 20, True),
    chart("Marts · Obesity vs diabetes by country", "mart_country_health", BAR, "country",
          [M("adult_obesity", "AVG"), M("diabetes_prevalence", "AVG")], 20, True),
    chart("Marts · Personality (OCEAN) by country", "mart_personality_by_country", BAR, "country",
          [M("extraversion", "AVG"), M("openness", "AVG"), M("conscientiousness", "AVG")], 20, True),
]


def dashboard(title, chart_ids):
    """Build a 2-charts-per-row dashboard layout (position_json v2, 12-col grid)."""
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
    did = post("/api/v1/dashboard/",
               {"dashboard_title": title, "position_json": json.dumps(pos), "published": True})["id"]
    print(f"dashboard '{title}' -> {did}")
    return did


dashboard("Weyland Marts — Music", music)
dashboard("Weyland Marts — Health", health)
print(f"\nDone: 7 mart datasets, {len(music) + len(health)} charts, 2 dashboards. Open {BASE} -> Dashboards.")
