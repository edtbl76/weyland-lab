"""Music dataset fan-out transform — now just the explicit music DomainConfig over the shared broker.

All mechanism (readers, the 5 format writers, per-file iceberg, size guard, null-coerce, streamed avro,
read-gated allowlists, commit) lives in datasets_lib. This file declares which raw/ folders feed each
format for the music domain; build_transform_assets() turns that into datasets_music_parquet/_arrow/
_avro/_lance/_iceberg + _commit. Allowlists are explicit (the storage grid is a guideline, not config)."""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.loaders import build_store_load_assets
from .datasets_lib.streaming_producer import build_stream_produce_assets

# parquet/arrow/avro/iceberg cover every music dataset; lance is selective (grid: skip fma_genres, lastfm,
# musicbrainz, lp_musiccaps_* — row-heavy / no embedding value). The allowlist also fences out any stale
# raw/ folders (e.g. a renamed-away msd/) so they never reach the silver/gold layers.
_ALL = frozenset({
    "spotify_tracks", "fma_tracks", "fma_genres", "fma_echonest", "fma_features",
    "uci_year_prediction", "lastfm", "musicbrainz", "gtzan",
    "lp_musiccaps_mc", "lp_musiccaps_mtt", "audioset",
})
_LANCE = frozenset({
    "spotify_tracks", "fma_tracks", "fma_echonest", "fma_features",
    "uci_year_prediction", "gtzan", "audioset",
})

MUSIC_CFG = DomainConfig(
    domain="music",
    repo="music",
    namespace="datasets_music",
    group_name="datasets_music",
    land_deps=(
        "datasets_music_spotify_land", "datasets_music_fma_tracks_land",
        "datasets_music_fma_genres_land", "datasets_music_fma_echonest_land",
    ),
    parquet_allow=_ALL, arrow_allow=_ALL, avro_allow=_ALL, iceberg_allow=_ALL,
    lance_allow=_LANCE,
    # Cassandra (grid=Y): uci_year_prediction + lastfm — the music domain's first Tier-2 store loaders.
    # Partition key = a natural column (query-first): uci by year (the prediction target), lastfm by user
    # (lifetime user↔artist playcounts — no timestamps, so partition-by-user, not a time series). Guesses
    # fall back to a row_id dump + a logged column list if the silver column name differs.
    cassandra_allow={"uci_year_prediction": "year", "lastfm": "user_id"},
    # ClickHouse (grid=Y, "search"/analytics): fma_tracks, uci, musicbrainz, lp_musiccaps_mc/mtt, audioset.
    clickhouse_allow=frozenset({
        "fma_tracks", "uci_year_prediction", "musicbrainz",
        "lp_musiccaps_mc", "lp_musiccaps_mtt", "audioset",
    }),
    # OpenSearch (grid=Y, similarity/embedding search): the audio-feature + caption sets. Doc-per-row index.
    opensearch_allow=frozenset({
        "spotify_tracks", "fma_tracks", "fma_echonest", "fma_features", "uci_year_prediction",
        "gtzan", "lp_musiccaps_mc", "lp_musiccaps_mtt", "audioset",
    }),
    # Neo4j (grid=Y): the relationship-shaped music sets — MODELED as graphs, not flat dumps. Starting with the
    # two cleanest; fma_tracks / musicbrainz / audioset are follow-on GraphSpecs. Column guesses fall back to a
    # logged column list + 0 rows if the silver name differs (the loader logs columns on every dataset).
    neo4j_allow={
        # genre taxonomy tree — one label, self-referential edge (child.genre_id → parent.genre_parent_id).
        # Silver columns are genre_-prefixed: genre_id, genre_title, genre_handle, genre_color, genre_parent_id.
        "fma_genres": {
            "nodes": [{"label": "Genre", "key": "genre_id",
                       "props": ["genre_title", "genre_handle", "genre_color"]}],
            "edges": [{"rel": "SUBGENRE_OF",
                       "src": ("Genre", "genre_id", "genre_id"),
                       "dst": ("Genre", "genre_id", "genre_parent_id"),
                       "props": []}],
        },
        # bipartite listen graph — (:User)-[:PLAYS {play_count}]->(:Artist); the count is an EDGE property.
        # Full ~17M PLAYS (no cap) — needs the 4h run timeout + 2G neo4j pagecache to complete.
        "lastfm": {
            "nodes": [
                {"label": "User", "key": "user_id", "props": ["gender", "age", "country"]},
                {"label": "Artist", "key": "name", "col": "artist_name", "props": []},
            ],
            "edges": [{"rel": "PLAYS",
                       "src": ("User", "user_id", "user_id"),
                       "dst": ("Artist", "name", "artist_name"),
                       "props": ["play_count"]}],
        },
        # audio-event graph — (:Clip)-[:HAS_LABEL]->(:Label). human_labels is a stringified list
        # ("['Speech', 'Inside, small room']"), so dst_list parses it in Python (ast.literal_eval — keeps
        # commas inside a label) and UNWINDs one edge per label (dst MERGE'd per element).
        "audioset": {
            "nodes": [{"label": "Clip", "key": "video_id"}],
            "edges": [{"rel": "HAS_LABEL",
                       "src": ("Clip", "video_id", "video_id"),
                       "dst": ("Label", "name", "human_labels"),
                       "dst_list": True}],
        },
        # track graph — (:Track)-[:BY]->(:Artist), -[:ON]->(:Album), -[:IN_GENRE]->(:Genre). Artist is keyed by
        # name so tracks attach to the SAME :Artist nodes lastfm created (unifying the graphs); IN_GENRE links
        # into the fma_genres :Genre tree (track_genres is a stringified list-of-dicts → dst_list_key pulls each
        # genre_id, coerced to int to match the tree's node key). clear_labels omits Artist AND Genre so a
        # rebuild never wipes lastfm's PLAYS graph or the genre tree (DETACH DELETE Track clears its own edges).
        "fma_tracks": {
            "clear_labels": ["Track", "Album"],
            "nodes": [
                {"label": "Track", "key": "track_id",
                 "props": ["track_title", "track_listens", "track_favorites", "track_duration"]},
                {"label": "Artist", "key": "name", "col": "artist_name"},
                {"label": "Album", "key": "album_id", "props": ["album_title"]},
            ],
            "edges": [
                {"rel": "BY", "src": ("Track", "track_id", "track_id"),
                 "dst": ("Artist", "name", "artist_name")},
                {"rel": "ON", "src": ("Track", "track_id", "track_id"),
                 "dst": ("Album", "album_id", "album_id")},
                {"rel": "IN_GENRE", "src": ("Track", "track_id", "track_id"),
                 "dst": ("Genre", "genre_id", "track_genres"),
                 "dst_list": True, "dst_list_key": "genre_id"},
            ],
        },
        # NOT modeled: musicbrainz (flat mbid/text/entity_type dictionary — no inter-row relationships → grid N).
    },
    # Qdrant + Weaviate (grid=Y, identical sets): audio-feature vectors (z-scored) + caption text vectors (bge).
    # Dropped: fma_tracks (metadata, not features — audio-sim is fma_features/echonest via track_id), gtzan was
    # fixed to a real feature matrix (librosa extraction in the land). open_food_facts → B78 (4.5M, capped).
    vector_allow={
        "fma_features": {"numeric_exclude": ["track_id"], "id": "track_id"},                       # 518-dim
        "fma_echonest": {"numeric_exclude": ["track_id"], "id": "track_id",                        # ~244-dim
                         "payload": ["echonest_metadata_artist_name", "echonest_metadata_album_name"]},
        "uci_year_prediction": {"numeric_exclude": ["year"], "payload": ["year"]},                 # 90-dim timbre
        "spotify_tracks": {"numeric": ["danceability", "energy", "key", "loudness", "mode", "speechiness",
                                       "acousticness", "instrumentalness", "liveness", "valence", "tempo"],
                           "id": "track_id", "payload": ["track_name", "artists", "track_genre"]},   # 11-dim
        "gtzan": {"numeric_exclude": ["label"], "payload": ["genre"]},                              # ~53-dim librosa
        "lp_musiccaps_mc": {"text": ["caption_ground_truth"], "id": "ytid",
                            "payload": ["caption_summary", "aspect_list"]},                          # 384-dim bge
        "lp_musiccaps_mtt": {"text": ["caption_writing"], "payload": ["title", "artist_name", "tag_top50"]},
        "audioset": {"text": ["human_labels"], "id": "video_id"},
    },
    # Redpanda (grid=Y, stream-shaped): lastfm listen events → Avro topic, keyed by user_id (same-user events
    # land on one partition). ~14M rows capped to 100k for the demo replay ("Avro in motion", not a bulk dump).
    stream_allow={
        "lastfm": {"key": "user_id", "cap": 100_000},
    },
)

(
    datasets_music_parquet, datasets_music_arrow, datasets_music_avro,
    datasets_music_lance, datasets_music_iceberg, datasets_music_commit,
) = build_transform_assets(MUSIC_CFG)

datasets_music_checks = build_asset_checks(MUSIC_CFG)
datasets_music_store_assets = build_store_load_assets(MUSIC_CFG)
datasets_music_stream_assets = build_stream_produce_assets(MUSIC_CFG)
