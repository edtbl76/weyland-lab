package lab.weyland.flink;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;

import org.apache.avro.Schema;
import org.apache.avro.generic.GenericData;
import org.apache.avro.generic.GenericRecord;
import org.apache.flink.formats.avro.typeutils.GenericRecordAvroTypeInfo;
import org.apache.flink.runtime.testutils.MiniClusterResourceConfiguration;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.test.junit5.MiniClusterExtension;
import org.apache.flink.util.CloseableIterator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;

/**
 * B151: the health job's real topology, run end to end on an in-JVM Flink MiniCluster.
 *
 * <p>The arithmetic ({@code meanStep}, {@code riskJson}, {@code parseDataValue}) has its own unit tests. This proves
 * the WIRING those tests cannot see: records keyed by state reach {@code RunningMean} with per-state keyed state,
 * the skip rule drops footnote rows, and the JSON leaves the topology. Kafka is swapped out at the seam
 * ({@link HealthStateRisk#topology}), so no broker or registry is needed. Parallelism 1 keeps output order exact.
 */
class HealthStateRiskPipelineTest {

    private static final String CALIFORNIA = "California";

    @RegisterExtension
    static final MiniClusterExtension FLINK = new MiniClusterExtension(
            new MiniClusterResourceConfiguration.Builder()
                    .setNumberTaskManagers(1)
                    .setNumberSlotsPerTaskManager(1)
                    .build());

    private static GenericRecord row(Schema schema, String state, Object dataValue) {
        GenericRecord r = new GenericData.Record(schema);
        r.put("Locationdesc", state);
        r.put("Data_value", dataValue);
        return r;
    }

    private static List<String> run(List<GenericRecord> input) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        Schema schema = HealthStateRisk.readerSchema();
        DataStream<GenericRecord> src = env.fromData(input, new GenericRecordAvroTypeInfo(schema));
        List<String> out = new ArrayList<>();
        try (CloseableIterator<String> it = HealthStateRisk.topology(src).executeAndCollect()) {
            it.forEachRemaining(out::add);
        }
        return out;
    }

    @Test
    void recordsFlowThroughAsPerStateRunningMeansAndFootnoteRowsAreSkipped() throws Exception {
        Schema schema = HealthStateRisk.readerSchema();
        List<String> out = run(List.of(
                row(schema, CALIFORNIA, "10"),     // string-typed value (the union allows it)
                row(schema, "Texas", 4.0),           // double-typed value
                row(schema, CALIFORNIA, null),     // suppressed row: skipped
                row(schema, CALIFORNIA, "n/a"),    // footnote row: skipped
                row(schema, CALIFORNIA, 20.0)));   // California's SECOND counted value: n=2, mean 15

        assertEquals(List.of(
                "{\"state\":\"California\",\"n\":1,\"mean_risk\":10.0000}",
                "{\"state\":\"Texas\",\"n\":1,\"mean_risk\":4.0000}",
                "{\"state\":\"California\",\"n\":2,\"mean_risk\":15.0000}"), out);
    }

    @Test
    void aRecordWithNoStateIsKeyedAndRenderedAsThePlaceholder() throws Exception {
        Schema schema = HealthStateRisk.readerSchema();
        List<String> out = run(List.of(row(schema, null, "7"), row(schema, null, "9")));

        assertEquals(List.of(
                "{\"state\":\"??\",\"n\":1,\"mean_risk\":7.0000}",
                "{\"state\":\"??\",\"n\":2,\"mean_risk\":8.0000}"), out);
    }
}
