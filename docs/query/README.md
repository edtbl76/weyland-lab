# Query cookbook — one file per data store

Useful, dataset-specific queries for the hydrated Tier-2 stores. These target the **actual data we loaded**
(who_gho, brfss, big_five, lastfm, usda, open_food_facts, fma, uci, musicbrainz, audioset, …), not generic
syntax demos.

| Store | File | What's in it |
|---|---|---|
| ClickHouse | [clickhouse.md](clickhouse.md) | OLAP — usda (food/nutrients), OFF, fma, uci, musicbrainz-subset, audioset |
| Cassandra | [cassandra.md](cassandra.md) | wide-column — who_gho, big_five, lastfm, uci (partition-key queries) |
| CockroachDB | [cockroachdb.md](cockroachdb.md) | distributed SQL — brfss, nhis |
| MongoDB | [mongodb.md](mongodb.md) | documents — who_gho, open_food_facts, aidlc-kb |
| MySQL | [mysql.md](mysql.md) | 6 health DBs — nhanes, big_five, who_gho, cdc, brfss, nhis |
| TimescaleDB | [timescaledb.md](timescaledb.md) | hypertables — platform metrics + who_gho time series |
| MusicBrainz PG | [musicbrainz-postgres.md](musicbrainz-postgres.md) | full native mbdump — artists/recordings/links |
| Neo4j | [neo4j.md](neo4j.md) | graphs — music datasets (genre tree, lastfm listens) + AIDLC methodology (`:Entry`) + RAG (`Document`/`Chunk`) + GDS; importable favorites: [AIDLC](neo4j-aidlc-favorites.csv) / [Music](neo4j-music-favorites.csv) |
| Qdrant | [qdrant.md](qdrant.md) | vector similarity — audio-feature + caption vectors (fma_features/echonest, uci, spotify, gtzan, lp_musiccaps, audioset, big_five); collection per dataset |
| Weaviate | [weaviate.md](weaviate.md) | same dataset vectors as Qdrant (class per dataset, BYO vectors) — two backends |
| Redpanda | [redpanda.md](redpanda.md) | streaming — Avro event topics (`datasets.*`) + Debezium CDC (`cdc.*`); rpk/consume, schema registry, CDC envelope |
| LanceDB | [lancedb.md](lancedb.md) | embedded/serverless vector store (Lance-native, on object storage) — same vectors as Qdrant/Weaviate, queried in-process |

**Connecting:** each store's access (svc / ingress / port-forward / creds) is in its runbook and
[../hosts.md](../hosts.md). Most are reachable from IntelliJ via the k8s-plugin port-forward, or in-pod via
`kubectl -n data-mesh exec deploy/<store> -- <client>`.

**Schemas drift** — datasets get reloaded and columns can change. When a query references a column that isn't
there, introspect first (each file opens with a "list tables/columns" query) and adapt. Treat these as
starting points, not contracts.
