#!/usr/bin/env python3
"""Seed Lightdash with starter table-charts (+ a dashboard) over the dbt marts via the REST API — content you can
then `lightdash download` to version as code. Least-effort bootstrap: no UI clicking.

Prereq: mint a Lightdash personal-access-token (Lightdash → Settings → Personal access tokens). Then run from a
box that can reach lightdash.weyland.lab (workstation/rogueone), with `requests` installed:

    LIGHTDASH_TOKEN=<token> python3 lightdash_seed.py

Env: LIGHTDASH_URL (default https://lightdash.weyland.lab), LIGHTDASH_TOKEN (required).

Lightdash field IDs are `<model>_<column-or-metric-name>` — the dimensions are the mart columns, the metrics are
the `meta.metrics` keys we defined in schema.yml (avg_*, total_*_sum, *_count, …). If a POST 400s with
"field not found", refresh the dbt project in Lightdash first (so the metrics exist), or fix the id below.
"""
import os
import sys
import uuid

import requests

BASE = os.environ.get("LIGHTDASH_URL", "https://lightdash.weyland.lab").rstrip("/")
TOKEN = os.environ.get("LIGHTDASH_TOKEN")
if not TOKEN:
    sys.exit("set LIGHTDASH_TOKEN — Lightdash → Settings → Personal access tokens")

# Verify TLS against the mkcert root CA (the LAN wildcard signer) — do NOT disable verification. Override the
# path with LIGHTDASH_CA_BUNDLE if your mkcert CAROOT differs; falls back to system trust if not found.
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


def chart(name, table, dims, metrics, sort=None, limit=25):
    fields = dims + metrics
    mq = {"exploreName": table, "dimensions": dims, "metrics": metrics, "filters": {},
          "sorts": ([{"fieldId": sort, "descending": True}] if sort else []),
          "limit": limit, "tableCalculations": []}
    body = {"name": name, "tableName": table, "metricQuery": mq,
            "chartConfig": {"type": "table", "config": {"showTableNames": False}},
            "tableConfig": {"columnOrder": fields}, "spaceUuid": space}
    cid = api("POST", f"/api/v1/projects/{proj}/saved", json=body)["uuid"]
    print(f"  chart '{name}' -> {cid}")
    return cid


CHARTS = [
    ("Top artists by plays", "mart_artist_popularity",
     ["mart_artist_popularity_artist_name"], ["mart_artist_popularity_total_plays_sum"],
     "mart_artist_popularity_total_plays_sum"),
    ("Genre audio profile", "mart_spotify_audio",
     ["mart_spotify_audio_track_genre"],
     ["mart_spotify_audio_track_count", "mart_spotify_audio_avg_energy", "mart_spotify_audio_avg_danceability"],
     "mart_spotify_audio_track_count"),
    ("State diabetes prevalence", "mart_state_health_trends",
     ["mart_state_health_trends_state"], ["mart_state_health_trends_avg_diabetes_pct"],
     "mart_state_health_trends_avg_diabetes_pct"),
    ("Country life expectancy", "mart_country_health",
     ["mart_country_health_country"], ["mart_country_health_avg_life_expectancy"],
     "mart_country_health_avg_life_expectancy"),
    ("Personality by country", "mart_personality_by_country",
     ["mart_personality_by_country_country"],
     ["mart_personality_by_country_avg_extraversion", "mart_personality_by_country_avg_openness"], None),
]

ids = [chart(*c) for c in CHARTS]

# lay the charts 2-wide on a dashboard (Lightdash grid is 36 cols)
tiles = [{"uuid": str(uuid.uuid4()), "type": "saved_chart",
          "properties": {"savedChartUuid": cid, "belongsToDashboard": False},
          "x": (i % 2) * 18, "y": (i // 2) * 9, "w": 18, "h": 9}
         for i, cid in enumerate(ids)]
dash = api("POST", f"/api/v1/projects/{proj}/dashboards",
           json={"name": "Marts overview", "description": "Starter charts over the dbt marts.",
                 "tiles": tiles, "tabs": [], "spaceUuid": space})
print(f"dashboard 'Marts overview' -> {dash['uuid']}")
print(f"\nDone. Open {BASE} → Spaces. Codify as YAML with `lightdash download`.")
