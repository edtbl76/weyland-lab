# Data Pipeline Flows — Music & Health Domains

End-to-end ingestion pipelines for all datasets. Each source lands in lakeFS, transforms to silver/gold
formats, then loads into the appropriate stores. Read paths are shown per format.

---

## Music Domain

```
Spotify CSV ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                    ├──► Arrow ──► JupyterHub/polars
                                    ├──► Avro ──► Kafka (future)
                                    ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (embeddings)
                                    └──► DuckDB (live)

FMA Tracks ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                   ├──► Arrow ──► JupyterHub/polars
                                   ├──► Avro ──► Kafka (future)
                                   ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (embeddings)
                                   └──► DuckDB (live)

FMA Genres ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                   ├──► Arrow ──► JupyterHub/polars
                                   ├──► Neo4j (genre taxonomy graph)
                                   └──► DuckDB (live)

FMA Echonest ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                     ├──► Arrow ──► JupyterHub/polars
                                     ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (audio embeddings)
                                     └──► DuckDB (live)

MSD (UCI 515k subset) ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                               ├──► Arrow ──► JupyterHub/polars
                                               ├──► Avro ──► Kafka (future)
                                               ├──► Lance ──► LanceDB ──► Qdrant/Weaviate
                                               ├──► Neo4j (artist graph)
                                               ├──► OpenSearch (song/artist search)
                                               ├──► Cassandra (song feature writes at scale)
                                               └──► DuckDB (live)
                                               [Full 1M MSD via AWS snapshot → B76]

Last.fm ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                ├──► Arrow ──► JupyterHub/polars
                                ├──► Avro ──► Kafka (future)
                                ├──► TimescaleDB (listening trends)
                                ├──► Cassandra (user listen streams)
                                ├──► Neo4j (artist/tag graph)
                                └──► DuckDB (live)

Spotify Charts ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                       ├──► Arrow ──► JupyterHub/polars
                                       ├──► TimescaleDB (weekly chart trends)
                                       └──► DuckDB (live)

MusicBrainz ──► land ──► lakeFS raw ──► Postgres (native pg dump)
                                    ├──► Parquet ──► Iceberg/Trino
                                    ├──► Arrow ──► JupyterHub/polars
                                    ├──► OpenSearch (artist/recording search)
                                    ├──► Neo4j (music knowledge graph)
                                    └──► DuckDB (live)
```

---

## Health Domain

```
NHANES XPT ──► land ──► lakeFS raw ──► XPT→CSV ──► Parquet ──► Iceberg/Trino
                                               ├──► Arrow ──► JupyterHub/polars
                                               ├──► MySQL
                                               └──► DuckDB (live)

Big Five ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                 ├──► Arrow ──► JupyterHub/polars
                                 ├──► Avro ──► Kafka (future)
                                 ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (profile similarity)
                                 ├──► MySQL
                                 ├──► Cassandra (survey write scale)
                                 ├──► Neo4j (personality graph)
                                 └──► DuckDB (live)

WHO GHO JSON ──► land ──► lakeFS raw ──► flatten ──► Parquet ──► Iceberg/Trino
                                                 ├──► Arrow ──► JupyterHub/polars
                                                 ├──► MySQL
                                                 ├──► MongoDB (nested JSON docs)
                                                 ├──► TimescaleDB (country/year trends)
                                                 ├──► Cassandra (country/year series)
                                                 └──► DuckDB (live)

CDC Physical Activity ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                              ├──► Arrow ──► JupyterHub/polars
                                              ├──► MySQL
                                              └──► DuckDB (live)

BRFSS ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                              ├──► Arrow ──► JupyterHub/polars
                              ├──► Avro ──► Kafka (future)
                              ├──► MySQL
                              ├──► CockroachDB (geo-partitioned)
                              └──► DuckDB (live)

NHIS ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                             ├──► Arrow ──► JupyterHub/polars
                             ├──► Avro ──► Kafka (future)
                             ├──► MySQL
                             ├──► CockroachDB (geo-partitioned)
                             └──► DuckDB (live)

USDA FoodData ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino
                                      ├──► Arrow ──► JupyterHub/polars
                                      ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (food embeddings)
                                      ├──► OpenSearch (food/nutrient search)
                                      └──► DuckDB (live)

Open Food Facts ──► land ──► lakeFS raw ──► decompress ──► Parquet ──► Iceberg/Trino
                                                       ├──► Arrow ──► JupyterHub/polars
                                                       ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (product embeddings)
                                                       ├──► MongoDB (doc per product)
                                                       ├──► OpenSearch (product/ingredient search)
                                                       └──► DuckDB (live)
```

---

## Store Summary

| Store | Role | Seeded from |
|---|---|---|
| lakeFS | Versioned file gateway | land assets |
| Parquet/Iceberg | Gold ACID tables (Trino) | transform |
| Arrow | In-memory IPC (JupyterHub/polars) | transform |
| Avro | Streaming format (Kafka future) | transform |
| Lance | ML/vector fast access | transform |
| DuckDB/GizmoSQL | Live Parquet queries (no load) | reads lakeFS |
| Trino | Federation (Iceberg + Postgres) | reads Iceberg/Nessie |
| MySQL | Relational health datasets | raw CSV |
| Postgres | MusicBrainz + operational data | native pg dump / existing |
| MongoDB | Nested JSON documents | raw JSON (WHO GHO, Open Food Facts) |
| CockroachDB | Geo-partitioned survey data | Parquet |
| Cassandra | Time-series / wide-column at scale | Parquet |
| Neo4j | Knowledge graphs (genre, artist, personality) | Parquet |
| OpenSearch | Full-text / BM25 search | Parquet |
| LanceDB | Lance file queries + embedding source | Lance |
| Qdrant | Dense vector similarity | LanceDB → embeddings |
| Weaviate | Dense vector similarity | LanceDB → embeddings |
| TimescaleDB | Operational time-series (eval, guardrail, pipeline metrics) | Dagster timeseries job |
| JupyterHub | Interactive analytics / polars notebooks | Arrow / lakeFS |
