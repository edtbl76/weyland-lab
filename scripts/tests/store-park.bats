#!/usr/bin/env bats
# store-park.sh — wake / park the B199 default-parked stores by editing the ONE line in git that sets their replica
# count (Argo selfHeal reverts any live scale, so git is the only switch that sticks). Runs against COPIES of the real
# manifests (STORE_PARK_ROOT seam) so the repo is never touched by a test.

setup() {
  REAL="${BATS_TEST_DIRNAME}/../../nodes/mother/lab/weyland-platform/k8s"
  T="$(mktemp -d)"
  mkdir -p "$T/data-mesh" "$T/superset"
  cp "$REAL/data-mesh/cassandra.yaml" "$REAL/data-mesh/mongodb.yaml" "$REAL/data-mesh/cockroachdb.yaml" "$T/data-mesh/"
  cp "$REAL/superset/superset-values.yaml" "$T/superset/"
  export STORE_PARK_ROOT="$T" STORE_PARK_NO_KUBECTL=1
  # DataHub stub: records each call; exits with $DH_RC (default 0). Never touches a real GMS.
  cat > "$T/dh" <<'STUB'
#!/usr/bin/env bash
echo "$*" >> "$DH_LOG"; [ "$1" = status ] && for n in "${@:2}"; do echo "$n: paused"; done; exit "${DH_RC:-0}"
STUB
  chmod +x "$T/dh"
  export STORE_PARK_DATAHUB_CMD="$T/dh" DH_LOG="$T/dh.log"; : > "$T/dh.log"
  S="${BATS_TEST_DIRNAME}/../store-park.sh"
}
teardown() { rm -rf "$T" "$T.origin" "$T.other"; }

replicas_of() {  # replicas_of <store> -> the replica count git sets
  case "$1" in
    superset-worker) python3 -c "import yaml;print(yaml.safe_load(open('$T/superset/superset-values.yaml'))['supersetWorker']['replicas']['replicaCount'])" ;;
    *) python3 -c "import yaml;print([d for d in yaml.safe_load_all(open('$T/data-mesh/$1.yaml')) if d and d.get('kind') in ('Deployment','StatefulSet')][0]['spec']['replicas'])" ;;
  esac
}

@test "every store starts parked (replicas 0) in git" {
  for s in cassandra mongodb cockroachdb superset-worker; do [ "$(replicas_of $s)" = 0 ] || { echo "$s"; return 1; }; done
}

@test "wake sets exactly that store to 1 and leaves the others parked" {
  run bash "$S" wake cockroachdb
  [ "$status" -eq 0 ]
  [ "$(replicas_of cockroachdb)" = 1 ]
  for s in cassandra mongodb superset-worker; do [ "$(replicas_of $s)" = 0 ]; done
  [[ "$output" == *"git"* ]]   # it tells you to push — it never pushes itself
}

@test "wake then park round-trips the file byte-for-byte" {
  cp "$T/data-mesh/mongodb.yaml" "$T/before.yaml"
  run bash "$S" wake mongodb
  [ "$status" -eq 0 ]
  [ "$(replicas_of mongodb)" = 1 ]          # it really woke (a missing script must not pass this test)
  run bash "$S" park mongodb
  [ "$status" -eq 0 ]
  [ "$(replicas_of mongodb)" = 0 ]
  cmp "$T/before.yaml" "$T/data-mesh/mongodb.yaml"
}

@test "the superset worker's nested Helm value is switched, not a stray replicas line" {
  run bash "$S" wake superset-worker
  [ "$status" -eq 0 ]
  [ "$(replicas_of superset-worker)" = 1 ]
  python3 -c "import yaml;d=yaml.safe_load(open('$T/superset/superset-values.yaml'));assert d['supersetWorker']['replicas']['enabled'] is True"
}

@test "wake all wakes every parked store" {
  run bash "$S" wake all
  [ "$status" -eq 0 ]
  for s in cassandra mongodb cockroachdb superset-worker; do [ "$(replicas_of $s)" = 1 ] || { echo "$s"; return 1; }; done
}

@test "waking an already-awake store is a no-op, not an error" {
  bash "$S" wake cassandra
  run bash "$S" wake cassandra
  [ "$status" -eq 0 ]
  [[ "$output" == *"already"* ]]
}

@test "an unknown store is refused with the valid list (exit 2), nothing edited" {
  cp -r "$T" "$T.snap"
  run bash "$S" wake clickhouse
  [ "$status" -eq 2 ]
  [[ "$output" == *"cassandra"* && "$output" == *"superset-worker"* ]]
  diff -r "$T.snap/data-mesh" "$T/data-mesh"; rm -rf "$T.snap"
}

@test "a manifest whose replica line is missing fails closed (exit 2)" {
  sed -i 's/^  replicas: 0$/  replicaz: 0/' "$T/data-mesh/cassandra.yaml"
  run bash "$S" wake cassandra
  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot find"* ]]
}

@test "status lists each store with what git sets" {
  bash "$S" wake mongodb
  run bash "$S" status
  [ "$status" -eq 0 ]
  [[ "$output" == *"mongodb"*"git=1"* ]]
  [[ "$output" == *"cassandra"*"git=0"* ]]
}

@test "wait refuses (exit 2) when it cannot ask the cluster, never a false Ready" {
  run bash "$S" wait cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"cluster"* ]]
}

# wait must SAY what it is waiting for — silent polling read as a hang in the first live drill (2026-10-01).
@test "wait prints progress while the cluster catches up, then reports Ready" {
  mkdir -p "$T/bin"; echo 0 > "$T/n"
  cat > "$T/bin/kubectl" <<'STUB'
#!/usr/bin/env bash
n=$(cat "$STUB_N"); echo $((n+1)) > "$STUB_N"
if [ "$n" -lt 2 ]; then printf '0/'; else printf '1/1'; fi
STUB
  chmod +x "$T/bin/kubectl"
  bash "$S" wake cockroachdb >/dev/null
  run env -u STORE_PARK_NO_KUBECTL PATH="$T/bin:$PATH" STUB_N="$T/n" STORE_PARK_POLL=0 STORE_PARK_PROGRESS_EVERY=1 bash "$S" wait cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"waiting"*"git wants 1"*"desired=0"* ]]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "wake points at the sync that skips Argo's ~3 min poll" {
  run bash "$S" wake cassandra
  [[ "$output" == *"argocd app sync data-mesh"* ]]
  run bash "$S" wake superset-worker
  [[ "$output" == *"argocd app sync superset"* ]]
}

# --- DataHub: one command parks the store AND pauses its ingestion schedule (and wake restores it) ---------------------

@test "park pauses the store's DataHub schedule" {
  bash "$S" wake cockroachdb >/dev/null; : > "$DH_LOG"
  run bash "$S" park cockroachdb
  [ "$status" -eq 0 ]
  grep -qx "pause CockroachDB - Weyland" "$DH_LOG"
}

@test "wake restores the store's exact DataHub schedule" {
  run bash "$S" wake mongodb
  [ "$status" -eq 0 ]
  grep -qx "resume MongoDB - Weyland 45 3 \* \* \* America/New_York" "$DH_LOG"
  run bash "$S" wake cassandra
  grep -qx "resume Cassandra - Weyland 15 4 \* \* 0 America/New_York" "$DH_LOG"
}

@test "the superset worker has no DataHub ingestion, so no DataHub call" {
  run bash "$S" wake superset-worker
  [ "$status" -eq 0 ]
  [ ! -s "$DH_LOG" ]
}

@test "a DataHub failure is exit 2 and says the git edit is done but the schedule is not" {
  run env DH_RC=2 bash "$S" wake cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"schedule NOT changed"* ]]
  [ "$(replicas_of cockroachdb)" = 1 ]
}

@test "status shows each store's DataHub schedule" {
  run bash "$S" status
  [ "$status" -eq 0 ]
  [[ "$output" == *"cockroachdb"*"datahub=paused"* ]]
  [[ "$output" == *"superset-worker"*"datahub=-"* ]]
}

# --- up / down (B232): edit + commit ONLY the manifest + push + DataHub + wait, in one command ---------------------------
# These run REAL git (the manifest copies become a repo with a bare origin), not a git stub: the contract under test is
# git's — what `commit -- <path>` leaves staged, what a rejected push prints. kubectl is a stub reporting $KSTATE.

git_repo() {  # make $T a clone of a bare origin, everything committed and pushed, plus a kubectl stub
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
  git init -q --bare -b main "$T.origin"
  git -C "$T" init -q -b main
  git -C "$T" remote add origin "$T.origin"
  printf 'dh\ndh.log\nbin/\nn\n' > "$T/.gitignore"
  git -C "$T" add -A && git -C "$T" commit -q -m init && git -C "$T" push -q origin main
  mkdir -p "$T/bin"
  # kubectl: the Argo admin Secret read answers $KPW (unset = a default password); any other call answers $KSTATE
  printf '#!/usr/bin/env bash\ncase "$*" in *argocd-initial-admin-secret*) printf %%s "${KPW-s3cret-pw}" ;; *) printf %%s "${KSTATE:-1/1}" ;; esac\n' \
    > "$T/bin/kubectl"
  # argocd: `app list` is the session check ($ARGO_SESSION=1 = live); `app sync` logs its args and the token it got
  printf '#!/usr/bin/env bash\nif [ "$2" = list ]; then [ "${ARGO_SESSION:-0}" = 1 ] || { echo "invalid session: token is expired" >&2; exit 20; }; exit 0; fi\necho "$* token=${ARGOCD_AUTH_TOKEN:-none}" >> "$ARGO_LOG"; exit "${ARGO_SYNC_RC:-0}"\n' \
    > "$T/bin/argocd"
  # curl: the session API — logs its argv and its stdin separately, answers $CURL_BODY
  printf '#!/usr/bin/env bash\necho "$*" >> "$CURL_ARGV"; cat >> "$CURL_STDIN"; printf %%s "${CURL_BODY-{\\"token\\":\\"tok-123\\"}}"\n' \
    > "$T/bin/curl"
  chmod +x "$T/bin/kubectl" "$T/bin/argocd" "$T/bin/curl"
  export PATH="$T/bin:$PATH" STORE_PARK_POLL=0 ARGO_LOG="$T/argo.log" CURL_ARGV="$T/curl.argv" CURL_STDIN="$T/curl.stdin"
  : > "$ARGO_LOG"; : > "$CURL_ARGV"; : > "$CURL_STDIN"
  printf 'argo.log\ncurl.argv\ncurl.stdin\n' >> "$T/.git/info/exclude"
  unset STORE_PARK_NO_KUBECTL
}
commits() { git -C "$T" rev-list --count HEAD; }
pushed() { git -C "$T.origin" rev-list --count main; }

@test "up commits exactly the one manifest, pushes it, and reports Ready" {
  git_repo
  run bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [ "$(git -C "$T" show --name-only --format= HEAD)" = "data-mesh/cockroachdb.yaml" ]
  [ "$(git -C "$T" log -1 --format=%s)" = "store-park: up cockroachdb (replicas 1)" ]
  [ "$(git -C "$T" rev-parse HEAD)" = "$(git -C "$T.origin" rev-parse main)" ]   # it is on origin, not just local
  [ "$(replicas_of cockroachdb)" = 1 ]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "down commits replicas 0, pushes, pauses DataHub, and waits until parked" {
  git_repo
  KSTATE=1/1 bash "$S" up mongodb >/dev/null; : > "$DH_LOG"
  run env KSTATE=0/ bash "$S" down mongodb
  [ "$status" -eq 0 ]
  [ "$(git -C "$T" log -1 --format=%s)" = "store-park: down mongodb (replicas 0)" ]
  [ "$(pushed)" = 3 ]
  grep -qx "pause MongoDB - Weyland" "$DH_LOG"
  [[ "$output" == *"mongodb: parked (0/0)"* ]]
}

@test "up resumes the store's exact DataHub schedule" {
  git_repo
  run bash "$S" up cassandra
  [ "$status" -eq 0 ]
  grep -qx "resume Cassandra - Weyland 15 4 \* \* 0 America/New_York" "$DH_LOG"
}

@test "up leaves the owner's other uncommitted and staged work untouched and uncommitted" {
  git_repo
  echo "# owner edit" >> "$T/superset/superset-values.yaml"
  echo new > "$T/staged.txt"; git -C "$T" add staged.txt
  run bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [ "$(git -C "$T" show --name-only --format= HEAD)" = "data-mesh/cockroachdb.yaml" ]
  git -C "$T" diff --name-only | grep -qx "superset/superset-values.yaml"       # still modified, not committed
  git -C "$T" diff --cached --name-only | grep -qx "staged.txt"                 # still staged, not committed
}

@test "up all is ONE commit holding every manifest, and warns about the memory first" {
  git_repo
  run bash "$S" up all
  [ "$status" -eq 0 ]
  [ "$(commits)" = 2 ]
  [ "$(git -C "$T" show --name-only --format= HEAD | sort | tr '\n' ' ')" = "data-mesh/cassandra.yaml data-mesh/cockroachdb.yaml data-mesh/mongodb.yaml superset/superset-values.yaml " ]
  [[ "$output" == *"waking 4 stores at once"* ]]
}

@test "up refuses (exit 2, nothing committed) when the manifest already has uncommitted changes" {
  git_repo
  echo "# stray" >> "$T/data-mesh/cockroachdb.yaml"
  run bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"uncommitted changes"*"cockroachdb.yaml"* ]]
  [ "$(commits)" = 1 ]
  [ "$(replicas_of cockroachdb)" = 0 ]                                          # refused BEFORE editing
}

@test "up refuses (exit 2, nothing committed) when the branch is not main" {
  git_repo
  git -C "$T" checkout -q -b feature
  run bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"not main"*"feature"* ]]
  [ "$(commits)" = 1 ]
}

@test "up refuses (exit 2, nothing committed) when main is behind origin/main" {
  git_repo
  git clone -q "$T.origin" "$T.other"
  git -C "$T.other" commit -q --allow-empty -m elsewhere && git -C "$T.other" push -q origin main
  run bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"behind origin/main"* ]]
  [ "$(commits)" = 1 ]
  [ "$(replicas_of cockroachdb)" = 0 ]
}

@test "up refuses (exit 2) when main is AHEAD of origin/main — its push would publish the owner's commits" {
  git_repo
  git -C "$T" commit -q --allow-empty -m "owner's unpushed work"
  run bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"ahead of origin/main"* ]]
  [ "$(pushed)" = 1 ]
}

@test "up refuses (exit 2) when it cannot fetch origin, never assumes it is up to date" {
  git_repo
  git -C "$T" remote set-url origin "$T.nowhere"
  run bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"cannot fetch"* ]]
  [ "$(replicas_of cockroachdb)" = 0 ]
}

@test "a rejected push exits 2 with git's reason and says the commit is local only" {
  git_repo
  printf '#!/bin/sh\necho "denied by test hook" >&2\nexit 1\n' > "$T.origin/hooks/pre-receive"
  chmod +x "$T.origin/hooks/pre-receive"
  run bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"push failed"* && "$output" == *"denied by test hook"* ]]
  [[ "$output" == *"NOT pushed"* ]]
  [ "$(pushed)" = 1 ]
  [ ! -s "$DH_LOG" ]                                     # nothing after a failed push: no schedule change, no wait
}

@test "up on a store already awake in git commits and pushes nothing, then still waits" {
  git_repo
  bash "$S" up cockroachdb >/dev/null
  run bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"already awake"* ]]
  [ "$(commits)" = 2 ] && [ "$(pushed)" = 2 ]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "up exits 1 when the store is not Ready within the timeout, after the push" {
  git_repo
  run env KSTATE=1/ STORE_PARK_WAIT_TIMEOUT=0 bash "$S" up cockroachdb
  [ "$status" -eq 1 ]
  [[ "$output" == *"NOT there yet"* ]]
  [ "$(pushed)" = 2 ]                                    # the push happened; only Ready is missing
}

@test "up still waits, then exits 2, when the DataHub schedule could not be set" {
  git_repo
  run env DH_RC=2 bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [[ "$output" == *"schedule NOT changed"* ]]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
  [ "$(pushed)" = 2 ]
}

# --- up / down skip Argo's ~3 min poll: sync right after the push (best effort, never a gate) ----------------------------
# Owner, 2026-10-24: most of each live run was Argo's poll. With no live CLI session the script swaps the cluster's admin
# password for a short-lived token through the session API — password on curl's STDIN, token in the sync's ENVIRONMENT,
# neither on a command line nor in the output — and never touches the owner's saved CLI session.

@test "up syncs the store's Argo app right after the push, with the live CLI session" {
  git_repo
  run env ARGO_SESSION=1 bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  grep -q "^app sync data-mesh .*--async.* token=none$" "$ARGO_LOG"
  [ ! -s "$CURL_ARGV" ]                                  # a live session needs no token
  [[ "$output" == *"argo: sync of data-mesh requested (CLI session)"* ]]
}

@test "with no live session, up gets a token from the session API — password on stdin, token in the env, neither printed" {
  git_repo
  run bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  grep -q '"password": "s3cret-pw"' "$CURL_STDIN"        # the password went in on stdin
  ! grep -q "s3cret-pw" "$CURL_ARGV"                      # and never on curl's command line
  grep -q "/api/v1/session" "$CURL_ARGV"
  grep -q "^app sync data-mesh .*--plaintext.* token=tok-123$" "$ARGO_LOG"
  ! grep -q "tok-123" <(grep -v 'token=tok-123$' "$ARGO_LOG")   # the token is not an argument either
  [[ "$output" != *"s3cret-pw"* && "$output" != *"tok-123"* ]]
  [[ "$output" == *"argo: sync of data-mesh requested (token)"* ]]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "the Argo Secret cannot be read: one line, then Argo's own poll, and up still succeeds" {
  git_repo
  run env KPW= bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"argo: no CLI session, and cannot read Secret argocd/argocd-initial-admin-secret"*"Argo's own poll"* ]]
  [ ! -s "$ARGO_LOG" ]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "the session API refuses: one line naming it, then Argo's own poll, and up still succeeds" {
  git_repo
  run env CURL_BODY='{"error":"Invalid username or password","code":16}' bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"argo: no CLI session, and the session API gave no token"*"Argo's own poll"* ]]
  [ ! -s "$ARGO_LOG" ]
}

@test "a sync that does not return cleanly is one line, never a failure" {
  git_repo
  run env ARGO_SESSION=1 ARGO_SYNC_RC=20 bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"argo: sync of data-mesh did not return cleanly"*"Argo's own poll"* ]]
  [[ "$output" == *"cockroachdb: Ready (1/1)"* ]]
}

@test "no argocd CLI: one line, then Argo's own poll" {
  git_repo
  run env STORE_PARK_ARGOCD="$T/no-such-argocd" bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [[ "$output" == *"argo: no argocd CLI"*"Argo's own poll"* ]]
}

@test "up all syncs each Argo app once (data-mesh and superset)" {
  git_repo
  run env ARGO_SESSION=1 bash "$S" up all
  [ "$status" -eq 0 ]
  [ "$(grep -c '^app sync data-mesh ' "$ARGO_LOG")" = 1 ]
  [ "$(grep -c '^app sync superset ' "$ARGO_LOG")" = 1 ]
}

@test "nothing to push means nothing to sync" {
  git_repo
  ARGO_SESSION=1 bash "$S" up cockroachdb >/dev/null; : > "$ARGO_LOG"
  run env ARGO_SESSION=1 bash "$S" up cockroachdb
  [ "$status" -eq 0 ]
  [ ! -s "$ARGO_LOG" ]
}

@test "a rejected push syncs nothing" {
  git_repo
  printf '#!/bin/sh\nexit 1\n' > "$T.origin/hooks/pre-receive"; chmod +x "$T.origin/hooks/pre-receive"
  run env ARGO_SESSION=1 bash "$S" up cockroachdb
  [ "$status" -eq 2 ]
  [ ! -s "$ARGO_LOG" ]
}

@test "up with no store is refused with usage (exit 2)" {
  git_repo
  run bash "$S" up
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: store-park.sh up <store|all>"* ]]   # the up-specific usage, not the catch-all
}
