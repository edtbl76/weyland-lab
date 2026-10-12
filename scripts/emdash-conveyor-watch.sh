#!/usr/bin/env bash
# emdash-conveyor-watch.sh — the freshness signal for the software-factory conveyor (B179, 2026-10-12). Run daily at
# 06:00 NY by the user timer nodes/rogueone/systemd/emdash-conveyor-watch.{service,timer}.
#
# The Emdash automation `agent-ready-nightly` runs at 04:00 ONLY while the Emdash app is running: its scheduler lives in
# the app (no daemon, unit, timer or cron), and a missed slot waits for the next launch. So the failure to catch is
# silence. This reads Emdash's own run records, READ-ONLY (`emdash4-automations.db`, opened mode=ro), and reports to an
# Uptime-Kuma push monitor (KUMA_CONVEYOR_PUSH_URL in scripts/.env), which also alerts if this watch stops running.
# EXIT: 0 a run started within the window · 1 no run in the window, or the automation is disabled · 2 could not check
# (no database, unreadable, or the automation missing). Fail closed: an unread store is never "fresh".
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${EMDASH_WATCH_NO_ENV:-}" ] && [ -f "$REPO_ROOT/scripts/.env" ]; then
  set -a; . "$REPO_ROOT/scripts/.env"; set +a
fi
DB="${EMDASH_AUTOMATIONS_DB:-$HOME/.config/emdash/emdash4-automations.db}"
NAME="${EMDASH_AUTOMATION_NAME:-agent-ready-nightly}"
MAX_HOURS="${EMDASH_WATCH_MAX_HOURS:-26}"          # a daily run, plus slack for the 06:00 check after a 04:00 slot

out="$(python3 - "$DB" "$NAME" "$MAX_HOURS" "${EMDASH_WATCH_NOW:-}" <<'PY'
import json, os, sqlite3, sys, time
db, name, max_hours, now = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
now = int(now) if now else int(time.time() * 1000)
if not os.path.isfile(db):
    print(f"2|could not read the Emdash store: {db} not found"); sys.exit()
try:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    deps = [(a, e, json.loads(p)) for a, e, p in c.execute(
        "select automation_id, enabled, payload from automation_deployments")]
    dep = next(((a, e, p) for a, e, p in deps if p.get("name") == name), None)
    if dep is None:
        print(f"2|automation {name} not found in {db}"); sys.exit()
    aid, enabled, _ = dep
    started = [json.loads(p).get("startedAt") for (p,) in c.execute(
        "select payload from automation_runs where automation_id=?", (aid,))]
except (sqlite3.Error, ValueError) as exc:
    print(f"2|could not read the Emdash store: {type(exc).__name__}: {exc}"); sys.exit()
last = max((s for s in started if s), default=None)
age = None if last is None else (now - last) / 3_600_000
if not enabled:
    print(f"1|automation {name} is disabled in Emdash"); sys.exit()
if age is None or age > max_hours:
    seen = "never" if age is None else f"{age:.1f} h ago"
    print(f"1|no run started in the last {max_hours:g} h (last: {seen}) — is Emdash running on rogueone?"); sys.exit()
print(f"0|last run started {age:.1f} h ago")
PY
)"
verdict="${out%%|*}"; msg="${out#*|}"
case "$verdict" in 0|1|2) ;; *) verdict=2; msg="the check itself failed: ${out:-no output}" ;; esac
echo "emdash-conveyor-watch: exit $verdict — $msg"

if [ -z "${KUMA_CONVEYOR_PUSH_URL:-}" ]; then
  echo "KUMA_CONVEYOR_PUSH_URL unset — verdict NOT reported to Kuma (runbooks/software-factory.md § Freshness)" >&2
else
  state=up; [ "$verdict" -ne 0 ] && state=down
  q="$(python3 -c 'import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))' "$msg")"
  curl -fsS -m 15 "${KUMA_CONVEYOR_PUSH_URL}?status=${state}&msg=${q}" >/dev/null 2>&1 \
    || echo "could not reach Kuma — the push monitor will alert on the missed heartbeat" >&2
fi
exit "$verdict"
