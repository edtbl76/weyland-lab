#!/usr/bin/env bats
# B198 — the repo-guards entrypoint for the placement inventory. The decisions are covered in
# test_placement_check.py; these prove the wrapper passes arguments through and does not swallow exit codes, since
# `.woodpecker.yml` reads only its status.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-placement.sh"
}

teardown() {
  teardown_stubs
}

@test "the real inventory passes the repo check" {
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK — placement.yaml"* ]]
}

@test "an unreadable inventory is exit 2 through the wrapper, not a pass" {
  printf 'workloads: [unclosed\n' >"$STUB_DIR/p.yaml"
  run bash "$GUARD" --file "$STUB_DIR/p.yaml"
  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot check placement"* ]]
}

@test "a model element with no row is exit 1 naming it" {
  grep -v 'likec4: "ragEmbed"' "$REPO_ROOT/placement.yaml" >"$STUB_DIR/p.yaml"
  run bash "$GUARD" --file "$STUB_DIR/p.yaml"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ragEmbed"* ]]
}

@test "the migration table prints the deliberate moves" {
  run bash "$GUARD" --migration
  [ "$status" -eq 0 ]
  [[ "$output" == *"rag-embed.service"* && "$output" == *"## Summary"* ]]
}

# The nightly CronJob runs the embedded copies, not the repo files. Two copies of a guard (or its data) drift silently
# on both sides, so both must be byte-identical; scripts/embed-placement.sh regenerates them.
@test "the CronJob's embedded script and inventory are byte-identical to the repo" {
  manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/placement-coverage.yaml"
  run python3 - "$manifest" "$REPO_ROOT" <<'PY'
import sys, yaml
cm = next(d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "ConfigMap")["data"]
root = sys.argv[2]
for key, path in (("placement_check.py", "scripts/placement_check.py"), ("placement.yaml", "placement.yaml")):
    if cm.get(key) != open(f"{root}/{path}").read():
        print(f"DRIFT {key} — run scripts/embed-placement.sh"); sys.exit(1)
print("identical")
PY
  [ "$status" -eq 0 ]
  [[ "$output" == "identical" ]]
}
