"""Music dataset fan-out transform — now just the explicit music DomainConfig over the shared broker.

All mechanism (readers, the 5 format writers, per-file iceberg, size guard, null-coerce, streamed avro,
read-gated allowlists, commit) lives in datasets_lib. This file declares which raw/ folders feed each
format for the music domain; build_transform_assets() turns that into datasets_music_parquet/_arrow/
_avro/_lance/_iceberg + _commit. Allowlists are explicit (the storage grid is a guideline, not config)."""
from .datasets_lib.broker import build_transform_assets
from .datasets_lib.config import DomainConfig

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
)

(
    datasets_music_parquet, datasets_music_arrow, datasets_music_avro,
    datasets_music_lance, datasets_music_iceberg, datasets_music_commit,
) = build_transform_assets(MUSIC_CFG)
