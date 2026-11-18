#!/bin/sh
# pipeline-status.sh (B200, 2026-11-18) — the TRUE status of this multi-workflow pipeline, for the `finish` workflow.
#
# WHY: inside a workflow, $CI_PIPELINE_STATUS and `when: status` only see THAT workflow. On the throwaway branch
# b200-status-test, pipeline #683 failed (workflow `bad`) while `finish` read CI_PIPELINE_STATUS=success and ran its
# success-gated step. notify-port would have posted success for a red pipeline and notify-slack would have stayed
# silent. So the status is read from Woodpecker's API; anonymous reads work because weyland-lab is a public repo, so no
# token enters CI.
#
# Prints ONE line on stdout, `success` or `failure`, then the per-workflow states on the next line:
#   failure  any OTHER workflow is failure / error / killed
#   success  every OTHER workflow is success / skipped
#   unknown  anything else (still running, unreadable API, no other workflow, no CI_WORKFLOW_NAME): prints `failure`
#            so callers fail closed, explains on stderr with UNKNOWN, and exits 2.
# Exit 0 = determined. The caller's own workflow ($CI_WORKFLOW_NAME) is never counted.
#
# Env: CI_WORKFLOW_NAME, CI_REPO (owner/name), CI_PIPELINE_NUMBER, WOODPECKER_API (default: the in-cluster server).
# Test seam: PIPELINE_JSON_FILE replaces both HTTP calls with a file. Needs curl + jq.
# Tests: scripts/tests/pipeline-status.bats. Runbook: docs/runbooks/woodpecker.md § Workflows.
set -u

unknown() { echo "failure"; echo "UNKNOWN: $1 — reporting failure (fail closed)" >&2; exit 2; }

[ -n "${CI_WORKFLOW_NAME:-}" ] || unknown "CI_WORKFLOW_NAME is not set, so this workflow cannot exclude itself"

if [ -n "${PIPELINE_JSON_FILE:-}" ]; then
  json="$(cat "$PIPELINE_JSON_FILE" 2>/dev/null)" || unknown "cannot read $PIPELINE_JSON_FILE"
else
  api="${WOODPECKER_API:-http://woodpecker-server.woodpecker.svc.cluster.local}"
  [ -n "${CI_REPO:-}" ] && [ -n "${CI_PIPELINE_NUMBER:-}" ] || unknown "CI_REPO or CI_PIPELINE_NUMBER is not set"
  id="$(curl -sf --connect-timeout 10 --max-time 20 "$api/api/repos/lookup/$CI_REPO" | jq -r '.id // empty' 2>/dev/null)"
  [ -n "$id" ] || unknown "cannot read the repo id for $CI_REPO from $api"
  json="$(curl -sf --connect-timeout 10 --max-time 20 "$api/api/repos/$id/pipelines/$CI_PIPELINE_NUMBER")" \
    || unknown "cannot read pipeline $CI_PIPELINE_NUMBER from $api"
fi

# "<name>=<state>" for every workflow except this one; jq fails on anything that is not the expected shape.
states="$(printf '%s' "$json" | jq -r --arg me "$CI_WORKFLOW_NAME" \
  '.workflows | map(select(.name != $me)) | .[] | "\(.name)=\(.state)"' 2>/dev/null)" \
  || unknown "cannot read the workflows in the API response"
[ -n "$states" ] || unknown "no other workflow in pipeline ${CI_PIPELINE_NUMBER:-?}"

failed="" pending=""
for s in $states; do
  case "${s#*=}" in
    success|skipped) ;;
    failure|error|killed) failed="$failed $s" ;;
    *) pending="$pending $s" ;;
  esac
done

summary="$(printf '%s' "$states" | tr '\n' ' ')"
if [ -n "$failed" ]; then
  echo "failure"; echo "$summary"; exit 0
fi
[ -z "$pending" ] || unknown "a workflow has not finished:$pending"
echo "success"; echo "$summary"
