"""Weyland Feast feature definitions — two views that together exercise the whole feature-store pattern:

1. track_audio_features (STATIC) — entity `track`, the 11 Spotify audio features (danceability … tempo). No real
   event time (a track's audio doesn't change), so a synthetic event_timestamp. This is the serving/registry
   half: get_online_features(track_id) → the audio vector a recommender consumes.
2. state_health_risk (TIME-VARYING) — entity `state`, event time = the BRFSS survey `Year`, features = the
   crude-prevalence % of four chronic conditions (diabetes/asthma/COPD/depression) per (state, year). Real,
   interpretable, genuinely time/geo-varying — the point-in-time half: get_historical_features joins each label
   AS OF its year with no leakage from future years.

Sources are Postgres tables in the `feast` DB (loaded from silver by feast_ops._load_offline_sources)."""
from datetime import timedelta

from feast import Entity, FeatureService, FeatureView, Field
from feast.infra.offline_stores.contrib.postgres_offline_store.postgres_source import PostgreSQLSource
from feast.types import Float32

track = Entity(name="track", join_keys=["track_id"])
state = Entity(name="state", join_keys=["state"])

_AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
          "acousticness", "instrumentalness", "liveness", "valence", "tempo"]

track_source = PostgreSQLSource(
    name="track_audio_features_src",
    query="SELECT * FROM track_audio_features",
    timestamp_field="event_timestamp",
)
track_audio_features = FeatureView(
    name="track_audio_features",
    entities=[track],
    ttl=timedelta(days=36500),   # static → effectively no expiry
    schema=[Field(name=f, dtype=Float32) for f in _AUDIO],
    source=track_source,
    online=True,
)

state_source = PostgreSQLSource(
    name="state_health_risk_src",
    query="SELECT * FROM state_health_risk",
    timestamp_field="event_timestamp",
)
_CONDITIONS = ["diabetes_pct", "asthma_pct", "copd_pct", "depression_pct"]
state_health_risk = FeatureView(
    name="state_health_risk",
    entities=[state],
    ttl=timedelta(days=36500),
    schema=[Field(name=c, dtype=Float32) for c in _CONDITIONS],
    source=state_source,
    online=True,
)

# FeatureServices = named bundles a model/consumer requests (train/serve on the same definition).
recommender_v1 = FeatureService(name="recommender_v1", features=[track_audio_features])
health_v1 = FeatureService(name="health_v1", features=[state_health_risk])
