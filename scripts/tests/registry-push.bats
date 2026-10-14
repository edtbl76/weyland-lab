#!/usr/bin/env bats
# B211 (2026-10-14) — the registry's push host. registry.weyland.lab took unauthenticated pushes from any pod or LAN
# machine, so anyone could replace an image every workload pulls. Pushes now go to registry-push.weyland.lab (basic auth
# at Traefik); registry.weyland.lab stays the pull name (GET/HEAD). These tests pin the two client sides:
#   - push-image.sh (rogueone) tags the pull ref to the push host, pushes there, and VERIFIES through the pull host
#     (the finalize check means "pullable", which is what a deploy needs);
#   - scripts/ci/build-images.sh writes the push credentials into a private docker config before building, and refuses
#     to start when the credentials are missing (a push that would 401 mid-pipeline is a worse failure than none).

load helper

setup() {
  setup_stubs
  PUSH="$REPO_ROOT/scripts/push-image.sh"
  BUILD="$REPO_ROOT/scripts/ci/build-images.sh"
  W="$(mktemp -d)"
}

teardown() { teardown_stubs; rm -rf "$W"; }

@test "push-image.sh pushes a registry.weyland.lab ref through the push host and verifies via the pull host" {
  stub docker 0 ""
  stub curl 0 '{"name":"weyland-guard","tags":["git-abc12345"]}'
  run bash "$PUSH" registry.weyland.lab/weyland-guard:git-abc12345
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  called_with docker "tag registry.weyland.lab/weyland-guard:git-abc12345 registry-push.weyland.lab/weyland-guard:git-abc12345"
  called_with docker "push registry-push.weyland.lab/weyland-guard:git-abc12345"
  called_with curl "https://registry.weyland.lab/v2/weyland-guard/tags/list"
}

@test "push-image.sh never pushes to the pull host (it refuses unauthenticated writes now)" {
  stub docker 0 ""
  stub curl 0 '{"tags":["v1"]}'
  run bash "$PUSH" registry.weyland.lab/x:v1
  not_called_with docker "push registry.weyland.lab/x:v1"
}

@test "push-image.sh still fails, named, when the tag never finalizes" {
  stub docker 0 ""
  stub curl 0 '{"tags":[]}'
  PUSH_ATTEMPTS=2 run bash "$PUSH" registry.weyland.lab/x:v1
  [ "$status" -eq 1 ]
  [[ "$output" == *"still missing"* ]]
}

@test "build-images.sh refuses to build when the push host is set but its credentials are not" {
  printf 'img\tservices/x\tgit-1\tk8s/x.yaml\n' > "$W/plan"
  REGISTRY_PUSH_HOST=registry-push.weyland.lab REGISTRY_PUSH_AUTH="" PLAN="$W/plan" BUMPS="$W/bumps" HOME="$W" \
    run sh "$BUILD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"REGISTRY_PUSH_AUTH"* ]]
  never_called buildctl
}

@test "build-images.sh writes the push credentials to a private docker config, never to its output" {
  printf 'img\tservices/x\tgit-1\tk8s/x.yaml\n' > "$W/plan"
  stub buildctl 1 ""      # buildkitd unreachable: the script stops right after writing the config
  REGISTRY_PUSH_HOST=registry-push.weyland.lab REGISTRY_PUSH_AUTH="ci:s3cret-pw" PLAN="$W/plan" BUMPS="$W/bumps" \
    DOCKER_CONFIG="$W/docker" run sh "$BUILD"
  [[ "$output" != *"s3cret-pw"* ]]
  [ -f "$W/docker/config.json" ]
  [ "$(stat -c %a "$W/docker/config.json")" = "600" ]
  python3 -c "
import json,base64,sys
d=json.load(open('$W/docker/config.json'))
assert base64.b64decode(d['auths']['registry-push.weyland.lab']['auth']).decode()=='ci:s3cret-pw', d
"
}
