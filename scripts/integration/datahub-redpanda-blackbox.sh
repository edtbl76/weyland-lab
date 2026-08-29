#!/usr/bin/env bash
#
# datahub-redpanda-blackbox.sh — integration assertion that DataHub is actually CONSUMING from Redpanda
# (B88 gap #2). The sibling of guard-blackbox.sh, one service boundary over.
#
# WHY THIS EXISTS. On 2026-08-29 DataHub was repointed off the chart's bundled (unmaintained
# bitnamilegacy) Kafka onto the in-namespace Redpanda by changing `global.kafka.bootstrap.server`. The
# risk that repoint introduces is a SILENT one: DataHub's source of truth is Postgres + OpenSearch, so
# the UI keeps serving the full catalog even if the event bus is severed — a disconnected DataHub looks
# byte-identical to a healthy one until metadata changes quietly stop propagating. That is the
# absence-as-success pattern this whole effort exists to remove, sitting on a live service seam. So this
# asserts the thing the UI cannot: that DataHub's MAE/MCE consumers are connected to Redpanda and
# actively consuming.
#
# WHAT IT ASSERTS (grounded in the live broker + datahub-values.yaml, not assumed):
#   1. the DataHub topic spine exists on Redpanda — `DataHubUpgradeHistory_v1` (the one GMS reads to
#      decide whether schema migrations ran) plus the MetadataChangeLog/Proposal topics events flow on;
#   2. the `generic-mae-consumer-job-client` and `generic-mce-consumer-job-client` groups are STABLE —
#      an Empty/Dead state means the consumer disconnected. ONLY these groups: the `flink-*` groups are
#      legitimately Empty when their jobs idle, so a blanket "all Stable" check would false-fire.
#
# EXIT CODES (same contract as the test lanes and guard-blackbox):
#   0  DataHub topics present AND MAE/MCE consumers Stable
#   1  a topic is missing, or a DataHub consumer is absent / not Stable   -> real finding (event bus severed)
#   2  Redpanda could not be reached, or the lane could not run           -> broken lane, fail closed
#
# rpk's exit code is NOT trusted as the verdict — the repo has been burned three times by tools whose
# exit status disagreed with what they printed (promtool, woodpecker-cli, curl). Every check reads what
# rpk PRINTED (the listing header + the rows), and treats "no listing came back" as unreachable (2).
set -uo pipefail

BROKERS="${REDPANDA_BROKERS:-redpanda.data-mesh.svc.cluster.local:9092}"

die2() { printf 'BROKEN LANE (cannot run): %s\n' "$*" >&2; exit 2; }
command -v rpk >/dev/null 2>&1 || die2 "rpk not on PATH"

fails=0
fail() { printf 'FAIL: %s\n' "$*" >&2; fails=1; }

# ── topics ─────────────────────────────────────────────────────────────────────────────────────────
topics="$(rpk topic list -X brokers="$BROKERS" 2>&1)"; rc=$?
# A real listing carries the PARTITIONS header. rpk exiting non-zero, printing nothing, or printing an
# error (no header) all mean "could not reach the broker" — fail CLOSED to 2, never read as topics missing.
{ [ "$rc" -eq 0 ] && printf '%s\n' "$topics" | grep -qi 'PARTITIONS'; } \
  || die2 "redpanda unreachable at $BROKERS, or 'rpk topic list' returned no listing:
$topics"

for t in DataHubUpgradeHistory_v1 MetadataChangeLog_Versioned_v1 MetadataChangeProposal_v1; do
  printf '%s\n' "$topics" | grep -qw "$t" \
    || fail "DataHub topic '$t' is MISSING on redpanda — the event flow DataHub depends on is broken"
done

# ── consumer groups ─────────────────────────────────────────────────────────────────────────────────
groups="$(rpk group list -X brokers="$BROKERS" 2>&1)"; rc=$?
{ [ "$rc" -eq 0 ] && printf '%s\n' "$groups" | grep -qi 'STATE'; } \
  || die2 "could not list consumer groups on $BROKERS:
$groups"

# ONLY the DataHub consumers. The flink-* groups are Empty when idle — asserting them would false-fire.
for g in generic-mae-consumer-job-client generic-mce-consumer-job-client; do
  line="$(printf '%s\n' "$groups" | grep -w "$g")"
  if [ -z "$line" ]; then
    fail "DataHub consumer group '$g' is ABSENT — DataHub is not consuming from redpanda"
  elif ! printf '%s\n' "$line" | grep -qw Stable; then
    fail "DataHub consumer group '$g' is not Stable (disconnected or idle) — got: $line"
  fi
done

[ "$fails" -eq 0 ] || { printf 'datahub<->redpanda: one or more assertions FAILED against %s\n' "$BROKERS" >&2; exit 1; }
printf 'OK — datahub<->redpanda: topic spine present and MAE/MCE consumers Stable on %s\n' "$BROKERS"
exit 0
