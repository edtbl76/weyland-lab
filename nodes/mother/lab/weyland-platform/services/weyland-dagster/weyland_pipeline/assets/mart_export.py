"""dbt-mart training-set export (the trainer-side "dbt as source of truth" payoff, UC-mart).

Lands `iceberg.dbt.mart_spotify_audio` — the TESTED dbt mart — in lakeFS as parquet so the external rogueone
trainer can fit on it via `--source mart`, symmetric with `--source feast`.

**Why this is an in-cluster, MESHED asset and not part of the trainer:** the mart lives in Trino
(`trino.data-mesh.svc`), whose only LAN exposure (`trino.weyland.lab`) is Keycloak forward-auth gated —
programmatic reads are blocked, and the trainer runs external on rogueone. So the privileged Trino read runs
HERE (Dagster is meshed → reaches the Trino coordinator directly, no auth) and the result lands in lakeFS. The
trainer then reads that parquet exactly as it reads the silver/feast parquet. This is the same bridge pattern as
`genre_feast_training_set` — the only difference is the source (dbt mart vs Feast point-in-time join).

The cleaning/dedup/rare-genre filtering that the trainer used to do inline (and the feast asset does on labels)
now lives ONCE in dbt (`mart_spotify_audio`), so this asset just reads + writes — the mart is the source of truth.

See docs/query/dbt-marts.md + docs/runbooks/remote-training.md."""
import io as _bio
import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib import io

_AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
          "acousticness", "instrumentalness", "liveness", "valence", "tempo"]
_REPO = "music"
_DATASET = "mart_spotify_audio"   # the trainer reads music/<branch>/parquet/mart_spotify_audio/


def _trino_conn():
    """The dagster pod is meshed → reaches the in-cluster Trino coordinator directly (no forward-auth).
    The `trino` python client ships with dbt-trino (already installed)."""
    import trino

    return trino.dbapi.connect(
        host=os.environ.get("TRINO_HOST", "trino.data-mesh.svc.cluster.local"),
        port=8080, user="dagster", catalog="iceberg", schema="dbt", http_scheme="http",
    )


@asset(group_name="datasets_music_ml",
       description="dbt-mart CONSUMER (UC-mart): export the TESTED mart iceberg.dbt.mart_spotify_audio (track_id + "
                   "11 audio features + genre, already deduped/cleaned/rare-genre-filtered in dbt) → lakeFS "
                   "music/parquet/mart_spotify_audio/. Runs MESHED in-cluster because Trino's LAN ingress is "
                   "forward-auth gated + the trainer is external; the rogueone trainer then fits it via "
                   "--source mart. Makes the dbt mart — not hand-cleaned silver — the trainer's source of truth.")
def mart_spotify_audio_export(context):
    conn = _trino_conn()
    cols = "track_id, " + ", ".join(_AUDIO) + ", track_genre"
    context.log.info(f"reading iceberg.dbt.mart_spotify_audio ({cols}) via Trino…")
    df = pd.read_sql(f"SELECT {cols} FROM iceberg.dbt.mart_spotify_audio", conn)
    conn.close()
    df["track_id"] = df["track_id"].astype(str)
    for c in _AUDIO:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=_AUDIO + ["track_genre"]).drop_duplicates("track_id")
    context.log.info(f"mart_spotify_audio: {len(df):,} rows / {df['track_genre'].nunique()} genres")

    mc = io.client()
    buf = _bio.BytesIO()
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), buf)
    io.put(mc, _REPO, f"parquet/{_DATASET}/part.parquet", buf.getvalue())

    import lakefs

    lc = lakefs.Client(host=io.endpoint(), username=os.environ["LAKEFS_ACCESS_KEY_ID"],
                       password=os.environ["LAKEFS_SECRET_ACCESS_KEY"])
    br = lakefs.Repository(_REPO, client=lc).branch(io.branch())
    committed, cid = False, ""
    if list(br.uncommitted()):
        ref = br.commit(message="mart_spotify_audio_export (dbt mart → trainer source)",
                        metadata={"producer": "dagster:mart_spotify_audio_export"})
        cid = ref.get_commit().id
        committed = True
        context.log.info(f"lakeFS {_REPO}/{io.branch()}: committed → {cid[:12]}")
    else:
        context.log.info(f"lakeFS {_REPO}/{io.branch()}: no change to commit")

    out = {"rows": len(df), "genres": int(df["track_genre"].nunique()),
           "path": f"lakefs://{_REPO}/{io.branch()}/parquet/{_DATASET}/", "committed": committed}
    return Output(out, metadata={"rows": MetadataValue.int(out["rows"]),
                                 "genres": MetadataValue.int(out["genres"]),
                                 "path": MetadataValue.text(out["path"]),
                                 "commit": MetadataValue.text(cid or "—")})
