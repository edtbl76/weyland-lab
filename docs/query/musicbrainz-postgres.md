# MusicBrainz Postgres — query cookbook

**Connect:** `musicbrainz-postgres.data-mesh.svc:5432`, db `musicbrainz_db`, schema `musicbrainz`
(user `musicbrainz` / its password). IntelliJ → PostgreSQL driver, port-forward the svc `5432`. In-pod:
`kubectl -n data-mesh exec -it deploy/musicbrainz-postgres -- psql -U musicbrainz musicbrainz_db`.

This is the **full native `mbdump`** — 2.9M artists, 39.3M recordings, 1.1M links — the real MusicBrainz schema
(distinct from the small HF `musicbrainz_*` subset in ClickHouse). `SET search_path = musicbrainz;` first.

### Explore
```sql
SET search_path = musicbrainz;
\dt                                   -- the ~200 MB schema tables
SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 20;
```

### Artists & recordings
```sql
-- artists by country/area
SELECT a2.name AS area, count(*) AS artists
FROM artist a JOIN area a2 ON a.area = a2.id
GROUP BY a2.name ORDER BY artists DESC LIMIT 25;

-- most prolific artists by recording count (via artist_credit)
SELECT ac.name AS artist, count(*) AS recordings
FROM recording r JOIN artist_credit ac ON r.artist_credit = ac.id
GROUP BY ac.name ORDER BY recordings DESC LIMIT 25;

-- recordings for a specific artist
SELECT r.name, r.length/1000 AS seconds
FROM recording r JOIN artist_credit ac ON r.artist_credit = ac.id
WHERE ac.name = 'Radiohead' ORDER BY r.name LIMIT 50;
```

### Releases
```sql
-- releases per year (from release_group first-release-date)
SELECT rgm.first_release_date_year AS year, count(*) AS releases
FROM release_group rg JOIN release_group_meta rgm ON rg.id = rgm.id
WHERE rgm.first_release_date_year IS NOT NULL
GROUP BY year ORDER BY year DESC LIMIT 40;

-- an artist's release groups (albums/EPs/singles)
SELECT rg.name, rgpt.name AS type
FROM release_group rg
JOIN artist_credit ac ON rg.artist_credit = ac.id
LEFT JOIN release_group_primary_type rgpt ON rg.type = rgpt.id
WHERE ac.name = 'Miles Davis' ORDER BY rg.name;
```

### Relationships (the 1.1M links)
```sql
-- artist↔artist relationship types (member of band, collaboration, …)
SELECT lt.name AS relationship, count(*) AS n
FROM l_artist_artist laa JOIN link l ON laa.link = l.id JOIN link_type lt ON l.link_type = lt.id
GROUP BY lt.name ORDER BY n DESC;
```

### MusicBrainz-isms
- Names go through `artist_credit` (a recording/release can be credited to multiple artists) — join through it,
  not directly to `artist`.
- `gid` columns are the stable MBIDs (UUIDs) you'd use to cross-reference other datasets.
- 39M `recording` rows — filter (by artist_credit, gid, or a name prefix) before scanning; add indexes if needed.
