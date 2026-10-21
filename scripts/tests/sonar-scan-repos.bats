#!/usr/bin/env bats
# The sonar-scan-repos runner (k8s/sonarqube/sonar-scan-repos.yaml, ConfigMap key sonar-all.sh) — what arguments each
# pre-cloned repo is scanned with. It runs the REAL script out of the manifest against fake repos, with a stub
# `sonar-scanner` that records its arguments, so the assertions are on the runner's per-repo decisions.
#
# Why the Java case exists (2026-10-19): freejack gained 177 source-only .java lesson files (no build, so no
# compiled classes; its other 1,527 .java are vendored third-party code under vendor/, excluded by **/vendor/**); SonarQube's Java analyzer refuses to run without `sonar.java.binaries`, so the whole freejack
# scan failed and with it the 2026-10-18 Job. Source-only analysis = point that setting at an empty directory.

setup() {
  T="$BATS_TEST_TMPDIR"
  MANIFEST="$BATS_TEST_DIRNAME/../../nodes/mother/lab/weyland-platform/k8s/sonarqube/sonar-scan-repos.yaml"
  python3 - "$MANIFEST" "$T/sonar-all.sh" <<'PY'
import sys, yaml
for d in yaml.safe_load_all(open(sys.argv[1])):
    if d and d.get("kind") == "ConfigMap":
        open(sys.argv[2], "w").write(d["data"]["sonar-all.sh"])
PY
  mkdir -p "$T/bin" "$T/src"
  # Stub scanner: one line per call — the project key, then every argument; exits 1 for a repo named "broken".
  cat > "$T/bin/sonar-scanner" <<'SH'
#!/bin/sh
key=""; for a in "$@"; do case "$a" in -Dsonar.projectKey=*) key="${a#-Dsonar.projectKey=}";; esac; done
echo "$key $*" >> "$CALLS"
[ "$key" = "broken" ] && exit 1
exit 0
SH
  chmod +x "$T/bin/sonar-scanner"
  export PATH="$T/bin:$PATH" CALLS="$T/calls" SONAR_SRC="$T/src" SONAR_HOST_URL="http://sonar" SONAR_TOKEN="t"
}

call_for() { grep "^$1 " "$CALLS"; }

@test "a repo with .java files and no build gets source-only Java analysis (an empty binaries dir)" {
  mkdir -p "$T/src/freejack/lessons/x"; echo 'public class A {}' > "$T/src/freejack/lessons/x/A.java"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  line="$(call_for freejack)"
  [[ "$line" == *"-Dsonar.java.binaries="* ]]
  dir="$(echo "$line" | tr ' ' '\n' | sed -n 's/^-Dsonar.java.binaries=//p')"
  [ -d "$dir" ] && [ -z "$(ls -A "$dir")" ]
}

@test "a repo without .java files gets no Java setting" {
  mkdir -p "$T/src/blog"; echo 'export {}' > "$T/src/blog/a.ts"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 0 ]
  call_for blog >/dev/null || { echo "blog was never scanned"; return 1; }
  [[ "$(call_for blog)" != *"sonar.java.binaries"* ]]
  [[ "$(call_for blog)" == *"-Dsonar.sources=."* ]]
}

@test "a repo whose own sonar-project.properties sets java binaries is left to its own config" {
  mkdir -p "$T/src/own"; echo 'class B {}' > "$T/src/own/B.java"
  printf 'sonar.sources=src\nsonar.java.binaries=build/classes\n' > "$T/src/own/sonar-project.properties"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 0 ]
  call_for own >/dev/null || { echo "own was never scanned"; return 1; }
  [[ "$(call_for own)" != *"sonar.java.binaries"* ]]
  [[ "$(call_for own)" != *"-Dsonar.sources=."* ]]
}

@test "a repo with its own properties but .java and no binaries setting still gets source-only Java" {
  mkdir -p "$T/src/studio"; echo 'class C {}' > "$T/src/studio/C.java"
  printf 'sonar.sources=src\n' > "$T/src/studio/sonar-project.properties"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 0 ]
  [[ "$(call_for studio)" == *"-Dsonar.java.binaries="* ]]
  [[ "$(call_for studio)" != *"-Dsonar.sources=."* ]]
}

@test ".java files under node_modules do not count" {
  mkdir -p "$T/src/web/node_modules/pkg"; echo 'class D {}' > "$T/src/web/node_modules/pkg/D.java"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 0 ]
  call_for web >/dev/null || { echo "web was never scanned"; return 1; }
  [[ "$(call_for web)" != *"sonar.java.binaries"* ]]
}

@test "one failing repo still scans the rest and fails the job" {
  mkdir -p "$T/src/broken" "$T/src/zeta"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 1 ]
  call_for zeta
  [[ "$output" == *"sonar-scanner failed for broken"* ]]
}

@test "the runner uses no tool the scanner image lacks (sonar-scanner-cli has no find)" {
  # Observed 2026-10-19: `command -v find` fails in sonarsource/sonar-scanner-cli:latest (Amazon Linux 2023).
  ! grep -vE '^[[:space:]]*#' "$T/sonar-all.sh" | grep -nE '(^|[^_[:alnum:]])find[[:space:]]'
}

# B229 DoD re-audit (2026-10-21): a repo the init container failed to clone was simply absent from /src, so the loop
# never saw it and the Job went green with that repo unscanned. The init container now records each failure in
# /src/.clone-failed and the runner fails on it, naming the repo, while still scanning the rest.

@test "a repo that failed to clone fails the job by name, and the cloned ones are still scanned" {
  mkdir -p "$T/src/alpha"
  printf 'private-repo\n' > "$T/src/.clone-failed"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"not scanned (clone failed): private-repo"* ]]
  call_for alpha >/dev/null || { echo "alpha was never scanned"; return 1; }
}

@test "no clone-failed marker and every scan passing is exit 0" {
  mkdir -p "$T/src/alpha"
  run sh "$T/sonar-all.sh"
  [ "$status" -eq 0 ]
  [[ "$output" != *"clone failed"* ]]
}

@test "the init container records a failed clone in the marker the runner reads" {
  python3 - "$MANIFEST" <<'PY'
import sys, yaml
for d in yaml.safe_load_all(open(sys.argv[1])):
    if d and d.get("kind") == "CronJob":
        init = d["spec"]["jobTemplate"]["spec"]["template"]["spec"]["initContainers"][0]
        script = init["command"][-1]
        assert ">> /src/.clone-failed" in script, "the clone loop does not record failures in /src/.clone-failed"
        print("ok")
PY
}
