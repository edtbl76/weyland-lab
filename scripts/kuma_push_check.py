#!/usr/bin/env python3
"""kuma_push_check.py — every Uptime-Kuma push monitor's heartbeat interval matches the runbook (2026-10-13).

Kuma's default heartbeat interval is 60 s. A push monitor fed by a daily job then goes red a minute after every good push,
and nobody can tell that from a real failure. It happened three times (machine-inventory-drift and agent-memory, found
2026-10-03; emdash-conveyor, 2026-10-13, where 90000 went into the RETRY interval). The expected intervals live in ONE
place, the push-monitor table in docs/runbooks/uptime-kuma.md. Kuma's are read from its SQLite store, read-only, through
mother (`kubectl exec … sqlite3 -readonly`) — Kuma has no config in git and its API is socket.io behind a login.

Findings: an interval that differs from the runbook, a documented monitor missing or paused in Kuma, and a push monitor
with no runbook row. Run nightly inside machine-inv-drift.sh (its Kuma signal goes down on a finding).

  usage: kuma_push_check.py [--runbook docs/runbooks/uptime-kuma.md]
  exit:  0 every push monitor matches · 1 findings (named) · 2 could not check (Kuma unreadable, no push monitors,
         no table in the runbook) — never read as clean
"""
import argparse
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNBOOK = os.path.join(REPO_ROOT, "docs", "runbooks", "uptime-kuma.md")
SECTION = "## Push monitors"
ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|\s*\*\*(\d+)\s*s\*\*")
QUERY = "select id,name,active,interval,retry_interval,maxretries from monitor where type='push';"
# Read-only: sqlite3 -readonly inside the Kuma pod; kubectl runs on mother (feedback: kubectl-on-mother).
READ_CMD = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "emangini@mother",
            "KUBECONFIG=$HOME/.kube/config kubectl -n weyland exec deploy/uptime-kuma -- "
            f"sqlite3 -readonly /app/data/kuma.db \"{QUERY}\""]


class CannotRead(Exception):
    pass


def expected_intervals(runbook_text: str) -> dict:
    """{monitor: heartbeat seconds} from the table under '## Push monitors' (the next '## ' ends it)."""
    out, inside = {}, False
    for line in runbook_text.splitlines():
        if line.startswith("## "):
            inside = line.startswith(SECTION)
            continue
        m = ROW_RE.match(line) if inside else None
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def read_kuma() -> str:
    try:
        r = subprocess.run(READ_CMD, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CannotRead(f"reading Kuma via mother failed: {exc}") from exc
    if r.returncode != 0:
        raise CannotRead(f"reading Kuma via mother exited {r.returncode}: {r.stderr.strip()[-300:]}")
    return r.stdout


def parse_kuma(text: str) -> dict:
    rows = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) != 6 or not parts[3].isdigit():
            print(f"kuma_push_check: unexpected row from Kuma: {line[:120]!r}", file=sys.stderr)
            sys.exit(2)
        rows[parts[1]] = {"active": parts[2] == "1", "interval": int(parts[3])}
    return rows


def compare(expected: dict, actual: dict) -> list:
    findings = []
    for name, want in sorted(expected.items()):
        got = actual.get(name)
        if got is None:
            findings.append(f"{name}: in the runbook but not a push monitor in Kuma")
            continue
        if not got["active"]:
            findings.append(f"{name}: paused in Kuma")
        if got["interval"] != want:
            findings.append(f"{name}: heartbeat interval {got['interval']} s, runbook says {want} s "
                            "(Kuma → Edit → Heartbeat Interval, not Retry)")
    for name in sorted(set(actual) - set(expected)):
        findings.append(f"{name}: push monitor with no row in docs/runbooks/uptime-kuma.md")
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runbook", default=RUNBOOK)
    args = ap.parse_args(argv)
    with open(args.runbook, encoding="utf-8") as f:
        expected = expected_intervals(f.read())
    if not expected:
        print(f"kuma_push_check: no push-monitor table under '{SECTION}' in {args.runbook}", file=sys.stderr)
        return 2
    try:
        actual = parse_kuma(read_kuma())
    except CannotRead as exc:
        print(f"kuma_push_check: {exc}", file=sys.stderr)
        return 2
    if not actual:
        print("kuma_push_check: Kuma returned no push monitors — nothing checked, which is not clean", file=sys.stderr)
        return 2
    findings = compare(expected, actual)
    for f in findings:
        print(f"  ❌ {f}")
    if findings:
        print(f"kuma push monitors: {len(findings)} finding(s)")
        return 1
    print(f"OK — {len(actual)} push monitor(s) match docs/runbooks/uptime-kuma.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
