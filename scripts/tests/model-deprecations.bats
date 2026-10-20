#!/usr/bin/env bats
# B223 — the deprecated-model guard. Its decisions are covered in test_model_lifecycle.py; this asserts the wrapper's
# exit contract end to end (with the REASON, not just the status — a bare non-zero also passes on exit 127) and that
# the anthropic-model-watch CronJob runs the SAME logic and manifest (two copies of a guard drift silently).

setup() {
  load helper
  WORK="$(mktemp -d)"
  export MODEL_GUARD_TODAY=2026-10-19
}

teardown() {
  rm -rf "$WORK"
}

@test "passes on the current tree, and says how much it scanned" {
  run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"model-deprecations: OK — "*" Anthropic model reference(s) in "*" file(s)"* ]]
}

@test "fails naming file:line when a config names claude-3-5-haiku-20241022 (retired 2026-02-19)" {
  mkdir -p "$WORK/k8s/app"
  printf 'a: 1\nmodel: anthropic/claude-3-5-haiku-20241022\n' > "$WORK/k8s/app/config.yaml"
  SCAN_ROOT="$WORK" run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"FAIL k8s/app/config.yaml:2  anthropic/claude-3-5-haiku-20241022 -> claude-3-5-haiku-20241022 retired 2026-02-19; replacement claude-haiku-4-5-20251001"* ]]
}

@test "a deprecated model retiring inside 30 days fails; with more time it only warns" {
  printf 'model: claude-sonnet-4-5-20250929\n' > "$WORK/c.yaml"
  SCAN_ROOT="$WORK" MODEL_GUARD_TODAY=2026-11-05 run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"retires 2026-11-30 — 25 day(s) left"* ]]
  SCAN_ROOT="$WORK" run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"WARN c.yaml:1"*"deprecated 2026-09-30, retires 2026-11-30"* ]]
}

@test "exits 2, never clean, when the manifest is missing" {
  printf 'model: claude-haiku-4-5\n' > "$WORK/c.yaml"
  SCAN_ROOT="$WORK" MODEL_MANIFEST="$WORK/nope.json" run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK — cannot read the model manifest"* ]]
}

@test "exits 2 when the manifest is malformed" {
  printf 'model: claude-haiku-4-5\n' > "$WORK/c.yaml"
  printf '{"models": [{"id": "claude-haiku-4-5-20251001", "state": "gone"}]}' > "$WORK/m.json"
  SCAN_ROOT="$WORK" MODEL_MANIFEST="$WORK/m.json" run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK — claude-haiku-4-5-20251001: state 'gone'"* ]]
}

@test "exits 2 when there is nothing to scan" {
  SCAN_ROOT="$WORK" run bash "$REPO_ROOT/scripts/check-model-deprecations.sh"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK — no config or code files"* ]]
}

@test "the CronJob's embedded logic and manifest are byte-identical to scripts/" {
  manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/bifrost/anthropic-model-watch.yaml"
  run python3 - "$manifest" "$REPO_ROOT/scripts" <<'PY'
import sys, yaml
cm = next(d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "ConfigMap")["data"]
for key in ("model_lifecycle.py", "anthropic-models.json"):
    if cm.get(key) != open(f"{sys.argv[2]}/{key}").read():
        print(f"DRIFT in {key} — run scripts/embed-anthropic-model-watch.sh"); sys.exit(1)
print("identical")
PY
  [ "$status" -eq 0 ]
  [[ "$output" == "identical" ]]
}

@test "the CronJob is covered by ScheduledJobFailed and the daily ScheduledJobStale budget" {
  rules="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/cron-freshness-rules.yaml"
  run grep -c 'anthropic-model-watch' "$rules"
  [ "$status" -eq 0 ]
  [ "$output" -ge 2 ]
}
