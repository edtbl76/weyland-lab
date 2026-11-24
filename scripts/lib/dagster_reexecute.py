"""Re-execute ONE failed Dagster run from its failure (B243, 2026-11-24): the allowlist action dagster-reexecute-run.

Runs INSIDE the dagster-user-code pod, piped over stdin (one stdlib file, no copy in the image), like dagster_runs.py:

  kubectl exec -i -n weyland deploy/dagster-user-code -- python3 - --run <full-run-id> < scripts/lib/dagster_reexecute.py

One GraphQL mutation, launchRunReexecution with strategy FROM_FAILURE (the shape read from this Dagster's schema,
2026-11-24). The new run is tagged weyland/started-by=morning-remediation, so the morning report tells a run the agent
started from a real fault. Exit 0 launched · 1 Dagster refused or errored (printed) · 2 bad arguments or unreachable.
Only the morning runner calls this, through scripts/lib/morning_actions.py (the allowlist); tests:
scripts/tests/test_dagster_reexecute.py. Runbook: docs/runbooks/morning-remediation.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

URL = "http://dagster-webserver.weyland.svc.cluster.local:3000/graphql"
RUN_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
TAG = {"key": "weyland/started-by", "value": "morning-remediation"}
QUERY = """mutation Reexecute($params: ReexecutionParams!) {
  launchRunReexecution(reexecutionParams: $params) {
    __typename
    ... on LaunchRunSuccess { run { runId } }
    ... on PythonError { message }
    ... on Error { message }
  }
}"""


STATUS_QUERY = """query Status($id: ID!) { runOrError(runId: $id) { __typename ... on Run { status } } }"""


def status_body(run_id: str) -> dict:
    """A read-only query for one run's status (used to verify a re-execution before reporting it fixed)."""
    return {"query": STATUS_QUERY, "variables": {"id": run_id}}


def status_of(answer: dict) -> str:
    res = (answer.get("data") or {}).get("runOrError") or {}
    return res.get("status") if res.get("__typename") == "Run" else "NOT_FOUND"


def mutation_body(run_id: str) -> dict:
    return {"query": QUERY, "variables": {"params": {"parentRunId": run_id, "strategy": "FROM_FAILURE",
                                                     "extraTags": [TAG]}}}


def outcome(answer: dict) -> tuple[bool, str]:
    if answer.get("errors"):
        return False, "GraphQL error: " + "; ".join(e.get("message", "?") for e in answer["errors"])[:400]
    res = (answer.get("data") or {}).get("launchRunReexecution") or {}
    if res.get("__typename") == "LaunchRunSuccess":
        return True, f"re-executed from failure as run {res['run']['runId']}"
    return False, f"{res.get('__typename', 'no answer')}: {res.get('message', '')}"[:400]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Re-execute one failed Dagster run from its failure (B243).")
    ap.add_argument("--run", required=True)
    ap.add_argument("--status", action="store_true", help="only print the run's status (read-only)")
    args = ap.parse_args(argv)
    if not RUN_ID.fullmatch(args.run):
        print(f"not a Dagster run id: {args.run!r}", file=sys.stderr)
        raise SystemExit(2)
    body = status_body(args.run) if args.status else mutation_body(args.run)
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            answer = json.load(resp)
    except Exception as exc:   # unreachable is never "launched"
        print(f"could not ask Dagster: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.status:
        print(status_of(answer))
        return 0
    ok, msg = outcome(answer)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
