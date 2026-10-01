#!/usr/bin/env bats
#
# npm_install_locked (scripts/lib/lang-fixtures.sh) — how the node lanes install a project's dependencies.
#
# Found 2026-09-30 (CI 212): golden-paths/frontend/angular had no package-lock.json, so `npm install` resolved
# `ignore@7.0.11` three minutes after it was published, while its tarball still 404'd, and the lane broke on an
# upstream publish it never chose. A lockfile + `npm ci` makes the lane install exactly what was committed; a project
# with no lockfile is a broken lane (exit 2), not a silent float to whatever is newest.

load helper

setup() {
  setup_stubs
  # shellcheck source=scripts/lib/lang-fixtures.sh
  . "${BATS_TEST_DIRNAME}/../lib/lang-fixtures.sh"
  PROJ="$(mktemp -d)"
  echo '{"name":"p"}' > "$PROJ/package.json"
}
teardown() { teardown_stubs; rm -rf "$PROJ"; }

@test "a project with a lockfile installs with npm ci (never npm install)" {
  echo '{}' > "$PROJ/package-lock.json"
  stub npm 0
  run npm_install_locked "$PROJ"
  [ "$status" -eq 0 ]
  grep -q '^npm ci' "$STUB_LOG"
  ! grep -q '^npm install' "$STUB_LOG"
}

@test "a project with NO lockfile is a broken lane (exit 2), and npm is never run" {
  stub npm 0
  run npm_install_locked "$PROJ"
  [ "$status" -eq 2 ]
  [[ "$output" == *"LANE BROKEN: no package-lock.json"* ]]
  ! grep -q '^npm' "$STUB_LOG"
}

@test "npm ci failing is a broken lane (exit 2), naming the directory" {
  echo '{}' > "$PROJ/package-lock.json"
  stub npm 1
  run npm_install_locked "$PROJ"
  [ "$status" -eq 2 ]
  [[ "$output" == *"LANE BROKEN: npm ci failed in $PROJ"* ]]
}

@test "node_modules already present (a CI cache) skips the install" {
  mkdir "$PROJ/node_modules"
  stub npm 1
  run npm_install_locked "$PROJ"
  [ "$status" -eq 0 ]
  ! grep -q '^npm' "$STUB_LOG"
}

@test "every node golden path commits a lockfile (so the lane never floats)" {
  root="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"   # absolute: the lane runs bats from scripts/tests, not the root
  missing=""
  while IFS= read -r pj; do
    d="$(dirname "$pj")"
    case "$d" in *node_modules*) continue ;; esac
    [ -f "$root/$d/package-lock.json" ] || missing="$missing $d"
  done < <(cd "$root" && find golden-paths -name package.json -not -path '*/node_modules/*' -not -path '*/.*/*')
  [ -z "$missing" ] || { echo "no package-lock.json:$missing"; false; }
}

@test "every node golden-path Dockerfile installs with npm ci (the image build never floats either)" {
  root="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
  floating=""
  while IFS= read -r df; do
    d="$(dirname "$df")"
    [ -f "$root/$d/package.json" ] || continue
    grep -q 'npm install' "$root/$df" && floating="$floating $d"
  done < <(cd "$root" && find golden-paths -name Dockerfile -not -path '*/node_modules/*' -not -path '*/.*/*')
  [ -z "$floating" ] || { echo "Dockerfile uses npm install (use npm ci):$floating"; false; }
}
