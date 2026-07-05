# Feast — query cookbook (feature serving)

Feast is a **feature store**, not a queryable DB — you don't SQL it, you *retrieve features by entity key*. Two
capabilities: **online** (low-latency, latest value, from Valkey) and **historical/point-in-time** (leakage-free
training sets, from the Postgres offline store). Two feature views: `track_audio_features` (entity `track`, 11
Spotify audio features — static) and `state_health_risk` (entity `state`, chronic-condition prevalence %s per
year — time-varying). See [../runbooks/datasets-hydration.md](../runbooks/datasets-hydration.md) +
[../diagrams/flow-feast.md](../diagrams/flow-feast.md).

**Access:**
- **REST** — `https://feast.weyland.lab` (LAN, no auth — it's an API) or in-cluster `feast-server.data-mesh.svc:6566`.
- **OpenAPI / Swagger** — `https://feast.weyland.lab/docs` (interactive) · `/openapi.json` (spec). `feast serve`
  is FastAPI, so these are auto-generated.
- **SDK** — `FeatureStore(repo_path="/app/feast_repo")` in the dagster-user-code pod (has feast + the repo).

## Online — REST (`POST /get-online-features`)
Serve latest features by entity key (the low-latency capability):
```
curl -sk https://feast.weyland.lab/get-online-features -H 'Content-Type: application/json' -d '{
  "features": ["state_health_risk:diabetes_pct","state_health_risk:asthma_pct","state_health_risk:copd_pct"],
  "entities": {"state": ["CA","NY","TX"]}
}'
```
By a **feature service** (a named bundle a consumer requests) instead of listing features:
```
curl -sk https://feast.weyland.lab/get-online-features -H 'Content-Type: application/json' -d '{
  "feature_service": "health_v1", "entities": {"state": ["CA","FL"]}
}'
```
Track audio features (the recommender-shaped view):
```
curl -sk https://feast.weyland.lab/get-online-features -H 'Content-Type: application/json' -d '{
  "feature_service": "recommender_v1", "entities": {"track_id": ["<a track_id>"]}
}'
```

## Online — SDK
```python
from feast import FeatureStore
fs = FeatureStore(repo_path="/app/feast_repo")
fs.get_online_features(
    features=["state_health_risk:diabetes_pct","state_health_risk:asthma_pct"],
    entity_rows=[{"state":"CA"},{"state":"NY"}],
).to_dict()
```

## Point-in-time — historical (SDK) — the capability that justifies a feature store
Each row is joined **as of its own timestamp** — no leakage from future surveys. Note CA-2013 ≠ CA-2019:
```python
import pandas as pd
edf = pd.DataFrame({"state":["CA","CA","NY"],
                    "event_timestamp": pd.to_datetime(["2013-06-01","2019-06-01","2016-06-01"], utc=True)})
fs.get_historical_features(entity_df=edf,
    features=["state_health_risk:diabetes_pct","state_health_risk:asthma_pct"]).to_df()
```

## Materialize / apply (rebuild)
`scripts/feast_setup.py` (in the dagster pod) reloads the offline sources from silver → `feast apply` →
`feast materialize-incremental`. Re-run after silver changes:
```
kubectl -n weyland exec -i deploy/dagster-user-code -- python - < ~/weyland-dagster/scripts/feast_setup.py
```

## Feast-isms
- **Don't query Valkey directly** — Feast stores features there in its own binary encoding (serialized entity
  keys + protobuf values); you'll see blobs, not `diabetes_pct=12.6`. Retrieve via the API/SDK, not Redis.
- **The registry (Postgres) is on the serving path** — every `FeatureStore` init reads it, so online serving is
  Valkey + Postgres, not pure Valkey. The feast-server pod is meshed for STRICT-mTLS Postgres.
- **A feature service** (`recommender_v1`/`health_v1`) is the unit a consumer requests — one definition serves
  both training (`get_historical_features`) and serving (`get_online_features`) → no train/serve skew.
