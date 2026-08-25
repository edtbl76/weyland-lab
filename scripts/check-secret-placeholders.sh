#!/usr/bin/env bash
# Placeholder guard for the SealedSecrets allow-list (B147).
#
# WHY THIS EXISTS: `weyland/port-creds` held the literal strings `YOUR_ID` / `YOUR_SECRET` for 63 days.
# Every signal was green the whole time — sealed ✅, committed ✅, Argo-applied ✅, `DATA 2` ✅, mounted by
# a running pod ✅ — and it authenticated to nothing, so the B62 AI-Dev Usage pipeline silently never ran
# a single successful ingest. `ai_session` sat at 37 entities, all of them hand-seeded 23 minutes BEFORE
# the credential was even created.
#
# Nothing in the estate could have caught that. DoD Pillar 6 asks whether secrets are RESTORABLE, and the
# honest answer was yes: a full restore would faithfully reproduce a 401. A placeholder and a real
# credential are byte-indistinguishable from outside — the only way to tell is to decode the value and
# LOOK at it, which is what this does.
#
# ⚠ DELIBERATELY NOT IN CI, and the reason is a real trade rather than an oversight. This needs to READ
# SECRETS, and the Woodpecker step pods run as `woodpecker:default`, which cannot (`kubectl auth can-i get
# secrets -n weyland` -> no). Wiring it in would mean granting CI cluster-wide secret read so it can run a
# lint — a permanent, broad privilege bought for a periodic check. Not worth it.
#
# Run it BY HAND at DoD time and after any secret change. The durable form is a CronJob with a dedicated
# SA scoped to the two namespaces that actually hold allow-listed secrets, alongside the pr-lifecycle
# watchdogs — filed as its own work rather than smuggled in here.
#
#   usage: scripts/check-secret-placeholders.sh [--list]
#          --list   print every allow-listed secret and its per-key verdict, exit 0
#
# INPUTS. By default it reads the allow-list out of `seal-secrets.sh` and pulls each Secret with kubectl.
# For testing (and offline runs) point these at fixtures instead:
#
#   SEAL_SCRIPT           the script holding the SECRETS=(…) array
#   SECRET_SNAPSHOT_JSON  {"<ns>/<name>": {"<key>": "<decoded value>"}} — skips kubectl entirely
#
# FAILS CLOSED. An unparseable allow-list, an unreadable Secret, or a secret that is in the allow-list but
# absent from the cluster is a loud error — never a quiet pass over zero items. "Checked nothing, found
# nothing" is the exact shape of bug this guard exists to catch, and it would be grimly funny to ship it
# inside the guard itself. (This repo has done that twice.)
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

SEAL_SCRIPT="${SEAL_SCRIPT:-$PLATFORM_DIR/scripts/seal-secrets.sh}"

# --- accepted, with the reason -------------------------------------------------------------------
#
# One row per tolerated value: <ns/name>|<key>|<why it is legitimately this way>
#
# Same posture as `check-pip-audit-ignores.sh`: an exception must state the CONDITION that makes it
# fine, so a reader can re-check it rather than trust it. Keep this SHORT — every entry here is a
# credential this guard has stopped looking at.
ACCEPTED=(
  "data-mesh/trino-metrics-auth|password|Trino's metrics endpoint accepts ANY username and IGNORES the password entirely (documented at k8s/data-mesh/trino.yaml:154), so an empty value is correct rather than missing. NOTE: verifying this on 2026-08-25 found that Trino exports NO metrics to Prometheus at all - zero trino_ series and no up series for a trino job - despite a 59-day-old ServiceMonitor. That is a real and separate defect (B148); it is NOT caused by this empty password."
)

is_accepted() { # is_accepted <ns/name> <key>
  local row e_entry e_key
  for row in "${ACCEPTED[@]}"; do
    IFS="|" read -r e_entry e_key _ <<<"$row"
    [ "$e_entry" = "$1" ] && [ "$e_key" = "$2" ] && return 0
  done
  return 1
}

# --- the decision -------------------------------------------------------------------------------
#
# is_placeholder <decoded-value> -> 0 when the value looks like a placeholder or is empty.
#
# THE HARD PART IS NOT FINDING PLACEHOLDERS, IT IS NOT FLAGGING REAL CONFIG. The first version used a
# bare `<[a-z-]+>` pattern — written for `<your-token-here>` — and immediately flagged
# `data-mesh/clickhouse-users`, whose value is an XML document beginning `<clickhouse>`. A guard that
# cries wolf on a legitimate secret gets muted, and a muted guard is worth nothing; that is the same
# argument this repo keeps making about permanently-lit alerts.
#
# The discriminator that works: a credential is a SHORT, SINGLE-LINE token. Config is long or
# multi-line. So anything multi-line, or longer than the longest plausible credential, is config and is
# never inspected for placeholder words.
is_placeholder() { # is_placeholder <value>
  local v="${1-}"
  # Trim surrounding whitespace/newlines.
  v="$(printf '%s' "$v" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

  # An empty secret value is its own bug — it starts a pod happily and fails only at runtime.
  [ -z "$v" ] && return 0

  # Multi-line => structured config (XML, PEM, YAML, a kubeconfig). Not a credential, never a placeholder.
  case "$v" in *$'\n'*) return 1 ;; esac

  # Longer than any plausible credential => config. 200 chars is generous: the longest real value in
  # this repo's allow-list is a 64-char client secret and a GitHub PAT at 93.
  [ "${#v}" -gt 200 ] && return 1

  # Now, and only now, the placeholder vocabulary. Anchored to the WHOLE value or to a standalone token
  # so a real credential that happens to contain "test" survives.
  printf '%s' "$v" | grep -qiE \
    '^(your[_-]?[a-z]*|change[_-]?me|replace[_-]?me|placeholder|todo|tbd|test|example|foo|bar|xxx+|secret|password|<[^>]*>)$' \
    && return 0
  # ...plus the same words as an embedded ALL-CAPS token, which is how YOUR_ID / YOUR_SECRET appear.
  printf '%s' "$v" | grep -qE \
    '(^|[^A-Za-z])(YOUR|CHANGEME|CHANGE_ME|REPLACEME|REPLACE_ME|PLACEHOLDER)([^A-Za-z]|$)' \
    && return 0
  return 1
}

# --- allow-list ---------------------------------------------------------------------------------
#
# Parsed OUT of seal-secrets.sh rather than duplicated here. Two copies of the list would drift, and the
# drift would be silent on both sides — a secret missing from this guard's copy would simply never be
# checked, which is indistinguishable from it being clean.
allow_list_entries() { # allow_list_entries <seal-script>
  local f="${1:?usage: allow_list_entries <seal-script>}"
  [ -r "$f" ] || { echo "FATAL: cannot read the seal script: $f" >&2; return 1; }
  local out
  out="$(python3 - "$f" <<'PY'
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'^SECRETS=\((.*?)^\)', src, re.S | re.M)
if not m:
    print("no SECRETS=( … ) array found", file=sys.stderr); raise SystemExit(2)
rows = []
for line in m.group(1).splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    rows.append(line.split()[0])
if not rows:
    print("the SECRETS array parsed to ZERO entries", file=sys.stderr); raise SystemExit(2)
print("\n".join(rows))
PY
)" || { echo "FATAL: could not parse the SECRETS allow-list from $f" >&2; return 1; }
  printf '%s\n' "$out"
}

# --- reading the live values ----------------------------------------------------------------------

# secret_keys <ns/name> -> `<key>\t<base64 of the decoded value>` per line.
#
# THE VALUE IS BASE64 ON PURPOSE. Emitting it raw breaks on any MULTI-LINE secret: the `while read` loop
# in main() treats every line as a new key/value row, so `clickhouse-users` arrived as three bogus rows
# and the fragment `<clickhouse>` matched the angle-bracket placeholder pattern. The multi-line guard in
# is_placeholder never even ran, because it never saw a multi-line value. Found by the bats case written
# for exactly that secret.
secret_keys() { # secret_keys <ns/name>
  local entry="$1" ns name
  ns="${entry%%/*}"; name="${entry#*/}"
  if [ -n "${SECRET_SNAPSHOT_JSON:-}" ]; then
    python3 - "$SECRET_SNAPSHOT_JSON" "$entry" <<'PY'
import base64, json, sys
snap = json.load(open(sys.argv[1], encoding="utf-8"))
e = sys.argv[2]
if e not in snap:
    print(f"{e} is in the allow-list but ABSENT from the cluster", file=sys.stderr)
    raise SystemExit(1)
for k, v in snap[e].items():
    print(k + "\t" + base64.b64encode(v.encode()).decode())
PY
    return $?
  fi
  local body
  body="$(kubectl -n "$ns" get secret "$name" -o json 2>/dev/null)" || {
    echo "$entry is in the allow-list but ABSENT from the cluster (or unreadable)" >&2; return 1; }
  printf '%s' "$body" | python3 -c "
import sys, json, base64
d = json.load(sys.stdin)
for k, v in (d.get('data') or {}).items():
    try: raw = base64.b64decode(v).decode('utf-8', 'replace')
    except Exception: raw = ''
    print(k + '\t' + base64.b64encode(raw.encode()).decode())
"
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1
  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 1; }

  local entries; entries="$(allow_list_entries "$SEAL_SCRIPT")" || exit 1
  local total=0 bad=0 unreadable=0

  local entry key b64 val
  while IFS= read -r entry; do
    [ -n "$entry" ] || continue
    total=$((total + 1))
    local rows
    if ! rows="$(secret_keys "$entry" 2>&1)"; then
      echo "  ❌ $entry — $rows" >&2
      unreadable=$((unreadable + 1)); continue
    fi
    while IFS="$(printf '\t')" read -r key b64; do
      [ -n "${key:-}" ] || continue
      val="$(printf '%s' "$b64" | python3 -c 'import sys,base64;sys.stdout.write(base64.b64decode(sys.stdin.read()).decode("utf-8","replace"))')"
      if is_placeholder "$val"; then
        if is_accepted "$entry" "$key"; then
          [ "$list_only" -eq 1 ] && printf '  ACCEPTED %-38s %-28s (documented exception)\n' "$entry" "$key"
          continue
        fi
        echo "  ❌ $entry key=$key looks like a PLACEHOLDER: '$(printf '%s' "$val" | head -c 24)'" >&2
        bad=$((bad + 1))
      elif [ "$list_only" -eq 1 ]; then
        printf '  ok  %-42s %-28s (%d chars)\n' "$entry" "$key" "${#val}"
      fi
    done <<<"$rows"
  done <<<"$entries"

  [ "$list_only" -eq 1 ] && { echo "listed $total secret(s)."; return 0; }

  if [ "$bad" -ne 0 ] || [ "$unreadable" -ne 0 ]; then
    echo >&2
    echo "❌ $bad placeholder value(s) and $unreadable unreadable secret(s) across $total allow-listed secrets." >&2
    echo "   A sealed placeholder is restorable, mounted, and authenticates to NOTHING — that is how" >&2
    echo "   weyland/port-creds silently killed the B62 pipeline for 63 days (B147)." >&2
    exit 1
  fi
  echo "OK — $total allow-listed secret(s), no placeholder or empty values."
}

if [ -z "${SECRET_PLACEHOLDER_LIB:-}" ]; then
  main "$@"
fi
