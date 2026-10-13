#!/usr/bin/env bats
# Tests for scripts/minio-restore-drill.sh (2026-10-13) — prints a one-off Job that restores one bucket from the
# minio-backup PVC (mother NVMe) into a scratch bucket and compares them. docs/dr.md listed the MinIO mirror's restore
# as "`mc mirror` back from the PVC" with no procedure and no test. The Job runs only when a person pipes it to
# kubectl; it is never under k8s/ (Argo would re-run it on every sync). Pinned here: the generator's decisions.

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../minio-restore-drill.sh"
  BACKUP="$BATS_TEST_DIRNAME/../../nodes/mother/lab/weyland-platform/k8s/minio/backup.yaml"
}

@test "a mirrored bucket yields one valid Job manifest in ns minio" {
  run bash "$SCRIPT" ai-sessions
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | python3 -c '
import sys, yaml
docs = [d for d in yaml.safe_load_all(sys.stdin) if d]
assert len(docs) == 1, len(docs)
j = docs[0]
assert j["kind"] == "Job" and j["metadata"]["namespace"] == "minio"
assert j["metadata"]["name"].startswith("minio-restore-drill-ai-sessions-")
spec = j["spec"]["template"]["spec"]
assert spec["restartPolicy"] == "Never" and j["spec"]["backoffLimit"] == 0
assert j["spec"]["ttlSecondsAfterFinished"] > 0
'
}

@test "the backup PVC is mounted READ-ONLY (a drill never writes the backup)" {
  run bash "$SCRIPT" ai-sessions
  printf '%s\n' "$output" | python3 -c '
import sys, yaml
spec = yaml.safe_load(sys.stdin)["spec"]["template"]["spec"]
assert spec["volumes"][0]["persistentVolumeClaim"] == {"claimName": "minio-backup", "readOnly": True}
assert spec["containers"][0]["volumeMounts"][0]["readOnly"] is True
'
}

@test "the image and credentials are the backup CronJob's own (no drift)" {
  run bash "$SCRIPT" ai-sessions
  image="$(grep -oE 'image: [^ ]+' "$BACKUP" | head -1 | cut -d' ' -f2)"
  [[ "$output" == *"image: $image"* ]]
  [[ "$output" == *"name: minio-creds, key: MINIO_ROOT_USER"* ]]
}

@test "the Job script fails closed and always removes the scratch bucket" {
  run bash "$SCRIPT" ai-sessions
  [[ "$output" == *"trap "* ]]
  [[ "$output" == *"mc rb --force"* ]]
  [[ "$output" == *"DRILL FAIL"*"exit 2"* ]]
  [[ "$output" == *'B="ai-sessions"'* ]]
  [[ "$output" == *'DRILL OK bucket=$B'* ]]
}

@test "a bucket the CronJob does not mirror is refused (exit 2) — a drill of an unbacked bucket proves nothing" {
  run bash "$SCRIPT" rogueone-backup
  [ "$status" -eq 2 ]
  [[ "$output" == *"not mirrored by minio-backup"*"ai-sessions"* ]]
}

@test "no bucket, or a malformed name, is exit 2 with usage" {
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
  run bash "$SCRIPT" 'x; rm -rf /'
  [ "$status" -eq 2 ]
}

@test "the pod carries the drill labels, so the runbook's 'logs -l app=minio-restore-drill' finds it" {
  # Observed 2026-10-13 (the first live drill): labels on the Job only — `kubectl logs -l` found nothing.
  run bash "$SCRIPT" ai-sessions
  printf '%s\n' "$output" | python3 -c '
import sys, yaml
j = yaml.safe_load(sys.stdin)
assert j["spec"]["template"]["metadata"]["labels"] == {"app": "minio-restore-drill", "bucket": "ai-sessions"}
'
}
