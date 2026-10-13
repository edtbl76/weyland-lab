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

  usage: issue_time_report.py --sessions <dir of session JSONs> --issues <issues.json[.gz]> [--json | --port]
  exit:  0 report printed (or, with --port, pushed to Port and read back) · 1 --port read-back did not match ·
         2 an input is absent, unreadable or carries nothing to report, or the Port API failed (fail closed)

--port writes one `issue_time` entity per issue (blueprint tofu/port/issue_time.tf, related to the Linear integration's
`linearIssue`), reads every one back, deletes entities no longer in the report, and upserts the `time_per_issue`
dashboard from tofu/port/pages/time_per_issue.json. Credentials: PORT_CLIENT_ID / PORT_CLIENT_SECRET in the env.
"""
import argparse
import datetime as dt
import glob
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

B_TITLE_RE = re.compile(r"(B\d+(?:\.\d+)?)\b")


class InputError(Exception):
    pass


class NotFound(InputError):
    pass


BLUEPRINT = "issue_time"
PAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tofu", "port", "pages",
                         "time_per_issue.json")
PAGE_CREATE_ONLY = ("type", "sidebar")
PROPS = ("backlog", "agent_hours", "sessions", "output_tokens", "api_equiv_usd", "lead_days", "cycle_days",
         "first_agent_at", "unmapped")


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


class PortClient:
    """Port REST with a client-credentials token; every non-2xx is an InputError (404 → NotFound)."""

    def __init__(self, client_id, client_secret, base=None):
        self.base = (base or os.environ.get("PORT_API_BASE", "https://api.port.io")).rstrip("/")
        body = {"clientId": client_id, "clientSecret": client_secret}
        self.token = self._send("POST", "/v1/auth/access_token", body, auth=False)["accessToken"]

    def _send(self, method, path, body=None, auth=True):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {self.token}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            err = NotFound if e.code == 404 else InputError
            raise err(f"{method} {path} -> HTTP {e.code}: {e.read()[:200]!r}") from e
        except (OSError, ValueError) as e:
            raise InputError(f"{method} {path} failed: {e}") from e

    def request(self, method, path, body=None):
        return self._send(method, path, body)


def port_entities(rows, in_port):
    """One `issue_time` entity per row, related to its linearIssue only when that entity exists in Port (`in_port`):
    an unmapped B number is never guessed, and Port 404s a relation to an issue its Linear integration did not sync
    (EMA-206, 2026-10-13) — the time is still recorded."""
    return [{"identifier": x["issue"],
             "title": f"{x['issue']} · {x['backlog']}" if x["backlog"] else x["issue"],
             "properties": {k: x[k] for k in PROPS},
             "relations": {"issue": x["issue"]} if not x["unmapped"] and x["issue"] in in_port else {}}
            for x in rows]


def dashboard_page():
    with open(PAGE_FILE, encoding="utf-8") as f:
        return json.load(f)


def _verify(wanted, live):
    """Read-back: every property of every entity we wrote is live with the same value."""
    problems = []
    for e in wanted:
        got = live.get(e["identifier"])
        if got is None:
            problems.append(f"{e['identifier']}: missing after upsert")
            continue
        for k, v in e["properties"].items():
            if (got.get("properties") or {}).get(k) != v:
                problems.append(f"{e['identifier']}: {k} is {(got.get('properties') or {}).get(k)!r}, wrote {v!r}")
    return problems


def push_to_port(rows, port):
    """Upsert, read back, delete stale entities, upsert the dashboard. 0 ok · 1 read-back mismatch · 2 API failure."""
    base = f"/v1/blueprints/{BLUEPRINT}/entities"
    try:
        in_port = {e["identifier"] for e in port.request("GET", "/v1/blueprints/linearIssue/entities")
                   .get("entities", [])}
        ents = port_entities(rows, in_port)
        orphans = sorted(x["issue"] for x in rows if not x["unmapped"] and x["issue"] not in in_port)
        for e in ents:
            port.request("POST", base + "?upsert=true&merge=true", e)
        live = {e["identifier"]: e for e in port.request("GET", base).get("entities", [])}
        problems = _verify(ents, live)
        stale = sorted(set(live) - {e["identifier"] for e in ents})
        for ident in stale:
            port.request("DELETE", f"{base}/{urllib.parse.quote(ident, safe='')}")
        page = dashboard_page()
        try:
            port.request("GET", f"/v1/pages/{page['identifier']}")
            # `type` and `sidebar` are create-only: PATCH answers 422 "Unrecognized keys" (observed 2026-10-13)
            update = {k: v for k, v in page.items() if k not in PAGE_CREATE_ONLY}
            port.request("PATCH", f"/v1/pages/{page['identifier']}", update)
        except NotFound:
            port.request("POST", "/v1/pages", page)
    except InputError as e:
        print(f"issue_time_report: Port: {e}", file=sys.stderr)
        return 2
    for p in problems:
        print(f"issue_time_report: read-back: {p}", file=sys.stderr)
    if problems:
        return 1
    print(f"port: {len(ents)} {BLUEPRINT} entities upserted and read back, {len(stale)} stale deleted; "
          f"dashboard {page['identifier']} upserted")
    if orphans:
        print(f"port: {len(orphans)} without a linearIssue in Port: {', '.join(orphans)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions", required=True, help="directory of ai_session_feeder JSONs")
    ap.add_argument("--issues", required=True, help="B194 snapshot issues.json.gz (or plain issues.json)")
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true", help="print rows as JSON instead of a table")
    out.add_argument("--port", action="store_true", help="push to Port (issue_time entities + the dashboard)")
    args = ap.parse_args(argv)
    try:
        rows = build(load_sessions(args.sessions), load_issues(args.issues))
        if args.port:
            cid, secret = os.environ.get("PORT_CLIENT_ID"), os.environ.get("PORT_CLIENT_SECRET")
            if not cid or not secret:
                raise InputError("PORT_CLIENT_ID / PORT_CLIENT_SECRET unset (tofu/port/.env)")
            return push_to_port(rows, PortClient(cid, secret))
    except InputError as e:
        print(f"issue_time_report: {e}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(rows, indent=1) if args.json else _table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
