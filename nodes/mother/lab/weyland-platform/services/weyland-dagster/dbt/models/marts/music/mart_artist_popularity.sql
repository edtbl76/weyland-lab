-- Mart: per-artist popularity from Last.fm — total plays + distinct listeners, one row per artist. Last.fm
-- carries musicbrainz_artist_id, so we left-join MusicBrainz on the mbid (clean, not a fuzzy name match) for a
-- canonical URL. One row per artist_name.
{{ config(materialized='table') }}

with plays as (
    select
        musicbrainz_artist_id as mbid,
        artist_name,
        user_id,
        play_count
    from {{ source('datasets_music', 'lastfm') }}
    where artist_name is not null
),

artist_agg as (
    select
        artist_name,
        max(mbid) as mbid,
        sum(play_count) as total_plays,
        count(distinct user_id) as n_listeners
    from plays
    group by artist_name
),

mb as (
    select mbid, max(url) as musicbrainz_url
    from {{ source('datasets_music', 'musicbrainz_artist') }}
    where mbid is not null
    group by mbid
)

select
    a.artist_name,
    a.mbid,
    a.total_plays,
    a.n_listeners,
    mb.musicbrainz_url
from artist_agg a
left join mb on a.mbid = mb.mbid
