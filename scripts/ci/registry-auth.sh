#!/bin/sh
# B211 (2026-10-14) — registry push credentials for CI. registry.weyland.lab is the PULL name (GET/HEAD only); pushes go
# to the push host behind basic auth. Sourced by scripts/ci/build-images.sh and scripts/run-golden-path-jobs.sh:
#   registry_push_auth <push-host>
# writes "$REGISTRY_PUSH_AUTH" (user:password, the Woodpecker secret registry_push_auth) into a private docker config
# ($DOCKER_CONFIG/config.json, mode 600), which buildctl and cosign read. Returns 1, named, when the credentials are
# missing: a push that 401s mid-pipeline is worse than not starting. Never prints the credentials.
registry_push_auth() {
  _host="$1"
  [ -n "${REGISTRY_PUSH_AUTH:-}" ] || { echo "REGISTRY_PUSH_AUTH is unset — cannot push to ${_host} (Woodpecker secret registry_push_auth)"; return 1; }
  DOCKER_CONFIG="${DOCKER_CONFIG:-$(mktemp -d)}"; export DOCKER_CONFIG
  mkdir -p "$DOCKER_CONFIG"
  ( umask 077; printf '{"auths":{"%s":{"auth":"%s"}}}\n' "$_host" \
      "$(printf '%s' "$REGISTRY_PUSH_AUTH" | base64 | tr -d '\n')" > "$DOCKER_CONFIG/config.json" )
}
