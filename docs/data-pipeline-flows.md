# Data Pipeline Flows — Music & Health Domains

End-to-end ingestion pipelines for all datasets. Each source lands in lakeFS, transforms to silver/gold
formats, then loads into the appropriate stores. Read paths are shown per format.

---

## Music Domain

```
Spotify CSV ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt (transforms)
                                    ├──► Arrow ──► JupyterHub/polars
                                    ├──► Avro ──► Kafka → consumers
                                    ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (embeddings)
                                    ├──► Feast (audio feature store)
                                    ├──► MLflow (experiment tracking)
                                    └──► DuckDB (live)

FMA Tracks ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                   ├──► Arrow ──► JupyterHub/polars
                                   ├──► Avro ──► Kafka → consumers
                                   ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (embeddings)
                                   ├──► OpenSearch (track/artist search)
                                   ├──► Neo4j (genre graph)
                                   ├──► Feast (track features)
                                   └──► DuckDB (live)

FMA Genres ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                   ├──► Arrow ──► JupyterHub/polars
                                   ├──► Neo4j (genre taxonomy graph)
                                   └──► DuckDB (live)

FMA Echonest ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                     ├──► Arrow ──► JupyterHub/polars
                                     ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (audio embeddings)
                                     ├──► Feast (audio features)
                                     └──► DuckDB (live)

FMA Features (518) ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                          ├──► Arrow ──► JupyterHub/polars
                                          ├──► Lance ──► LanceDB ──► Qdrant/Weaviate
                                          ├──► ClickHouse (OLAP feature queries)
                                          ├──► Feast (rich audio feature store)
                                          └──► DuckDB (live)

MSD (UCI 515k subset) ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                               ├──► Arrow ──► JupyterHub/polars
                                               ├──► Avro ──► Kafka → consumers
                                               ├──► Lance ──► LanceDB ──► Qdrant/Weaviate
                                               ├──► ClickHouse (OLAP)
                                               ├──► Neo4j (artist graph)
                                               ├──► OpenSearch (song/artist search)
                                               ├──► Cassandra (song feature writes at scale)
                                               ├──► Feast (audio features)
                                               ├──► MLflow (experiment tracking)
                                               └──► DuckDB (live)
                                               [Full 1M MSD + FMA large audio via AWS snapshot → B76]

Last.fm ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                ├──► Arrow ──► JupyterHub/polars
                                ├──► Avro ──► Kafka (listen stream)
                                ├──► TimescaleDB (listening trends)
                                ├──► Cassandra (user listen streams)
                                ├──► Neo4j (artist/tag graph)
                                └──► DuckDB (live)

MusicBrainz ──► land ──► lakeFS raw ──► Postgres (native pg dump)
                                    ├──► Parquet ──► Iceberg/Trino ──► dbt
                                    ├──► Arrow ──► JupyterHub/polars
                                    ├──► OpenSearch (artist/recording search)
                                    ├──► Neo4j (music knowledge graph)
                                    └──► DuckDB (live)

GTZAN ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                              ├──► Arrow ──► JupyterHub/polars
                              ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (genre embeddings)
                              ├──► Feast (genre features)
                              ├──► MLflow (genre classification experiments)
                              └──► DuckDB (live)

LP-MusicCaps-MC ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                        ├──► Arrow ──► JupyterHub/polars
                                        ├──► OpenSearch (caption search)
                                        ├──► Qdrant/Weaviate (caption embeddings)
                                        └──► DuckDB (live)

LP-MusicCaps-MTT ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                         ├──► Arrow ──► JupyterHub/polars
                                         ├──► OpenSearch (tag/caption search)
                                         ├──► Qdrant/Weaviate (caption embeddings)
                                         └──► DuckDB (live)

AudioSet (balanced) ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                           ├──► Arrow ──► JupyterHub/polars
                                           ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (audio event embeddings)
                                           ├──► ClickHouse (OLAP event queries)
                                           ├──► Neo4j (audio event graph)
                                           ├──► OpenSearch (audio event search)
                                           ├──► Feast (audio event features)
                                           ├──► MLflow (audio classification experiments)
                                           └──► DuckDB (live)
```

---

## Health Domain

```
NHANES XPT ──► land ──► lakeFS raw ──► XPT→CSV ──► Parquet ──► Iceberg/Trino ──► dbt
                                               ├──► Arrow ──► JupyterHub/polars
                                               ├──► MySQL
                                               ├──► Feast (biomarker features)
                                               └──► DuckDB (live)

Big Five ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                 ├──► Arrow ──► JupyterHub/polars
                                 ├──► Avro ──► Kafka (survey stream)
                                 ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (profile similarity)
                                 ├──► MySQL
                                 ├──► Cassandra (survey write scale)
                                 ├──► Neo4j (personality graph)
                                 ├──► Feast (personality features)
                                 ├──► MLflow (personality-health experiments)
                                 └──► DuckDB (live)

WHO GHO JSON ──► land ──► lakeFS raw ──► flatten ──► Parquet ──► Iceberg/Trino ──► dbt
                                                 ├──► Arrow ──► JupyterHub/polars
                                                 ├──► MySQL
                                                 ├──► MongoDB (nested JSON docs)
                                                 ├──► TimescaleDB (country/year trends)
                                                 ├──► Cassandra (country/year series)
                                                 ├──► ClickHouse (OLAP population analytics)
                                                 └──► DuckDB (live)

CDC Physical Activity ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                              ├──► Arrow ──► JupyterHub/polars
                                              ├──► MySQL
                                              ├──► Feast (activity features)
                                              └──► DuckDB (live)

BRFSS ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                              ├──► Arrow ──► JupyterHub/polars
                              ├──► Avro ──► Kafka (survey stream)
                              ├──► MySQL
                              ├──► CockroachDB (geo-partitioned)
                              ├──► ClickHouse (OLAP health behavior queries)
                              ├──► Feast (health risk features)
                              └──► DuckDB (live)

NHIS ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                             ├──► Arrow ──► JupyterHub/polars
                             ├──► Avro ──► Kafka (survey stream)
                             ├──► MySQL
                             ├──► CockroachDB (geo-partitioned)
                             ├──► ClickHouse (OLAP)
                             ├──► Feast (health features)
                             └──► DuckDB (live)

USDA FoodData ──► land ──► lakeFS raw ──► Parquet ──► Iceberg/Trino ──► dbt
                                      ├──► Arrow ──► JupyterHub/polars
                                      ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (food embeddings)
                                      ├──► ClickHouse (OLAP food/nutrient queries)
                                      ├──► OpenSearch (food/nutrient search)
                                      ├──► Feast (nutrition features)
                                      └──► DuckDB (live)

Open Food Facts ──► land ──► lakeFS raw ──► decompress ──► Parquet ──► Iceberg/Trino ──► dbt
                                                       ├──► Arrow ──► JupyterHub/polars
                                                       ├──► Lance ──► LanceDB ──► Qdrant/Weaviate (product embeddings)
                                                       ├──► MongoDB (doc per product)
                                                       ├──► ClickHouse (OLAP product analytics)
                                                       ├──► OpenSearch (product/ingredient search)
                                                       ├──► Feast (product features)
                                                       └──► DuckDB (live)
```

---

## Store Summary

| Store | Role | Seeded from |
|---|---|---|
| lakeFS | Versioned file gateway | land assets |
| Parquet/Iceberg | Gold ACID tables (Trino) | transform |
| Arrow | In-memory IPC (JupyterHub/polars) | transform |
| Avro → Kafka | Streaming format / event bus | transform → Kafka consumers |
| Lance | ML/vector fast access | transform |
| DuckDB/GizmoSQL | Live Parquet queries (no load) | reads lakeFS |
| Trino | Federation (Iceberg + Postgres) | reads Iceberg/Nessie |
| dbt | SQL transforms over Iceberg/Trino | reads Iceberg, writes Iceberg |
| ClickHouse | OLAP analytics (fast aggregations at scale) | Parquet |
| MySQL | Relational health datasets | raw CSV |
| Postgres | MusicBrainz + operational data | native pg dump / existing |
| MongoDB | Nested JSON documents | raw JSON (WHO GHO, Open Food Facts) |
| CockroachDB | Geo-partitioned survey data | Parquet |
| Cassandra | Time-series / wide-column at scale | Parquet |
| Neo4j | Knowledge graphs (genre, artist, personality, audio events) | Parquet |
| OpenSearch | Full-text / BM25 search | Parquet |
| LanceDB | Lance file queries + embedding source | Lance |
| Qdrant | Dense vector similarity | LanceDB → embeddings |
| Weaviate | Dense vector similarity | LanceDB → embeddings |
| Feast | Feature store (ML feature materialization + serving) | Parquet / lakeFS |
| MLflow | Experiment tracking + model registry | existing + new experiments |
| TimescaleDB | Operational time-series (eval, guardrail, pipeline metrics) | Dagster timeseries job |
| JupyterHub | Interactive analytics / polars notebooks | Arrow / lakeFS |
