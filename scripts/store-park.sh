#!/usr/bin/env bash
# store-park.sh — wake or park the stores B199 parks by default (2026-10-01).
#
# WHY GIT, NOT kubectl: every Argo app runs selfHeal, so a live `kubectl scale` is reverted within ~3 min. The ONLY
# switch that sticks is the replica count committed to git. This script edits exactly that one line; you push it
# (you handle all git), Argo applies it, and `wait` tells you when the store is really Ready.
#
#   store-park.sh status                 # each store: what git sets, and what is running
#   store-park.sh wake  <store|all>      # set replicas 1 in git (then push)
#   store-park.sh park  <store|all>      # set replicas 0 in git (then push)
#   store-park.sh wait  <store|all>      # after the push: block until it is Ready (or the timeout)
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

# datahub <args...> — run scripts/datahub_schedule.py against the real GMS: a temporary local port-forward to
# data-mesh/datahub-datahub-gms and the token from the cluster Secret weyland/datahub-token, held only in this
# process's environment (never printed, never written). STORE_PARK_DATAHUB_CMD replaces all of it (the bats seam).
datahub() {
  if [ -n "${STORE_PARK_DATAHUB_CMD:-}" ]; then "$STORE_PARK_DATAHUB_CMD" "$@"; return; fi
  local port=$(( 20000 + RANDOM % 10000 )) pf rc token
  token="$(kubectl -n weyland get secret datahub-token -o jsonpath='{.data.token}' 2>/dev/null | base64 -d 2>/dev/null)"
  [ -n "$token" ] || { echo "DataHub: cannot read the token from Secret weyland/datahub-token" >&2; return 2; }
  kubectl -n data-mesh port-forward svc/datahub-datahub-gms "$port:8080" >/dev/null 2>&1 & pf=$!
  for _ in $(seq 1 30); do (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && break; sleep 0.5; done
  DATAHUB_GMS_URL="http://127.0.0.1:$port" DATAHUB_GMS_TOKEN="$token" python3 "$REPO_ROOT/scripts/datahub_schedule.py" "$@"
  rc=$?; kill "$pf" 2>/dev/null; wait "$pf" 2>/dev/null; return $rc
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
    dh_failed=""
    for s in $list; do
      n="$(dh_name_of "$s")"; [ -n "$n" ] || continue
      if [ "$want" = 0 ]; then datahub pause "$n" || dh_failed="$dh_failed $s"
      else datahub resume "$n" "$(dh_cron_of "$s")" "$TZ_NY" || dh_failed="$dh_failed $s"; fi
    done
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
  wait)
    [ -n "$target" ] || die "usage: store-park.sh wait <store|all>"
    list="$(expand "$target")" || exit 2
    [ -z "${STORE_PARK_NO_KUBECTL:-}" ] && command -v kubectl >/dev/null || die "cannot ask the cluster (no kubectl) — not reporting Ready"
    deadline=$(( $(date +%s) + WAIT_TIMEOUT ))
    for s in $list; do
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
    done ;;
  *) die "usage: store-park.sh status | wake <store|all> | park <store|all> | wait <store|all>   (stores: $STORES)" ;;
esac
