#!/usr/bin/env python3
"""
B185 lane 2 — the owner's own time per Linear issue, from Clockify (manual timer).

Clockify's browser extension puts a timer on every Linear issue, named "[EMA-###] <title>". This reads the finished
entries and writes per-issue minutes to <out>/owner_time.json, which issue_time_report.py joins with lane 1's agent
time. Only issue ids and minutes leave the machine; entry text is read here and never written out.

  ActivityWatch (the automatic half) was RETIRED 2026-10-23: it failed its week-long trial on memory (27 of 53 samples
  over the 150 MB budget, peaking at 180 MB and growing with uptime), and the owner killed it. It is recorded as
  {"status": "retired"}, so the report shows its column as unknown, never as zero minutes; this never contacts it.

  Attribution (one issue per entry, never two, never guessed): the Linear button's "[EMA-###]" prefix, else the
  description's single EMA-style id, else its single B number (a hand-typed "B185 review" counts), else unattributed.
  Only finished entries count; a running timer is reported, not counted.

  usage: owner_time.py [--out DIR] [--env-file scripts/.env]
  env:   CLOCKIFY_API_KEY (or only that line of --env-file); absent = Clockify "not-configured", recorded as such,
         never as zero minutes
  exit:  0 written · 2 Clockify could not be read (an API error, a malformed result, an unreadable env file):
         nothing is written, so a stale-but-true file is never replaced by a partial one
Pure stdlib. Runbook: docs/runbooks/issue-time.md § Owner time.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict

CLOCKIFY = "https://api.clockify.me/api/v1"
RETIRED = {"activitywatch": {"status": "retired", "since": "2026-10-23",
                             "why": "failed its trial on memory (peak 180 MB > the 150 MB budget); killed by the owner"}}

EMA_ID = re.compile(r"\b([A-Z][A-Z0-9]*-\d+)\b")
B_ID = re.compile(r"\b(B\d{1,4}(?:\.\d+)?)\b")
CLOCKIFY_PREFIX = re.compile(r"^\[([A-Z][A-Z0-9]*-\d+)\]")
UNIT_SECONDS = {"D": 86400, "H": 3600, "M": 60, "S": 1}


class SourceError(Exception):
    pass


# --- attribution --------------------------------------------------------------------------------------------------

def issue_for_title(title):
    """The single issue a description names: one EMA-style id (outranks a backlog number beside it), else one B number."""
    emas = set(EMA_ID.findall(title or ""))
    if len(emas) == 1:
        return emas.pop()
    if emas:
        return None
    bs = set(B_ID.findall(title or ""))
    return bs.pop() if len(bs) == 1 else None


# --- Clockify -----------------------------------------------------------------------------------------------------

def _http_json(req, timeout=30):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _tokens(part, allowed):
    """[(value, unit)] for one side of an ISO duration (a number then a unit letter, units in `allowed` order, each at
    most once), or None when `part` is anything else. A character scan: no regex, so no backtracking."""
    toks, num = [], ""
    for ch in part:
        if ch.isdigit() or (ch == "." and num and "." not in num):
            num += ch
        elif ch in allowed and num and not num.endswith("."):
            toks.append((num, ch))
            num = ""
        else:
            return None
    units = [u for _, u in toks]
    if num or units != [u for u in allowed if u in units]:
        return None
    return toks


def iso_seconds(s):
    """Seconds in a Clockify ISO-8601 duration (PT25S, PT1H2M3S, P1DT1H). A token parser, not one big regex."""
    date, _, time = (s or "")[1:].partition("T") if (s or "").startswith("P") else ("x", "", "")
    d, t = _tokens(date, "D"), _tokens(time, "HMS")
    if d is None or t is None or not (d or t) or (s.endswith("T")):
        raise SourceError(f"unparseable Clockify duration {s!r}")
    return int(sum(float(v) * UNIT_SECONDS[u] for v, u in d + t))


def clockify_minutes(entries):
    """({issue: minutes}, unattributed minutes, running count). The id comes from the Linear button's "[EMA-###]"
    prefix, else from the description (a hand-typed "B185 review" counts)."""
    secs, unattributed, running = defaultdict(int), 0, 0
    for e in entries:
        ti = e.get("timeInterval") or {}
        if not ti.get("end") or not ti.get("duration"):
            running += 1
            continue
        s = iso_seconds(ti["duration"])
        desc = e.get("description") or ""
        m = CLOCKIFY_PREFIX.match(desc)
        issue = m.group(1) if m else issue_for_title(desc)
        if issue:
            secs[issue] += s
        else:
            unattributed += s
    return {k: round(v / 60, 2) for k, v in secs.items()}, round(unattributed / 60, 2), running


def clockify_key(env_file=None):
    """The Clockify key: from the environment, else ONLY the CLOCKIFY_API_KEY line of `env_file` (scripts/.env) — the
    producer unit doesn't load that file, and exporting every secret in it to the unit would be needlessly wide. "" when
    absent (not configured). A named env file that can't be read fails closed."""
    key = os.environ.get("CLOCKIFY_API_KEY", "").strip()
    if key or not env_file:
        return key
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                name, sep, value = line.strip().removeprefix("export ").partition("=")
                if sep and name.strip() == "CLOCKIFY_API_KEY":
                    return value.strip().strip("'\"")
    except OSError as e:
        raise SourceError(f"cannot read env file {env_file}: {e}") from e
    return ""


def _clockify_get(key, path):
    req = urllib.request.Request(CLOCKIFY + path, headers={"X-Api-Key": key})
    try:
        return _http_json(req)
    except urllib.error.HTTPError as e:
        raise SourceError(f"Clockify GET {path.split('?')[0]} -> HTTP {e.code}") from e
    except (OSError, ValueError) as e:   # URLError is an OSError
        raise SourceError(f"Clockify GET {path.split('?')[0]} failed: {e}") from e


def _clockify_entries(key):
    """Every time entry of the key's user in its default workspace (paged; the free plan allows 30 requests/hour)."""
    user = _clockify_get(key, "/user")
    ws, uid = user.get("defaultWorkspace"), user.get("id")
    if not ws or not uid:
        raise SourceError("Clockify /user returned no id or default workspace")
    entries, page = [], 1
    while True:
        batch = _clockify_get(key, f"/workspaces/{ws}/user/{uid}/time-entries?page-size=1000&page={page}")
        if not isinstance(batch, list):
            raise SourceError("Clockify time-entries did not return a list")
        entries += batch
        if len(batch) < 1000:
            return entries
        page += 1


# --- main ---------------------------------------------------------------------------------------------------------

def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.expanduser("~/.cache/owner-time"))
    ap.add_argument("--env-file", help="read CLOCKIFY_API_KEY (only that line) from this file, e.g. scripts/.env")
    args = ap.parse_args(argv)
    try:
        key = clockify_key(args.env_file)
        if key:
            minutes, unattributed, running = clockify_minutes(_clockify_entries(key))
            clockify = {"status": "ok", "unattributed_minutes": unattributed, "running_timers": running}
        else:
            minutes, clockify = {}, {"status": "not-configured"}
    except SourceError as e:
        print(f"owner_time: {e}", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    issues = {k: {"clockify_minutes": round(v, 2)} for k, v in sorted(minutes.items())}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    _write_json(os.path.join(args.out, "owner_time.json"),
                {"generated_at": now, "issues": issues, "sources": {**RETIRED, "clockify": clockify}})
    print(f"owner_time: {len(issues)} issue(s); Clockify {clockify['status']}; ActivityWatch retired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
