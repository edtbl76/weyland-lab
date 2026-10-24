#!/usr/bin/env bash
# store-park.sh — wake or park the stores B199 parks by default (2026-10-01).
#
# WHY GIT, NOT kubectl: every Argo app runs selfHeal, so a live `kubectl scale` is reverted within ~3 min. The ONLY
# switch that sticks is the replica count committed to git. This script edits exactly that one line; you push it
# (you handle all git), Argo applies it, and `wait` tells you when the store is really Ready.
#
#   store-park.sh up    <store|all>      # ONE command: replicas 1 + commit that file only + push + DataHub + wait
#   store-park.sh down  <store|all>      # ONE command: replicas 0 + commit that file only + push + DataHub + wait
#   store-park.sh status                 # each store: what git sets, and what is running
#   store-park.sh wake  <store|all>      # set replicas 1 in git (then push)
#   store-park.sh park  <store|all>      # set replicas 0 in git (then push)
#   store-park.sh wait  <store|all>      # after the push: block until it is Ready (or the timeout)
#
# `up`/`down` (B232) commit and push, so THE OWNER RUNS THEM (the owner handles all git); an agent hands over the
# command and never runs it. They commit ONLY the store manifests, by explicit path (never -a), with the fixed message
# `store-park: <up|down> <stores> (replicas N)`, and refuse (exit 2, nothing edited or committed) unless the push would
# carry that one commit alone: the branch is main, main is level with origin/main (neither behind nor ahead), and the
# manifests have no uncommitted changes of their own. A rejected push exits 2 with git's reason; nothing is forced.
# After the push they ask Argo to sync (best effort, see argo_sync) instead of waiting out its ~3 min poll.
#
# Stores: cassandra mongodb cockroachdb superset-worker. Exit: 0 ok · 1 not Ready in time · 2 refused / cannot tell.
# Undo the default parking when new hardware lands: B134 (EMA-195) § Undo on hardware.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
K="${STORE_PARK_ROOT:-$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s}"   # bats seam: a copy of the manifests
STORES="cassandra mongodb cockroachdb superset-worker"
WAIT_TIMEOUT="${STORE_PARK_WAIT_TIMEOUT:-600}"
POLL="${STORE_PARK_POLL:-10}"                     # seconds between checks (bats sets 0)
PROGRESS_EVERY="${STORE_PARK_PROGRESS_EVERY:-3}"  # print a progress line every N checks (~30s)

die() { printf '%s\n' "$*" >&2; exit 2; }

# file_of <store> -> manifest holding its replica count;  kind_of <store> -> the live object for kubectl
file_of() {
  case "$1" in
    superset-worker) echo "$K/superset/superset-values.yaml" ;;
    *) echo "$K/data-mesh/$1.yaml" ;;
  esac
}
kind_of() { case "$1" in cassandra) echo statefulset ;; *) echo deployment ;; esac; }
app_of() { case "$1" in superset-worker) echo superset ;; *) echo data-mesh ;; esac; }   # its Argo application

# Its DataHub ingestion source and the schedule `wake` restores (America/New_York). The Superset worker has none.
TZ_NY="America/New_York"
dh_name_of() { case "$1" in cassandra) echo "Cassandra - Weyland" ;; mongodb) echo "MongoDB - Weyland" ;;
                            cockroachdb) echo "CockroachDB - Weyland" ;; *) echo "" ;; esac; }
dh_cron_of() { case "$1" in cassandra) echo "15 4 * * 0" ;; mongodb) echo "45 3 * * *" ;; cockroachdb) echo "30 3 * * *" ;; esac; }

# datahub <args...> — run scripts/datahub_schedule.py against the real GMS through its LAN NodePort
# (datahub-gms-lan, k8s/data-mesh/query-lan.yaml; the lab never port-forwards) with the token from the cluster Secret
# weyland/datahub-token, held only in this process's environment (never printed, never written). DATAHUB_GMS_URL
# overrides the endpoint. STORE_PARK_DATAHUB_CMD replaces all of it (the bats seam).
datahub() {
  if [ -n "${STORE_PARK_DATAHUB_CMD:-}" ]; then "$STORE_PARK_DATAHUB_CMD" "$@"; return; fi
  local token
  token="$(kubectl -n weyland get secret datahub-token -o jsonpath='{.data.token}' 2>/dev/null | base64 -d 2>/dev/null)"
  [ -n "$token" ] || { echo "DataHub: cannot read the token from Secret weyland/datahub-token" >&2; return 2; }
  DATAHUB_GMS_URL="${DATAHUB_GMS_URL:-http://192.168.1.243:30818}" DATAHUB_GMS_TOKEN="$token" \
    python3 "$REPO_ROOT/scripts/datahub_schedule.py" "$@"
}

# argo_sync <app> — `up`/`down` only, after the push: ask Argo to sync now instead of waiting out its ~3 min poll. BEST
# EFFORT: every failure prints one line and leaves the wait to Argo's own poll; it never fails the command. With a live
# argocd CLI session it uses that. Otherwise it swaps the cluster's admin password (Secret argocd/argocd-initial-admin-
# secret, read through kubectl, never printed) for a short-lived token through the session API on the LAN NodePort: the
# password goes in on curl's STDIN, the token reaches `argocd app sync` in its ENVIRONMENT, so neither is on a command
# line, and the owner's saved CLI session is not touched. STORE_PARK_ARGOCD / STORE_PARK_ARGO_SERVER are the seams.
ARGOCD="${STORE_PARK_ARGOCD:-argocd}"
ARGO_SERVER="${STORE_PARK_ARGO_SERVER:-mother:30880}"
argo_sync() {
  local app="$1" pw token fallback="— leaving it to Argo's own poll (~3 min)"
  command -v "$ARGOCD" >/dev/null || { echo "argo: no argocd CLI $fallback"; return 0; }
  if "$ARGOCD" app list --grpc-web -o name >/dev/null 2>&1; then
    if "$ARGOCD" app sync "$app" --grpc-web --async >/dev/null 2>&1; then echo "argo: sync of $app requested (CLI session)"
    else echo "argo: sync of $app did not return cleanly (often a concurrent Argo operation) $fallback"; fi
    return 0
  fi
  pw="$(kubectl -n argocd get secret argocd-initial-admin-secret -o 'go-template={{.data.password | base64decode}}' 2>/dev/null)"
  [ -n "$pw" ] || { echo "argo: no CLI session, and cannot read Secret argocd/argocd-initial-admin-secret $fallback"; return 0; }
  token="$(printf '%s' "$pw" \
    | python3 -c 'import json,sys; print(json.dumps({"username": "admin", "password": sys.stdin.read()}))' \
    | curl -s -m 10 -X POST -H 'Content-Type: application/json' --data @- "http://$ARGO_SERVER/api/v1/session" \
    | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("token", ""))
except ValueError: print("")')"
  [ -n "$token" ] || { echo "argo: no CLI session, and the session API gave no token $fallback"; return 0; }
  if ARGOCD_AUTH_TOKEN="$token" "$ARGOCD" app sync "$app" --server "$ARGO_SERVER" --plaintext --grpc-web --async >/dev/null 2>&1; then
    echo "argo: sync of $app requested (token)"
  else echo "argo: sync of $app did not return cleanly (often a concurrent Argo operation) $fallback"; fi
}

# replica_line <store> -> "<line-number> <value>" of the ONE line that sets its replicas; fails closed otherwise.
# Data-mesh stores: the workload's `  replicas: N` (the only 2-space `replicas:` in the file). Superset worker: the
# `    replicaCount: N` inside the top-level `supersetWorker:` block (other components have their own blocks).
replica_line() {
  local f; f="$(file_of "$1")"
  [ -f "$f" ] || die "cannot find $f"
  local hits
  if [ "$1" = superset-worker ]; then
    hits="$(awk '/^[^[:space:]#]/{blk=($1=="supersetWorker:")} blk && /^    replicaCount: [0-9]+$/{print NR, $2}' "$f")"
  else
    hits="$(awk '/^  replicas: [0-9]+$/{print NR, $2}' "$f")"
  fi
  [ "$(printf '%s\n' "$hits" | grep -c .)" -eq 1 ] || die "cannot find exactly one replica line for $1 in $f (found: ${hits:-none})"
  printf '%s\n' "$hits"
}

set_replicas() {  # set_replicas <store> <0|1>
  local store="$1" want="$2" rl line val f
  rl="$(replica_line "$store")" || exit 2      # capture first: a failure inside <<<"$(...)" would be lost
  read -r line val <<<"$rl"
  f="$(file_of "$store")"
  if [ "$val" = "$want" ]; then
    echo "$store: already $( [ "$want" = 1 ] && echo awake || echo parked ) in git (replicas $want) — nothing to change"
    return 0
  fi
  sed -i "${line}s/: ${val}\$/: ${want}/" "$f"
  echo "$store: replicas ${val} -> ${want} in ${f#"$REPO_ROOT"/}"
  CHANGED="$CHANGED $f"
}

expand() {  # expand <store|all> -> the store list, refusing an unknown name
  [ "$1" = all ] && { echo "$STORES"; return; }
  case " $STORES " in *" $1 "*) echo "$1" ;; *) die "unknown store '$1' — one of: $STORES (or all)";; esac
}

live() {  # live <store> -> "desired/ready" from the cluster, or "?" when it cannot ask
  [ -n "${STORE_PARK_NO_KUBECTL:-}" ] && { echo "?"; return; }
  kubectl -n data-mesh get "$(kind_of "$1")" "$1" \
    -o jsonpath='{.spec.replicas}/{.status.readyReplicas}' 2>/dev/null || echo "?"
}

# preflight <manifest...> — `up`/`down` push, so refuse (exit 2) unless that push would carry only their own commit.
# Runs BEFORE any edit. Sets TOP to the work tree holding the manifests (the lab repo; a scratch repo under bats).
preflight() {
  local branch behind ahead f
  TOP="$(git -C "$K" rev-parse --show-toplevel 2>/dev/null)" || die "refused: $K is not inside a git work tree"
  branch="$(git -C "$TOP" symbolic-ref --short -q HEAD)" || branch="a detached HEAD"
  [ "$branch" = main ] || die "refused: the branch is not main (it is $branch) — nothing edited or committed"
  git -C "$TOP" fetch -q origin main 2>/dev/null \
    || die "refused: cannot fetch origin main, so cannot tell whether main is up to date — nothing edited or committed"
  if ! behind="$(git -C "$TOP" rev-list --count HEAD..origin/main)" || ! ahead="$(git -C "$TOP" rev-list --count origin/main..HEAD)"; then
    die "refused: cannot compare main with origin/main — nothing edited or committed"
  fi
  [ "$behind" -eq 0 ] || die "refused: main is $behind commit(s) behind origin/main — git pull first; nothing edited or committed"
  [ "$ahead" -eq 0 ] || die "refused: main is $ahead commit(s) ahead of origin/main — push or drop them first (this command's push would publish them too); nothing edited or committed"
  for f in "$@"; do
    [ -z "$(git -C "$TOP" status --porcelain -- "$f")" ] \
      || die "refused: uncommitted changes of your own in ${f#"$TOP"/} — commit or revert them first; nothing edited or committed"
  done
}

# set_schedules <0|1> <store...> — pause (0) or resume (1) each store's DataHub schedule; names the failures in DH_FAILED
set_schedules() {
  local want="$1" s n; shift
  DH_FAILED=""
  for s in "$@"; do
    n="$(dh_name_of "$s")"; [ -n "$n" ] || continue
    if [ "$want" = 0 ]; then datahub pause "$n" || DH_FAILED="$DH_FAILED $s"
    else datahub resume "$n" "$(dh_cron_of "$s")" "$TZ_NY" || DH_FAILED="$DH_FAILED $s"; fi
  done
}

# wait_for <store...> — block until the cluster runs what git sets for each; exit 1 at the timeout, 2 if it cannot ask
wait_for() {
  local s rl want n st desired ready hint deadline
  if [ -n "${STORE_PARK_NO_KUBECTL:-}" ] || ! command -v kubectl >/dev/null; then
    die "cannot ask the cluster (no kubectl) — not reporting Ready"
  fi
  deadline=$(( $(date +%s) + WAIT_TIMEOUT ))
  for s in "$@"; do
    rl="$(replica_line "$s")" || exit 2; read -r _ want <<<"$rl"
    n=0
    while :; do
      st="$(live "$s")"; desired="${st%/*}"; ready="${st#*/}"; ready="${ready:-0}"
      [ "$st" = "?" ] && die "$s: cannot read its state from the cluster — not reporting Ready"
      if [ "$desired" = "$want" ] && [ "$ready" = "$want" ]; then
        echo "$s: $( [ "$want" = 1 ] && echo "Ready (1/1)" || echo "parked (0/0)" )"; break
      fi
      n=$((n + 1))
      if [ $((n % PROGRESS_EVERY)) -eq 1 ] || [ "$PROGRESS_EVERY" -eq 1 ]; then
        hint=""; [ "$desired" != "$want" ] && hint=" — Argo has not applied the push yet (argocd app sync $(app_of "$s") to skip the ~3 min poll)"
        echo "$s: waiting — git wants $want, cluster has desired=$desired ready=$ready$hint"
      fi
      if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "$s: NOT there yet — git wants $want, cluster has desired=$desired ready=$ready (pushed? Argo synced?)" >&2
        exit 1
      fi
      sleep "$POLL"
    done
  done
}

cmd="${1:-}"; target="${2:-}"
CHANGED=""
case "$cmd" in
  status)
    names=(); for s in $STORES; do n="$(dh_name_of "$s")"; [ -n "$n" ] && names+=("$n"); done
    dh_out="$(datahub status "${names[@]}" 2>&1)" || dh_out=""
    for s in $STORES; do
      rl="$(replica_line "$s")" || exit 2; read -r _ v <<<"$rl"
      n="$(dh_name_of "$s")"; d="-"
      if [ -n "$n" ]; then d="$(printf '%s\n' "$dh_out" | grep -F "$n: " | head -1)"; d="${d#"$n: "}"; d="${d:-?}"; fi
      printf '%-16s git=%s  live(desired/ready)=%-4s datahub=%s\n' "$s" "$v" "$(live "$s")" "$d"
    done ;;
  wake|park)
    [ -n "$target" ] || die "usage: store-park.sh $cmd <store|all>"
    list="$(expand "$target")" || exit 2
    want=1; [ "$cmd" = park ] && want=0
    for s in $list; do set_replicas "$s" "$want"; done
    # shellcheck disable=SC2086  # the store list is fixed words, split on purpose
    set_schedules "$want" $list; dh_failed="$DH_FAILED"
    if [ -n "$CHANGED" ]; then
      echo
      apps="$(for s in $list; do app_of "$s"; done | sort -u | tr '\n' ' ')"
      echo "Now commit + push the file(s) above with git (this script never pushes). Argo applies it on its own"
      echo "within ~3 min; to apply it now instead:"
      for a in $apps; do echo "  argocd app sync $a"; done
      echo "Then wait until it is really there:"
      echo "  bash $REPO_ROOT/scripts/store-park.sh wait $target"
    fi
    if [ -n "$dh_failed" ]; then
      echo "!! DataHub schedule NOT changed for:$dh_failed — the git edit above IS done. Re-run this command to retry" >&2
      echo "   the schedule (the git edit is then a no-op), or set it in the DataHub UI." >&2
      exit 2
    fi ;;
  up|down)
    [ -n "$target" ] || die "usage: store-park.sh $cmd <store|all>"
    list="$(expand "$target")" || exit 2
    want=1; [ "$cmd" = down ] && want=0
    files=()
    for s in $list; do replica_line "$s" >/dev/null || exit 2; files+=("$(file_of "$s")"); done
    preflight "${files[@]}"
    count="$(wc -w <<<"$list")"
    if [ "$want" = 1 ] && [ "$count" -gt 1 ]; then
      echo "!! waking $count stores at once — all four together need ~9 GB of mother's memory (runbooks/node-capacity.md)" >&2
    fi
    for s in $list; do set_replicas "$s" "$want"; done
    if [ -n "$CHANGED" ]; then
      msg="store-park: $cmd $list (replicas $want)"
      # shellcheck disable=SC2086  # CHANGED is a list of manifest paths (no spaces), split on purpose
      git -C "$TOP" commit -q -m "$msg" -- $CHANGED \
        || die "commit failed — the replica edit is in the working tree, not committed; nothing pushed"
      if ! out="$(git -C "$TOP" push -q origin main 2>&1)"; then
        printf 'push failed: %s\n' "$out" >&2
        echo "The commit \"$msg\" ($(git -C "$TOP" rev-parse --short HEAD)) is local only — NOT pushed. The DataHub" >&2
        echo "schedule was not changed and nothing waited. Push it yourself (never forced), then re-run:" >&2
        echo "  bash $REPO_ROOT/scripts/store-park.sh $cmd $target" >&2
        exit 2
      fi
      echo "pushed: $msg"
      for a in $(for s in $list; do app_of "$s"; done | sort -u); do argo_sync "$a"; done
    fi
    # shellcheck disable=SC2086  # the store list is fixed words, split on purpose
    set_schedules "$want" $list
    [ -n "$DH_FAILED" ] && echo "!! DataHub schedule NOT changed for:$DH_FAILED — the push IS done; re-run this command to retry the schedule, or set it in the DataHub UI." >&2
    # shellcheck disable=SC2086
    wait_for $list
    [ -z "$DH_FAILED" ] || exit 2 ;;
  wait)
    [ -n "$target" ] || die "usage: store-park.sh wait <store|all>"
    list="$(expand "$target")" || exit 2
    # shellcheck disable=SC2086  # the store list is fixed words, split on purpose
    wait_for $list ;;
  *) die "usage: store-park.sh up <store|all> | down <store|all> | status | wake <store|all> | park <store|all> | wait <store|all>   (stores: $STORES)" ;;
esac
