package lab.weyland.flink;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.ArrayList;
import java.util.List;

import org.apache.flink.runtime.testutils.MiniClusterResourceConfiguration;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.table.api.TableResult;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;
import org.apache.flink.test.junit5.MiniClusterExtension;
import org.apache.flink.types.Row;
import org.apache.flink.util.CloseableIterator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;

/**
 * B151: the SQL runner's statement loop, run end to end on an in-JVM Flink MiniCluster.
 *
 * <p>{@code stripLineComments} has its own unit tests. This proves the rest of what {@code main} does with a real
 * script: comments are dropped, the script is split on {@code ;}, a {@code SET} reaches the table config instead of
 * being executed (executeSql rejects SET), DDL runs, and the final statement executes and produces rows.
 */
class SqlRunnerPipelineTest {

    @RegisterExtension
    static final MiniClusterExtension FLINK = new MiniClusterExtension(
            new MiniClusterResourceConfiguration.Builder()
                    .setNumberTaskManagers(1)
                    .setNumberSlotsPerTaskManager(1)
                    .build());

    private static final String SCRIPT = String.join("\n",
            "-- B151 test pipeline",
            "SET 'pipeline.name' = 'b151-sql-runner-test';",
            "CREATE TEMPORARY VIEW people AS",
            "  SELECT * FROM (VALUES (1, 'ada'), (2, 'bob'), (3, 'cy')) AS t(id, name);  -- three rows",
            "",
            "SELECT id, UPPER(name) AS name FROM people WHERE id > 1  -- the last statement runs the job",
            "");

    @Test
    void aScriptRunsThroughTheRealTableEnvironment() throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        StreamTableEnvironment tEnv = StreamTableEnvironment.create(env);

        TableResult last = SqlRunner.run(tEnv, SCRIPT);

        List<String> rows = new ArrayList<>();
        try (CloseableIterator<Row> it = last.collect()) {
            it.forEachRemaining(r -> rows.add(r.getField(0) + ":" + r.getField(1)));
        }
        assertEquals(List.of("2:BOB", "3:CY"), rows);
        assertEquals("b151-sql-runner-test",
                tEnv.getConfig().getConfiguration().toMap().get("pipeline.name"),
                "the SET statement must land in the table config");
    }
}
