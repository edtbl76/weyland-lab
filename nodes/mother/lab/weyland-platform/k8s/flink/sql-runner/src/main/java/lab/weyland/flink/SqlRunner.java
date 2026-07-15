package lab.weyland.flink;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.table.api.bridge.java.StreamTableEnvironment;

/**
 * B83 - declarative Flink SQL runner for FlinkSessionJobs.
 *
 * Reads a .sql file (arg[0], baked into the image under /opt/flink/sql/), strips line comments, splits on ';',
 * and runs each statement through the TableEnvironment. DDL (CREATE CATALOG/DATABASE/TABLE) executes eagerly; the
 * final INSERT submits the streaming/bounded job to the session cluster. One SQL file = one pipeline.
 *
 * Naive comment/split handling is fine for our scripts (no ';' or '--' inside string literals). If that ever
 * changes, swap in a real SQL splitter.
 */
public final class SqlRunner {

    // SET 'key' = 'value' -> apply to config; executeSql() rejects SET as a statement.
    private static final Pattern SET_STMT =
            Pattern.compile("^SET\\s+'([^']+)'\\s*=\\s*'([^']*)'$", Pattern.CASE_INSENSITIVE | Pattern.DOTALL);

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            throw new IllegalArgumentException("usage: SqlRunner <path-to-.sql-file>");
        }

        String raw = new String(Files.readAllBytes(Paths.get(args[0])));

        // strip line comments: everything from "--" to end-of-line
        StringBuilder sb = new StringBuilder();
        for (String line : raw.split("\n", -1)) {
            int c = line.indexOf("--");
            sb.append(c >= 0 ? line.substring(0, c) : line).append('\n');
        }

        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        StreamTableEnvironment tEnv = StreamTableEnvironment.create(env);

        for (String part : sb.toString().split(";")) {
            String stmt = part.trim();
            if (stmt.isEmpty()) {
                continue;
            }
            Matcher m = SET_STMT.matcher(stmt);
            if (m.matches()) {
                System.out.println("[sql-runner] SET " + m.group(1) + " = " + m.group(2));
                tEnv.getConfig().getConfiguration().setString(m.group(1), m.group(2));
                continue;
            }
            System.out.println("[sql-runner] " + stmt.replaceAll("\\s+", " "));
            tEnv.executeSql(stmt);
        }
    }

    private SqlRunner() {
    }
}
