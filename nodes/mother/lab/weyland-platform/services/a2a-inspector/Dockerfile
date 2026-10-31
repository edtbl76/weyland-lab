# A2A Inspector (B17) — a patch layer over the hand-built v1, so the fix is reproducible from git.
#
# v1 was built from github.com/a2aproject/a2a-inspector and pushed by hand, with no Dockerfile in this repo. Its uv
# environment carried certifi 2025.6.15, inside GHSA-6q48-6c7w-9gw2 (CRITICAL, compromised emSign intermediates; fixed
# in 2026.10.19), found by the 2026-10-22 scan. The image starts with `uv run`, which re-syncs the venv to uv.lock at
# start, so the upgrade goes into the LOCK, then the venv is synced from it (a venv-only upgrade would be undone).
# v4 (2026-10-22, later): PyJWT too (v1 locked 2.10.1; the HIGH advisory of 2026-10-21/22 is fixed in 2.14.0).
# Rebuilding v1 itself from upstream is still a recorded gap (docs/backlog.md B211 DoD).
#   docker build -t registry.weyland.lab/a2a-inspector:vN nodes/mother/lab/weyland-platform/services/a2a-inspector
#   bash scripts/push-image.sh registry.weyland.lab/a2a-inspector:vN      (next FREE tag; then bump k8s/a2a-inspector)
FROM registry.weyland.lab/a2a-inspector:v1@sha256:06b0d76b603fb3c4cb21d3e4548d8580d98eb8bcd09cac9184e09eba2f4c9747
WORKDIR /app
# pipefail: the grep below is the check that the lock really moved; a failing step must fail the build.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# v5 (2026-10-31, B234): pyasn1 too (v1 locked 0.6.1; GHSA-2qm8-x737-gmw5 et al., 4 HIGH, fixed in 0.6.5). The certifi
# check is now ">= 2026.10.19", not an exact match: --upgrade-package resolves the NEWEST certifi (2026.10.23 today), so
# the exact check failed closed on every rebuild once a newer certifi shipped.
RUN uv lock --upgrade-package certifi --upgrade-package pyjwt --upgrade-package pyasn1 \
    && grep -A1 '^name = "certifi"' uv.lock | grep -qE 'version = "(2026\.10\.(19|2[0-9]|3[01])|2026\.1[12]\.[0-9]+|20(2[7-9]|[3-9][0-9])\.[0-9]+\.[0-9]+)"' \
    && grep -A1 '^name = "pyasn1"' uv.lock | grep -qE 'version = "0\.6\.([5-9]|[1-9][0-9])"' \
    && grep -A1 '^name = "pyjwt"' uv.lock | grep -qE 'version = "2\.(1[4-9]|[2-9][0-9])\.' \
    && uv sync --locked
WORKDIR /app/backend
