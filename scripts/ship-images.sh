#!/usr/bin/env bash
# B135 + B131 — take a pushed change from source to a VERIFIED rollout, in one command.
#
# THE PROBLEM THIS EXISTS FOR: the loop from a source change to a running pod is seven steps, and it
# is complete on both ends and broken in the middle. Three of those steps can be skipped without
# anything going red — the pipeline can report success having opened no PR, a merged PR is not
# evidence of a running pod, and Argo's ~3-minute poll means "merged" and "deployed" are different
# times. Five runs on 2026-08-20 stumbled four times, every stumble a skipped step rather than a
# fault. The cost is not lost minutes, it is FALSE CONFIDENCE.
#
# So the design rule here is one line long: a gate that cannot verify itself is worse than no gate,
# because it produces a green signal. Every gate below asserts against an authoritative source —
# origin/main, the Woodpecker API, the GitHub API, and the live cluster resource — and the command
# refuses to advance past any gate it cannot positively verify.
#
#   usage: scripts/ship-images.sh [--dry-run]
#
# Runs on the DEV MACHINE (rogueone). Needs: git, gh, woodpecker-cli, argocd, kubectl.
set -euo pipefail

# Sourced by scripts/tests/ship-images.bats with SHIP_IMAGES_LIB=1 to exercise the predicates
# directly. Everything above main() must therefore be side-effect free.
. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

REG="registry.weyland.lab"
REPO="edtbl76/weyland-lab"
CI_AUTHOR="weyland-ci"
BASE="main"

# Waits. Overridable so the test suite can drive the poll loops with no wall-clock cost
# (SHIP_POLL_INTERVAL=0), which is also why they are read with `${VAR-default}` and not `:-`.
SHIP_POLL_TIMEOUT="${SHIP_POLL_TIMEOUT:-1800}"    # 30m — a cold user-code build is slow
# The SAME detector CI runs, so the local answer and the pipeline's cannot disagree. Overridable for
# the test suite only.
SHIP_DETECT="${SHIP_DETECT:-$(dirname "${BASH_SOURCE[0]}")/ci/detect-changes.sh}"
SHIP_ROLLOUT_TIMEOUT="${SHIP_ROLLOUT_TIMEOUT:-300}" # 5m — Argo polls every ~3m

# Credentials live in the gitignored scripts/.env (lab convention). Overridable for the test suite.
SHIP_ENV_FILE="${SHIP_ENV_FILE:-$REPO_ROOT/scripts/.env}"

# An image-tag line is `<anything> registry.weyland.lab/<image>:<tag>`. Anchoring on the registry
# host rather than on "a line containing a colon" is what makes diff_is_tags_only trustworthy.
TAG_LINE_RE="${REG//./\\.}/[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+"

# --- Gate predicates ------------------------------------------------------------------
# Small, pure, and separately testable on purpose: these are the decisions, and a decision that can
# only be exercised by running the whole loop is a decision nobody checks.

# FR1.2 — is local HEAD the same commit origin/main carries?
# The pipeline diffs <oldsha>..HEAD at its own start; nothing compares HEAD to origin/main. That gap
# is the mechanism behind "triggered before the push landed".
head_matches_origin() {
  local head origin
  head="$(git rev-parse HEAD 2>/dev/null)" || return 1
  origin="$(git rev-parse "origin/${BASE}" 2>/dev/null)" || return 1
  [ -n "$head" ] && [ "$head" = "$origin" ]
}

# FR1.4 — does the new tag actually differ from what is deployed? That difference IS the evidence
# the change was picked up; sameness means the rollout has not happened yet (or never will).
sha_differs_from_deployed() {
  local newtag="${1:?usage: sha_differs_from_deployed <newtag> <deployed-image-ref>}"
  local deployed_ref="${2:?usage: sha_differs_from_deployed <newtag> <deployed-image-ref>}"
  [ "$newtag" != "${deployed_ref##*:}" ]
}

# FR2.1 — first of the two merge conditions.
#
# KEYED ON THE COMMIT AUTHOR, NOT THE PR AUTHOR. `weyland-ci` is not a GitHub account and never will
# be: scripts/ci/open-deploy-pr.sh sets it with `git config user.name`, which stamps the COMMIT, while
# the PR itself is opened through the API with $GITHUB_TOKEN — a PAT owned by the human. So the PR
# author is always `edtbl76` and the original check could never pass. Found on the first live run
# (2026-08-22), where it aborted at FR2.1 on a PR that was entirely legitimate.
#
# The commit author is the real CI marker, and it is exactly as hard to forge as the old check was
# meant to be: anything CI produced carries it, anything a human pushed does not.
#
# USE `.name`, NOT `.login`. Second time I made this mistake: `.login` is the GitHub ACCOUNT, and since
# `weyland-ci` is not one, GitHub returns it empty — `{"email":"ci@weyland.lab","login":"","name":"weyland-ci"}`.
# `.name` is the git commit author that `git config user.name` actually stamps.
#
# An EMPTY commit list fails closed. "Could not determine the authors" is not "the authors are fine".
pr_commits_are_ci() {
  local pr="${1:?usage: pr_commits_are_ci <pr-number>}"
  local authors seen=0
  authors="$(gh pr view "$pr" --repo "$REPO" --json commits \
    --template '{{range .commits}}{{range .authors}}{{.name}}{{"\n"}}{{end}}{{end}}' 2>/dev/null)"
  [ -n "$authors" ] || return 1
  local a
  while read -r a; do
    [ -n "$a" ] || continue
    seen=1
    [ "$a" = "$CI_AUTHOR" ] || return 1
  done <<<"$authors"
  [ "$seen" -eq 1 ]
}

# FR2.1 — the UNSPOOFABLE half of the identity check, and the one that actually bounds the threat.
#
# Everything else about a PR's provenance is self-asserted: `git config user.name weyland-ci` is a
# string anyone can set. `edtbl76/weyland-lab` is PUBLIC and carries no branch protection (FR2.4), so
# without this check a stranger could fork it, push `ci/image-bump-<current-main-sha>` with a
# tags-only diff authored as `weyland-ci`, and this loop would merge it to main.
#
# `isCrossRepository` is decided by GitHub, not by the committer. CI pushes to the BASE repo with its
# own token (scripts/ci/open-deploy-pr.sh), so a CI bump PR is ALWAYS same-repo and a fork PR is never
# CI's. Fails closed on an unreadable answer.
#
# Deliberately NOT signature verification: Woodpecker signs nothing today, so pinning a CI key means
# building a signing path first. Revisit if the repo ever accepts pushes from more than one human.
pr_is_same_repo() {
  local pr="${1:?usage: pr_is_same_repo <pr-number>}" cross
  cross="$(gh pr view "$pr" --repo "$REPO" --json isCrossRepository \
    --template '{{.isCrossRepository}}' 2>/dev/null)"
  [ "$cross" = "false" ]
}

# FR2.1 — second merge condition: the diff touches NOTHING but image-tag lines.
#
# Written as "no line fails to match" rather than "some line matches". The mixed-diff case is the
# whole point: a bump PR carrying a smuggled resource-limit change still contains a tag line, so any
# check shaped as "does this look like a bump?" waves it through.
diff_is_tags_only() {
  local diff_file="${1:?usage: diff_is_tags_only <diff-file>}"
  [ -f "$diff_file" ] || return 1
  local offenders
  offenders="$(grep -E '^[+-]' "$diff_file" \
    | grep -Ev '^(\+\+\+|---)' \
    | grep -Evc "$TAG_LINE_RE")" || offenders=0
  [ "$offenders" -eq 0 ]
}

# FR4.2 — the branch shape CI pushes. Anchored: `feature/ci-image-bump-thing` is somebody's own
# branch and deleting it during cleanup would be destroying a human's work.
is_image_bump_branch() {
  [[ "${1:?usage: is_image_bump_branch <branch>}" =~ ^ci/image-bump-[0-9a-f]+$ ]]
}

# --- Gate sequencing ------------------------------------------------------------------
# FR1.6 — the command must report WHICH gate stopped it and why, not just that something did. So a
# gate is a wrapper rather than a bare `if`: passing through it is the only way to advance, and
# failing it records the identity of the failure before unwinding.

FAILED_GATE=""
FAILED_REASON=""
ORPHAN_BRANCH=""

gate() { # gate <id> <what it is asserting> <command...>
  local id="$1" desc="$2"
  shift 2
  printf '→ %s: %s\n' "$id" "$desc"
  if "$@"; then
    printf '  ✓ %s\n' "$id"
    return 0
  fi
  FAILED_GATE="$id"
  FAILED_REASON="$desc"
  return 1
}

# FR4.2 — best-effort removal of partial state this run created. Only ever an orphan
# `ci/image-bump-<sha>` branch, and only after is_image_bump_branch has vouched for the name.
#
# WHY IT MATTERS: manifests are both the input to change detection (they carry the old sha) and the
# output of the PR step. A run that leaves the registry holding a tag the manifests never received
# makes the NEXT run diff from a stale sha.
# Does an open PR exist for this branch? FAILS CLOSED — if GitHub cannot be asked, the answer is YES.
#
# The costs here are wildly asymmetric. A wrong "no" DELETES a branch backing a real PR, destroying
# this run's own output; a wrong "yes" merely leaves a branch behind, which the staleness watchdog
# surfaces the next morning. So the unknown case takes the safe side — and note that reading an
# unanswerable query as a negative answer is precisely the silent-failure family this loop exists to
# prevent. `open_bump_prs` cannot serve here: it ends in `2>/dev/null | grep … || true`, so a dead
# `gh` and "no PRs" are indistinguishable in its output.
branch_has_open_pr() {
  local branch="${1:?usage: branch_has_open_pr <branch>}" out
  if ! out="$(gh pr list --repo "$REPO" --state open --head "$branch" \
        --json number --template '{{range .}}{{.number}}{{"\n"}}{{end}}' 2>&1)"; then
    printf '  cannot ask GitHub whether %s has an open PR (%s) — assuming it does, keeping it\n' \
      "$branch" "$(printf '%s' "$out" | head -n1)" >&2
    return 0
  fi
  [ -n "$(printf '%s' "$out" | tr -d '[:space:]')" ]
}

# Bring the local branch up to the origin/main the merge just advanced. Fast-forward ONLY — never
# rebase or merge on the operator's behalf. Never fails the run: being behind is friction, not a
# broken deploy, and aborting a verified rollout over a git state would be the wrong trade.
sync_local_main() {
  if ! git fetch origin "$BASE" >/dev/null 2>&1; then
    printf '  ⚠ could not fetch origin/%s — your local clone is now BEHIND the merge\n' "$BASE" >&2
    return 0
  fi
  if git merge --ff-only "origin/${BASE}" >/dev/null 2>&1; then
    printf '→ local %s fast-forwarded to the merge\n' "$BASE"
    return 0
  fi
  printf '  ⚠ local %s could NOT fast-forward (local commits or a dirty tree) — it is behind\n' "$BASE" >&2
  printf '    origin/%s moved when PR #%s merged; reconcile it yourself before your next push.\n' "$BASE" "${1:-?}" >&2
  return 0
}

cleanup() {
  [ -n "$ORPHAN_BRANCH" ] || return 0
  is_image_bump_branch "$ORPHAN_BRANCH" || return 0
  # ORPHAN_BRANCH is set immediately after the trigger and cleared only once the PR lookup succeeds.
  # An abort in BETWEEN — which is where the 2026-08-24 run died, at FR1.3, after deploy-handoff had
  # already opened PR #36 — therefore reached this function with a branch that was not orphaned at
  # all. It printed "deleting orphan branch ci/image-bump-dab283e9"; the delete failed only because
  # the ISP happened to be down. Ask GitHub before destroying anything.
  if branch_has_open_pr "$ORPHAN_BRANCH"; then
    printf '→ cleanup: %s backs an open PR — keeping it\n' "$ORPHAN_BRANCH"
    return 0
  fi
  printf '→ cleanup: deleting orphan branch %s\n' "$ORPHAN_BRANCH"
  git push --delete origin "$ORPHAN_BRANCH" >/dev/null 2>&1
}

# FR4.3 — cleanup is best-effort and must not mask the original failure. The exit reason reported is
# the gate that failed; a failed cleanup is a warning underneath it, never a replacement for it.
abort() {
  # "stopped at FR2.1 — PR #33 is CI-authored" read as though the check had SUCCEEDED, because the
  # gate description is phrased as the assertion. Say what was expected, so the line cannot be misread.
  printf '❌ stopped at %s — expected: %s\n' "$FAILED_GATE" "$FAILED_REASON" >&2
  if ! cleanup; then
    printf '⚠ cleanup did not complete; the failure above is still the reason for this exit\n' >&2
  fi
  exit 1
}

# --- Authoritative lookups ------------------------------------------------------------
# NFR1: every one of these asks a system that KNOWS, never infers.

# The tag CI will produce for the current commit. Identical derivation to detect-changes.sh — if
# these two ever disagree the whole loop compares the wrong things.
head_tag() {
  printf 'git-%s\n' "$(git rev-parse --short=8 HEAD)"
}

# FR1.5 — is a POD running this tag? Not "did the PR merge", not "does the manifest say so".
live_carries_tag() {
  local tag="${1:?usage: live_carries_tag <tag>}"
  kubectl get pods -A -o jsonpath='{..image}' 2>/dev/null | grep -q ":${tag}\\b"
}

# EVERY image a bump diff raises the tag on. Not "the first" — see all_bumped_images_live.
bumped_images() {
  grep -E '^\+' "${1:?usage: bumped_images <diff-file>}" \
    | grep -oE "${REG//./\\.}/[A-Za-z0-9._-]+:" | sed -E "s#.*/##; s#:\$##" | sort -u
}

# The first one, for the FR1.4 "is there anything to do" comparison.
bumped_image() {
  bumped_images "$1" | head -n1
}

# FR1.5 — EVERY bumped image must carry the tag, and the failure must NAME the stragglers.
#
# THE BUG THIS REPLACES: the gate called live_carries_tag, which greps ALL pods for the tag and passes
# on a single match. On 2026-08-22 dagster-user-code carried git-36c4d3e0 while weyland-tool-server sat
# on git-ef734fc8, and the command printed "shipped — git-36c4d3e0 is live". A verification gate that
# goes green on a partial rollout is the precise failure this project exists to remove — and it was in
# the gate meant to catch it. "Some pod somewhere has the tag" was never the question.
all_bumped_images_live() {
  local tag="${1:?usage: all_bumped_images_live <tag> <diff-file>}"
  local diff_file="${2:?usage: all_bumped_images_live <tag> <diff-file>}"
  local img tags stale="" checked=0
  [ -f "$diff_file" ] || { printf '  cannot read the bumped-image list (%s)\n' "$diff_file" >&2; return 1; }
  while read -r img; do
    [ -n "$img" ] || continue
    tags="$(deployed_tags_for "$img")"
    checked=$((checked + 1))
    # EVERY tag seen for this image must be the target — not merely "the target appears somewhere".
    # A mid-rollout image legitimately shows two tags, and that is not shipped yet.
    if [ -z "$tags" ]; then
      stale="${stale} ${img}(absent)"
    elif [ "$tags" != "$tag" ]; then
      stale="${stale} ${img}($(printf '%s' "$tags" | tr '\n' ',' | sed 's/,$//'))"
    fi
  done <<<"$(bumped_images "$diff_file")"
  # Verifying NOTHING is not verifying successfully.
  [ "$checked" -gt 0 ] || { printf '  no bumped images found to verify — refusing to call that shipped\n' >&2; return 1; }
  [ -z "$stale" ] && return 0
  printf '  not yet on %s:%s\n' "$tag" "$stale" >&2
  return 1
}

# One row per (workload, container): namespace, name, image, probe|NOPROBE, desired, available.
#
# Deployments and StatefulSets only — the workload kinds that carry both a readinessProbe and a
# replica count. A CI image that runs as a Job (scan-suite) legitimately has neither; smoke_ok
# reports those as unchecked rather than failing them.
#
# go-template, not jq: gh and kubectl both ship the template engine in-process (see open_bump_prs).
# availableReplicas is ABSENT rather than 0 when nothing is up, hence the explicit else-0 — an empty
# field would compare equal to an empty desired and read as healthy.
workload_probe_status() {
  kubectl get deploy,statefulset -A -o go-template='{{range .items}}{{$ns := .metadata.namespace}}{{$n := .metadata.name}}{{$d := .spec.replicas}}{{$st := .status}}{{range .spec.template.spec.containers}}{{$ns}}{{"\t"}}{{$n}}{{"\t"}}{{.image}}{{"\t"}}{{if .readinessProbe}}probe{{else}}NOPROBE{{end}}{{"\t"}}{{$d}}{{"\t"}}{{if $st.availableReplicas}}{{$st.availableReplicas}}{{else}}0{{end}}{{"\n"}}{{end}}{{end}}' 2>/dev/null
}

# SMOKE — FR1.5 proves the right BYTES are on the node. This proves something asked the process a
# question and got an answer.
#
# THE GAP THIS CLOSES: `Ready` is only evidence when a probe measured something. With no
# readinessProbe a pod reports 1/1 Ready the moment PID 1 is alive. On 2026-08-23 dagster-user-code
# had no probe at all — it is the gRPC code server every Dagster run executes inside, it deploys
# Recreate so no old pod is still serving, and if it came up unable to load its definitions this loop
# would have printed "✓ shipped" while every Dagster run failed. Asserting readiness without
# asserting that readiness was MEASURED is the same nothing-verified class as the partial-rollout bug
# in all_bumped_images_live.
#
# So a missing probe FAILS the gate. That is deliberate: it makes the probe a shipping requirement
# rather than a nice-to-have, and any future workload added without one fails loudly the first time
# its image is bumped.
smoke_ok() {
  local tag="${1:?usage: smoke_ok <tag> <diff-file>}"
  local diff_file="${2:?usage: smoke_ok <tag> <diff-file>}"
  [ -f "$diff_file" ] || { printf '  cannot read the bumped-image list (%s)\n' "$diff_file" >&2; return 1; }

  local rows
  rows="$(workload_probe_status)"
  # An empty table is a failure to OBSERVE, never an observation of health. Same reason
  # all_bumped_images_live refuses a zero count.
  if [ -z "$rows" ]; then
    printf '  no workload status returned — refusing to call that smoke-verified\n' >&2
    return 1
  fi

  local img ns name image probe desired avail matched
  local unmeasured="" unhealthy="" unchecked="" verified=0
  while read -r img; do
    [ -n "$img" ] || continue
    matched=0
    while IFS=$'\t' read -r ns name image probe desired avail; do
      [ "$image" = "${REG}/${img}:${tag}" ] || continue
      matched=1
      if [ "$probe" != "probe" ]; then
        unmeasured="${unmeasured} ${ns}/${name}"
      elif [ "${avail:-0}" != "${desired:-0}" ] || [ "${desired:-0}" = "0" ]; then
        unhealthy="${unhealthy} ${ns}/${name}(${avail:-0}/${desired:-0})"
      else
        verified=$((verified + 1))
      fi
    done <<<"$rows"
    [ "$matched" = "1" ] || unchecked="${unchecked} ${img}"
  done <<<"$(bumped_images "$diff_file")"

  # Named, never silent: a run must not imply coverage it does not have.
  if [ -n "$unchecked" ]; then
    printf '  no workload runs:%s — not smoke-checked (Job/CronJob images are expected here)\n' "$unchecked" >&2
  fi
  if [ -n "$unmeasured" ]; then
    printf '  no readiness probe, so Ready proves nothing:%s\n' "$unmeasured" >&2
    return 1
  fi
  if [ -n "$unhealthy" ]; then
    printf '  probe-backed but not all replicas available:%s\n' "$unhealthy" >&2
    return 1
  fi
  printf '  %d workload(s) probe-backed and fully available\n' "$verified" >&2
  return 0
}

# --- TXN: one REAL transaction per shipped service (B140) -----------------------------
#
# FR1.5 proves the right BYTES are on the node. SMOKE proves a readinessProbe measured something.
# NEITHER asks the service to do its job, and on 2026-08-24 that gap was live:
#
#   feast-server was Argo-healthy, REST-answering and green on the `/health` probe — while its ONLINE
#   STORE WAS EMPTY. Valkey held 228 keys, all Langfuse's `bull:*`, zero Feast keys. Every entity key
#   returned null, including invented ones.
#
# And dagster-user-code's probe is `tcpSocket 4000`: it proves the gRPC server BOUND, not that its
# definitions LOADED. A code server that binds and fails to load sails through SMOKE.
#
# RUNS IN-CLUSTER via `kubectl exec`, deliberately. Every UI but feast.weyland.lab sits behind
# Keycloak forward-auth and 307s an unauthenticated curl; the alternative is carrying a credential
# into the deploy path, which puts Keycloak in the ship critical path. In-cluster avoids the question.
#
# The in-cluster probes print ONE verdict token (`TXN_OK` / `TXN_FAIL <reason>`) and the shell decides
# on that, so the decision stays testable without a cluster.

txn_pod() {
  kubectl -n weyland get pod -l app=dagster-user-code \
    -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' 2>/dev/null | awk '{print $1}'
}

# Dagster: did the code location actually LOAD? `loadStatus` must be LOADED and the location must not
# be a PythonError. This is the assertion the TCP probe cannot make.
txn_dagster() {
  local pod="${1:?usage: txn_dagster <pod>}"
  kubectl -n weyland exec "$pod" -- python3 -c '
import json, urllib.request
q = {"query": "{ workspaceOrError { __typename ... on Workspace { locationEntries { name loadStatus locationOrLoadError { __typename } } } } }"}
try:
    r = urllib.request.Request("http://dagster-webserver.weyland.svc.cluster.local:3000/graphql",
        data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
    w = json.load(urllib.request.urlopen(r, timeout=25))["data"]["workspaceOrError"]
    entries = w.get("locationEntries") or []
    if not entries:
        print("TXN_FAIL no code locations at all"); raise SystemExit
    bad = [e for e in entries
           if e.get("loadStatus") != "LOADED"
           or (e.get("locationOrLoadError") or {}).get("__typename") != "RepositoryLocation"]
    print("TXN_FAIL " + json.dumps(bad)[:200] if bad else "TXN_OK")
except Exception as e:
    print("TXN_FAIL " + type(e).__name__ + " " + str(e)[:120])
' 2>/dev/null
}

# Feast: serve a feature for a REAL entity key sampled from the offline table, and assert the VALUE is
# not null. `statuses: ["PRESENT"]` is NOT evidence — Feast returns PRESENT with a null value for keys
# it never materialized, so a status-based check stays green against a completely empty store.
txn_feast() {
  local pod="${1:?usage: txn_feast <pod>}"
  kubectl -n weyland exec "$pod" -- python3 -c '
import json, os, urllib.request
try:
    import psycopg2
    dsn = ("host=weyland-postgres.weyland.svc.cluster.local port=5432 dbname=feast user=weyland "
           "password=" + os.environ.get("WEYLAND_PG_PASSWORD", "") + " sslmode=disable")
    with psycopg2.connect(dsn) as c, c.cursor() as cur:
        cur.execute("SELECT state FROM state_health_risk ORDER BY event_timestamp DESC LIMIT 1")
        row = cur.fetchone()
    if not row or not row[0]:
        print("TXN_FAIL offline table state_health_risk is empty"); raise SystemExit
    key = row[0]
    body = {"features": ["state_health_risk:depression_pct"], "entities": {"state": [key]}}
    r = urllib.request.Request("http://feast-server.data-mesh.svc.cluster.local:6566/get-online-features",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(r, timeout=25))
    vals = [v for res in d.get("results", []) for v in res.get("values", [])]
    feat = d["results"][-1]["values"][0] if d.get("results") else None
    print("TXN_OK" if feat is not None else "TXN_FAIL feast served null for real key " + str(key))
except Exception as e:
    print("TXN_FAIL " + type(e).__name__ + " " + str(e)[:120])
' 2>/dev/null
}

txn_ok() {
  local tag="${1:?usage: txn_ok <tag> <diff-file>}"
  local diff_file="${2:?usage: txn_ok <tag> <diff-file>}"
  [ -f "$diff_file" ] || { printf '  cannot read the bumped-image list (%s)\n' "$diff_file" >&2; return 1; }

  local pod img verdict checked=0 failed="" unchecked=""
  pod="$(txn_pod)"
  # Verifying nothing is not verifying successfully.
  [ -n "$pod" ] || { printf '  no running dagster-user-code pod to run transactions from — refusing to report verified\n' >&2; return 1; }

  while read -r img; do
    [ -n "$img" ] || continue
    case "$img" in
      weyland-dagster-user-code) verdict="$(txn_dagster "$pod")" ;;
      feast-server)              verdict="$(txn_feast "$pod")" ;;
      # NAMED, never silently passed — same discipline as smoke_ok. A CI image that runs as a Job has
      # no transaction to make; saying so is honest, implying it was verified is not.
      *) unchecked="${unchecked} ${img}"; continue ;;
    esac
    checked=$((checked + 1))
    case "$verdict" in
      TXN_OK*) : ;;
      *) failed="${failed} ${img}(${verdict:-no-answer})" ;;
    esac
  done <<<"$(bumped_images "$diff_file")"

  [ -n "$unchecked" ] && printf '  no transaction defined, NOT verified:%s\n' "$unchecked" >&2
  if [ -n "$failed" ]; then
    printf '  transaction FAILED:%s\n' "$failed" >&2
    return 1
  fi
  if [ "$checked" -eq 0 ] && [ -z "$unchecked" ]; then
    printf '  no images to run a transaction against — refusing to call that verified\n' >&2
    return 1
  fi
  printf '  %d service(s) answered a real transaction\n' "$checked" >&2
  return 0
}

# Every tag the cluster currently declares or runs for one image, one per line, deduped.
#
# TWO SOURCES, because two kinds of workload answer "is this live?" differently:
#   - long-running (Deployment/StatefulSet/DaemonSet) -> the images of its RUNNING pods
#   - scheduled    (CronJob)                          -> the CronJob's own pod template
#
# RUNNING PODS ONLY, and NEVER a bare `head -n1`. Both halves were wrong, and both bit on 2026-08-24:
# the loop merged PR #37, every workload really was on git-afb1fb5d, and FR1.5 still reported
# `scan-suite(git-ef734fc8)`. It had read two COMPLETED Job pods —
# `code-scan-suite-29791500` and the leftover `scan-suite-adhoc` — whose templates are IMMUTABLE and
# therefore carry their creation-time image forever. `head -n1` then let one arbitrary historical
# record outvote the live workload. That gate would have failed on scan-suite permanently.
#
# The CronJob source is not an extra: `scan-suite` runs ONLY as a weekly CronJob, so outside the few
# minutes it executes it has NO pod at all, and a pod-only check reads `absent` and fails forever.
# smoke_ok already special-cases Job-shaped images; this is the same accommodation for FR1.5.
deployed_tags_for() {
  local img="${1:?usage: deployed_tags_for <image>}"
  {
    kubectl get pods -A --field-selector=status.phase=Running -o jsonpath='{..image}' 2>/dev/null | tr ' ' '\n'
    kubectl get cronjob -A -o jsonpath='{..image}' 2>/dev/null | tr ' ' '\n'
  } | grep -E "^${REG//./\\.}/${img}:" | sed 's#.*:##' | sort -u || true
}

# Open image-bump PRs as `<number><TAB><branch><TAB><author>`, newest first. Go-template rather than
# --jq: gh ships the template engine in-process, and jq is one more thing to install.
open_bump_prs() {
  gh pr list --repo "$REPO" --state open --limit 50 \
    --json number,headRefName,author \
    --template '{{range .}}{{.number}}{{"\t"}}{{.headRefName}}{{"\t"}}{{.author.login}}{{"\n"}}{{end}}' \
    2>/dev/null | grep -F 'ci/image-bump-' || true
}

# Argo Application name -> source path, read from the manifests themselves so this cannot drift as
# applications are added. Only path-based Applications appear; Helm-chart ones have no path to match.
# `<name>|<path>|<include-glob>`. The glob matters: TWELVE loose-file apps all declare
# `path: .../k8s` and are told apart ONLY by `directory.include`. Matching on path alone picks one of
# the twelve arbitrarily — which is how weyland-tool-server.yaml resolved to `postgres` on 2026-08-22
# and the tool-server app went unsynced while the run reported success.
argo_app_paths() {
  awk '
    /^apiVersion:/            { if (name && path) print name "|" path "|" inc; name=""; path=""; inc=""; inmeta=0 }
    /^metadata:/              { inmeta=1; next }
    /^[a-z]/                  { inmeta=0 }
    inmeta && /^  name:/      { if (!name) name=$2 }
    /^    path:/              { path=$2 }
    /^      include:/         { inc=$2; gsub(/^.|.$/, "", inc) }
    END                       { if (name && path) print name "|" path "|" inc }
  ' "$PLATFORM_DIR"/k8s/argocd/applications/*.yaml "$PLATFORM_DIR"/k8s/argocd/*.yaml 2>/dev/null
}

# NFR4 — the applications a diff actually touches, so a sync is never `--all`. B134: a full
# re-compare across 78 applications is a CPU spike on a node already past its request ceiling.
#
# Longest-prefix wins: `k8s` is itself an Application path (the loose top-level manifests), so a
# first-match scan would attribute every change to it.
affected_apps() {
  local diff_file="${1:?usage: affected_apps <diff-file>}"
  local pairs changed
  pairs="$(argo_app_paths)"
  changed="$(grep -E '^\+\+\+ b/' "$diff_file" | sed 's#^+++ b/##' | sort -u)"
  local f n p best_name best_len len
  for f in $changed; do
    best_name=""
    best_len=0
    while IFS='|' read -r n p inc; do
      [ -n "$p" ] || continue
      case "$f" in "$p"/*) : ;; *) continue ;; esac
      # An include glob is a hard filter, not a tiebreak: if the app declares one, the file must be in
      # it. `{a.yaml,b.yaml}` -> strip the braces and compare against the basename.
      if [ -n "$inc" ]; then
        local base="${f##*/}" want
        local matched=0
        inc="${inc#\{}"; inc="${inc%\}}"
        while IFS=',' read -r -d ',' want || [ -n "$want" ]; do
          want="$(printf '%s' "$want" | tr -d ' ')"
          [ "$want" = "$base" ] && matched=1
        done <<<"${inc},"
        [ "$matched" -eq 1 ] || continue
      fi
      len=${#p}
      # A glob-scoped app beats a bare-path app on the same directory: it is the more specific claim.
      [ -n "$inc" ] && len=$((len + 1000))
      if [ "$len" -gt "$best_len" ]; then
        best_len="$len"
        best_name="$n"
      fi
    done <<<"$pairs"
    # `if`, NOT `[ -n … ] && printf`. As an `&&` list this is the loop body's LAST command, so when no
    # app matches it returns 1 — and with `set -o pipefail` the enclosing `… done | sort -u` pipeline
    # then returns 1 too, even though sort succeeded. The caller's bare `apps="$(affected_apps …)"`
    # assignment made that fatal under `set -e`: on a bump PR touching a manifest no Argo application
    # claims, the loop died SILENTLY right after merging — no sync, no FR1.5, no error line. An `if`
    # with no else returns 0. (Found 2026-08-24; third instance of this class in this script.)
    if [ -n "$best_name" ]; then printf '%s\n' "$best_name"; fi
  done | sort -u
}

# --- Pipeline ------------------------------------------------------------------------

# `woodpecker-cli --output json` DOES NOT WORK. The flag is accepted and then silently ignored — the
# CLI prints its human table anyway (verified against the live server, v3.x, 2026-08-22). Nothing
# errors; you just get a table where you expected JSON, so a parser reading it finds no fields, the
# pipeline number comes back empty, and every run dies at the trigger step. Stubs cannot catch this
# class of bug: they return whatever shape you tell them to.
#
# go-template is the only machine-readable format, and the payload is a SLICE
# (`[]*woodpecker.Pipeline`) even for a single pipeline — `{{.Number}}` alone fails with
# "can't evaluate field Number in type []*woodpecker.Pipeline". Hence the range.
WP_FIELDS='go-template={{range .}}{{.Number}} {{.Status}}{{"\n"}}{{end}}'

# First non-blank line's Nth field, so a trailing newline from the template cannot become an answer.
wp_field() {
  awk -v n="$1" 'NF { print $n; exit }'
}

# FR1.3 — poll to completion, then say what happened. `pending` and `running` are the only
# non-terminal states; anything else ends the wait, including the ones that are neither success nor
# a build failure (killed, declined, blocked).
poll_pipeline() {
  local num="${1:?usage: poll_pipeline <number>}"
  local interval="${SHIP_POLL_INTERVAL-10}"
  local waited=0 status="" show_rc=0 cli_fails=0 errfile show_err=""
  while [ "$waited" -le "$SHIP_POLL_TIMEOUT" ]; do
    # An empty status is treated as non-terminal below, which is right for a pipeline that has not
    # reported yet and WRONG for a CLI that cannot answer at all. Undistinguished, a dead CLI looks
    # exactly like a slow build for the full 30-minute timeout and then reports "ended as: unknown".
    # Three consecutive failures is a broken client, not a quiet pipeline.
    errfile="$(mktemp)"
    status="$(woodpecker-cli pipeline show "$REPO" "$num" --output "$WP_FIELDS" 2>"$errfile" | wp_field 2)" && show_rc=0 || show_rc=$?
    show_err="$(cat "$errfile")"
    rm -f "$errfile"
    if [ "$show_rc" -ne 0 ]; then
      cli_fails=$((cli_fails + 1))
      if [ "$cli_fails" -ge 3 ]; then
        printf '  woodpecker-cli failed %s times running while polling #%s (exit %s): %s\n' \
          "$cli_fails" "$num" "$show_rc" "$show_err" >&2
        return 1
      fi
    else
      cli_fails=0
    fi
    case "$status" in
      success) return 0 ;;
      pending | running | "") : ;;
      *) break ;;
    esac
    [ "$interval" != "0" ] && sleep "$interval"
    waited=$((waited + interval))
    [ "$interval" = "0" ] && [ "$waited" -eq 0 ] && waited=$((waited + 1))
  done
  printf '  pipeline #%s ended as: %s\n' "$num" "${status:-unknown}" >&2
  # A bare status is exactly the thing this command exists to stop reporting.
  printf '  ── failing step log ───────────────────────────────\n' >&2
  woodpecker-cli pipeline log show "$REPO" "$num" 2>/dev/null | tail -n 40 >&2 || true
  printf '  ───────────────────────────────────────────────────\n' >&2
  return 1
}

# Load the repo's own credentials rather than hoping the caller sourced them.
#
# WHY, precisely: `woodpecker-cli` reads a `.env` from its WORKING DIRECTORY. Once the loop became
# safe to run from any directory (2026-08-24), that turned into a live hazard — run from
# nodes/.../tofu/port and the CLI dutifully loads Port's `.env`, which carries PORT_CLIENT_ID and
# no WOODPECKER_* key at all. That is exactly what happened: the CLI came up unauthenticated and
# `pipeline create` failed. Loading the repo's env file here makes the run independent of both the
# caller's shell and whatever `.env` happens to sit in the current directory.
#
# Absent file is NOT an error: the operator may have sourced it already, and the runbook documents
# doing so by hand. A real credential problem is reported at the gate that needs the credential,
# with the variable named — not here, where all we would know is that a file is missing.
load_env() {
  [ -f "$SHIP_ENV_FILE" ] || return 0
  set -a
  # shellcheck disable=SC1090  # path is a runtime value; the file is gitignored and never in-tree
  . "$SHIP_ENV_FILE"
  set +a
}

# ── EMA-172 — Port `deployment` entity (DORA deployment frequency) ─────────────────────────────
#
# The `deployment` blueprint already carries `createdAt` / `deploymentStatus` / `environment` and
# MIRRORS `github_lead_time_hours` from the linked PR's `cycle_time_hours`. So lead-time-for-changes
# was already wired; deployment FREQUENCY had no data, because nothing ever created a deployment
# entity. B144 exists to keep `githubPullRequest` clean precisely so these scorecards mean something
# — this closes the other half.
#
# THE ISSUE SAID `environment`, AND THAT WAS WRONG. The `environment` blueprint has no properties at
# all (one relation to k8s_cluster), so re-upserting it per deploy would carry no new information.
# `deployment` is the entity a frequency metric counts; `environment` is a dimension on it.
#
# THIS RUNS AFTER THE SHIP IS VERIFIED AND CAN NEVER ABORT ONE. The deploy already happened and
# passed FR1.5 + TXN; failing the script over catalog bookkeeping would turn a real deploy into a red
# run. But it is not allowed to be silent either: a swallowed emit under-counts deployment frequency
# forever, and "the scorecard stopped moving" is indistinguishable from "we stopped deploying".
# Contract: loud warning, non-zero from the function, ship still succeeds.

# deployment_payload <tag> <service> <pr_id> <iso8601> -> entity JSON on stdout.
#
# The identifier is `<service>-<tag>`: STABLE for a given tag (re-running a ship upserts rather than
# double-counting one deploy) and UNIQUE across tags (each real deploy is its own entity, which is
# what a frequency metric counts).
#
# ENUM VALUES ARE EXACT. Port drops an out-of-enum property value SILENTLY (runbooks/opentofu.md) —
# the API accepts the write and the property is simply absent afterwards. `Success` and `Production`
# are the blueprint's spellings, not approximations of them.
deployment_payload() { # deployment_payload <tag> <service> <pr_id> <iso8601>
  python3 - "${1:?tag}" "${2:?service}" "${3-}" "${4:?timestamp}" <<'PYPAYLOAD'
import json, sys
tag, service, pr_id, ts = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
rel = {"service": service}
# An empty relation would either 422 or dangle. Both relations are optional in the blueprint, so
# ABSENT is the honest representation of "unknown" — never "".
if pr_id:
    rel["github_pull_request"] = pr_id
print(json.dumps({
    "identifier": f"{service}-{tag}",
    "title": f"{service} {tag}",
    "properties": {
        "createdAt": ts,
        "deploymentStatus": "Success",
        "environment": "Production",
    },
    "relations": rel,
}))
PYPAYLOAD
}

# The POST is reached through indirection so the suite can substitute a stub. A PATH stub cannot work
# here — a shell function always beats an executable of the same name, so the real implementation
# would shadow the stub and the test would hit the LIVE Port API while appearing to pass. Same
# reasoning as port-pr-reconcile's GH_STATE_FN.
PORT_EMIT_FN="${PORT_EMIT_FN:-__port_upsert_deployment}"

__emit_fail() { return 1; }   # test double

__port_upsert_deployment() { # __port_upsert_deployment <payload-file>
  local body http tok
  body="$(mktemp)"
  # curl writes the body to a file and the STATUS to stdout, so the two are never conflated. A
  # `curl -sf | python3` pipeline turns a 401 into empty input, which reads as a successful parse of
  # nothing — the exact failure this repo keeps finding.
  http="$(curl -s -o "$body" -w '%{http_code}' -X POST https://api.port.io/v1/auth/access_token \
    -H 'Content-Type: application/json' \
    -d "{\"clientId\":\"${PORT_CLIENT_ID}\",\"clientSecret\":\"${PORT_CLIENT_SECRET}\"}")" || {
      echo "  !! Port token request failed at the transport layer" >&2; rm -f "$body"; return 1; }
  [ "$http" = "200" ] || { echo "  !! Port token endpoint returned HTTP ${http}" >&2; rm -f "$body"; return 1; }
  tok="$(python3 -c 'import sys,json;print(json.load(sys.stdin).get("accessToken",""))' < "$body")"
  rm -f "$body"
  [ -n "$tok" ] || { echo "  !! Port returned no accessToken" >&2; return 1; }
  # upsert=true so re-shipping the same tag updates rather than 409s.
  http="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    "https://api.port.io/v1/blueprints/deployment/entities?upsert=true&merge=true" \
    -H "Authorization: Bearer ${tok}" -H 'Content-Type: application/json' -d @"$1")" || {
      echo "  !! Port deployment upsert failed at the transport layer" >&2; return 1; }
  case "$http" in
    200|201) return 0 ;;
    *) echo "  !! Port deployment upsert returned HTTP ${http}" >&2; return 1 ;;
  esac
}

emit_deployment() { # emit_deployment <tag> <service> <pr_id>
  local tag="${1:?}" service="${2:?}" pr_id="${3-}" ts payload rc=0
  # A missing credential must NOT read as "nothing to emit" — that is the silent skip this repo keeps
  # building by accident.
  if [ -z "${PORT_CLIENT_ID:-}" ] || [ -z "${PORT_CLIENT_SECRET:-}" ]; then
    echo "  !! PORT_CLIENT_ID / PORT_CLIENT_SECRET not set - DORA deployment NOT recorded" >&2
    return 1
  fi
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  payload="$(mktemp)"
  deployment_payload "$tag" "$service" "$pr_id" "$ts" > "$payload" || { rm -f "$payload"; return 1; }
  "$PORT_EMIT_FN" "$payload" || rc=1
  rm -f "$payload"
  if [ "$rc" -ne 0 ]; then
    echo "  !! could not record the deployment in Port - DORA deployment-frequency will under-count this ship." >&2
    return 1
  fi
  # `printf --` because the format starts with `->`, which printf otherwise parses as an option:
  # `printf: ->: invalid option`. Caught on the first live emit.
  printf -- '-> Port deployment recorded: %s-%s\n' "$service" "$tag"
  return 0
}

main() {
  load_env
  gate FR1.2 "local HEAD matches origin/${BASE}" head_matches_origin || abort

  local newtag short_sha
  newtag="$(head_tag)"
  short_sha="${newtag#git-}"
  printf '→ target tag: %s\n' "$newtag"

  # NFR3 — idempotence. "Already deployed" is two conditions, not one: the tag is live AND no bump
  # PR is still open. A live tag with an open bump PR means there is outstanding work, not that the
  # last run finished.
  local open_prs
  open_prs="$(open_bump_prs)"
  if [ -z "$open_prs" ] && live_carries_tag "$newtag"; then
    printf '✓ already deployed — %s is live and no image-bump PR is open. Nothing to do.\n' "$newtag"
    return 0
  fi

  # "No PR because nothing changed" is NOT "no PR because the handoff broke" — the second is C9, the
  # first is an ordinary quiet day. Asking the same detector CI uses, BEFORE triggering, keeps those
  # two apart and skips a pipeline that would build nothing. Without this, a docs-only commit ends in
  # a red FR1.4 abort that reads like a failure.
  #
  # AN EMPTY PLAN IS ONLY MEANINGFUL IF THE DETECTOR SUCCEEDED. Until 2026-08-24 this ran the
  # detector as `>/dev/null 2>&1` and looked only at the plan file, so "the detector found no work"
  # and "the detector could not run" produced the identical green line. Run from a subdirectory with
  # three images genuinely stale, it printed "✓ nothing to ship" and exited 0. Read the status, and
  # keep the detector's own words — they are the only description of what went wrong.
  local plan detect_out detect_rc
  plan="$(mktemp)"
  detect_out="$(PLAN="$plan" sh "$SHIP_DETECT" 2>&1)" && detect_rc=0 || detect_rc=$?
  if [ "$detect_rc" -ne 0 ]; then
    rm -f "$plan"
    FAILED_GATE="DETECT"
    FAILED_REASON="change detection to succeed — it exited ${detect_rc}, so an empty plan cannot be read as 'nothing changed'. Detector output: ${detect_out}"
    abort
  fi
  if [ ! -s "$plan" ]; then
    rm -f "$plan"
    printf '✓ nothing to ship — no image build context changed since its deployed tag.\n'
    return 0
  fi
  rm -f "$plan"

  printf '→ triggering pipeline on %s (%s)\n' "$REPO" "$BASE"
  #
  # THIS ASSIGNMENT USED TO KILL THE SCRIPT SILENTLY. It was a bare `num="$(woodpecker-cli ... |
  # wp_field 1)"` under `set -euo pipefail`: when the CLI exits non-zero, `pipefail` makes the
  # pipeline non-zero, `set -e` terminates the run right here, and the `[ -n "$num" ]` guard on the
  # next line NEVER EXECUTES — the one guard written for this failure was unreachable in the case it
  # names, and `2>/dev/null` had already thrown away the reason. On 2026-08-24 the loop printed
  # "→ triggering pipeline" and returned to a clean prompt; no pipeline was created and nothing said
  # why. Capture the status explicitly, keep stderr in a file so it cannot be mistaken for output,
  # and let the guard run.
  local num create_rc errfile create_err
  errfile="$(mktemp)"
  num="$(woodpecker-cli pipeline create "$REPO" --branch "$BASE" --output "$WP_FIELDS" 2>"$errfile" | wp_field 1)" && create_rc=0 || create_rc=$?
  create_err="$(cat "$errfile")"
  rm -f "$errfile"
  # A number, or nothing. `--output json` is accepted and silently ignored by woodpecker-cli v3, so
  # a successful call can still print the human table whose first field is the word "NUMBER".
  # Polling that would wait out the full timeout on a pipeline that does not exist.
  case "$num" in
    '' | *[!0-9]*) num="" ;;
  esac
  if [ "$create_rc" -ne 0 ] || [ -z "$num" ]; then
    FAILED_GATE="FR1.3"
    if [ -z "${WOODPECKER_TOKEN:-}" ]; then
      FAILED_REASON="woodpecker-cli to create a pipeline — it exited ${create_rc} and WOODPECKER_TOKEN is unset. Credentials come from ${SHIP_ENV_FILE}; note that woodpecker-cli also reads a .env from the CURRENT directory, so running elsewhere can load the wrong one. Output: ${create_err}"
    else
      FAILED_REASON="woodpecker-cli to create a pipeline and return its number — it exited ${create_rc}. Output: ${create_err}"
    fi
    abort
  fi
  # From here on a branch may exist that no merge will claim. FR4.2 tracks it.
  ORPHAN_BRANCH="ci/image-bump-${short_sha}"
  printf '  pipeline #%s\n' "$num"

  gate FR1.3 "pipeline #${num} completed successfully" poll_pipeline "$num" || abort

  # Locate the PR the build opened.
  open_prs="$(open_bump_prs)"
  local pr_num="" pr_branch="" pr_author=""
  while IFS=$'\t' read -r n b a; do
    [ "$b" = "ci/image-bump-${short_sha}" ] || continue
    pr_num="$n"
    pr_branch="$b"
    pr_author="$a"
  done <<<"$open_prs"

  if [ -z "$pr_num" ]; then
    # C9, caught client-side: the pipeline went green having opened no PR. If the tag is already
    # live there was genuinely nothing to build; otherwise this is the silent failure itself.
    if live_carries_tag "$newtag"; then
      printf '✓ nothing to ship — %s is already live and the pipeline built no new images.\n' "$newtag"
      ORPHAN_BRANCH=""
      return 0
    fi
    FAILED_GATE="FR1.4"
    FAILED_REASON="pipeline #${num} succeeded but opened no image-bump PR and ${newtag} is not live"
    abort
  fi
  printf '→ PR #%s (%s, by %s)\n' "$pr_num" "$pr_branch" "$pr_author"
  # FR4.2 — STOP TRACKING THE BRANCH AS AN ORPHAN THE MOMENT A PR CLAIMS IT.
  # It used to be cleared only after a successful merge, so aborting anywhere between "PR opened" and
  # "merged" deleted the head branch of a live PR — and GitHub auto-closes a PR when its head branch
  # goes. That is what closed PR #33 on the first live run (2026-08-22). An orphan is a branch pushed
  # WITHOUT a PR; this one has one.
  ORPHAN_BRANCH=""

  # FR2.3 — close superseded older bumps FIRST. Merging #12 after #13 rolls images backwards.
  local n b a
  while IFS=$'\t' read -r n b a; do
    [ -n "$n" ] || continue
    [ "$n" = "$pr_num" ] && continue
    is_image_bump_branch "$b" || continue
    printf '→ closing superseded bump PR #%s (%s)\n' "$n" "$b"
    gh pr close "$n" --repo "$REPO" --delete-branch >/dev/null 2>&1 || \
      printf '  ⚠ could not close #%s — continuing\n' "$n" >&2
  done <<<"$open_prs"

  local diff_file
  diff_file="$(mktemp)"
  gh pr diff "$pr_num" --repo "$REPO" >"$diff_file" 2>/dev/null || true

  # FR1.4 — the PR's tag must differ from what is deployed. Sameness is not success, it is evidence
  # the change was never picked up.
  #
  # Compared against an image the PR ACTUALLY TOUCHES, not against whatever pod the cluster happens
  # to list first. An arbitrary comparand makes the gate pass or fail for reasons unrelated to it.
  # The comment above was already right and the old implementation contradicted it: `deployed_tag_for`
  # ended in `head -n1`, which IS "whatever pod the cluster happens to list first". Collapse the whole
  # tag set instead — only an image that is ENTIRELY on the new tag counts as already-deployed. An
  # empty set, an older tag, or a mid-rollout mix all mean there is still work to do.
  local image deployed deployed_ref
  image="$(bumped_image "$diff_file")"
  deployed="$(deployed_tags_for "${image:-none}")"
  if [ "$deployed" = "$newtag" ]; then
    deployed_ref="${REG}/${image}:${newtag}"
  else
    deployed_ref="${REG}/${image:-none}:not-fully-${newtag}"
  fi
  gate FR1.4 "the cluster is not already running ${newtag} for ${image:-the bumped image}" \
    sha_differs_from_deployed "$newtag" "$deployed_ref" || abort

  # FR2.1 — both conditions, or no merge.
  gate FR2.1 "PR #${pr_num} originates from ${REPO} itself, not a fork" pr_is_same_repo "$pr_num" || abort
  gate FR2.1 "every commit on PR #${pr_num} authored by ${CI_AUTHOR}" pr_commits_are_ci "$pr_num" || abort
  gate FR2.1 "PR #${pr_num} touches nothing but image-tag lines" diff_is_tags_only "$diff_file" || abort

  printf '→ merging PR #%s\n' "$pr_num"
  gh pr merge "$pr_num" --repo "$REPO" --squash --delete-branch >/dev/null 2>&1 || {
    FAILED_GATE="FR2.1"
    FAILED_REASON="gh pr merge failed for #${pr_num}"
    abort
  }
  # Merged: the branch is claimed, so it is no longer this run's orphan to clean up.
  ORPHAN_BRANCH=""

  # STEP 5 OF THE DOCUMENTED LOOP, and it was missing until 2026-08-24.
  #
  # The merge above advances origin/main. Without pulling, the local clone sits exactly one commit
  # behind after EVERY successful run — so the operator's next push is rejected and they hand-merge to
  # recover. That happened twice before anyone connected it to this script, because the symptom shows
  # up in a human's git workflow several steps away from the loop that caused it.
  #
  # FAST-FORWARD ONLY, on purpose. If the local branch has its own commits or a dirty tree, ff fails —
  # and that is the correct outcome: say so and continue. Rebasing or merging on the operator's behalf
  # would be this script rewriting history it does not own.
  sync_local_main "$pr_num"


  # FR1.5a / NFR4 — reconcile only what changed, via the CLI the runbook documents. The refresh
  # annotation and `kubectl patch` on the Application CRD are forbidden (docs/runbooks/argocd.md).
  # Belt and braces: even with affected_apps fixed to return 0, a bare command-substitution assignment
  # under `set -euo pipefail` is the shape that has killed this script silently three times today.
  # "No apps matched" is a legitimate answer, handled two lines below — never a reason to vanish.
  local apps
  apps="$(affected_apps "$diff_file")" || apps=""
  if [ -z "$apps" ]; then
    printf '⚠ no Argo application matched the changed manifests — relying on Argo'"'"'s own poll\n' >&2
  else
    local app
    for app in $apps; do
      printf '→ argocd app sync %s\n' "$app"
      argocd app sync "$app" --timeout 300 >/dev/null 2>&1 || \
        printf '  ⚠ sync of %s did not return cleanly — the live check below is the real gate\n' "$app" >&2
    done
  fi
  # FR1.5 — the only assertion that proves anything shipped.
  #
  # THE WAIT MUST POLL THE SAME PREDICATE THE GATE ASSERTS. It used to wait on `live_carries_tag`,
  # which is satisfied as soon as ANY pod anywhere carries the tag — so it stopped waiting the instant
  # the FIRST new pod appeared, then handed a still-rolling cluster to a gate that requires EVERY
  # bumped image to be on the tag. A wait that is weaker than its gate does not wait for the thing
  # being gated; it just sleeps a bit.
  #
  # This mismatch was always there and was masked by FR1.5's old `head -n1`, which was loose in the
  # same direction. Tightening the gate (2026-08-24) made it visible on run #29:
  #   `not yet on git-8c120f9d: feast-server(git-2c73c898,git-afb1fb5d) weyland-dagster-user-code(...)`
  # — a genuine mid-rollout, aborted as a failure.
  local waited=0 interval="${SHIP_POLL_INTERVAL-10}"
  while ! all_bumped_images_live "$newtag" "$diff_file" >/dev/null 2>&1; do
    [ "$waited" -ge "$SHIP_ROLLOUT_TIMEOUT" ] && break
    [ "$interval" != "0" ] && sleep "$interval"
    waited=$((waited + interval))
    [ "$interval" = "0" ] && break
  done
  gate FR1.5 "every image this run bumped is live on ${newtag}" \
    all_bumped_images_live "$newtag" "$diff_file" || abort

  # All three gates read $diff_file, so it stays until every one is done. Deleting it early is exactly
  # how the FR1.5 check came to pass vacuously on an empty image list.
  gate SMOKE "every bumped workload is probe-backed and fully available" \
    smoke_ok "$newtag" "$diff_file" || abort

  # B140 — the last one asks the service to actually DO something. FR1.5 proves the bytes are there,
  # SMOKE proves a probe measured something, and on 2026-08-24 both were green for feast-server while
  # its online store was completely empty.
  gate TXN "every shipped service answers a real transaction" \
    txn_ok "$newtag" "$diff_file" || abort

  rm -f "$diff_file"
  # Say what was VERIFIED, not what the gate is named. Run #31 shipped store-scaler, whose TXN line
  # correctly read "no transaction defined, NOT verified: store-scaler / 0 service(s) answered" — and
  # this line then claimed it was "answering real transactions". The gate was honest; the summary
  # under it was not, which is the same false-confidence this whole loop exists to remove.
  printf '✓ shipped: %s is live and smoke-verified (see the TXN line above for what answered a real transaction).\n' "$newtag"

  # EMA-172 — record the deploy for DORA deployment-frequency. AFTER the gates, deliberately: this
  # only ever describes a ship that FR1.5 and TXN already proved. It cannot abort the run (the deploy
  # is real whatever Port says), but a failure is loud, because a silently-missed emit makes the
  # scorecard indistinguishable from a lab that stopped deploying.
  #
  # The PR id is GitHub's INTERNAL id, not the PR number: Port's githubPullRequest entities are keyed
  # on it (identifier 4240999487, with prNumber 3 as a property). Without it the deployment still
  # records — the relation is optional — but `github_lead_time_hours`, which mirrors the PR's
  # cycle_time_hours, stays empty.
  local pr_id=""
  if [ -n "${pr_num:-}" ]; then
    pr_id="$(gh api "repos/${REPO}/pulls/${pr_num}" --jq '.id' 2>/dev/null || true)"
  fi
  emit_deployment "$newtag" "weyland-lab" "$pr_id" || true
}

# Source guard: `SHIP_IMAGES_LIB=1 source ship-images.sh` loads the predicates without running.
if [ -z "${SHIP_IMAGES_LIB:-}" ]; then
  main "$@"
fi
