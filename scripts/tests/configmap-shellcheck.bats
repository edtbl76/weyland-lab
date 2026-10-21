#!/usr/bin/env bats
# scripts/check-configmap-shellcheck.sh (B230, 2026-10-19) — shellcheck the shell scripts that live INSIDE k8s
# ConfigMaps, which CI's `shellcheck scripts/**` step never sees. These pin the guard's decisions with a stub
# shellcheck (the bats image has none): what it extracts, how it names a finding, and that it fails closed (exit 2)
# whenever it could not check — never a clean pass over nothing. The real-shellcheck negative case is in the demo.

setup() {
  T="$BATS_TEST_TMPDIR"
  mkdir -p "$T/k8s/a" "$T/bin"
  export CM_SHELLCHECK_K8S_DIR="$T/k8s" PATH="$T/bin:$PATH"
  SCRIPT="$BATS_TEST_DIRNAME/../check-configmap-shellcheck.sh"
  # Stub: a script containing the marker line gets one warning in shellcheck's gcc format, and exit 1.
  cat > "$T/bin/shellcheck" <<'SH'
#!/bin/sh
rc=0
for a in "$@"; do
  case "$a" in -*) continue;; esac
  if grep -q 'PLANTED_BUG' "$a"; then echo "$a:2:1: warning: planted [SC2086]"; rc=1; fi
done
exit $rc
SH
  chmod +x "$T/bin/shellcheck"
  cm "a/job.yaml" "run.sh" 'echo ok'
}

# cm <path under k8s/> <data key> <script body> — a ConfigMap (plus a CronJob document, as real manifests have)
cm() {
  mkdir -p "$(dirname "$T/k8s/$1")"
  printf 'apiVersion: v1\nkind: ConfigMap\nmetadata: {name: x}\ndata:\n  %s: |\n    #!/bin/sh\n    %s\n---\napiVersion: batch/v1\nkind: CronJob\nmetadata: {name: y}\n' "$2" "$3" > "$T/k8s/$1"
}

@test "clean scripts are exit 0 and the count is printed" {
  cm "b/other.yaml" "go.sh" 'echo fine'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK — 2 shell script(s) (2 ConfigMap key(s), 0 inline sh -c)"* ]]
}

@test "a finding is exit 1 and names manifest:key with shellcheck's line" {
  cm "b/bad.yaml" "broken.sh" 'PLANTED_BUG'
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"b/bad.yaml:broken.sh:2:1: warning: planted [SC2086]"* ]]
  [[ "$output" == *"1 of 2 shell script(s)"* ]]
}

@test "keys that are not .sh are ignored" {
  cm "b/py.yaml" "run.py" 'PLANTED_BUG'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK — 1 shell script(s) (1 ConfigMap key(s), 0 inline sh -c)"* ]]
}

@test "no shell scripts at all is exit 2, never a clean pass over nothing" {
  rm -rf "$T/k8s"; mkdir -p "$T/k8s"; cm "a/x.yaml" "conf.ini" 'k=v'
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK: no ConfigMap shell script found"* ]]
}

@test "a missing k8s directory is exit 2" {
  export CM_SHELLCHECK_K8S_DIR="$T/absent"
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK"* ]]
}

@test "an unparseable manifest is exit 2, named" {
  printf 'kind: ConfigMap\ndata: [unclosed\n' > "$T/k8s/a/broken.yaml"
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK: a/broken.yaml"* ]]
}

@test "no shellcheck on PATH is exit 2" {
  rm "$T/bin/shellcheck"
  run env PATH="$T/bin:/usr/local/bin:/usr/bin:/bin" bash "$SCRIPT"
  if command -v shellcheck >/dev/null 2>&1; then skip "a real shellcheck is on the system PATH"; fi
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK: shellcheck not found"* ]]
}

@test "the real repo's scripts are all found (13 ConfigMap keys and 37 inline sh -c scripts today)" {
  unset CM_SHELLCHECK_K8S_DIR
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  cmk=$(echo "$output" | sed -n 's/^OK — [0-9]* shell script(s) (\([0-9]*\) ConfigMap.*/\1/p')
  inl=$(echo "$output" | sed -n 's/.*ConfigMap key(s), \([0-9]*\) inline.*/\1/p')
  [ "${cmk:-0}" -ge 13 ] && [ "${inl:-0}" -ge 37 ] || { echo "$output"; return 1; }
}

# B230 DoD re-audit (2026-10-21): scripts passed inline as `sh -c '<script>'` in a container's command/args (37 of them,
# e.g. the sonar-scan-repos clone loop) were never linted; and two could-not-check paths read as a finding (exit 1).

# job <path> <container command json> — a CronJob whose one container runs the given command list
job() {
  mkdir -p "$(dirname "$T/k8s/$1")"
  printf 'apiVersion: batch/v1\nkind: CronJob\nmetadata: {name: nightly}\nspec:\n  jobTemplate:\n    spec:\n      template:\n        spec:\n          containers:\n            - name: run\n              command: %s\n' "$2" > "$T/k8s/$1"
}

@test "an inline sh -c script in a container's command is checked, and a finding names manifest:Kind/name/container" {
  job "c/inline.yaml" '["sh", "-c", "PLANTED_BUG"]'
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"c/inline.yaml:CronJob/nightly/run:2:1: warning: planted"* ]]
}

@test "a clean inline script is counted, not flagged" {
  job "c/inline.yaml" '["/bin/sh", "-c", "echo fine"]'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"1 inline sh -c"* ]]
}

@test "the extractor failing (e.g. python cannot import yaml) is exit 2, never a finding" {
  printf '#!/bin/sh\necho "ModuleNotFoundError: No module named yaml" >&2\nexit 1\n' > "$T/bin/python3"; chmod +x "$T/bin/python3"
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK"* ]]
}

@test "shellcheck failing to run on a script (exit 2 or more) is exit 2, never a finding" {
  printf '#!/bin/sh\necho "shellcheck: cannot read file" >&2\nexit 3\n' > "$T/bin/shellcheck"; chmod +x "$T/bin/shellcheck"
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"CANNOT CHECK"* && "$output" == *"shellcheck exited 3"* ]]
}
