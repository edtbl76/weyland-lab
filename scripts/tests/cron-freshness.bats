#!/usr/bin/env bats
# Scheduled-work freshness watchdog (B135 observability).
#
# WHAT THIS EXISTS TO CATCH: `nightly-images` sat `enabled: false` from 2026-08-18 to 2026-08-22 while
# docs/schedules.md documented it as running daily. Four days of silence. No alert in the estate could
# have caught it — all 41 alert rules watch things that ARE running, and a Woodpecker cron is not a
# Kubernetes object at all, so kube-state-metrics cannot see it either.
#
# Same ConfigMap-extraction arrangement as pr-staleness.bats: the logic under test is the exact shell
# the CronJob runs, pulled back out of the manifest, because a tested copy beside a deployed copy
# drifts silently while both halves keep passing their own checks.

setup() {
  load helper
  setup_stubs
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/cron-freshness.yaml"
  LOGIC="$STUB_DIR/cron-freshness.sh"
  extract_configmap_script "$MANIFEST" "cron-freshness.sh" >"$LOGIC"
}

teardown() {
  teardown_stubs
}

@test "the decision logic is actually extractable from the deployed manifest" {
  # Tripwire: without this, every test below is vacuously green against an empty file.
  [ -s "$LOGIC" ]
  grep -q 'is_disabled' "$LOGIC"
  grep -q 'next_exec_overdue' "$LOGIC"
}

@test "a disabled cron is the headline failure and is detected" {
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run is_disabled 'false'
  [ "$status" -eq 0 ]
}

@test "an enabled cron is not reported as disabled" {
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run is_disabled 'true'
  [ "$status" -ne 0 ]
}

@test "a missing or unparseable enabled field is treated as disabled, not as healthy" {
  # Fail closed. An absent field is a failure to observe; reading it as "enabled" would reproduce the
  # exact bug class this watchdog exists for — an absent result standing for success.
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run is_disabled ''
  [ "$status" -eq 0 ]
  run is_disabled 'null'
  [ "$status" -eq 0 ]
}

@test "next_exec in the past beyond the grace window is overdue" {
  # This is the tell that actually found the dead cron: a next_exec that has already passed means the
  # scheduler is not advancing it.
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run next_exec_overdue 1787000000 1787460000 3600   # ~128h in the past
  [ "$status" -eq 0 ]
}

@test "next_exec in the future is not overdue" {
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run next_exec_overdue 1787500000 1787460000 3600
  [ "$status" -ne 0 ]
}

@test "a next_exec just past its time is inside the grace window and does not alert" {
  # The scheduler needs room to actually run the job. Alerting the instant next_exec passes would
  # fire on every normal execution.
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run next_exec_overdue 1787459000 1787460000 3600   # ~17m past, grace 1h
  [ "$status" -ne 0 ]
}

@test "next_exec of 0 (never scheduled) is overdue" {
  # Woodpecker reports next_exec 0 for a cron that has never been scheduled. That is precisely the
  # disabled-since-creation state, and it must not read as "far future".
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  run next_exec_overdue 0 1787460000 3600
  [ "$status" -eq 0 ]
}

@test "fetch_crons fails closed on a non-200 response" {
  # The pr-staleness lesson, pinned here too: curl -sf collapsing every non-2xx to exit 0 turned a 401
  # into "no crons found", which is indistinguishable from a healthy repo with no crons.
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  stub curl 0 '401'
  run fetch_crons 2
  [ "$status" -ne 0 ]
  [[ "$output" == *"NOT reporting"* ]]
}

@test "fetch_crons fails closed when curl cannot reach the host at all" {
  CRON_FRESHNESS_LIB=1 source "$LOGIC"
  stub curl 7 ''
  run fetch_crons 2
  [ "$status" -ne 0 ]
  [[ "$output" == *"NOT reporting"* ]]
}
