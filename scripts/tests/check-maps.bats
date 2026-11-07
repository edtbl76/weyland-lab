#!/usr/bin/env bats
#
# check-maps.sh (B189 Closing Gap, 2026-11-06) — the hand-written HTML maps must keep up with the systems they show.
# Found doing B189: the CI map said 23 steps while the pipeline had 70, and the Platform Map had no Slack, Grafana
# Cloud IRM or Trunk although all three were live. Pillar 2 checked diagrams, not maps, so B184, U14 and B189 shipped
# without them. Three checks: every pipeline step is named on the CI map; the CI map's "N-step" claim is the real
# count; every LikeC4 external system has a data-c4 row on the Platform Map.

load helper

setup() {
  CHK="$REPO_ROOT/scripts/check-maps.sh"
  T="$(mktemp -d)"
  export CHECK_MAPS_PIPELINE="$T/pipeline.yml" CHECK_MAPS_CI_MAP="$T/ci.html"
  export CHECK_MAPS_LIKEC4="$T/model.likec4" CHECK_MAPS_PLATFORM_MAP="$T/platform.html"
  printf 'steps:\n  - name: yaml-syntax\n    image: x\n  - name: test-python\n    image: x\n' > "$CHECK_MAPS_PIPELINE"
  printf '<p class="lede">runs a 2-step Woodpecker pipeline</p>\n<div class="step"><span class="name">yaml-syntax</span></div>\n<div class="lane"><span class="n">test-python</span></div>\n' > "$CHECK_MAPS_CI_MAP"
  printf 'model {\n  slack = ext "Slack" "the feed"\n  trunk = ext "Trunk Flaky Tests" "tests"\n}\n' > "$CHECK_MAPS_LIKEC4"
  printf '<div class="row" data-c4="slack">Slack</div>\n<div class="row" data-c4="trunk">Trunk</div>\n' > "$CHECK_MAPS_PLATFORM_MAP"
}

teardown() {
  [ -n "${T:-}" ] && [ -d "$T" ] && rm -rf "$T"
  return 0
}

@test "clean maps pass and say what they checked" {
  run bash "$CHK"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK"*"2 pipeline step(s)"*"2 external system(s)"* ]]
}

@test "a pipeline step missing from the CI map fails and names it" {
  printf '  - name: trunk-upload\n    image: x\n' >> "$CHECK_MAPS_PIPELINE"
  sed -i 's/2-step/3-step/' "$CHECK_MAPS_CI_MAP"
  run bash "$CHK"
  [ "$status" -eq 1 ]
  [[ "$output" == *"CI map is missing step"*"trunk-upload"* ]]
}

@test "a step name only in prose does not count: it must be a step or lane entry" {
  printf '  - name: trunk-upload\n    image: x\n' >> "$CHECK_MAPS_PIPELINE"
  sed -i 's/2-step/3-step/' "$CHECK_MAPS_CI_MAP"
  printf '<p>results go to trunk-upload later</p>\n' >> "$CHECK_MAPS_CI_MAP"
  run bash "$CHK"
  [ "$status" -eq 1 ]
  [[ "$output" == *"trunk-upload"* ]]
}

@test "a stale step count in the CI map's lede fails" {
  sed -i 's/2-step/23-step/' "$CHECK_MAPS_CI_MAP"
  run bash "$CHK"
  [ "$status" -eq 1 ]
  [[ "$output" == *"says 23 steps"*"has 2"* ]]
}

@test "a LikeC4 external with no data-c4 row on the Platform Map fails and names it" {
  printf 'model {\n  slack = ext "Slack" "x"\n  trunk = ext "Trunk Flaky Tests" "y"\n  grafanaIrm = ext "Grafana Cloud IRM" "z"\n}\n' > "$CHECK_MAPS_LIKEC4"
  run bash "$CHK"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Platform Map has no row for"*"grafanaIrm"* ]]
}

@test "a missing input file is exit 2, never a pass" {
  rm "$CHECK_MAPS_CI_MAP"
  run bash "$CHK"
  [ "$status" -eq 2 ]
  [[ "$output" == *"not found"* ]]
}

@test "a pipeline with no steps is exit 2 (nothing checked is not a pass)" {
  printf 'steps: []\n' > "$CHECK_MAPS_PIPELINE"
  run bash "$CHK"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no steps"* ]]
}

@test "a model with no externals is exit 2" {
  printf 'model {\n}\n' > "$CHECK_MAPS_LIKEC4"
  run bash "$CHK"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no ext"* ]]
}

@test "the real repo passes" {
  unset CHECK_MAPS_PIPELINE CHECK_MAPS_CI_MAP CHECK_MAPS_LIKEC4 CHECK_MAPS_PLATFORM_MAP
  run bash "$CHK"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
