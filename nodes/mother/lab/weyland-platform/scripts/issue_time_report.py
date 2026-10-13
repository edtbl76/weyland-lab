#!/usr/bin/env python3
"""
B185 lane 1 — time per Linear issue: agent session time, plus lead and cycle time.

Joins the ai_session_feeder's per-session summaries (each carries `issues{}`: active minutes, tokens and API-equivalent
$ per issue, attributed by what the prompts named) with a B194 Linear snapshot (`issues.json.gz`). Backlog numbers
(B179) map to their Linear issue by the title prefix ("B179 — …"); EMA ids are used as they are.

  lead_days  = completedAt − createdAt
  cycle_days = completedAt − min(startedAt, first agent activity)   (most issues never record startedAt; activity
               that began after completion is rework and never starts the cycle — no known start → unknown)

Coverage limit: Claude Code prunes old transcripts, so `first agent activity` is the first one still on disk (or in
the MinIO mirror the feeder ships to); an issue worked before the oldest retained log has too late a start.

Only issue ids and numbers are read and printed — never prompt text. Pure stdlib.

  usage: issue_time_report.py --sessions <dir of session JSONs> --issues <issues.json[.gz]> [--json]
  exit:  0 report printed · 2 an input is absent, unreadable or carries nothing to report (fail closed)
"""
import argparse
import datetime as dt
import glob
import gzip
import json
import os
import re
import sys
from collections import defaultdict

B_TITLE_RE = re.compile(r"(B\d+(?:\.\d+)?)\b")


class InputError(Exception):
    pass


def _ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def load_sessions(path):
    """{issue id: [bucket, …]} from every session JSON that carries attribution; InputError when none does."""
    files = sorted(glob.glob(os.path.join(path, "*.json")))
    if not files:
        raise InputError(f"no session summaries in {path}")
    per_issue = defaultdict(list)
    attributed = 0
    for p in files:
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError) as e:
            raise InputError(f"cannot read session summary {p}: {e}") from e
        if not isinstance(s, dict) or "issues" not in s:
            continue
        attributed += 1
        for issue, bucket in s["issues"].items():
            per_issue[issue].append(bucket)
    if not attributed:
        raise InputError(f"no session in {path} carries per-issue attribution (run the B185 feeder first)")
    return per_issue


def load_issues(path):
    """The snapshot's issue list (gzip or plain JSON); InputError when it cannot be read or holds no issues."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        issues = json.loads(raw)
    except (OSError, ValueError) as e:              # EOFError/BadGzipFile/JSONDecodeError are all ValueError or OSError
        raise InputError(f"cannot read Linear snapshot {path}: {e}") from e
    if not isinstance(issues, list) or not issues:
        raise InputError(f"Linear snapshot {path} holds no issues")
    return issues


def _backlog_map(issues):
    """B number → its issue. Two issues with one number: the unarchived one wins; still two → unmapped (never guess)."""
    by_b = defaultdict(list)
    for i in issues:
        m = B_TITLE_RE.match(i.get("title") or "")
        if m:
            by_b[m.group(1)].append(i)
    out = {}
    for b, cands in by_b.items():
        live = [i for i in cands if not i.get("archivedAt")]
        pick = live if live else cands
        if len(pick) == 1:
            out[b] = pick[0]
    return out


def _days(start, end):
    return round((end - start).total_seconds() / 86400, 1) if start and end else None


def _earliest(a, b):
    return b if a is None or (b and _ts(b) < _ts(a)) else a


def _accumulate(row, buckets):
    for b in buckets:
        row["minutes"] += b.get("active_minutes", 0.0)
        row["output_tokens"] += b.get("output_tokens", 0)
        row["api_equiv_usd"] += b.get("api_equiv_value_usd", 0.0)
        row["sessions"] += 1
        row["first_agent_at"] = _earliest(row["first_agent_at"], b.get("first_at"))


def _finish(row):
    """Lead and cycle time from the Linear record; the agent minutes become hours."""
    lin = row.pop("_linear") or {}
    if row["backlog"] is None:                      # an EMA id seen directly: name its backlog number when it has one
        m = B_TITLE_RE.match(lin.get("title") or "")
        row["backlog"] = m.group(1) if m else None
    completed = _ts(lin.get("completedAt"))
    # agent activity that began after completion is later rework (a closed item named again), never the cycle's start
    starts = [t for t in (_ts(lin.get("startedAt")), _ts(row["first_agent_at"]))
              if t and (completed is None or t <= completed)]
    row["lead_days"] = _days(_ts(lin.get("createdAt")), completed)
    row["cycle_days"] = _days(min(starts), completed) if starts else None
    row["agent_hours"] = round(row.pop("minutes") / 60, 1)
    row["api_equiv_usd"] = round(row["api_equiv_usd"], 2)
    return row


def build(per_issue, issues):
    by_ident = {i["identifier"]: i for i in issues}
    by_b = _backlog_map(issues)
    rows = {}
    for key, buckets in per_issue.items():
        issue = by_ident.get(key) or by_b.get(key)
        rid = issue["identifier"] if issue else key
        row = rows.setdefault(rid, {"issue": rid, "backlog": None, "unmapped": issue is None,
                                    "minutes": 0.0, "output_tokens": 0, "api_equiv_usd": 0.0, "sessions": 0,
                                    "first_agent_at": None, "_linear": issue})
        if key.startswith("B"):
            row["backlog"] = key
        _accumulate(row, buckets)
    return sorted((_finish(r) for r in rows.values()), key=lambda x: (-x["agent_hours"], x["issue"]))


def _fmt(v):
    return "-" if v is None else str(v)


def _table(rows):
    lines = [f"{'issue':10s} {'backlog':8s} {'agent_h':>8s} {'sessions':>8s} "
             f"{'lead_d':>7s} {'cycle_d':>7s} {'out_tok':>11s}"]
    for x in rows:
        flag = "  (unmapped)" if x["unmapped"] else ""
        lines.append(f"{x['issue']:10s} {_fmt(x['backlog']):8s} {x['agent_hours']:>8.1f} {x['sessions']:>8d} "
                     f"{_fmt(x['lead_days']):>7s} {_fmt(x['cycle_days']):>7s} {x['output_tokens']:>11,}{flag}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions", required=True, help="directory of ai_session_feeder JSONs")
    ap.add_argument("--issues", required=True, help="B194 snapshot issues.json.gz (or plain issues.json)")
    ap.add_argument("--json", action="store_true", help="print rows as JSON instead of a table")
    args = ap.parse_args(argv)
    try:
        rows = build(load_sessions(args.sessions), load_issues(args.issues))
    except InputError as e:
        print(f"issue_time_report: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(rows, indent=1) if args.json else _table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
