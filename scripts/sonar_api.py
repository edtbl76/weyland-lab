#!/usr/bin/env python3
"""sonar_api.py — read the weyland SonarQube API from rogueone (2026-10-02).

    sonar_api.py gate [projectKey]          # why the quality gate passed/failed: conditions + new-code issues + hotspots
    sonar_api.py <api-path> [key=value ...]  # any GET, raw JSON — e.g. rules/search activation=true languages=py,java

Reaches Sonar through the LAN NodePort `sonarqube-api-lan` (mother.weyland.lab:30969 -> sonarqube:9000) as `admin`, with
the password from SONAR_ADMIN_PW in the gitignored scripts/.env — load it first, never paste it:
    set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a
The password is only ever sent as a Basic-auth header; it is never printed.

Why this exists: the runbook command it replaces curled from INSIDE the sonarqube pod with `$SONAR_ADMIN_PW`, which the
pod does not carry — it returned 401, so it had never worked. Exit: 0 ok / gate passed · 1 gate FAILED · 2 cannot read.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# Plain HTTP on purpose — the NodePort is the ONLY machine path: the HTTPS ingress (sonarqube.weyland.lab) is behind
# Keycloak forward-auth and answers an API call with a 307 to the browser login. LAN-only; reviewed SAFE in Sonar.
SONAR_URL = os.environ.get("SONAR_URL", "http://mother.weyland.lab:30969").rstrip("/")
PROJECT = "weyland-lab"


class CannotRead(Exception):
    pass


def get(path: str, params: dict) -> dict:
    pw = os.environ.get("SONAR_ADMIN_PW")
    if not pw:
        raise CannotRead("SONAR_ADMIN_PW is not set — load scripts/.env first (set -a && . scripts/.env && set +a)")
    url = f"{SONAR_URL}/api/{path.strip('/')}?{urllib.parse.urlencode(params)}"
    auth = base64.b64encode(f"admin:{pw}".encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        raise CannotRead(f"GET /api/{path} -> HTTP {exc.code}: {exc.read()[:300]!r}") from exc
    except (OSError, ValueError) as exc:   # OSError covers urllib.error.URLError
        raise CannotRead(f"GET /api/{path} failed: {exc}") from exc


def gate(project: str) -> int:
    st = get("qualitygates/project_status", {"projectKey": project})["projectStatus"]
    print(f"gate {project}: {st['status']}")
    for c in st.get("conditions", []):
        print(f"  {c['status']} {c['metricKey']} {c.get('actualValue')} ({c.get('comparator')} {c.get('errorThreshold')})")
    iss = get("issues/search", {"componentKeys": project, "inNewCodePeriod": "true", "resolved": "false", "ps": 100})
    print(f"new-code issues: {iss['total']}")
    for i in iss["issues"]:
        where = f"{i['component'].split(':', 1)[-1]}:{i.get('line', '?')}"
        print(f"  {i['severity']} {i['rule']} {where} — {i['message'][:120]}")
    hs = get("hotspots/search", {"projectKey": project, "inNewCodePeriod": "true", "status": "TO_REVIEW", "ps": 50})
    print(f"hotspots to review: {hs['paging']['total']}")
    for h in hs.get("hotspots", []):
        print(f"  {h['vulnerabilityProbability']} {h['component'].split(':', 1)[-1]}:{h.get('line', '?')} — {h['message'][:120]}")
    return 0 if st["status"] == "OK" else 1


def main(argv: list) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        if argv[0] == "gate":
            return gate(argv[1] if len(argv) > 1 else PROJECT)
        params = {}
        for kv in argv[1:]:
            if "=" not in kv:
                print(f"bad parameter {kv!r} — use key=value", file=sys.stderr)
                return 2
            k, v = kv.split("=", 1)
            params[k] = v
        print(json.dumps(get(argv[0], params), indent=2))
        return 0
    except CannotRead as exc:
        print(f"sonar_api: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
