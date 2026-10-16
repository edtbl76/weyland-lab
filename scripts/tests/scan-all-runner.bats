#!/usr/bin/env bats
# k8s/code-quality/scan-suite.yaml `scan-all.sh` — the per-repo loop the code-scan-suite CronJob runs (2026-10-16).
#
# scan.py now exits 3 on a SCAN DEFECT (a crashed tool, an image it could not scan) after posting everything else.
# The loop must keep scanning every remaining repo, then exit 3 so the Job's podFailurePolicy fails it without a
# retry. A plain failure (a clone, scan.py exiting 1) stays exit 1, which keeps the one retry for a transient error.

load helper

setup() {
  setup_stubs
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/code-quality/scan-suite.yaml"
  RUNNER="$STUB_DIR/scan-all.sh"
  extract_configmap_script "$MANIFEST" scan-all.sh > "$RUNNER"
  [ -s "$RUNNER" ]
  REAL_PY="$(command -v python3)"   # captured BEFORE the python3 stub below shadows it
  # python3 stands in for scan.py: exit code per repo from a map file, default 0.
  printf '#!/usr/bin/env bash\nrc="$(awk -v r="$SCAN_TARGET" '"'"'$1==r{print $2}'"'"' "%s/rcmap")"\necho "scanned $SCAN_TARGET"\nexit "${rc:-0}"\n' "$STUB_DIR" > "$STUB_DIR/python3"
  chmod +x "$STUB_DIR/python3"
  # git clone fails only for a repo named "unclonable".
  printf '#!/usr/bin/env bash\ncase "$*" in *unclonable*) exit 128 ;; esac\nexit 0\n' > "$STUB_DIR/git"
  chmod +x "$STUB_DIR/git"
  : > "$STUB_DIR/rcmap"
  export GITHUB_TOKEN=x
}

teardown() { teardown_stubs; }

@test "every repo clean is exit 0" {
  SCAN_REPOS="a b" run sh "$RUNNER"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"scanned a"* && "$output" == *"scanned b"* ]]
}

@test "a scan defect in one repo still scans the rest, then exits 3" {
  printf 'a 3\n' > "$STUB_DIR/rcmap"
  SCAN_REPOS="a b" run sh "$RUNNER"
  [ "$status" -eq 3 ] || { echo "$output"; return 1; }
  [[ "$output" == *"scanned b"* ]] || { echo "$output"; return 1; }
  [[ "$output" == *"SCAN DEFECT"*"a"* ]] || { echo "$output"; return 1; }
}

@test "a plain scan failure stays exit 1 (keeps the retry for a transient error)" {
  printf 'a 1\n' > "$STUB_DIR/rcmap"
  SCAN_REPOS="a b" run sh "$RUNNER"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
}

@test "a clone failure stays exit 1" {
  SCAN_REPOS="unclonable b" run sh "$RUNNER"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CLONE FAILED"* && "$output" == *"scanned b"* ]] || { echo "$output"; return 1; }
}

@test "a defect AND a clone failure is exit 3: the defect is the one a retry cannot fix" {
  printf 'b 3\n' > "$STUB_DIR/rcmap"
  SCAN_REPOS="unclonable b" run sh "$RUNNER"
  [ "$status" -eq 3 ] || { echo "$output"; return 1; }
}

@test "the CronJob fails the Job on exit 3 without a retry (podFailurePolicy)" {
  run "$REAL_PY" - "$MANIFEST" <<'PY'
import sys, yaml
cj = [d for d in yaml.safe_load_all(open(sys.argv[1])) if d and d.get("kind") == "CronJob"][0]
pfp = cj["spec"]["jobTemplate"]["spec"].get("podFailurePolicy") or {}
rules = pfp.get("rules") or []
ok = [r for r in rules if r.get("action") == "FailJob" and 3 in ((r.get("onExitCodes") or {}).get("values") or [])
      and (r.get("onExitCodes") or {}).get("operator") == "In"]
print("FailJob-on-3 rules:", len(ok))
sys.exit(0 if ok else 1)
PY
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
