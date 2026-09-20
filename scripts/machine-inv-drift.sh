#!/usr/bin/env bash
# B170 — nightly machine-inventory drift check + PR opener. Runs on rogueone (a user systemd timer, like the
# B130 restic backup), because that is where discretionary installs actually happen and rogueone already holds
# the fleet SSH keys, `gh` auth, and PR_TOKEN / Port creds / KUMA_INVENTORY_PUSH_URL in scripts/.env.
#
# WHAT IT DOES each run:
#   1. Emit + read-back verify the COMMITTED catalog to Port (keeps Port tracking the accepted SoT; reuses the
#      B169 verify gate). Non-fatal to the scan.
#   2. For each REACHABLE host: `collect | machine_inventory.py merge --prune` — reconcile the catalog (add new
#      installs, drop uninstalls, preserve your keep/remove decisions). This runs inside an ISOLATED git
#      worktree off origin/main, so your working checkout is never touched. An UNREACHABLE host is SKIPPED,
#      never pruned — merge refuses empty stdin, so a host we could not scan can never be blanked.
#   3. If the catalog changed → commit it on ONE branch and open (or update) a single inventory PR. Merging the
#      PR IS the cataloging — no hand data-entry.
#   4. Push a Kuma heartbeat: `up` when clean AND every host was reachable; `down` (→ Telegram, same channel as
#      the restic dead-man's-switch) on drift or an unreachable host. No ping for > the heartbeat window (box
#      off for days) also trips Kuma — one monitor covers ran / drifted / host-unreachable.
#
#   usage: machine-inv-drift.sh            # the nightly run (systemd timer)
#          machine-inv-drift.sh --dry-run  # scan + reconcile into a throwaway worktree, print the diff, but
#                                          # NO push / PR / Port / Kuma — for a demo or a manual check
#
# Fail-closed: an unreachable host is skipped (never a mass-prune); a failed emit/verify is reported, not hidden.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── seams (bats fixtures override these; prod defaults are the real tools) ────────────────────────────────
REPO="${MACHINE_INV_REPO:-edtbl76/weyland-lab}"
BASE="${MACHINE_INV_BASE:-main}"
BRANCH="${MACHINE_INV_DRIFT_BRANCH:-chore/machine-inventory-drift}"
HOSTS="${MACHINE_INV_HOSTS:-rogueone mother weyland}"
COLLECT_CMD="${MACHINE_INV_COLLECT_CMD:-bash $REPO_ROOT/scripts/collect-machine-inventory.sh}"
INV_CMD="${MACHINE_INV_PY_CMD:-python3 $REPO_ROOT/scripts/machine_inventory.py}"
PORT_ENV="${MACHINE_INV_PORT_ENV:-$REPO_ROOT/nodes/mother/lab/weyland-platform/tofu/port/.env}"

# decide_signal <drift 0|1> <unreachable-hosts> <summary> — the pure Kuma/Telegram decision. Prints
# "<up|down>\t<msg>". `up` ONLY when the catalog is clean AND every host was reachable; anything else is `down`
# so it reaches Telegram. Kept separate + side-effect-free so bats can pin every state without a network.
decide_signal() {
  local drift="$1" unreachable="$2" summary="$3"
  if [ -n "$unreachable" ] && [ "$drift" = "1" ]; then
    printf 'down\tmachine-inventory drift (%s) + unreachable:%s\n' "$summary" "$unreachable"
  elif [ -n "$unreachable" ]; then
    printf 'down\tmachine-inventory: host(s) unreachable:%s\n' "$unreachable"
  elif [ "$drift" = "1" ]; then
    printf 'down\tmachine-inventory drift: %s\n' "$summary"
  else
    printf 'up\tmachine-inventory: clean, all hosts reachable\n'
  fi
}

kuma_push() {  # kuma_push <up|down> <msg> — dead-man's-switch heartbeat (same mechanism as restic, B130)
  [ -n "${KUMA_INVENTORY_PUSH_URL:-}" ] || { echo "KUMA_INVENTORY_PUSH_URL unset — skip heartbeat" >&2; return 0; }
  local enc; enc="$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$2")"
  curl -fsS -m 15 "${KUMA_INVENTORY_PUSH_URL}?status=$1&msg=${enc}" >/dev/null \
    && echo "Kuma: pinged $1" || echo "Kuma ping failed (non-fatal)" >&2
}

# open_or_update_pr <worktree> — commit the reconciled SoT on $BRANCH and ensure ONE open PR. A force-push to
# an existing branch auto-updates its open PR; only `gh pr create` when none is open. FAILS the run on a git/gh
# error rather than pretending success.
open_or_update_pr() {
  local wt="$1"
  : "${PR_TOKEN:?PR_TOKEN unset (scripts/.env) — cannot open the inventory PR}"
  export GH_TOKEN="$PR_TOKEN"
  git -C "$wt" checkout -q -B "$BRANCH"   # cut the branch here (worktree was detached), keeping the reconcile
  git -C "$wt" -c user.name="machine-inventory bot" -c user.email="noreply@weyland.lab" \
      commit -q -m "chore(inventory): reconcile host software drift" -- machine-inventory.yaml
  git -C "$wt" push -q -f -u origin "$BRANCH" || { echo "!! push to origin/$BRANCH failed" >&2; return 1; }
  local existing
  existing="$(gh pr list --repo "$REPO" --state open --head "$BRANCH" --json number -q '.[0].number' 2>/dev/null || true)"
  if [ -n "$existing" ]; then
    echo "→ updated open inventory PR #$existing"
  elif gh pr create --repo "$REPO" --base "$BASE" --head "$BRANCH" \
        --title "chore(inventory): host software drift" \
        --body "Automated by machine-inv-drift.sh (B170). Merging this PR catalogs the changes below. Review the diff; set keep/remove on any new discretionary item, or just merge to accept it. Removals are software no longer installed."; then
    echo "→ opened inventory PR"
  else
    echo "!! gh pr create failed" >&2; return 1
  fi
}

main() {
  local dry=0; [ "${1:-}" = "--dry-run" ] && dry=1
  cd "$REPO_ROOT" || { echo "!! cannot cd to $REPO_ROOT" >&2; return 1; }

  # Creds for the PR (PR_TOKEN) + the Kuma heartbeat (KUMA_INVENTORY_PUSH_URL) live in the gitignored
  # scripts/.env, exactly like the restic backup (B130); Port creds are sourced per-use from PORT_ENV below.
  # A --dry-run needs none of these, so a missing .env is fine there.
  # shellcheck disable=SC1091
  [ -f "$REPO_ROOT/scripts/.env" ] && { set -a; . "$REPO_ROOT/scripts/.env"; set +a; }

  # 1) keep Port synced with the ACCEPTED (committed) catalog + read-back verify (B169). Never blocks the scan.
  if [ "$dry" = "0" ] && [ -f "$PORT_ENV" ]; then
    # shellcheck disable=SC1090  # PORT_ENV is a runtime path (gitignored .env), not a constant to follow
    ( set -a; . "$PORT_ENV"; set +a; $INV_CMD emit all && $INV_CMD verify all ) \
      || echo "!! emit/verify reported an issue (see above) — continuing to the scan" >&2
  fi

  # isolated worktree off origin/main so the live checkout is never dirtied
  git fetch -q origin "$BASE" || echo "⚠ could not fetch origin/$BASE — reconciling against local $BASE" >&2
  local wt; wt="$(mktemp -d)/wt"
  # Detached — a dry run creates NO branch in your repo; the branch is cut only when we open the PR.
  git worktree add -q --detach "$wt" "origin/$BASE" 2>/dev/null \
    || git worktree add -q --detach "$wt" "$BASE"
  # shellcheck disable=SC2064
  trap "git -C '$REPO_ROOT' worktree remove --force '$wt' >/dev/null 2>&1 || true" RETURN

  # 2) reconcile each REACHABLE host into the worktree's SoT (unreachable → skipped, never pruned)
  local unreachable="" h
  for h in $HOSTS; do
    if $COLLECT_CMD "$h" | MACHINE_INV_SOT="$wt/machine-inventory.yaml" $INV_CMD merge --prune "$h"; then :; else
      echo "!! could not scan $h (unreachable or empty) — skipped, catalog untouched for it" >&2
      unreachable="$unreachable $h"
    fi
  done

  # 3) drift = the reconciled SoT differs from origin/main. Summarize + open/update the PR.
  local drift=0 summary="none"
  if ! git -C "$wt" diff --quiet -- machine-inventory.yaml; then
    drift=1
    summary="$(git -C "$wt" diff --numstat -- machine-inventory.yaml | awk '{print "+"$1"/-"$2" lines"}')"
    if [ "$dry" = "1" ]; then
      echo "── DRY RUN: catalog would change ($summary) ──"
      git -C "$wt" --no-pager diff -- machine-inventory.yaml
    else
      open_or_update_pr "$wt" || { kuma_push down "machine-inventory: PR step FAILED"; return 1; }
    fi
  else
    echo "catalog in sync — no drift"
  fi

  # 4) heartbeat → Telegram on down (drift or unreachable)
  local sig state msg
  sig="$(decide_signal "$drift" "$unreachable" "$summary")"
  state="${sig%%$'\t'*}"; msg="${sig#*$'\t'}"
  echo "signal: $state — $msg"
  [ "$dry" = "0" ] && kuma_push "$state" "$msg"
  return 0
}

# lib seam: `MACHINE_INV_DRIFT_LIB=1 . machine-inv-drift.sh` exposes the functions to bats without running.
[ "${MACHINE_INV_DRIFT_LIB:-}" = "1" ] && return 0
main "$@"
