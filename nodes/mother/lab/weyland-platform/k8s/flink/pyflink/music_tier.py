# B83 Job 4 - PyFlink (music). The one surface the SQL jobs (Table API in SQL) and the Java job (DataStream keyed
# state) do not cover: a real PYTHON UDF executed per row by the Python worker. Reads the bounded
# datasets.music.lastfm replay (lastfm-360K: each row = a user's TOTAL plays of an artist, in play_count), sums
# play_count per artist, and a Python UDF buckets that total into a human popularity tier ->
# upsert-kafka analytics.music.artist_tier.
from pyflink.table import EnvironmentSettings, TableEnvironment, DataTypes
from pyflink.table.udf import udf


# The point of the whole job: arbitrary Python that Flink SQL can't express, run per row via the Python worker
# (Flink ships rows to a python process over the py4j/Beam boundary). Buckets an artist's TOTAL play_count (summed
# across all users) into a popularity tier. Thresholds are calibrated to THIS sampled topic's real distribution
# (measured: max 442, p90 10, p50 2) so the tiers actually spread across artists rather than all landing in one.
@udf(result_type=DataTypes.STRING())
def popularity_tier(plays):
    if plays is None:
        return "unknown"
    if plays >= 100:
        return "viral"
    if plays >= 30:
        return "popular"
    if plays >= 8:
        return "rising"
    return "niche"


def main():
    t_env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
    t_env.get_config().set("python.executable", "/usr/bin/python3")
    # Mini-batch: a non-windowed GROUP BY on a streaming source emits an update PER input row (retract + new). On a
    # multi-million-row replay that is a flood of intermediate upserts. Mini-batch buffers and folds them, so the
    # sink sees far fewer updates and the final tier per artist still lands.
    t_env.get_config().set("table.exec.mini-batch.enabled", "true")
    t_env.get_config().set("table.exec.mini-batch.allow-latency", "5 s")
    t_env.get_config().set("table.exec.mini-batch.size", "20000")
    t_env.create_temporary_function("popularity_tier", popularity_tier)

    # Source: the SAME bounded lastfm replay the RTA SQL job reads (earliest -> latest then stop). avro-confluent
    # via the Redpanda schema registry. Field names match the producer's registered schema (lowercase for lastfm).
    t_env.execute_sql("""
      CREATE TEMPORARY TABLE lastfm_src (
        artist_name STRING,
        play_count  BIGINT
      ) WITH (
        'connector' = 'kafka',
        'topic' = 'datasets.music.lastfm',
        'properties.bootstrap.servers' = 'redpanda.data-mesh.svc.cluster.local:9092',
        'properties.group.id' = 'flink-pyflink-artist-tier',
        'scan.startup.mode' = 'earliest-offset',
        'scan.bounded.mode' = 'latest-offset',
        'format' = 'avro-confluent',
        'avro-confluent.url' = 'http://redpanda.data-mesh.svc.cluster.local:8081'
      )
    """)

    # Sink: the per-artist aggregation is a CHANGELOG (retract) stream, so a plain kafka sink would reject it.
    # upsert-kafka keys by artist_name and compacts the changelog into the topic -> latest (plays, tier) per artist.
    t_env.execute_sql("""
      CREATE TEMPORARY TABLE artist_tier (
        artist_name STRING,
        plays       BIGINT,
        tier        STRING,
        PRIMARY KEY (artist_name) NOT ENFORCED
      ) WITH (
        'connector' = 'upsert-kafka',
        'topic' = 'analytics.music.artist_tier',
        'properties.bootstrap.servers' = 'redpanda.data-mesh.svc.cluster.local:9092',
        'key.format' = 'json',
        'value.format' = 'json'
      )
    """)

    t_env.execute_sql("""
      INSERT INTO artist_tier
      SELECT artist_name, plays, popularity_tier(plays) AS tier
      FROM (
        SELECT artist_name, SUM(play_count) AS plays
        FROM lastfm_src
        GROUP BY artist_name
      )
    """)


if __name__ == '__main__':
    main()
