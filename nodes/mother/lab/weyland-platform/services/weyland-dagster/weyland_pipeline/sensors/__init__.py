"""Sensors for the weyland pipeline.

datasets_music_raw_sensor     — triggers music transform when new raw files land in lakeFS
datasets_music_freshness_sensor — triggers music land job if any asset is stale (>30 days)
datasets_health_freshness_sensor — triggers health land job if any asset is stale (>7 days)
"""
import os
from datetime import datetime, timedelta, timezone

from dagster import AssetKey, DefaultSensorStatus, RunRequest, SkipReason, sensor

from weyland_pipeline.schedules import (
    weyland_datasets_music_transform_job,
    weyland_datasets_music_land_job,
    weyland_datasets_health_land_job,
)

MUSIC_LAND_ASSETS = [
    "datasets_music_spotify_land",
    "datasets_music_fma_tracks_land",
    "datasets_music_fma_genres_land",
    "datasets_music_fma_echonest_land",
    "datasets_music_fma_features_land",
    "datasets_music_uci_year_prediction_land",
    "datasets_music_lastfm_land",
    "datasets_music_musicbrainz_land",
    "datasets_music_gtzan_land",
    "datasets_music_lp_musiccaps_mc_land",
    "datasets_music_lp_musiccaps_mtt_land",
    "datasets_music_audioset_land",
]

HEALTH_LAND_ASSETS = [
    "datasets_health_nhanes_land",
    "datasets_health_big_five_land",
    "datasets_health_who_gho_land",
    "datasets_health_cdc_physical_activity_land",
    "datasets_health_brfss_land",
    "datasets_health_nhis_land",
    "datasets_health_usda_fooddata_land",
    "datasets_health_open_food_facts_land",
]


def _stale_assets(context, asset_names, max_age_days):
    """Return list of asset names that haven't been materialized within max_age_days."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)
    stale = []
    for name in asset_names:
        key = AssetKey([name])
        record = context.instance.get_latest_materialization_event(key)
        if record is None:
            stale.append(name)
        else:
            ts = datetime.fromtimestamp(record.timestamp, tz=timezone.utc)
            if ts < cutoff:
                stale.append(name)
    return stale


@sensor(
    job=weyland_datasets_music_transform_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.STOPPED,
)
def datasets_music_raw_sensor(context):
    from minio import Minio

    client = Minio(
        os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000"),
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )
    bucket = os.environ.get("DATASETS_BUCKET", "datasets")
    domain = os.environ.get("DATASETS_DOMAIN", "music")

    latest = None
    for obj in client.list_objects(bucket, prefix=f"{domain}/raw/", recursive=True):
        if not obj.object_name.endswith(".csv"):
            continue
        stamp = obj.last_modified.isoformat() if obj.last_modified else obj.object_name
        if latest is None or stamp > latest:
            latest = stamp

    if latest is None:
        return SkipReason("no raw CSVs yet")
    if context.cursor == latest:
        return SkipReason("no new raw writes since last run")
    context.update_cursor(latest)
    return RunRequest(run_key=latest)


@sensor(
    job=weyland_datasets_music_land_job,
    minimum_interval_seconds=3600,  # check hourly
    default_status=DefaultSensorStatus.STOPPED,
)
def datasets_music_freshness_sensor(context):
    """Fire the music land job if any music land asset is older than 30 days."""
    stale = _stale_assets(context, MUSIC_LAND_ASSETS, max_age_days=30)
    if not stale:
        return SkipReason("all music land assets are fresh (< 30 days)")
    context.log.info(f"Stale music assets: {stale}")
    return RunRequest(run_key=f"music_freshness_{datetime.now(tz=timezone.utc).date()}")


@sensor(
    job=weyland_datasets_health_land_job,
    minimum_interval_seconds=3600,  # check hourly
    default_status=DefaultSensorStatus.STOPPED,
)
def datasets_health_freshness_sensor(context):
    """Fire the health land job if any health land asset is older than 7 days."""
    stale = _stale_assets(context, HEALTH_LAND_ASSETS, max_age_days=7)
    if not stale:
        return SkipReason("all health land assets are fresh (< 7 days)")
    context.log.info(f"Stale health assets: {stale}")
    return RunRequest(run_key=f"health_freshness_{datetime.now(tz=timezone.utc).date()}")
