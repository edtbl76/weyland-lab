-- Mart: per-genre audio "signature" — mean + stddev of each of the 11 audio features across mart_spotify_audio.
-- Answers "what does techno vs. jazz sound like on average" and gives the genre classifier an interpretable
-- baseline. One row per genre. A mart built ON a mart (mart_spotify_audio) — the intermediate/mart layering.
{{ config(materialized='table') }}

with tracks as (
    select * from {{ ref('mart_spotify_audio') }}
)

select
    track_genre,
    count(*) as n_tracks,
    avg(danceability) as danceability_mean,
    stddev(danceability) as danceability_std,
    avg(energy) as energy_mean,
    stddev(energy) as energy_std,
    avg(key) as key_mean,
    stddev(key) as key_std,
    avg(loudness) as loudness_mean,
    stddev(loudness) as loudness_std,
    avg(mode) as mode_mean,
    stddev(mode) as mode_std,
    avg(speechiness) as speechiness_mean,
    stddev(speechiness) as speechiness_std,
    avg(acousticness) as acousticness_mean,
    stddev(acousticness) as acousticness_std,
    avg(instrumentalness) as instrumentalness_mean,
    stddev(instrumentalness) as instrumentalness_std,
    avg(liveness) as liveness_mean,
    stddev(liveness) as liveness_std,
    avg(valence) as valence_mean,
    stddev(valence) as valence_std,
    avg(tempo) as tempo_mean,
    stddev(tempo) as tempo_std
from tracks
group by track_genre
