"""Why did a Dagster run fail? A read-only diagnostic (B239). Runbook: docs/runbooks/dagster.md.

Runs INSIDE the dagster-user-code pod, piped over stdin, so it is one stdlib file and needs no copy in the image:

  kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - < scripts/lib/dagster_runs.py
  kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --job datahub_catalog_emit_job < scripts/lib/dagster_runs.py
  kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --run <full-run-id> < scripts/lib/dagster_runs.py
  kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --health < scripts/lib/dagster_runs.py

Lists the most recent FAILED runs (all jobs, or one job), then explains the newest (or the given run): each failed
step's error and the run's failure message. `--health` reports daemon heartbeats and code-location loading.
GraphQL queries only, never a mutation. Exit 0 printed / healthy, 1 no failed runs found or unhealthy (a finding),
2 could not ask Dagster.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

URL = "http://dagster-webserver.weyland.svc.cluster.local:3000/graphql"
JOB = re.compile(r"\w{1,128}", re.ASCII)  # ASCII: Python's \w otherwise also matches Unicode letters
RUN_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
MAX_MSG = 400


def runs_query(job: str | None, limit: int) -> str:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1-50")
    if job is not None and not JOB.fullmatch(job):
        raise ValueError(f"job name {job!r} must be letters, digits and underscores")
    job_filter = f',pipelineName:"{job}"' if job else ""
    return ("{runsOrError(filter:{statuses:[FAILURE]%s},limit:%d){__typename "
            "... on Runs{results{runId jobName status startTime}} ... on PythonError{message}}}") % (job_filter, limit)


def run_query(run_id: str) -> str:
    if not RUN_ID.fullmatch(run_id or ""):
        raise ValueError(f"run id {run_id!r} must be a full run id (36 characters, from the run list)")
    return ('{runOrError(runId:"%s"){__typename ... on Run{jobName status eventConnection(afterCursor:null){events{'
            "__typename ... on ExecutionStepFailureEvent{stepKey error{message}} ... on RunFailureEvent{message}}}} "
            "... on RunNotFoundError{message}}}") % run_id


def _one_line(text: str) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= MAX_MSG else text[:MAX_MSG] + " ..."


def failure_lines(events: list[dict]) -> list[str]:
    """The failed steps and the run failure, in event order."""
    out = []
    for e in events:
        if e.get("__typename") == "ExecutionStepFailureEvent":
            out.append(f"step failed: {e.get('stepKey')}: {_one_line((e.get('error') or {}).get('message', ''))}")
        elif e.get("__typename") == "RunFailureEvent":
            out.append(f"run failed: {_one_line(e.get('message', ''))}")
    if not out:
        out.append("no failure event recorded: the run process probably died from outside (OOM, eviction). Check "
                   "`kubectl -n weyland logs deploy/dagster-user-code --previous` and `kubectl -n weyland describe "
                   "pod -l app=dagster-user-code` (runs execute inside that pod).")
    return out


HEALTH_QUERY = ("{instance{daemonHealth{allDaemonStatuses{daemonType healthy required}}} workspaceOrError{__typename "
                "... on Workspace{locationEntries{name loadStatus locationOrLoadError{__typename ... on PythonError{message}}}} "
                "... on PythonError{message}}}")


def _daemon_lines(daemons: list[dict]) -> tuple[list[str], bool]:
    if not daemons:
        return ["UNHEALTHY: no daemon heartbeats reported (is dagster-daemon running?)"], False
    lines, ok = [], True
    for d in daemons:
        if d["required"] and not d["healthy"]:
            lines.append(f"UNHEALTHY daemon {d['daemonType']}")
            ok = False
        else:
            lines.append(f"daemon {d['daemonType']}: {'healthy' if d['healthy'] else 'not running (optional)'}")
    return lines, ok


def _location_lines(ws: dict) -> tuple[list[str], bool]:
    if ws.get("__typename") != "Workspace":
        return [f"workspace FAILED TO LOAD: {_one_line(ws.get('message', ''))}"], False
    if not ws["locationEntries"]:
        return ["UNHEALTHY: no code locations"], False
    lines, ok = [], True
    for loc in ws["locationEntries"]:
        err = loc.get("locationOrLoadError") or {}
        if err.get("__typename") == "PythonError":
            lines.append(f"code location {loc['name']}: FAILED TO LOAD: {_one_line(err.get('message', ''))}")
            ok = False
        else:
            lines.append(f"code location {loc['name']}: {loc['loadStatus']}")
    return lines, ok


def health_lines(data: dict) -> tuple[list[str], bool]:
    """Daemon heartbeats and code-location load status. Healthy only if every REQUIRED daemon reports healthy and every
    code location loaded; an empty daemon list is unhealthy (no heartbeat), never 'nothing wrong'."""
    daemon_lines, daemons_ok = _daemon_lines(data["instance"]["daemonHealth"]["allDaemonStatuses"])
    location_lines, locations_ok = _location_lines(data["workspaceOrError"])
    return daemon_lines + location_lines, daemons_ok and locations_ok


def run_rows(results: list[dict]) -> list[str]:
    rows = []
    for r in results:
        started = datetime.fromtimestamp(r.get("startTime") or 0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        rows.append(f"{r['runId']}  {started}  {r['jobName']}")
    return rows


def _ask(query: str) -> dict:
    req = urllib.request.Request(URL, data=json.dumps({"query": query}).encode(),
                                 headers={"Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def _show_health() -> int:
    lines, ok = health_lines(_ask(HEALTH_QUERY))
    print("\n".join(lines))
    print("OK" if ok else "UNHEALTHY")
    return 0 if ok else 1


def _list_failures(job: str | None, limit: int) -> str | int:
    """Print the recent failed runs; return the newest run id, or an exit code when there is nothing to explain."""
    runs = _ask(runs_query(job, limit))["runsOrError"]
    if runs["__typename"] != "Runs":
        print(f"dagster_runs: {runs.get('message', runs['__typename'])}", file=sys.stderr)
        return 2
    scope = f" for {job}" if job else ""
    if not runs["results"]:
        print(f"no failed runs{scope} among the most recent {limit}")
        return 1
    print(f"most recent failed runs{scope}:")
    print("\n".join("  " + r for r in run_rows(runs["results"])))
    return runs["results"][0]["runId"]


def explain_lines(run_id: str, run: dict) -> list[str]:
    """What to print for one run: its failures, or that it did not fail (a run given by --run may have succeeded)."""
    if run["status"] != "FAILURE":
        return [f"{run_id} ({run['jobName']}) is {run['status']}: it did not fail, so there is nothing to explain."
                + (" It succeeded." if run["status"] == "SUCCESS" else "")]
    return [f"why {run_id} ({run['jobName']}, {run['status']}) failed:"] + [
        "  " + ln for ln in failure_lines(run["eventConnection"]["events"])]


def _explain(run_id: str) -> int:
    run = _ask(run_query(run_id))["runOrError"]
    if run["__typename"] != "Run":
        print(f"dagster_runs: {run.get('message', run['__typename'])}", file=sys.stderr)
        return 2
    print("\n" + "\n".join(explain_lines(run_id, run)))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="dagster_runs")
    ap.add_argument("--job")
    ap.add_argument("--run")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--health", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.health:
            return _show_health()
        run_id = a.run or _list_failures(a.job, a.limit)
        if isinstance(run_id, int):  # _list_failures returned an exit code: nothing to explain
            return run_id
        return _explain(run_id)
    except ValueError as e:
        print(f"dagster_runs: {e}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, KeyError) as e:
        print(f"dagster_runs: could not ask Dagster at {URL}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
