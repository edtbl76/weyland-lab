-- Mart: the FMA genre taxonomy as a clean dimension — genre_id, title, parent (id + title), and a top-level
-- flag. A self-join on parent resolves the parent title. One row per genre. (The cross-dataset genre crosswalk
-- Spotify<->FMA<->GTZAN is a hand-curated seed, deliberately not attempted here.)
{{ config(materialized='table') }}

with g as (
    select
        cast(genre_id as bigint) as genre_id,
        cast(genre_title as varchar) as genre_title,
        cast(genre_parent_id as bigint) as parent_id
    from {{ source('datasets_music', 'fma_genres') }}
    where genre_id is not null
)

select
    g.genre_id,
    g.genre_title,
    nullif(g.parent_id, 0) as parent_id,
    p.genre_title as parent_title,
    (g.parent_id is null or g.parent_id = 0) as is_top_level
from g
left join g as p on g.parent_id = p.genre_id
