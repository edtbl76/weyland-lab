#!/usr/bin/env bash
# B185 — time per Linear issue: agent session time, lead and cycle time. The one command (runbook issue-time.md).
#
#   scripts/issue-time.sh            fetch the newest Linear snapshot, print the table (most agent time first)
#   scripts/issue-time.sh --json     the same rows as JSON
#   scripts/issue-time.sh --port     push to Port: issue_time entities (read back) + the Time per Issue dashboard
#
# Reads the session summaries the ai-session producer writes (~/.cache/ai-sessions) and the newest B194 snapshot
# (weyland/linear-backup/snapshots/<ts>/issues.json.gz + workflowStates.json.gz, copied to ~/.cache). All logic lives in
# nodes/mother/lab/weyland-platform/scripts/issue_time_report.py.
# B185 lane 2: the owner's own time (owner_time.py → ~/.cache/owner-time/owner_time.json) joins the rows when that file
# exists; without it the owner columns are unknown (not zero) and the script says so.
# EXIT: 0 ok · 1 Port read-back mismatch · 2 could not run (no snapshot, fetch failed, no Port credentials, bad input).
# Seams (tests): ISSUE_TIME_MC, ISSUE_TIME_REPORT, ISSUE_TIME_CACHE, ISSUE_TIME_SESSIONS, ISSUE_TIME_PORT_ENV,
#   ISSUE_TIME_OWNER.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MC="${ISSUE_TIME_MC:-mc}"
REPORT="${ISSUE_TIME_REPORT:-python3 $REPO_ROOT/nodes/mother/lab/weyland-platform/scripts/issue_time_report.py}"
CACHE="${ISSUE_TIME_CACHE:-$HOME/.cache}"
SESSIONS="${ISSUE_TIME_SESSIONS:-$HOME/.cache/ai-sessions}"
PORT_ENV="${ISSUE_TIME_PORT_ENV:-$REPO_ROOT/nodes/mother/lab/weyland-platform/tofu/port/.env}"
OWNER="${ISSUE_TIME_OWNER:-$HOME/.cache/owner-time/owner_time.json}"
SNAPSHOTS="weyland/linear-backup/snapshots"

mode=()
case "${1:-}" in
  "") ;;
  --json|--port) mode=("$1") ;;
  *) echo "usage: issue-time.sh [--json | --port]" >&2; exit 2 ;;
esac

if [ "${mode[0]:-}" = "--port" ]; then
  [ -f "$PORT_ENV" ] || { echo "issue-time: Port credentials not found ($PORT_ENV)" >&2; exit 2; }
  set -a
  # shellcheck source=/dev/null
  . "$PORT_ENV"
  set +a
fi

latest="$($MC ls "$SNAPSHOTS/" 2>/dev/null | awk 'NF {print $NF}' | sort | tail -1)"
latest="${latest%/}"
[ -n "$latest" ] || { echo "issue-time: no Linear snapshot listed under $SNAPSHOTS (B194 backup — linear-backup.md)" >&2; exit 2; }

mkdir -p "$CACHE"
issues="$CACHE/linear-issues.json.gz"
states="$CACHE/linear-workflow-states.json.gz"   # the state types: the Linear start, as the B194 dbt mart defines it
for pair in "issues.json.gz:$issues" "workflowStates.json.gz:$states"; do
  $MC cp -q "$SNAPSHOTS/$latest/${pair%%:*}" "${pair#*:}" >/dev/null \
    || { echo "issue-time: could not fetch $SNAPSHOTS/$latest/${pair%%:*}" >&2; exit 2; }
done

owner=()
if [ -f "$OWNER" ]; then
  owner=(--owner "$OWNER")
else
  echo "issue-time: owner time not collected ($OWNER absent; owner_time.py, runbook § Owner time)" >&2
fi

# shellcheck disable=SC2086  # REPORT is a command line (interpreter + script)
$REPORT --sessions "$SESSIONS" --issues "$issues" --states "$states" "${owner[@]}" "${mode[@]}"
