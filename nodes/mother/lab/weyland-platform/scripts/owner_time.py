#!/usr/bin/env python3
"""
B185 lane 2 — the owner's own time per Linear issue, from ActivityWatch (automatic) and Clockify (manual timer).

ActivityWatch (localhost:5600 on rogueone) records the active window and Chrome tab; Clockify's browser extension puts
a timer on every Linear issue, named "[EMA-###] <title>". This reads both and writes per-issue minutes to
<out>/owner_time.json, which issue_time_report.py joins with lane 1's agent time. Only issue ids and minutes leave the
machine; window titles, URLs and entry text are read here and never written out.

  Attribution (one issue per event, never two, never guessed):
    a Linear tab          the id in its URL (/issue/EMA-243): its title carries EMA-243 AND B185
    any other tab/window  the title's single EMA id, else its single B number, else unattributed
  ActivityWatch time is counted through AW's own query language: browser events only while Chrome is the active
  window (the window watcher sees the same tab, so both would double-count), non-browser windows separately, and
  every event intersected with not-afk. Each day is computed into <out>/aw-day-YYYY-MM-DD.json; the totals sum every
  day file, so history outlives the --days window. Clockify counts only finished entries.

  Also records the trial's resource use (systemd accounting of the aw-* user units) against EMA-243's kill
  criteria: > 1% average CPU or > 150 MB resident memory. Appended to <out>/resources.jsonl for the week's verdict.

  usage: owner_time.py [--out DIR] [--days N] [--host NAME] [--env-file scripts/.env]
  env:   CLOCKIFY_API_KEY (or only that line of --env-file); absent = Clockify "not-configured", recorded as such,
         never as zero minutes
  exit:  0 written · 2 a source could not be read (ActivityWatch unreachable, a Clockify API error, a malformed result):
         nothing is written, so a stale-but-true file is never replaced by a partial one
Pure stdlib. Runbook: docs/runbooks/issue-time.md § Owner time.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict

AW = "http://127.0.0.1:5600/api/0"
CLOCKIFY = "https://api.clockify.me/api/v1"
UNITS = ("aw-server", "aw-watcher-window", "aw-watcher-afk")
BROWSER_APP = "Google-chrome"
CPU_LIMIT_PCT, RSS_LIMIT_MB = 1.0, 150.0

LINEAR_URL_ID = re.compile(r"linear\.app/[^/]+/issue/([A-Z][A-Z0-9]*-\d+)", re.I)
EMA_ID = re.compile(r"\b([A-Z][A-Z0-9]*-\d+)\b")
B_ID = re.compile(r"\b(B\d{1,4}(?:\.\d+)?)\b")
CLOCKIFY_PREFIX = re.compile(r"^\[([A-Z][A-Z0-9]*-\d+)\]")
UNIT_SECONDS = {"D": 86400, "H": 3600, "M": 60, "S": 1}


class SourceError(Exception):
    pass


# --- attribution --------------------------------------------------------------------------------------------------

def issue_for_title(title):
    """The single issue a title names: one EMA-style id (outranks a backlog number beside it), else one B number."""
    emas = set(EMA_ID.findall(title or ""))
    if len(emas) == 1:
        return emas.pop()
    if emas:
        return None
    bs = set(B_ID.findall(title or ""))
    return bs.pop() if len(bs) == 1 else None


def issue_for_web(url, title):
    m = LINEAR_URL_ID.search(url or "")
    return m.group(1).upper() if m else issue_for_title(title)


# --- ActivityWatch ------------------------------------------------------------------------------------------------

def aw_query(host):
    return [f'afk = flood(query_bucket("aw-watcher-afk_{host}"));',
            'not_afk = filter_keyvals(afk, "status", ["not-afk"]);',
            f'win = flood(query_bucket("aw-watcher-window_{host}"));',
            'win = filter_period_intersect(win, not_afk);',
            f'chrome = filter_keyvals(win, "app", ["{BROWSER_APP}"]);',
            f'web = flood(query_bucket("aw-watcher-web-chrome_{host}"));',
            'web = filter_period_intersect(web, chrome);',
            f'other = exclude_keyvals(win, "app", ["{BROWSER_APP}"]);',
            'RETURN = {"web": web, "other": other};']


def _event_issue(kind, event):
    d = event.get("data") or {}
    return issue_for_web(d.get("url"), d.get("title")) if kind == "web" else issue_for_title(d.get("title"))


def aw_minutes(result):
    """({issue: minutes}, unattributed minutes) from one query result {"web": [...], "other": [...]}."""
    for k in ("web", "other"):
        if not isinstance(result, dict) or not isinstance(result.get(k), list):
            raise SourceError(f"ActivityWatch query result has no '{k}' event list")
    secs = defaultdict(float)
    for kind in ("web", "other"):
        for e in result[kind]:
            secs[_event_issue(kind, e)] += float(e.get("duration") or 0)
    unattributed = secs.pop(None, 0.0)
    return {k: round(v / 60, 2) for k, v in secs.items()}, round(unattributed / 60, 2)


def _http_json(req, timeout=30):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _aw_result(host, day):
    """One local day's query result. Any failure is a SourceError: an unreadable day is not an empty day."""
    start = dt.datetime.combine(day, dt.time()).astimezone()
    period = f"{start.isoformat()}/{(start + dt.timedelta(days=1)).isoformat()}"
    body = json.dumps({"timeperiods": [period], "query": aw_query(host)}).encode()
    req = urllib.request.Request(AW + "/query/", data=body, headers={"Content-Type": "application/json"})
    try:
        out = _http_json(req)
    except (OSError, ValueError) as e:   # URLError is an OSError
        raise SourceError(f"ActivityWatch query for {day} failed ({AW}): {e}") from e
    if not isinstance(out, list) or len(out) != 1:
        raise SourceError(f"ActivityWatch query for {day} returned {type(out).__name__}, not one result")
    return out[0]


# --- Clockify -----------------------------------------------------------------------------------------------------

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
    prefix, else from the description like a window title (a hand-typed "B185 review" counts)."""
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


# --- the trial's resource budget ----------------------------------------------------------------------------------

def _systemctl_show(unit):
    return subprocess.run(["systemctl", "--user", "show", unit, "-p", "CPUUsageNSec", "-p", "MemoryCurrent",
                           "-p", "ActiveEnterTimestampMonotonic", "-p", "ActiveState"],
                          capture_output=True, text=True, check=False).stdout


def _num(v):
    return int(v) if v and v.isdigit() else 0


def resources(show, uptime_s, ncpu):
    """CPU (average since each unit started) as % of one core and of the machine, total RSS, and the broken criteria."""
    cpu_s = active_s = rss = 0.0
    inactive = []
    for unit, text in show.items():
        kv = {k: v for k, sep, v in (line.partition("=") for line in text.strip().splitlines()) if sep}
        if kv.get("ActiveState") != "active":
            inactive.append(unit)
            continue
        cpu_s += _num(kv.get("CPUUsageNSec")) / 1e9
        rss += _num(kv.get("MemoryCurrent"))
        active_s = max(active_s, uptime_s - _num(kv.get("ActiveEnterTimestampMonotonic")) / 1e6)
    core = round(100 * cpu_s / active_s, 2) if active_s > 0 else 0.0
    out = {"cpu_pct_of_one_core": core, "cpu_pct_of_machine": round(core / ncpu, 3), "rss_mb": round(rss / 1e6, 1),
           "active_hours": round(active_s / 3600, 2), "inactive": sorted(inactive), "over_budget": []}
    if core > CPU_LIMIT_PCT:
        out["over_budget"].append("cpu > 1% of one core")
    if out["rss_mb"] > RSS_LIMIT_MB:
        out["over_budget"].append("rss > 150 MB")
    return out


def _uptime():
    with open("/proc/uptime", encoding="ascii") as f:
        return float(f.read().split()[0])


# --- main ---------------------------------------------------------------------------------------------------------

def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def collect(days, host, env_file=None):
    """Compute the recent days and Clockify; raise SourceError before anything is written."""
    today = dt.date.today()
    fresh = {}
    for n in range(days):
        day = today - dt.timedelta(days=n)
        fresh[day] = aw_minutes(_aw_result(host, day))
    key = clockify_key(env_file)
    if key:
        cm, cu, running = clockify_minutes(_clockify_entries(key))
        clockify = {"status": "ok", "unattributed_minutes": cu, "running_timers": running}
    else:
        cm, clockify = None, {"status": "not-configured"}
    show = {u: _systemctl_show(u) for u in UNITS}
    return fresh, cm, clockify, resources(show, _uptime(), os.cpu_count() or 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.expanduser("~/.cache/owner-time"))
    ap.add_argument("--days", type=int, default=2, help="recompute this many recent days (older day files are final)")
    ap.add_argument("--host", default=socket.gethostname(), help="the ActivityWatch bucket suffix")
    ap.add_argument("--env-file", help="read CLOCKIFY_API_KEY (only that line) from this file, e.g. scripts/.env")
    args = ap.parse_args(argv)
    try:
        fresh, cm, clockify, res = collect(args.days, args.host, args.env_file)
    except SourceError as e:
        print(f"owner_time: {e}", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    for day, (minutes, unattributed) in fresh.items():
        _write_json(os.path.join(args.out, f"aw-day-{day.isoformat()}.json"),
                    {"day": day.isoformat(), "issues": minutes, "unattributed_minutes": unattributed})
    aw, aw_un, day_files = defaultdict(float), 0.0, sorted(glob.glob(os.path.join(args.out, "aw-day-*.json")))
    for p in day_files:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        aw_un += d.get("unattributed_minutes", 0)
        for k, v in d.get("issues", {}).items():
            aw[k] += v
    issues = {k: {"aw_minutes": round(aw.get(k, 0.0), 2),
                  "clockify_minutes": None if cm is None else round(cm.get(k, 0.0), 2)}
              for k in sorted(set(aw) | set(cm or {}))}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    _write_json(os.path.join(args.out, "owner_time.json"),
                {"generated_at": now, "issues": issues, "resources": res,
                 "sources": {"activitywatch": {"status": "ok", "days": len(day_files),
                                               "unattributed_minutes": round(aw_un, 2)},
                             "clockify": clockify}})
    with open(os.path.join(args.out, "resources.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now, **res}) + "\n")
    print(f"owner_time: {len(issues)} issue(s); ActivityWatch {len(day_files)} day(s), Clockify {clockify['status']}; "
          f"trial CPU {res['cpu_pct_of_one_core']}% of a core, RSS {res['rss_mb']} MB"
          + (f"; OVER BUDGET: {', '.join(res['over_budget'])}" if res["over_budget"] else "")
          + (f"; INACTIVE: {', '.join(res['inactive'])}" if res["inactive"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
