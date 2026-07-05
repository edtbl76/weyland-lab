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


def _load_offline_sources():
    mc = io.client()
    eng = sqlalchemy.create_engine(_pg_url("feast"))

    sp = _read_silver(mc, "music", "spotify_tracks")
    cols = ["track_id"] + [c for c in _AUDIO if c in sp.columns]
    t = sp[cols].dropna(subset=["track_id"]).drop_duplicates("track_id").copy()
    t["track_id"] = t["track_id"].astype(str)
    for c in _AUDIO:
        if c in t.columns:
            t[c] = pd.to_numeric(t[c], errors="coerce").astype("float32")
    t["event_timestamp"] = pd.Timestamp("2020-01-01", tz="UTC")
    t.to_sql("track_audio_features", eng, if_exists="replace", index=False)
    print(f"track_audio_features: {len(t)} rows")

    b = _read_silver(mc, "health", "brfss")
    b = b[b["Break_Out"] == "Overall"].copy()
    b["Data_value"] = pd.to_numeric(b["Data_value"], errors="coerce")
    parts = []
    for col, (topic, resp) in _CONDS.items():
        sub = b[(b["Topic"] == topic) & (b["Response"] == resp)]
        parts.append(sub.groupby(["Locationabbr", "Year"])["Data_value"].mean().rename(col))
    hr = pd.concat(parts, axis=1).reset_index().rename(columns={"Locationabbr": "state"})
    hr["state"] = hr["state"].astype(str)
    hr["event_timestamp"] = pd.to_datetime(hr["Year"].astype(int).astype(str) + "-01-01", utc=True)
    hr = hr.drop(columns=["Year"])
    for col in _CONDS:
        hr[col] = hr[col].astype("float32")
    hr.to_sql("state_health_risk", eng, if_exists="replace", index=False)
    print(f"state_health_risk: {len(hr)} rows ({hr['state'].nunique()} states)")
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
