#!/usr/bin/env python3
"""Seed Lightdash with a best-case set of charts + two dashboards over the dbt marts via the REST API — content
you can then `lightdash download` to version as code. No UI clicking.

Prereq: mint a Lightdash personal-access-token (Lightdash -> Settings -> Personal access tokens), and make sure the
dbt project has been refreshed so the 44 meta.metrics exist. Then run from a box that reaches lightdash.weyland.lab
(workstation/rogueone), with `requests` installed:

    LIGHTDASH_TOKEN=<token> python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/lightdash_seed.py

Env: LIGHTDASH_URL (default https://lightdash.weyland.lab), LIGHTDASH_TOKEN (required), LIGHTDASH_CA_BUNDLE
(default ~/.local/share/mkcert/rootCA.pem).

Lightdash field IDs are `<model>_<column-or-metric-name>` — dimensions are the mart columns, metrics are the
meta.metrics keys from schema.yml (avg_*, total_*_sum, *_count, ...). Re-running creates duplicate charts; delete
the old ones in the UI if you re-run. If a POST 400s "field not found", the dbt refresh hasn't landed the metrics.
"""
import os
import sys
import uuid

import requests

BASE = os.environ.get("LIGHTDASH_URL", "https://lightdash.weyland.lab").rstrip("/")
TOKEN = os.environ.get("LIGHTDASH_TOKEN")
if not TOKEN:
    sys.exit("set LIGHTDASH_TOKEN — Lightdash -> Settings -> Personal access tokens")

# Verify TLS against the mkcert root CA (the LAN wildcard signer) — do NOT disable verification.
_CA = os.environ.get("LIGHTDASH_CA_BUNDLE") or os.path.expanduser("~/.local/share/mkcert/rootCA.pem")

S = requests.Session()
S.verify = _CA if os.path.exists(_CA) else True
S.headers.update({"Authorization": f"ApiKey {TOKEN}", "Content-Type": "application/json"})


def api(method, path, **kw):
    r = S.request(method, f"{BASE}{path}", **kw)
    if not r.ok:
        sys.exit(f"{method} {path} -> {r.status_code}: {r.text[:600]}")
    return r.json()["results"]


proj = api("GET", "/api/v1/org/projects")[0]["projectUuid"]
spaces = api("GET", f"/api/v1/projects/{proj}/spaces")
space = (spaces[0]["uuid"] if spaces
         else api("POST", f"/api/v1/projects/{proj}/spaces", json={"name": "Marts", "isPrivate": False})["uuid"])
print(f"project={proj}  space={space}")


def cartesian(name, table, x, ys, kind="bar", sort=None, desc=True, limit=25, flip=False):
    """Create one bar/line saved chart. x = dimension field id, ys = list of metric field ids."""
    metrics = list(ys)
    mq = {"exploreName": table, "dimensions": [x], "metrics": metrics, "filters": {},
          "sorts": [{"fieldId": (sort or x), "descending": desc}], "limit": limit, "tableCalculations": []}
    series = [{"encode": {"xRef": {"field": x}, "yRef": {"field": y}}, "type": kind} for y in ys]
    cfg = {"type": "cartesian", "config": {
        "layout": {"xField": x, "yField": metrics, "flipAxes": flip},
        "eChartsConfig": {"series": series}}}
    body = {"name": name, "tableName": table, "metricQuery": mq, "chartConfig": cfg,
            "tableConfig": {"columnOrder": [x] + metrics}, "spaceUuid": space}
    cid = api("POST", f"/api/v1/projects/{proj}/saved", json=body)["uuid"]
    print(f"  chart '{name}' -> {cid}")
    return cid


def dashboard(name, description, chart_ids):
    tiles = [{"uuid": str(uuid.uuid4()), "type": "saved_chart",
              "properties": {"savedChartUuid": cid, "belongsToDashboard": False},
              "x": (i % 2) * 18, "y": (i // 2) * 9, "w": 18, "h": 9}
             for i, cid in enumerate(chart_ids)]
    did = api("POST", f"/api/v1/projects/{proj}/dashboards",
              json={"name": name, "description": description, "tiles": tiles, "tabs": [], "spaceUuid": space})["uuid"]
    print(f"dashboard '{name}' -> {did}")
    return did


# ---- field id helpers: <table>_<field> ----
def f(table, field):
    return f"{table}_{field}"


AP, SP = "mart_artist_popularity", "mart_spotify_audio"
SH, CH, PC = "mart_state_health_trends", "mart_country_health", "mart_personality_by_country"

print("music charts:")
music = [
    cartesian("Top 20 artists by plays", AP, f(AP, "artist_name"), [f(AP, "total_plays_sum")],
              sort=f(AP, "total_plays_sum"), limit=20, flip=True),
    cartesian("Top 20 artists by listeners", AP, f(AP, "artist_name"), [f(AP, "total_listeners")],
              sort=f(AP, "total_listeners"), limit=20, flip=True),
    cartesian("Tracks per genre (top 20)", SP, f(SP, "track_genre"), [f(SP, "track_count")],
              sort=f(SP, "track_count"), limit=20, flip=True),
    cartesian("Genre energy vs danceability", SP, f(SP, "track_genre"),
              [f(SP, "avg_energy"), f(SP, "avg_danceability")], sort=f(SP, "avg_energy"), limit=20),
    cartesian("Genre acousticness vs valence", SP, f(SP, "track_genre"),
              [f(SP, "avg_acousticness"), f(SP, "avg_valence")], sort=f(SP, "avg_acousticness"), limit=20),
]

print("health charts:")
health = [
    cartesian("US chronic conditions over time", SH, f(SH, "year"),
              [f(SH, "avg_diabetes_pct"), f(SH, "avg_asthma_pct"), f(SH, "avg_copd_pct"), f(SH, "avg_depression_pct")],
              kind="line", sort=f(SH, "year"), desc=False, limit=500),
    cartesian("Diabetes prevalence by state (top 20)", SH, f(SH, "state"), [f(SH, "avg_diabetes_pct")],
              sort=f(SH, "avg_diabetes_pct"), limit=20, flip=True),
    cartesian("Life expectancy over time (global)", CH, f(CH, "year"),
              [f(CH, "avg_life_expectancy"), f(CH, "avg_healthy_life_expectancy")],
              kind="line", sort=f(CH, "year"), desc=False, limit=500),
    cartesian("Top 20 countries by life expectancy", CH, f(CH, "country"), [f(CH, "avg_life_expectancy")],
              sort=f(CH, "avg_life_expectancy"), limit=20, flip=True),
    cartesian("Obesity vs diabetes prevalence by country", CH, f(CH, "country"),
              [f(CH, "avg_adult_obesity"), f(CH, "avg_diabetes_prevalence")],
              sort=f(CH, "avg_adult_obesity"), limit=20),
    cartesian("Smoking vs alcohol by country", CH, f(CH, "country"),
              [f(CH, "avg_tobacco_smoking"), f(CH, "avg_alcohol_consumption")],
              sort=f(CH, "avg_tobacco_smoking"), limit=20),
    cartesian("Personality (OCEAN) by country", PC, f(PC, "country"),
              [f(PC, "avg_extraversion"), f(PC, "avg_openness"), f(PC, "avg_conscientiousness")],
              sort=f(PC, "avg_extraversion"), limit=20),
]

dashboard("Music — marts overview", "Artist popularity + genre audio signatures over the dbt marts.", music)
dashboard("Health — marts overview", "Chronic-condition trends, country health indicators, and personality.", health)

print(f"\nDone: {len(music) + len(health)} charts + 2 dashboards. Open {BASE} -> Spaces.")
print("Codify as YAML with `lightdash download`.")
