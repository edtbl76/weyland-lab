"""Music dataset fan-out transform — now just the explicit music DomainConfig over the shared broker.

All mechanism (readers, the 5 format writers, per-file iceberg, size guard, null-coerce, streamed avro,
read-gated allowlists, commit) lives in datasets_lib. This file declares which raw/ folders feed each
format for the music domain; build_transform_assets() turns that into datasets_music_parquet/_arrow/
_avro/_lance/_iceberg + _commit. Allowlists are explicit (the storage grid is a guideline, not config)."""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.checks import build_asset_checks
from .datasets_lib.config import DomainConfig
from .datasets_lib.loaders import build_store_load_assets

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
        # bipartite listen graph — (:User)-[:PLAYS {play_count}]->(:Artist); the count is an EDGE property
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
    },
)

(
    datasets_music_parquet, datasets_music_arrow, datasets_music_avro,
    datasets_music_lance, datasets_music_iceberg, datasets_music_commit,
) = build_transform_assets(MUSIC_CFG)

datasets_music_checks = build_asset_checks(MUSIC_CFG)
datasets_music_store_assets = build_store_load_assets(MUSIC_CFG)
