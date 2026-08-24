#!/usr/bin/env bash
# pip-audit accept-list expiry guard (B142).
#
# WHY THIS EXISTS: `pip-audit --ignore-vuln <ID>` is scoped to a VULNERABILITY ID and nothing else, so
# unlike the other two accept-lists in this repo it CANNOT expire on its own:
#
#   .trivyignore        entries are reasoned and dated, re-read by a human
#   osv-scanner.toml    PackageOverrides are scoped `version = "0.5.5"` -> the exception STOPS APPLYING
#                       the moment the package moves. That self-expiry is what made it safe, and on
#                       2026-08-24 (B136) it is exactly why the sqlparse block could be deleted with
#                       confidence rather than argued about.
#
# A pip-audit ignore has no such property. It suppresses the ID forever, including long after the
# reason evaporates -- which is the "dead exception outliving its reason" failure this repo hit three
# separate times on 2026-08-24 alone. So every ignore declared here must state the CONDITION that
# justifies it, and this guard asserts that condition still holds. When upstream fixes the blocker,
# CI goes RED and names the exception to delete. The accept-list cannot rot silently.
#
#   usage: scripts/check-pip-audit-ignores.sh [--list]
#          --list   print the accept-list and each condition's current state, exit 0
#
# FAILS CLOSED. An unreadable requirements file, an unresolvable package, or a condition it cannot
# evaluate is a loud error, never a skip -- verifying nothing is not verifying successfully.
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

DAGSTER_REQS="$PLATFORM_DIR/services/weyland-dagster/requirements.txt"

# --- the accept-list -------------------------------------------------------------------
#
# One row per ignored vulnerability:
#   <vuln-id>|<package>|<why it cannot be fixed>|<the condition that must still hold>
#
# KEEP THIS IN SYNC with the --ignore-vuln flags in
# nodes/mother/lab/weyland-platform/services/scan-suite/scan.py :: pip_audit().
# The sync itself is asserted below, so the two cannot drift.
ACCEPTED=(
  "PYSEC-2026-3447|setuptools|fix is 83.0.0, but acryl-datahub pins setuptools<82.0.0 in EVERY release including the latest (1.7.0.5, checked 2026-08-24) -- there is no version of the blocker that unblocks it|acryl-datahub still caps setuptools below 83"
)

# Does acryl-datahub still cap setuptools below the fixed version? Asked of PyPI, not of a comment.
# Returns 0 while the cap holds (exception still justified), 1 once it is lifted (delete the ignore).
acryl_still_caps_setuptools() {
  local ver
  ver="$(grep -oE '^acryl-datahub==[0-9.]+' "$DAGSTER_REQS" 2>/dev/null | head -1 | sed 's/.*==//')"
  [ -n "$ver" ] || { echo "❌ cannot read the acryl-datahub pin from $DAGSTER_REQS" >&2; return 2; }
  python3 - "$ver" <<'PY'
import json, sys, urllib.request
ver = sys.argv[1]
try:
    d = json.load(urllib.request.urlopen(
        f"https://pypi.org/pypi/acryl-datahub/{ver}/json", timeout=30))
except Exception as e:
    print(f"cannot reach PyPI for acryl-datahub {ver}: {e}", file=sys.stderr)
    raise SystemExit(2)          # cannot evaluate -> fail closed, never assume
reqs = d["info"].get("requires_dist") or []
caps = [r for r in reqs if r.lower().startswith("setuptools") and "<82" in r]
print(f"acryl-datahub {ver} setuptools pins: {caps or 'NONE'}")
raise SystemExit(0 if caps else 1)
PY
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1

  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 1; }
  [ -f "$DAGSTER_REQS" ] || { echo "❌ requirements missing: $DAGSTER_REQS" >&2; exit 1; }

  local scan_py="$PLATFORM_DIR/services/scan-suite/scan.py"
  [ -f "$scan_py" ] || { echo "❌ scan.py missing: $scan_py" >&2; exit 1; }

  local fail=0 row id pkg why cond
  printf '%-22s %-12s %s\n' "VULN" "PACKAGE" "CONDITION"
  for row in "${ACCEPTED[@]}"; do
    IFS='|' read -r id pkg why cond <<<"$row"

    # (1) the ignore must actually be wired into the scanner -- an accept-list nobody passes to
    #     pip-audit is a comment, and the finding would still count.
    #
    #     PARSE THE `IGNORED_VULNS` LITERAL, do not grep the file. The first version of this check
    #     was `grep -qF "$id" scan.py`, which passed even with `IGNORED_VULNS = []` because the ID
    #     also appears in the explanatory COMMENT above it. It was verifying the documentation, not
    #     the code -- found by mutation-testing this guard rather than by reading it.
    if ! python3 - "$scan_py" "$id" <<'PY'
import ast, re, sys
src, vid = open(sys.argv[1], encoding="utf-8").read(), sys.argv[2]
m = re.search(r"IGNORED_VULNS\s*=\s*(\[[^\]]*\])", src)
if not m:
    print("no IGNORED_VULNS literal found in scan.py", file=sys.stderr); raise SystemExit(2)
try:
    ids = ast.literal_eval(m.group(1))
except Exception as e:
    print(f"IGNORED_VULNS is not a literal list: {e}", file=sys.stderr); raise SystemExit(2)
raise SystemExit(0 if vid in ids else 1)
PY
    then
      echo "  ❌ ${id} is accepted here but is NOT in scan.py's IGNORED_VULNS list" >&2; fail=1
    fi

    # (2) the condition that justifies it must still hold.
    local state rc
    set +e; state="$(acryl_still_caps_setuptools 2>&1)"; rc=$?; set -e
    case "$rc" in
      0) printf '%-22s %-12s %s\n' "$id" "$pkg" "still blocked: $(printf '%s' "$state" | tail -1)" ;;
      1) printf '%-22s %-12s %s\n' "$id" "$pkg" "NO LONGER BLOCKED"
         echo "  ❌ ${id}: ${cond} is NO LONGER TRUE. The fix is reachable -- bump ${pkg}, then DELETE this" >&2
         echo "     exception from scripts/check-pip-audit-ignores.sh AND scan.py's IGNORED_VULNS." >&2
         echo "     It was accepted because: ${why}" >&2
         fail=1 ;;
      *) echo "  ❌ ${id}: cannot evaluate the condition (${state}) -- refusing to report OK" >&2; fail=1 ;;
    esac
  done

  [ "$list_only" -eq 1 ] && return 0

  if [ "$fail" -ne 0 ]; then
    echo >&2
    echo "❌ the pip-audit accept-list is stale or unwired (${#ACCEPTED[@]} entry/entries checked)." >&2
    exit 1
  fi
  echo "OK -- ${#ACCEPTED[@]} pip-audit exception(s), each still justified and wired into scan.py."
}

if [ -z "${PIP_AUDIT_IGNORES_LIB:-}" ]; then
  main "$@"
fi
