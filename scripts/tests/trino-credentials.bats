#!/usr/bin/env bats
# scripts/trino-credentials.sh (B233, 2026-10-23) — Trino's password front door. One password per caller identity lives
# in scripts/.env; `build` turns them into Trino's bcrypt password file plus the mkcert TLS cert, `apply` creates the
# Secrets from files (a value never sits in a command line), `seal` writes the SealedSecrets. The external tools are
# seams (HTPASSWD, MKCERT, KUBECTL, KUBESEAL); their real output shapes were observed first: `htpasswd -niBC 10 u`
# (password on stdin) prints `u:$2y$10$…` then a blank line, and Trino 468's file authenticator accepted exactly that (throwaway, 2026-10-23).

setup() {
  S="$BATS_TEST_DIRNAME/../trino-credentials.sh"
  export ENV_FILE="$BATS_TEST_TMPDIR/env"
  printf 'UNRELATED=keep-me\n' > "$ENV_FILE"
  OUT="$BATS_TEST_TMPDIR/out"
  CALLS="$BATS_TEST_TMPDIR/calls"
  : > "$CALLS"
  export CALLS
  export HTPASSWD="$BATS_TEST_TMPDIR/htpasswd"
  cat > "$HTPASSWD" <<'EOF'
#!/usr/bin/env bash
# real shape: htpasswd -niBC 10 user (password on stdin) -> "user:$2y$10$<53 chars>" + a blank line
read -r pw
[ -n "$pw" ] || { echo "no password on stdin" >&2; exit 1; }
printf '%s:$2y$10$%s\n\n' "$3" "fakehashfakehashfakehashfakehashfakehashfakehashfakeh"
EOF
  export MKCERT="$BATS_TEST_TMPDIR/mkcert"
  cat > "$MKCERT" <<'EOF'
#!/usr/bin/env bash
echo "mkcert $*" >> "$CALLS"
while [ $# -gt 0 ]; do
  case "$1" in
    -cert-file) printf -- '-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n' > "$2"; shift 2 ;;
    -key-file) printf -- '-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n' > "$2"; shift 2 ;;
    *) shift ;;
  esac
done
EOF
  export KUBECTL="$BATS_TEST_TMPDIR/kubectl"
  cat > "$KUBECTL" <<'EOF'
#!/usr/bin/env bash
echo "kubectl $*" >> "$CALLS"
case "$*" in
  "apply -f -") cat > /dev/null ;;   # the real apply reads the piped manifest
  *"create secret"*) echo "kind: Secret" ;;
  *"jsonpath"*TRINO_SHARED_SECRET*) printf '%s' "${STORED_OVERRIDE-$(printf 'A%.0s' $(seq 88))}" ;;
  *"jsonpath"*) printf '%s' "${STORED_OVERRIDE-$(printf 'A%.0s' $(seq 64))}" ;;
esac
EOF
  export KUBESEAL="$BATS_TEST_TMPDIR/kubeseal"
  printf '#!/usr/bin/env bash\necho "kind: SealedSecret"\n' > "$KUBESEAL"
  chmod +x "$HTPASSWD" "$MKCERT" "$KUBECTL" "$KUBESEAL"
  export SEALED_DIR="$BATS_TEST_TMPDIR/sealed"
  mkdir -p "$SEALED_DIR"
}

@test "generate fills every identity and the shared secret, keeps other lines, prints no value" {
  run bash "$S" generate
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  for k in DBT CUBE DATAHUB DATAHUB_COVERAGE MCP PROMETHEUS NOTEBOOK ANALYST PERF LIGHTDASH SUPERSET EMANGINI RANGER; do
    grep -qE "^TRINO_PW_${k}=[0-9a-f]{48}$" "$ENV_FILE" || { echo "missing TRINO_PW_$k"; cat "$ENV_FILE"; return 1; }
  done
  grep -qE '^TRINO_SHARED_SECRET=[0-9a-f]{64}$' "$ENV_FILE"
  grep -q '^UNRELATED=keep-me$' "$ENV_FILE"
  while IFS='=' read -r _ v; do
    [[ "$output" != *"$v"* ]] || { echo "a value was printed"; return 1; }
  done < <(grep '^TRINO_' "$ENV_FILE")
}

@test "generate is idempotent: an existing value is never replaced" {
  bash "$S" generate
  before="$(grep '^TRINO_' "$ENV_FILE")"
  run bash "$S" generate
  [ "$status" -eq 0 ]
  [ "$(grep '^TRINO_' "$ENV_FILE")" = "$before" ]
  [[ "$output" == *"added 0"* ]] || { echo "$output"; return 1; }
}

@test "generate --rotate replaces exactly one identity" {
  bash "$S" generate
  others="$(grep '^TRINO_' "$ENV_FILE" | grep -v '^TRINO_PW_CUBE=')"
  old="$(grep '^TRINO_PW_CUBE=' "$ENV_FILE")"
  run bash "$S" generate --rotate cube
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(grep '^TRINO_' "$ENV_FILE" | grep -v '^TRINO_PW_CUBE=')" = "$others" ]
  new="$(grep '^TRINO_PW_CUBE=' "$ENV_FILE")"
  [ "$new" != "$old" ]
  [ "$(grep -c '^TRINO_PW_CUBE=' "$ENV_FILE")" -eq 1 ]
}

@test "generate --rotate refuses an unknown identity" {
  bash "$S" generate
  run bash "$S" generate --rotate nobody
  [ "$status" -ne 0 ]
  [[ "$output" == *"unknown identity: nobody"* ]] || { echo "$output"; return 1; }
}

@test "build writes one bcrypt line per identity and the cert with every name Trino is reached by" {
  bash "$S" generate
  run bash "$S" build "$OUT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(grep -c . "$OUT/password.db")" -eq 13 ]
  grep -qE '^dbt:\$2y\$10\$' "$OUT/password.db"
  grep -qE '^datahub-coverage:\$2y\$10\$' "$OUT/password.db"
  if grep -q '^$' "$OUT/password.db"; then echo "blank line in password.db"; return 1; fi
  grep -q 'BEGIN PRIVATE KEY' "$OUT/tls.pem"
  grep -q 'BEGIN CERTIFICATE' "$OUT/tls.pem"
  for n in trino.data-mesh.svc.cluster.local trino.data-mesh.svc trino.data-mesh trino 192.168.1.243; do
    grep -qE "^mkcert .* $n( |\$)" "$CALLS" || { echo "cert lacks $n"; cat "$CALLS"; return 1; }
  done
  [ "$(stat -c %a "$OUT")" = 700 ]
}

@test "build fails closed on a missing password, naming it" {
  bash "$S" generate
  sed -i '/^TRINO_PW_MCP=/d' "$ENV_FILE"
  run bash "$S" build "$OUT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"TRINO_PW_MCP is not set"* ]] || { echo "$output"; return 1; }
  [ ! -s "$OUT/password.db" ]
}

@test "apply creates Trino's secret and one per in-cluster caller, from files" {
  bash "$S" generate
  bash "$S" build "$OUT"
  run bash "$S" apply "$OUT"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  grep -q 'kubectl -n data-mesh create secret generic trino-auth --from-file=password.db=.* --from-file=tls.pem=.* --from-file=TRINO_SHARED_SECRET=' "$CALLS"
  # datahub-coverage's CronJob runs in weyland (its manifest lives under k8s/monitoring/ — read the namespace, not the dir)
  for s in weyland/trino-dbt data-mesh/trino-cube data-mesh/trino-datahub weyland/trino-datahub-coverage \
           weyland/trino-mcp data-mesh/trino-metrics-auth jupyterhub/trino-notebook jupyterhub/trino-analyst \
           data-mesh/trino-perf; do
    grep -q "kubectl -n ${s%%/*} create secret generic ${s#*/} --from-file=username=.* --from-file=password=" "$CALLS" \
      || { echo "no create for $s"; cat "$CALLS"; return 1; }
  done
  if grep -q 'from-literal' "$CALLS"; then echo "a value went on a command line"; return 1; fi
  if grep -qE 'trino-(lightdash|superset|emangini|ranger)' "$CALLS"; then echo "a UI-only identity got a Secret"; return 1; fi
}

@test "apply leaves no plaintext behind in the work dir except what build made" {
  bash "$S" generate
  bash "$S" build "$OUT"
  bash "$S" apply "$OUT"
  [ "$(ls "$OUT" | sort | tr '\n' ' ')" = "password.db tls.pem " ]
}

@test "apply fails closed when a stored password is not the expected length" {
  bash "$S" generate
  bash "$S" build "$OUT"
  STORED_OVERRIDE='' run bash "$S" apply "$OUT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"stored value has the wrong length"* ]] || { echo "$output"; return 1; }
}

@test "seal writes one SealedSecret per secret, named ns__name.yaml" {
  run bash "$S" seal
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  for f in data-mesh__trino-auth weyland__trino-dbt data-mesh__trino-cube data-mesh__trino-datahub \
           weyland__trino-datahub-coverage weyland__trino-mcp data-mesh__trino-metrics-auth \
           jupyterhub__trino-notebook jupyterhub__trino-analyst data-mesh__trino-perf; do
    grep -q 'kind: SealedSecret' "$SEALED_DIR/$f.yaml" || { echo "no $f"; ls "$SEALED_DIR"; return 1; }
  done
  [ "$(ls "$SEALED_DIR" | wc -l)" -eq 10 ]
}

@test "an unknown subcommand is a usage error, not a silent no-op" {
  run bash "$S" frobnicate
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage:"* ]]
}
