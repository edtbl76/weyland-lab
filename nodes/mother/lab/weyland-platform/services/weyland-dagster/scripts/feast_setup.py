"""Feast setup — ensure the `feast` Postgres DB, load the two offline source tables from silver, then apply +
materialize (offline Postgres → Valkey online). Run in the dagster-user-code pod (has silver access + PG/Valkey
env + the feast_repo). Idempotent (source tables replaced, apply/materialize re-run safely).

  kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/feast_setup.py

Sources built:
  track_audio_features  — spotify_tracks: track_id + 11 audio features + a synthetic event_timestamp (static).
  state_health_risk     — brfss: crude-prevalence % of 4 chronic conditions per (state, year), event_timestamp=Year.
"""
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

import pandas as pd
import sqlalchemy

sys.path.insert(0, "/app")
from weyland_pipeline.assets.datasets_lib import io  # noqa: E402

FEAST_REPO = os.environ.get("FEAST_REPO", "/app/feast_repo")
_PW = os.environ["WEYLAND_PG_PASSWORD"]
_HOST = os.environ.get("WEYLAND_PG_HOST", "weyland-postgres.weyland.svc.cluster.local")
_AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
          "acousticness", "instrumentalness", "liveness", "valence", "tempo"]
_CONDS = {"diabetes_pct": ("Diabetes", "Yes"), "asthma_pct": ("Asthma", "Yes"),
          "copd_pct": ("COPD", "Yes"), "depression_pct": ("Depression", "Yes")}
# B113 Phase 5 — the finance price feature view (entity ticker, time-varying on `date`).
_PRICE_FEATS = ["ret_1d", "ret_5d", "ret_20d", "vol_5d", "vol_10d", "vol_20d",
                "volume_ratio", "range_20d", "sma_ratio_20d"]


def _pg_url(db):
    return f"postgresql://weyland:{_PW}@{_HOST}:5432/{db}"


def _ensure_feast_db():
    eng = sqlalchemy.create_engine(_pg_url("weyland"), isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        if not c.execute(sqlalchemy.text("SELECT 1 FROM pg_database WHERE datname='feast'")).scalar():
            c.execute(sqlalchemy.text("CREATE DATABASE feast"))
            print("created feast DB")
    eng.dispose()


def _read_silver(mc, repo, dataset):
    frames = []
    for obj in mc.list_objects(repo, prefix=f"{io.branch()}/parquet/{dataset}/", recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        tmp = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        tmp.close()
        try:
            mc.fget_object(repo, obj.object_name, tmp.name)
            frames.append(pd.read_parquet(tmp.name))
        finally:
            os.unlink(tmp.name)
    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


def _trino_conn():
    """Read the dbt marts straight from Trino (iceberg.dbt) — the dagster pod is meshed, so it reaches the
    in-cluster Trino coordinator. dbt-trino already installs the `trino` client."""
    import trino

    return trino.dbapi.connect(
        host=os.environ.get("TRINO_HOST", "trino.data-mesh.svc.cluster.local"),
        port=8080, user="feast", catalog="iceberg", schema="dbt", http_scheme="http",
    )


def _load_offline_sources():
    """Load Feast's offline source tables FROM the dbt marts (the tested source of truth) instead of re-cleaning
    silver here. The cleaning/aggregation now lives ONCE in dbt (mart_spotify_audio / mart_state_health_trends);
    this just reads those marts + adds Feast's event_timestamp. Run `dbt build` first so the marts exist."""
    eng = sqlalchemy.create_engine(_pg_url("feast"))
    conn = _trino_conn()

    # track_audio_features <- mart_spotify_audio (deduped, cleaned, rare genres dropped — all done in dbt now)
    t = pd.read_sql("SELECT track_id, " + ", ".join(_AUDIO) + " FROM iceberg.dbt.mart_spotify_audio", conn)
    t["track_id"] = t["track_id"].astype(str)
    for c in _AUDIO:
        t[c] = pd.to_numeric(t[c], errors="coerce").astype("float32")
    t["event_timestamp"] = pd.Timestamp("2020-01-01", tz="UTC")
    t.to_sql("track_audio_features", eng, if_exists="replace", index=False)
    print(f"track_audio_features: {len(t)} rows (from dbt iceberg.dbt.mart_spotify_audio)")

    # state_health_risk <- mart_state_health_trends (the BRFSS Overall/Yes pivot now lives in dbt, not this script)
    hr = pd.read_sql(
        "SELECT state, year, diabetes_pct, asthma_pct, copd_pct, depression_pct "
        "FROM iceberg.dbt.mart_state_health_trends", conn)
    hr["state"] = hr["state"].astype(str)
    hr["event_timestamp"] = pd.to_datetime(hr["year"].astype(int).astype(str) + "-01-01", utc=True)
    hr = hr.drop(columns=["year"])
    for col in _CONDS:
        hr[col] = pd.to_numeric(hr[col], errors="coerce").astype("float32")
    hr.to_sql("state_health_risk", eng, if_exists="replace", index=False)
    print(f"state_health_risk: {len(hr)} rows ({hr['state'].nunique()} states) (from dbt mart_state_health_trends)")

    # price_features <- mart_price_features (per-(ticker,date) trailing features for the Phase-5 ML lane). The
    # feature values are time-varying (unlike the static audio features), so event_timestamp = the trading date,
    # which is what makes Feast's point-in-time join meaningful here. ~hundreds of thousands of rows → chunked.
    pf = pd.read_sql(
        "SELECT ticker, date, " + ", ".join(_PRICE_FEATS) + " FROM iceberg.dbt.mart_price_features", conn)
    pf["ticker"] = pf["ticker"].astype(str)
    pf["event_timestamp"] = pd.to_datetime(pf["date"], utc=True)
    pf = pf.drop(columns=["date"])
    for col in _PRICE_FEATS:
        pf[col] = pd.to_numeric(pf[col], errors="coerce").astype("float32")
    pf.to_sql("price_features", eng, if_exists="replace", index=False, chunksize=5000)
    print(f"price_features: {len(pf)} rows ({pf['ticker'].nunique()} tickers) (from dbt mart_price_features)")

    conn.close()
    eng.dispose()


def main():
    _ensure_feast_db()
    _load_offline_sources()
    # apply (register definitions.py) + materialize (offline PG → Valkey) via the CLI (auto-discovers the repo).
    subprocess.run(["feast", "-c", FEAST_REPO, "apply"], check=True)
    subprocess.run(["feast", "-c", FEAST_REPO, "materialize-incremental",
                    datetime.now(timezone.utc).isoformat()], check=True)
    print("feast apply + materialize done")


if __name__ == "__main__":
    main()
