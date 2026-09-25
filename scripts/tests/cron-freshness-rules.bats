#!/usr/bin/env bats
# The backup CronJobs' FRESHNESS rule pages CRITICAL (2026-09-25).
#
# minio-backup sat in ImagePullBackOff for 13 days (2026-09-11 -> 2026-09-25): minio/mc vanished from Docker Hub.
# The only critical backup rule, ScheduledBackupFailed, keys on kube_job_status_failed — and a pod that cannot
# pull its image never FAILS, the Job just stays active. So the backups were covered at `critical` only for the
# failure mode that did not happen; the one that did (not succeeding at all) was a `warning` among ~300 Telegram
# messages a day. A backup that has not SUCCEEDED within its budget is lost data whatever the cause — failed,
# stuck, suspended — so its freshness rule must page at the same severity as its failure rule.

setup() {
  RULES="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s/monitoring/cron-freshness-rules.yaml"
}

# stale_rules_for <cronjob> -> one "<severity>\t<threshold>" line per ScheduledJobStale rule naming it.
stale_rules_for() {
  python3 - "$RULES" "$1" <<'PY'
import re, sys, yaml
doc = yaml.safe_load(open(sys.argv[1]))
job = sys.argv[2]
for g in doc["spec"]["groups"]:
    for r in g.get("rules", []):
        if r.get("alert") != "ScheduledJobStale":
            continue
        m = re.search(r'cronjob=~?"([^"]+)"\}\s*>\s*(\d+)', r["expr"])
        if m and job in m.group(1).split("|"):
            print(f'{r["labels"]["severity"]}\t{m.group(2)}')
PY
}

@test "each backup CronJob is named by exactly ONE ScheduledJobStale rule, at severity critical" {
  for j in minio-backup pg-backup postgres-backup; do
    run stale_rules_for "$j"
    [ "$status" -eq 0 ]
    [ "$(printf '%s\n' "$output" | grep -c .)" -eq 1 ] || { echo "$j: $output"; return 1; }
    [[ "$output" == critical$'\t'* ]] || { echo "$j is not critical: $output"; return 1; }
  done
}

@test "the backup freshness budget stays the daily 26h (93600s) — severity changed, not the threshold" {
  run stale_rules_for minio-backup
  [[ "$output" == *$'\t'93600 ]]
}

@test "non-backup daily jobs stay at warning (only lost-DATA jobs page)" {
  for j in docs-site-rebuild pr-staleness-check cron-freshness-check; do
    run stale_rules_for "$j"
    [[ "$output" == warning$'\t'* ]] || { echo "$j: $output"; return 1; }
  done
}
