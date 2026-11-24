#!/usr/bin/env python3
"""morning-remediation.py — B243: what broke overnight, what was tried, and the outcome (2026-11-24).

The rogueone user timer runs it at 05:30 NY (docs/schedules.md). By hand, on rogueone:

  python3 /home/edwardmangini/IdeaProjects/weyland/scripts/morning-remediation.py --dry-run      # collect + print
  python3 /home/edwardmangini/IdeaProjects/weyland/scripts/morning-remediation.py --triage-only  # + diagnose, no acts
  python3 /home/edwardmangini/IdeaProjects/weyland/scripts/morning-remediation.py                # the real run

Collect (morning_collect) -> per item: triage, one allowlisted action or a local fix branch (morning_run with
morning_deps) -> deliver: the summary to Slack #alerts, a comment on each Auto-Filed incident in Linear, the report
file in the state dir, then the Kuma heartbeat (absent when the run never happened, which is what pages; an
unchecked source is named in it and in the report). --dry-run and --triage-only post nothing unless --post is given.
Tests: scripts/tests/test_morning_cli.py. Runbook: docs/runbooks/morning-remediation.md.
"""
import argparse
import datetime
import fcntl
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request
import zoneinfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import morning_collect as mc  # noqa: E402
import morning_run as mr  # noqa: E402

NY = zoneinfo.ZoneInfo("America/New_York")


# --- delivery decisions (pure) --------------------------------------------------------------------------------------
def summary_line(report) -> str:
    if not report.outcomes:
        return "quiet night"
    counts = {}
    for o in report.outcomes:
        counts[o.result] = counts.get(o.result, 0) + 1
    return f"{len(report.outcomes)} item(s): " + ", ".join(f"{n} {k}" for k, n in counts.items())


def linear_comments(report) -> dict:
    out = {}
    for o in report.outcomes:
        ident = o.item.extra.get("identifier") if o.item.source == "incidents" else None
        if ident:
            out[ident] = (f"**Morning remediation (B243), {report.date}: {o.result}**\n\n"
                          + (f"Diagnosis ({o.classification}): {o.diagnosis}\n\n" if o.diagnosis else "")
                          + (f"Action: {o.action}\n\n" if o.action else "") + f"Outcome: {o.detail}")
    return out


def heartbeat_url(base: str, report) -> str:
    """The heartbeat means "the run happened" (a missed run is what pages, per EMA-342); an unchecked source is named
    in its message and in the Slack report, not paged."""
    unchecked = [k for k, v in report.status.items() if not v.startswith("checked")]
    msg = summary_line(report) + (f"; NOT CHECKED: {', '.join(unchecked)}" if unchecked else "")
    return f"{base}?" + urllib.parse.urlencode({"status": "up", "msg": msg[:200], "ping": ""})


def slack_ok(code: int, body: str) -> bool:
    return code == 200 and body.strip() == "ok"


def linear_ok(answer: dict) -> tuple:
    if answer.get("errors"):
        return False, answer["errors"][0].get("message", "error")
    res = (answer.get("data") or {}).get("commentCreate") or {}
    cid = (res.get("comment") or {}).get("id")
    return (True, cid) if res.get("success") and cid else (False, "no comment id returned")


# --- I/O ------------------------------------------------------------------------------------------------------------
def load_env(path: pathlib.Path) -> dict:
    env = dict(os.environ)
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.removeprefix("export ").strip()] = v.strip().strip('"').strip("'")
    return env


def _post(url: str, body: dict, headers: dict | None = None) -> tuple:
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def deliver(report, text: str, env: dict) -> list:
    """Each delivery's result, as lines for the run log (never a URL or a key)."""
    lines = []
    hook = env.get("SLACK_WEBHOOK_ALERTS")
    if not hook:
        lines.append("slack: NOT SENT (SLACK_WEBHOOK_ALERTS not set)")
    else:
        code, body = _post(hook, {"text": text})
        lines.append("slack: sent" if slack_ok(code, body) else f"slack: FAILED ({code} {body[:80]})")
    for ident, comment in linear_comments(report).items():
        mutation = "mutation($i: String!, $b: String!){commentCreate(input:{issueId:$i, body:$b}){success comment{id}}}"
        code, body = _post("https://api.linear.app/graphql", {"query": mutation, "variables": {"i": ident, "b": comment}},
                           {"Authorization": env.get("LINEAR_API_KEY", "")})
        try:
            ok, detail = linear_ok(json.loads(body))
        except ValueError:
            ok, detail = False, f"HTTP {code}"
        lines.append(f"linear {ident}: " + (f"commented ({detail})" if ok else f"FAILED ({detail})"))
    return lines


def push_heartbeat(report, env: dict) -> str:
    base = env.get("KUMA_MORNING_PUSH_URL")
    if not base:
        return "kuma: NOT PUSHED (KUMA_MORNING_PUSH_URL not set)"
    try:
        with urllib.request.urlopen(heartbeat_url(base, report), timeout=30) as resp:
            ok = json.loads(resp.read()).get("ok") is True
    except (OSError, ValueError) as exc:
        return f"kuma: FAILED ({type(exc).__name__})"
    return "kuma: pushed" if ok else "kuma: FAILED (Kuma did not answer ok)"


class TriageOnly:
    """Wraps the live deps: diagnose every item, act on none (the report says so)."""

    def __init__(self, deps):
        self.deps, self.history = deps, deps.history

    def triage(self, item):
        return self.deps.triage(item)

    def act(self, action, params):
        raise mr.ActionRefused(f"triage-only run: {action} {params} not attempted")

    def verify(self, *_):
        return False, "not run"

    def fix(self, *_):
        return {"branch": "(none)", "gates": "not run (triage-only)"}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description="B243 morning remediation")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="collect and print; no model, no action")
    mode.add_argument("--triage-only", action="store_true", help="collect and diagnose; no action, no fix")
    ap.add_argument("--post", action="store_true", help="deliver the report even in --dry-run / --triage-only")
    ap.add_argument("--since-hours", type=float, default=24)
    a = ap.parse_args(argv)

    env = load_env(ROOT / "scripts" / ".env")
    os.environ.update({k: v for k, v in env.items() if k not in os.environ})
    import morning_deps as md   # after the env is loaded
    md.STATE.mkdir(parents=True, exist_ok=True)
    lock = open(md.STATE / "run.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("morning-remediation: another run holds the lock; not starting a second one")
        return 3

    date = datetime.datetime.now(NY).date().isoformat()
    failures, status = mc.collect(time.time() - a.since_hours * 3600, mc.FETCHERS)
    if a.dry_run:
        report = mr.Report(date, status, [mr.Outcome(f, "collected (dry run)", "not triaged") for f in failures])
    else:
        live = md.LiveDeps(date=date, env=env)
        try:
            report = mr.run(failures, status, TriageOnly(live) if a.triage_only else live, date=date)
            if not a.triage_only:
                live.remember(report)
        finally:
            live.close()
    text = mr.render(report)
    print(text)
    reports = md.STATE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if a.dry_run:
        suffix = "-dry"
    elif a.triage_only:
        suffix = "-triage"
    (reports / f"{date}{suffix}.md").write_text(text + "\n")
    if (a.dry_run or a.triage_only) and not a.post:
        print("\n(delivery skipped: not a real run; --post to send)")
        return 0
    for line in [*deliver(report, text, env), push_heartbeat(report, env)]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
