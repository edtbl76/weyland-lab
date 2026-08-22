# Shared paths + status helpers for the repo-root bash scripts. Source it, do not execute it:
#
#   . "$(dirname "$0")/lib/common.sh"
#
# WHY THIS EXISTS: `here="$(cd "$(dirname "$0")/.." && pwd)"` was copy-pasted into six scripts and the
# literal path `nodes/mother/lab/weyland-platform` was hardcoded in eight. Moving the platform tree — or
# adding a second node under nodes/ — meant editing every one of them and hoping none were missed. There
# is now one definition.
#
# SCOPE — repo-root `scripts/*.sh` ONLY. `scripts/ci/*.sh` deliberately does NOT source this, and the
# reason is the environment boundary, not the shell dialect:
#
#   `scripts/*.sh`    developer scripts, run by hand on the DEV MACHINE during development.
#   `scripts/ci/*.sh` pipeline steps, run in alpine containers on MOTHER's cluster.
#
# Sourcing this from the CI scripts would make a dev-machine convenience file something the image
# pipeline must find and parse at build time — a runtime dependency across a boundary that is
# deliberately decoupled. That is a worse trade than the duplication it removes. (They are also POSIX
# `sh` while this uses BASH_SOURCE, but that is the smaller reason.)
#
# The duplicated `PLATFORM="nodes/mother/lab/weyland-platform"` is one literal, near-constant, and its
# divergence is loud rather than silent — a wrong path fails immediately with FileNotFoundError. If the
# tree ever moves, grep for PLATFORM=.

# shellcheck shell=bash
# (This file is sourced, never executed, so it has no shebang — the directive tells shellcheck
# which dialect to check it as. Without it: SC2148.)

# Guard against double-sourcing.
[ -n "${WEYLAND_COMMON_SOURCED:-}" ] && return 0
WEYLAND_COMMON_SOURCED=1

# Resolve from THIS file's location, not the caller's, so a script can be invoked from anywhere
# (`bash scripts/foo.sh`, `./scripts/foo.sh`, an absolute path, or a symlink's target directory).
#
# TWO levels up, not one: this file is scripts/lib/common.sh, so dirname is scripts/lib and the
# repo root is its grandparent. Getting this wrong resolves REPO_ROOT to scripts/ and every path
# built from it silently points one directory too deep — which is exactly what happened when this
# helper was first written (2026-08-21) and broke check-app-registry + check-quality-tools.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC2034  # consumed by the scripts that source this file, not used here
PLATFORM_DIR="$REPO_ROOT/nodes/mother/lab/weyland-platform"

# Paths only, on purpose. `say`/`ok`/`warn`/`die` status helpers were added here 2026-08-21 and
# removed the same day: nothing called them. The duplication they would have absorbed is 2 die-shaped
# sites and 8 status prints across 3 files, so adopting them meant editing working scripts to save
# nothing, while creating a second sanctioned way to print status. `run-scan-suite.sh` remains the
# convention exemplar (see the codekb's code-structure.md). Add a helper here when it has a caller.
