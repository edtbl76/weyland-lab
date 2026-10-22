#!/usr/bin/env bats
# scripts/check-dependabot-ignores.sh (B214 leftover, 2026-10-22) — every `ignore` in .github/dependabot.yml is backed by
# a live acceptance in osv-scanner.toml, and the directory's pin is still below the ignored range.
# An ignore silences SECURITY updates for that package in that directory. Nothing expires it, so the day the cap lifts
# and the pin moves on, a stale ignore would quietly block the next real fix. The osv accepts carry the reason and an
# expiry; this ties each ignore to one.
# Exit 0 = every ignore backed and live · 1 = a defect, named · 2 = cannot check. Checking nothing is never a pass.

load helper

setup() {
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-dependabot-ignores.sh"
  T="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$T/.github" "$T/services/alpha" "$T/services/beta"
  printf 'pillow==12.3.0\ncertifi==2026.10.19\n' > "$T/services/alpha/requirements.txt"
  printf 'setuptools==81.0.0\n' > "$T/services/beta/requirements-extra.txt"
  export DEPENDABOT_ROOT="$T" DEPENDABOT_CONFIG="$T/.github/dependabot.yml" OSV_CONFIG="$T/osv-scanner.toml"
  printf '[[PackageOverrides]]\nname = "pillow"\nversion = "12.3.0"\necosystem = "PyPI"\nvulnerability.ignore = true\nreason = "alpha: capped"\n' > "$OSV_CONFIG"
  printf '\n[[IgnoredVulns]]\nid = "GHSA-aaaa-bbbb-cccc"\nreason = "setuptools: kept below 83 on purpose in beta (pkg_resources)."\n' >> "$OSV_CONFIG"
}

teardown() { teardown_stubs; }

cfg() {  # cfg <dir> <package> <range> [<dir> <package> <range>]... — one pip entry per triple, each with one ignore
  { echo "version: 2"; echo "updates:"
    while [ $# -gt 0 ]; do
      printf '  - package-ecosystem: "pip"\n    directory: "%s"\n    open-pull-requests-limit: 0\n' "$1"
      printf '    ignore:\n      - dependency-name: "%s"\n        versions: ["%s"]\n' "$2" "$3"
      shift 3
    done
  } > "$DEPENDABOT_CONFIG"
}

@test "an ignore backed by a version-scoped override at the pinned version is exit 0, counted" {
  cfg /services/alpha pillow ">=13.0.0"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK — 1 Dependabot ignore(s)"* ]] || { echo "$output"; return 1; }
}

@test "an ignore backed by an advisory-id accept naming the package and directory is exit 0" {
  cfg /services/beta setuptools ">=82.0.0"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "an ignore with no osv accept is exit 1, named" {
  cfg /services/alpha certifi ">=2027.1.1"
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNBACKED: services/alpha ignores certifi"* ]] || { echo "$output"; return 1; }
}

@test "an override at a different version does not back the ignore" {
  printf 'pillow==12.2.0\n' > "$T/services/alpha/requirements.txt"
  cfg /services/alpha pillow ">=13.0.0"
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNBACKED: services/alpha ignores pillow"*"12.2.0"* ]] || { echo "$output"; return 1; }
}

@test "a pin already inside the ignored range is a dead ignore, exit 1" {
  printf 'pillow==13.0.0\n' > "$T/services/alpha/requirements.txt"
  printf '[[PackageOverrides]]\nname = "pillow"\nversion = "13.0.0"\necosystem = "PyPI"\nvulnerability.ignore = true\nreason = "x"\n' > "$OSV_CONFIG"
  cfg /services/alpha pillow ">=13.0.0"
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"DEAD: services/alpha ignores pillow >=13.0.0 but pins 13.0.0"* ]] || { echo "$output"; return 1; }
}

@test "an ignore for a package the directory does not pin is exit 1" {
  cfg /services/beta pillow ">=13.0.0"
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"NOT PINNED: services/beta ignores pillow"* ]] || { echo "$output"; return 1; }
}

@test "an advisory-id accept that names another directory does not back the ignore" {
  printf 'setuptools==81.0.0\n' > "$T/services/alpha/requirements.txt"
  cfg /services/alpha setuptools ">=82.0.0"
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNBACKED: services/alpha ignores setuptools"* ]] || { echo "$output"; return 1; }
}

@test "no ignores at all is exit 2, not a clean pass" {
  printf 'version: 2\nupdates:\n  - package-ecosystem: "pip"\n    directory: "/services/alpha"\n' > "$DEPENDABOT_CONFIG"
  run bash "$GUARD"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK: no ignore"* ]] || { echo "$output"; return 1; }
}

@test "a version range it cannot read is exit 2, never a guess" {
  cfg /services/alpha pillow "~> 13"
  run bash "$GUARD"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"*"~> 13"* ]] || { echo "$output"; return 1; }
}

@test "a missing osv-scanner.toml is exit 2" {
  cfg /services/alpha pillow ">=13.0.0"
  rm "$OSV_CONFIG"
  run bash "$GUARD"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"*"osv-scanner.toml"* ]] || { echo "$output"; return 1; }
}

@test "the real repo passes" {
  unset DEPENDABOT_ROOT DEPENDABOT_CONFIG OSV_CONFIG
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
