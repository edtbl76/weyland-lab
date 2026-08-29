#!/usr/bin/env bats
#
# scripts/integration/datahub-redpanda-blackbox.sh — asserts DataHub is CONSUMING from Redpanda (B88 #2).
#
# The failure this guards is silent: DataHub serves its whole catalog from Postgres + OpenSearch, so a
# severed Kafka bus looks identical to a healthy one in the UI. The only tell is on the broker — the
# MAE/MCE consumer groups go from Stable to Empty. These tests drive a stubbed `rpk` so the three
# outcomes are exercised without a live broker: 0 healthy, 1 event bus severed, 2 broker unreachable.

load helper

DR="scripts/integration/datahub-redpanda-blackbox.sh"

setup() {
  setup_stubs
  # rpk stub: branches on the subcommand and prints the file the test staged, exits the staged rc.
  cat >"$STUB_DIR/rpk" <<'RPK'
#!/usr/bin/env bash
case "$1 $2" in
  "topic list") [ -f "$RPK_TOPICS" ] && cat "$RPK_TOPICS"; exit "${RPK_TOPIC_RC:-0}" ;;
  "group list") [ -f "$RPK_GROUPS" ] && cat "$RPK_GROUPS"; exit "${RPK_GROUP_RC:-0}" ;;
  *) echo "unexpected rpk invocation: $*" >&2; exit 3 ;;
esac
RPK
  chmod +x "$STUB_DIR/rpk"
  export RPK_TOPICS="$STUB_DIR/topics" RPK_GROUPS="$STUB_DIR/groups"
}
teardown() { teardown_stubs; return 0; }

set_topics() { printf '%s\n' "$1" >"$STUB_DIR/topics"; }
set_groups() { printf '%s\n' "$1" >"$STUB_DIR/groups"; }

# The healthy live shape, trimmed from the real `rpk` output observed on the deployed broker.
healthy() {
  set_topics 'NAME                             PARTITIONS  REPLICAS
DataHubUpgradeHistory_v1         1           1
MetadataChangeLog_Versioned_v1   1           1
MetadataChangeProposal_v1        1           1
DataHubUsageEvent_v1             1           1'
  set_groups 'BROKER  GROUP                                    STATE
0       generic-mae-consumer-job-client          Stable
0       generic-mce-consumer-job-client          Stable
0       flink-health-state-risk                  Empty'
}

@test "healthy: DataHub topics present and MAE/MCE consumers Stable -> exit 0" {
  healthy
  run bash "$DR"
  [ "$status" -eq 0 ]
}

@test "an idle flink-* group being Empty does NOT fail — only DataHub groups are asserted" {
  # healthy() already includes flink-health-state-risk in Empty; its presence must not trip the gate.
  healthy
  run bash "$DR"
  [ "$status" -eq 0 ]
  [[ "$output" != *"flink"* ]]
}

@test "broker UNREACHABLE (rpk topic list fails) is a BROKEN lane (2), never a pass" {
  healthy
  RPK_TOPIC_RC=1 run bash "$DR"   # rpk non-zero + (empty file still) => no listing
  [ "$status" -eq 2 ]
  [[ "$output" == *"unreachable"* || "$output" == *"no listing"* ]]
}

@test "rpk exits 0 but prints NO listing (no header) is still unreachable (2) — exit code is not the verdict" {
  # The promtool/curl trap: a tool can exit 0 while its output says it failed. A topic list with no
  # PARTITIONS header is not a listing, so it must fail closed to 2, not read as "all topics missing".
  set_topics 'ERR: connection refused'
  set_groups 'BROKER  GROUP  STATE'
  run bash "$DR"
  [ "$status" -eq 2 ]
}

@test "the load-bearing topic DataHubUpgradeHistory_v1 missing is a real finding (1)" {
  healthy
  set_topics 'NAME                             PARTITIONS  REPLICAS
MetadataChangeLog_Versioned_v1   1           1
MetadataChangeProposal_v1        1           1'
  run bash "$DR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"DataHubUpgradeHistory_v1"* ]]
}

@test "the MAE consumer being ABSENT is a real finding (1) — DataHub not consuming" {
  healthy
  set_groups 'BROKER  GROUP                                    STATE
0       generic-mce-consumer-job-client          Stable'
  run bash "$DR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"generic-mae-consumer-job-client"* ]]
}

@test "the MAE consumer present but EMPTY (disconnected) is a real finding (1) — the silent-severance catch" {
  healthy
  set_groups 'BROKER  GROUP                                    STATE
0       generic-mae-consumer-job-client          Empty
0       generic-mce-consumer-job-client          Stable'
  run bash "$DR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"not Stable"* ]]
}

@test "the group listing being unreadable is a BROKEN lane (2), not a missing-consumer finding (1)" {
  healthy
  RPK_GROUP_RC=1 run bash "$DR"
  [ "$status" -eq 2 ]
}

@test "REDPANDA_BROKERS override is honoured" {
  healthy
  REDPANDA_BROKERS="other.redpanda:9092" run bash "$DR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"other.redpanda:9092"* ]]
}
