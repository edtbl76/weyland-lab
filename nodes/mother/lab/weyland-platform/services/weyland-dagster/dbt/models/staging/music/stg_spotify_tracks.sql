-- Staging: Spotify tracks from the Iceberg gold. Thin — select + cast the 11 audio features + genre + id,
-- drop rows missing an id or label. No dedup/business logic (that lives in the mart).
with src as (
    select * from {{ source('datasets_music', 'spotify_tracks') }}
)
select
    cast(track_id         as varchar) as track_id,
    cast(track_genre      as varchar) as track_genre,
    cast(danceability     as double)  as danceability,
    cast(energy           as double)  as energy,
    cast(key              as double)  as key,
    cast(loudness         as double)  as loudness,
    cast(mode             as double)  as mode,
    cast(speechiness      as double)  as speechiness,
    cast(acousticness     as double)  as acousticness,
    cast(instrumentalness as double)  as instrumentalness,
    cast(liveness         as double)  as liveness,
    cast(valence          as double)  as valence,
    cast(tempo            as double)  as tempo
from src
where track_id is not null
  and track_genre is not null
