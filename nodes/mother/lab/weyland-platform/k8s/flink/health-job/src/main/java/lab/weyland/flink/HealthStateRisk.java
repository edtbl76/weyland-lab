package lab.weyland.flink;

import org.apache.avro.Schema;
import org.apache.avro.generic.GenericRecord;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.functions.RichFlatMapFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.common.state.ValueState;
import org.apache.flink.api.common.state.ValueStateDescriptor;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.connector.base.DeliveryGuarantee;
import org.apache.flink.connector.kafka.sink.KafkaRecordSerializationSchema;
import org.apache.flink.connector.kafka.sink.KafkaSink;
import org.apache.flink.connector.kafka.source.KafkaSource;
import org.apache.flink.connector.kafka.source.enumerator.initializer.OffsetsInitializer;
import org.apache.flink.formats.avro.registry.confluent.ConfluentRegistryAvroDeserializationSchema;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.util.Collector;

/**
 * B83 Job 3 - Java DataStream example (health). Reads the BRFSS survey stream (Confluent-Avro), keys by US
 * state (Locationdesc, the state name), and maintains a per-state running mean of Data_value in keyed state,
 * emitting the updated (state, n, mean_risk) as JSON to analytics.health.state_risk. This proves the Java
 * DataStream + keyed state surface (the SQL jobs prove the Table API; PyFlink is job 4).
 */
public final class HealthStateRisk {

    private static final String BROKERS = "redpanda.data-mesh.svc.cluster.local:9092";
    private static final String REGISTRY = "http://redpanda.data-mesh.svc.cluster.local:8081";
    private static final String SRC_TOPIC = "datasets.health.brfss";
    private static final String SINK_TOPIC = "analytics.health.state_risk";

    // Minimal reader schema: only the two fields we need. Field names are CASE-SENSITIVE and must match the
    // producer's registered schema EXACTLY - it capitalizes (Locationdesc, Data_value). A mismatched reader field
    // is silently filled with its default (null), which would drop every record. Locationdesc is the state name
    // ("California"); Locationabbr in this dataset is a numeric long code, so the name is the better key. Data_value
    // is a double; the union stays a superset (["null","string","double"]) to tolerate other health streams.
    private static final String READER_SCHEMA =
            "{\"type\":\"record\",\"name\":\"BrfssRow\",\"namespace\":\"weyland.health\",\"fields\":["
          + "{\"name\":\"Locationdesc\",\"type\":[\"null\",\"string\"],\"default\":null},"
          + "{\"name\":\"Data_value\",\"type\":[\"null\",\"string\",\"double\"],\"default\":null}]}";

    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        Schema readerSchema = new Schema.Parser().parse(READER_SCHEMA);
        KafkaSource<GenericRecord> source = KafkaSource.<GenericRecord>builder()
                .setBootstrapServers(BROKERS)
                .setTopics(SRC_TOPIC)
                .setGroupId("flink-health-state-risk")
                .setStartingOffsets(OffsetsInitializer.earliest())
                .setValueOnlyDeserializer(
                        ConfluentRegistryAvroDeserializationSchema.forGeneric(readerSchema, REGISTRY))
                .build();

        KafkaSink<String> sink = KafkaSink.<String>builder()
                .setBootstrapServers(BROKERS)
                .setRecordSerializer(KafkaRecordSerializationSchema.builder()
                        .setTopic(SINK_TOPIC)
                        .setValueSerializationSchema(new SimpleStringSchema())
                        .build())
                .setDeliveryGuarantee(DeliveryGuarantee.AT_LEAST_ONCE)
                .build();

        DataStream<GenericRecord> in = env.fromSource(source, WatermarkStrategy.noWatermarks(), "brfss-src");

        in.keyBy(r -> str(r.get("Locationdesc")))
          .flatMap(new RunningMean())
          .sinkTo(sink);

        env.execute("health-state-risk");
    }

    /** Renders a possibly-null Avro field for the JSON sink; null becomes the "??" placeholder. */
    static String str(Object o) {
        return o == null ? "??" : o.toString();
    }

    /**
     * One step of the per-state running mean, extracted from {@link RunningMean#flatMap} by B88 so
     * the arithmetic is unit-testable without a Flink StateBackend.
     *
     * <p>This is the code most likely to be silently wrong: an off-by-one in the count or a stale
     * sum would skew EVERY state's mean_risk while the job still emits healthy-looking JSON. Nulls
     * in prior state (first record for a key) are treated as the identity (0 count, 0 sum).
     *
     * @return {@code {newCount, newMean}} — the updated count and the mean after adding {@code value}
     */
    static double[] meanStep(Long prevCount, Double prevSum, double value) {
        long count = (prevCount == null ? 0L : prevCount) + 1;
        double total = (prevSum == null ? 0.0 : prevSum) + value;
        return new double[] {count, total / count};
    }

    /** The sink line for one state, extracted so its exact JSON shape is pinned by a test. */
    static String riskJson(String state, long count, double mean) {
        return String.format("{\"state\":\"%s\",\"n\":%d,\"mean_risk\":%.4f}", str(state), count, mean);
    }

    /**
     * Decides whether an Avro {@code Data_value} contributes to the running mean.
     *
     * <p>Extracted from {@link RunningMean#flatMap} by B88 so the SKIP decisions are testable
     * without a Flink state backend. BRFSS carries footnote and suppressed rows whose Data_value is
     * null or non-numeric; silently skipping those is deliberate, and a test now pins it — an
     * accidental change to "parse as 0" would quietly drag every state's mean toward zero while
     * still reporting healthy output.
     *
     * @return the parsed value, or {@code null} when the row must be skipped
     */
    static Double parseDataValue(Object dv) {
        if (dv == null) {
            return null;
        }
        try {
            return Double.parseDouble(dv.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** Per-state running mean of data_value, held in keyed state; emits the updated stat as JSON per record. */
    public static final class RunningMean extends RichFlatMapFunction<GenericRecord, String> {
        private transient ValueState<Long> n;
        private transient ValueState<Double> sum;

        @Override
        public void open(Configuration c) {
            n = getRuntimeContext().getState(new ValueStateDescriptor<>("n", Long.class));
            sum = getRuntimeContext().getState(new ValueStateDescriptor<>("sum", Double.class));
        }

        @Override
        public void flatMap(GenericRecord r, Collector<String> out) throws Exception {
            Double parsed = parseDataValue(r.get("Data_value"));
            if (parsed == null) {
                return; // null or non-numeric data_value (footnote/suppressed row) - skip
            }
            double[] step = meanStep(n.value(), sum.value(), parsed);
            long count = (long) step[0];
            double mean = step[1];
            // persist the new count + sum (sum is reconstructed from mean*count to keep one source)
            n.update(count);
            sum.update(mean * count);
            out.collect(riskJson(str(r.get("Locationdesc")), count, mean));
        }
    }

    private HealthStateRisk() {
    }
}
