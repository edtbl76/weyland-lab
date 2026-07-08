-- Mart: analysis- and ML-ready Spotify audio features. One row per track (the raw set repeats a track_id across
-- genres), rare genres (< 20 tracks) dropped so a stratified split + per-class metrics are well-defined. This is
-- the TESTED, documented, lineage-tracked source the genre classifier + Feast `track_audio_features` should read
-- — replacing the ad-hoc `_read_spotify` cleaning in the trainer / feast_setup. Expect ~89.7k rows / 113 genres.
{{ config(materialized='table') }}

with tracks as (
    select * from {{ ref('stg_spotify_tracks') }}
),

-- collapse to one row per track_id (deterministic pick by genre)
deduped as (
    select
        *,
        row_number() over (partition by track_id order by track_genre) as _rn
    from tracks
),

-- how many tracks per genre (after dedup) — used to drop ultra-rare genres
genre_counts as (
    select track_genre, count(*) as n_tracks
    from deduped
    where _rn = 1
    group by track_genre
)

select
    d.track_id,
    d.track_genre,
    d.danceability,
    d.energy,
    d.key,
    d.loudness,
    d.mode,
    d.speechiness,
    d.acousticness,
    d.instrumentalness,
    d.liveness,
    d.valence,
    d.tempo
from deduped d
join genre_counts g on d.track_genre = g.track_genre
where d._rn = 1
  and g.n_tracks >= 20
