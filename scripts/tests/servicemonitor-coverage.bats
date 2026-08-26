#!/usr/bin/env bats
# B148 — ServiceMonitor / workload / scrape reconciliation.
#
# WHY THIS EXISTS: `data-mesh/trino`'s ServiceMonitor was created, committed, Argo-applied and
# `kubectl get`-able for 59 days while exporting exactly zero metrics. Nothing in the estate could
# say so, because the condition has NO POSITIVE SIGNAL anywhere:
#
#   kubectl get servicemonitor trino  -> exists, 60d          ✅
#   up{job="trino"}                   -> no data              (reads as "no traffic", not "broken")
#   the Grafana panel                 -> empty                (indistinguishable from idle)
#
# Prometheus only creates a scrape pool once discovery matches at least one endpoint, so a
# ServiceMonitor whose selector matches NOTHING is completely invisible in /api/v1/targets. It cannot
# be found by asking "is anything wrong"; it is only found by enumerating what SHOULD exist and
# subtracting what DOES — the same inverse question check-port-iac-coverage.sh asks of Port and
# ScheduledJobNeverSucceeded asks of CronJobs.
#
# THIS IS NOT A BINARY "IS IT SCRAPING" CHECK, and an earlier draft that was got the shape wrong. The
# guard reconciles THREE planes, and a disagreement between any of them is the defect:
#
#   INTENDED  .spec.replicas on the live workload
#   ACTUAL    .status.readyReplicas
#   OBSERVED  the Prometheus scrape-pool target count
#
# Reading INTENDED from the cluster is legitimate here ONLY because Argo selfHeal (verified on 75 of
# 78 apps; the 3 without are ConfigMap-only) continuously overwrites .spec.replicas from git. That
# makes the field a cached read of git rather than self-graded cluster state. The same mechanism that
# makes `argocd app rollback` a trap is what makes this field trustworthy.
#
# Without the INTENDED plane, `0 replicas` is ambiguous input rather than an answer: deliberately
# parked and crashed-at-3am are byte-identical. That ambiguity is the "an absent result must never
# stand for success" rule one level up.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-servicemonitor-coverage.sh"
}

teardown() {
  teardown_stubs
}

lib_source() {
  SERVICEMONITOR_COVERAGE_LIB=1 source "$GUARD"
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

# --- classify: the whole decision ----------------------------------------------------------------
#
# classify <intended> <actual> <targets> -> prints ONE verdict token.
#
# The matrix, and why each cell is what it is:
#
#   INTENDED  ACTUAL  OBSERVED  verdict    meaning
#   >0        >0      >0        ok         running and scraped
#   >0        >0      0         blind      RUNNING AND UNMONITORED  <- trino, the B148 defect
#   >0        0       *         down       should be up and is not
#   0         0       0         sleeping   deliberately parked, committed as replicas: 0
#   0         >0      *         zombie     awake without a declaration (cannot persist under selfHeal)
#   0         0       >0        stale      scraped after being parked; targets should have drained

@test "classify: running and scraped is ok" {
  lib_source
  run classify 1 1 1
  [ "$status" -eq 0 ]
  [ "$output" = "ok" ]
}

@test "classify: running with NO scrape pool is blind — the trino defect" {
  # The single most important row in this file. 1 replica desired, 1 ready, zero targets.
  lib_source
  run classify 1 1 0
  [ "$status" -eq 0 ]
  [ "$output" = "blind" ]
}

@test "classify: intended up but zero ready is down, regardless of targets" {
  lib_source
  run classify 1 0 0
  [ "$output" = "down" ]
  run classify 2 0 1
  [ "$output" = "down" ]
}

@test "classify: deliberately parked is sleeping, NOT a failure" {
  # replicas: 0 committed to git. This is the cell that stops the guard from being muted.
  lib_source
  run classify 0 0 0
  [ "$status" -eq 0 ]
  [ "$output" = "sleeping" ]
}

@test "classify: awake while declared parked is a zombie" {
  # Reverse drift. My binary draft marked this GREEN because it scrapes fine — it scrapes a thing
  # that should not exist, on a node already at ~80Gi with no swap.
  lib_source
  run classify 0 1 1
  [ "$output" = "zombie" ]
}

@test "classify: parked but still producing targets is stale" {
  lib_source
  run classify 0 0 2
  [ "$output" = "stale" ]
}

@test "classify: a multi-replica workload scraped on every pod is ok" {
  lib_source
  run classify 3 3 3
  [ "$output" = "ok" ]
}

@test "classify: partially-ready but scraped is ok, not down" {
  # A rolling update has readyReplicas < replicas for a minute. That is not a monitoring defect and
  # must not page. Something is ready and something is scraped.
  lib_source
  run classify 3 2 2
  [ "$output" = "ok" ]
}

@test "classify: no resolvable workload but actively scraping is unmanaged, not a failure" {
  # -1 means "nothing in Kubernetes declares intent for this". Real instances found on the live
  # cluster: monitoring-kube-prometheus-apiserver (a selector-less Service with manual Endpoints)
  # and -kubelet (a host process on each node). Neither has a Deployment and neither ever will, yet
  # both scrape correctly. Dropping them in ACCEPTED would stop checking them entirely — if the
  # kubelet scrape died we would never hear about it. The scrape itself is the evidence.
  lib_source
  run classify -1 -1 1
  [ "$status" -eq 0 ]
  [ "$output" = "unmanaged" ]
  run classify -1 -1 3
  [ "$output" = "unmanaged" ]
}

@test "classify: no resolvable workload AND no targets is an orphan — the trino shape" {
  # This is the cell that must NOT be softened by the unmanaged rule above. trino resolves to no
  # workload and scrapes nothing, so there is no evidence of correctness from either plane.
  lib_source
  run classify -1 -1 0
  [ "$status" -eq 0 ]
  [ "$output" = "orphan" ]
}

@test "classify: -1 is the ONLY negative it accepts" {
  # A sentinel is a contract, not a licence to accept junk. -2 or -99 means a lookup went wrong in a
  # way nobody designed for, and that must be loud.
  lib_source
  run classify -2 -1 1
  [ "$status" -ne 0 ]
  run classify -1 -1 -5
  [ "$status" -ne 0 ]
}

@test "classify: refuses non-numeric input rather than guessing" {
  # An unparsed field arriving as "" or "<none>" must be LOUD. Silently treating it as 0 would
  # classify a broken lookup as `sleeping` — a clean pass over a workload nobody measured.
  lib_source
  run classify "" 1 1
  [ "$status" -ne 0 ]
  run classify 1 "<none>" 1
  [ "$status" -ne 0 ]
}

# --- verdict severity ----------------------------------------------------------------------------

@test "is_failing: blind, down, zombie, stale and orphan fail; ok, sleeping and unmanaged pass" {
  lib_source
  for v in blind down zombie stale orphan; do
    run is_failing "$v"
    [ "$status" -eq 0 ]
  done
  for v in ok sleeping unmanaged; do
    run is_failing "$v"
    [ "$status" -ne 0 ]
  done
}

@test "is_failing: an UNKNOWN verdict fails closed" {
  # A verdict token this function has never heard of is a bug in the guard, and a bug in the guard
  # must not read as a pass. This repo has shipped that mistake twice.
  lib_source
  run is_failing "banana"
  [ "$status" -eq 0 ]
}

# --- scrape-pool lookup --------------------------------------------------------------------------

@test "pool_targets counts every endpoint index for one ServiceMonitor" {
  # Prometheus names a pool `serviceMonitor/<ns>/<name>/<endpointIndex>`. A ServiceMonitor with three
  # endpoints produces /0 /1 /2 and all three belong to it.
  lib_source
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[
  {"scrapePool":"serviceMonitor/monitoring/kubelet/0","health":"up"},
  {"scrapePool":"serviceMonitor/monitoring/kubelet/1","health":"up"},
  {"scrapePool":"serviceMonitor/monitoring/kubelet/2","health":"up"},
  {"scrapePool":"serviceMonitor/weyland/bifrost/0","health":"up"}
]}}
JSON
  run pool_targets "$STUB_DIR/t.json" monitoring kubelet
  [ "$output" = "3" ]
  run pool_targets "$STUB_DIR/t.json" weyland bifrost
  [ "$output" = "1" ]
}

@test "pool_targets returns 0 for a ServiceMonitor with no pool at all — the trino shape" {
  lib_source
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[{"scrapePool":"serviceMonitor/weyland/bifrost/0","health":"up"}]}}
JSON
  run pool_targets "$STUB_DIR/t.json" data-mesh trino
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test "pool_targets does NOT prefix-match a longer sibling name" {
  # `trino` must not be satisfied by `trino-worker`. Substring matching here would invent coverage.
  lib_source
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[{"scrapePool":"serviceMonitor/data-mesh/trino-worker/0","health":"up"}]}}
JSON
  run pool_targets "$STUB_DIR/t.json" data-mesh trino
  [ "$output" = "0" ]
}

@test "pool_targets counts only HEALTHY targets" {
  # A target that is discovered but failing every scrape yields no series. Counting it would report
  # coverage that does not exist — the exact class of bug this guard exists to catch.
  lib_source
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[
  {"scrapePool":"serviceMonitor/weyland/qdrant/0","health":"down"},
  {"scrapePool":"serviceMonitor/weyland/qdrant/0","health":"up"}
]}}
JSON
  run pool_targets "$STUB_DIR/t.json" weyland qdrant
  [ "$output" = "1" ]
}

@test "pool_targets on unreadable or malformed JSON is FATAL, never 0" {
  # "0 targets" and "I could not read the file" must never be the same answer. The first is a
  # finding; the second silently marks every ServiceMonitor blind, or with one `|| echo 0`, marks
  # them all fine.
  lib_source
  run pool_targets "$STUB_DIR/does-not-exist.json" weyland bifrost
  [ "$status" -ne 0 ]
  printf 'not json at all' > "$STUB_DIR/bad.json"
  run pool_targets "$STUB_DIR/bad.json" weyland bifrost
  [ "$status" -ne 0 ]
}

# --- accounting: every live ServiceMonitor must be reachable -------------------------------------

@test "a ServiceMonitor with NO backing workload is FATAL unless documented" {
  # kube-etcd is the real instance: kube-prometheus-stack ships it, k3s has no etcd, and it can never
  # match anything. That is legitimate — but it must be WRITTEN DOWN, not inferred from a zero.
  lib_source
  run is_accepted "monitoring/monitoring-kube-prometheus-kube-etcd"
  [ "$status" -eq 0 ]
  run is_accepted "data-mesh/trino"
  [ "$status" -ne 0 ]
}

@test "every ACCEPTED row carries a written reason" {
  # Same posture as check-pip-audit-ignores.sh: an exception must state the CONDITION that makes it
  # fine, so a reader can re-check it instead of trusting it.
  lib_source
  local row
  for row in "${ACCEPTED[@]}"; do
    local entry reason
    IFS="|" read -r entry reason <<<"$row"
    [ -n "$entry" ]
    [ "${#reason}" -gt 30 ]
  done
}

# --- end to end ----------------------------------------------------------------------------------

@test "end to end: a healthy estate passes" {
  cat > "$STUB_DIR/sm.json" <<'JSON'
[{"ns":"weyland","name":"bifrost","intended":1,"actual":1}]
JSON
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[{"scrapePool":"serviceMonitor/weyland/bifrost/0","health":"up"}]}}
JSON
  SM_SNAPSHOT_JSON="$STUB_DIR/sm.json" TARGETS_JSON="$STUB_DIR/t.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "end to end: the trino shape FAILS and says BLIND" {
  # Running, ready, and scraped by nothing.
  cat > "$STUB_DIR/sm.json" <<'JSON'
[{"ns":"data-mesh","name":"trino","intended":1,"actual":1}]
JSON
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[]}}
JSON
  SM_SNAPSHOT_JSON="$STUB_DIR/sm.json" TARGETS_JSON="$STUB_DIR/t.json" run bash "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"trino"* ]]
  [[ "$output" == *"blind"* ]]
}

@test "end to end: a deliberately parked store does NOT fail the run" {
  # The muting failure mode. If parking a store turns this guard red, it gets ignored, and then it is
  # worth nothing — the same argument this repo keeps making about permanently-lit alerts.
  cat > "$STUB_DIR/sm.json" <<'JSON'
[{"ns":"weyland","name":"qdrant","intended":0,"actual":0}]
JSON
  cat > "$STUB_DIR/t.json" <<'JSON'
{"data":{"activeTargets":[]}}
JSON
  SM_SNAPSHOT_JSON="$STUB_DIR/sm.json" TARGETS_JSON="$STUB_DIR/t.json" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"sleeping"* ]]
}

@test "end to end: an empty ServiceMonitor list is FATAL, not a clean pass" {
  # "Checked nothing, found nothing" is the precise shape of bug this guard exists to catch, and it
  # would be grimly funny to ship it inside the guard itself. This repo has done that twice.
  printf '[]' > "$STUB_DIR/sm.json"
  printf '{"data":{"activeTargets":[]}}' > "$STUB_DIR/t.json"
  SM_SNAPSHOT_JSON="$STUB_DIR/sm.json" TARGETS_JSON="$STUB_DIR/t.json" run bash "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"ZERO"* || "$output" == *"zero"* ]]
}

@test "end to end: the exit code distinguishes a finding from a crash" {
  # 1 = the estate has a defect. 2 = the guard could not do its job. Conflating them means a broken
  # guard reads exactly like a broken cluster, and gets 'fixed' by whoever is on call.
  printf '[{"ns":"data-mesh","name":"trino","intended":1,"actual":1}]' > "$STUB_DIR/sm.json"
  printf '{"data":{"activeTargets":[]}}' > "$STUB_DIR/t.json"
  SM_SNAPSHOT_JSON="$STUB_DIR/sm.json" TARGETS_JSON="$STUB_DIR/t.json" run bash "$GUARD"
  [ "$status" -eq 1 ]

  printf '[{"ns":"data-mesh","name":"trino","intended":1,"actual":1}]' > "$STUB_DIR/sm.json"
  SM_SNAPSHOT_JSON="$STUB_DIR/sm.json" TARGETS_JSON="$STUB_DIR/nope.json" run bash "$GUARD"
  [ "$status" -eq 2 ]
}
