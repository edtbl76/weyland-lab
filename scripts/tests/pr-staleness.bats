#!/usr/bin/env bats
# Age-threshold logic for the open-PR staleness alert (B131).
#
# The logic under test is not a repo script — it is the shell the CronJob actually runs, which lives
# in a ConfigMap inside k8s/pr-lifecycle/pr-staleness.yaml. These tests pull that exact text back out
# of the manifest and exercise it. That indirection is deliberate: a tested copy sitting beside the
# deployed copy drifts, and the drift is silent because both halves keep passing their own checks.

setup() {
  load helper
  setup_stubs
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/pr-staleness.yaml"
  LOGIC="$STUB_DIR/pr-staleness.sh"
  extract_configmap_script "$MANIFEST" "pr-staleness.sh" >"$LOGIC"
}

teardown() {
  teardown_stubs
}

@test "the decision logic is actually extractable from the deployed manifest" {
  # If this fails, every other test in this file is vacuously green against an empty file. It is the
  # tripwire for the ConfigMap-as-single-source-of-truth arrangement.
  [ -s "$LOGIC" ]
  grep -q 'is_stale' "$LOGIC"
}

@test "FR5.1 a CI image-bump PR is stale after one day" {
  PR_STALENESS_LIB=1 source "$LOGIC"
  run is_stale 'ci/image-bump-9a4996c6' 90000    # 25h
  [ "$status" -eq 0 ]
  run is_stale 'ci/image-bump-9a4996c6' 3600     # 1h
  [ "$status" -ne 0 ]
}

@test "FR5.1 every other PR is stale only after seven days" {
  PR_STALENESS_LIB=1 source "$LOGIC"
  run is_stale 'feature/new-thing' 90000         # 25h — well inside the 7d budget
  [ "$status" -ne 0 ]
  run is_stale 'feature/new-thing' 700000        # ~8d
  [ "$status" -eq 0 ]
}

@test "FR5.1/OQ4 the threshold keys on the branch prefix, not on who opened it" {
  # OQ4 resolved to the branch prefix: it is the more specific signal. A human can open a branch
  # named ci/image-bump-* and a bot can open anything else; the prefix says what the PR IS.
  PR_STALENESS_LIB=1 source "$LOGIC"
  run threshold_for 'ci/image-bump-9a4996c6'
  [ "$output" -eq 86400 ]
  run threshold_for 'main'
  [ "$output" -eq 604800 ]
  run threshold_for 'feature/ci-image-bump-lookalike'
  [ "$output" -eq 604800 ]
}

@test "FR5.2 the check covers all authors, not just the bot" {
  # The requirement is unfiltered coverage. Expressed as a property of the interface: the decision
  # takes a branch and an age and nothing else, so there is no author for it to filter on.
  PR_STALENESS_LIB=1 source "$LOGIC"
  run is_stale 'chore/human-opened-this' 700000
  [ "$status" -eq 0 ]
}

@test "FR5.5 the alert carries the labels and annotations the Telegram template renders" {
  # Shape check against the PrometheusRule-equivalent payload, so the synthetic alert renders
  # identically to every other alert in the lab (NFR5 — no routing change).
  grep -q 'severity' "$LOGIC"
  grep -q 'summary' "$LOGIC"
  grep -q 'description' "$LOGIC"
  grep -q 'alertname' "$LOGIC"
}

# --- The watchdog must never go quiet when it cannot see -------------------------------
# A monitor that reports "0 problems" because its data source failed is worse than no monitor: it
# emits a green signal. The first version of this script piped `curl -sf | jq > file`, and under
# `set -e` a pipeline's status is the LAST command's — so a 401, a 500 or no network at all reached
# jq as empty input, jq emitted nothing, and the run printed "0 open PR(s) checked, 0 alert(s)".
# Indistinguishable from a genuinely empty repo, which is exactly what weyland-lab is.

@test "a curl transport failure is fatal, not 'zero open PRs'" {
  PR_STALENESS_LIB=1 source "$LOGIC"
  export GITHUB_TOKEN=not-a-real-token
  stub curl 7 ''          # 7 = could not connect
  run fetch_open_prs edtbl76/weyland-lab
  [ "$status" -ne 0 ]
}

@test "a non-200 from GitHub is fatal, not 'zero open PRs'" {
  PR_STALENESS_LIB=1 source "$LOGIC"
  export GITHUB_TOKEN=not-a-real-token
  stub curl 0 '500'       # curl itself succeeds; the API did not
  run fetch_open_prs edtbl76/weyland-lab
  [ "$status" -ne 0 ]
  [[ "$output" == *"500"* ]]
}

@test "an expired or unscoped token (401) is fatal, not 'zero open PRs'" {
  PR_STALENESS_LIB=1 source "$LOGIC"
  export GITHUB_TOKEN=not-a-real-token
  stub curl 0 '401'
  run fetch_open_prs edtbl76/weyland-lab
  [ "$status" -ne 0 ]
  [[ "$output" == *"401"* ]]
}

# --- Multi-repo coverage ---------------------------------------------------------------
# FR5.2 originally scoped this to weyland-lab alone. Widened 2026-08-22 at the operator's direction
# once the PAT was granted read access to all six active repos.

@test "FR5.2 all six active repos are watched, not just weyland-lab" {
  PR_STALENESS_LIB=1 source "$LOGIC"
  for r in Algopedia ServiceTransformation emangini-tailwind-nextjs-contentlayer \
           startme-curator stud.io weyland-lab; do
    [[ "$REPOS" == *"edtbl76/$r"* ]] || {
      echo "missing repo: edtbl76/$r  (REPOS=$REPOS)"
      return 1
    }
  done
}

@test "FR5.2 one unreachable repo does not silently shrink the watch set" {
  # The subtle multi-repo failure: repo 3 of 6 401s, the loop swallows it, and the run reports on 5
  # repos while claiming to cover 6. Every repo must be attempted AND the run must end non-zero.
  export GITHUB_TOKEN=not-a-real-token
  stub curl 0 '403'
  run bash "$LOGIC"
  [ "$status" -ne 0 ]
  [ "$(calls_to curl | grep -c 'api.github.com')" -eq 6 ]
  [[ "$output" == *"403"* ]]
}

@test "the fetch reports success explicitly, so a real zero is distinguishable from a broken one" {
  # The log line that makes A3 (can the cluster reach GitHub at all?) provable from the job output.
  grep -q 'fetched' "$LOGIC"
}

@test "NFR7 the Job tells the Istio sidecar to quit so concurrencyPolicy Forbid cannot deadlock" {
  grep -q 'quitquitquit' "$MANIFEST"
  grep -q 'concurrencyPolicy: Forbid' "$MANIFEST"
}
