#!/usr/bin/env bats
# B197 — the DataHub ingestion watchdog's decisions are covered in test_datahub_ingestion_check.py. This asserts the
# one thing pytest cannot: the CronJob runs the SAME script. Two copies of a watchdog drift silently on both sides;
# scripts/embed-datahub-ingestion-watchdog.sh regenerates the embedded copy.

setup() {
  load helper
}

@test "the CronJob's embedded watchdog is byte-identical to scripts/datahub_ingestion_check.py" {
  manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/datahub-ingestion-watchdog.yaml"
  run python3 - "$manifest" "$REPO_ROOT/scripts/datahub_ingestion_check.py" <<'PY'
import sys, yaml
cm = next(d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "ConfigMap")["data"]
if cm.get("datahub_ingestion_check.py") != open(sys.argv[2]).read():
    print("DRIFT — run scripts/embed-datahub-ingestion-watchdog.sh"); sys.exit(1)
print("identical")
PY
  [ "$status" -eq 0 ]
  [[ "$output" == "identical" ]]
}
