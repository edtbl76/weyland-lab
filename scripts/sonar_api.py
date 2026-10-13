#!/usr/bin/env python3
"""sonar_api.py — read the weyland SonarQube API from rogueone (2026-10-02).

    sonar_api.py gate [projectKey]          # why the quality gate passed/failed: conditions + new-code issues + hotspots
    sonar_api.py review-safe <file> <reason> # mark that file's new-code hotspots REVIEWED/SAFE, reason as comment
    sonar_api.py precheck <file> [file ...]  # scan files in a throwaway project BEFORE handoff (the CI gate's rules)
    sonar_api.py <api-path> [key=value ...]  # any GET, raw JSON — e.g. rules/search activation=true languages=py,java

Reaches Sonar through the LAN NodePort `sonarqube-api-lan` (mother.weyland.lab:30969 -> sonarqube:9000) as `admin`, with
the password from SONAR_ADMIN_PW in the gitignored scripts/.env — load it first, never paste it:
    set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a
The password is only ever sent as a Basic-auth header; it is never printed.

Why this exists: the runbook command it replaces curled from INSIDE the sonarqube pod with `$SONAR_ADMIN_PW`, which the
pod does not carry — it returned 401, so it had never worked. Exit: 0 ok / gate passed · 1 gate FAILED · 2 cannot read.
precheck exits 0 clean · 1 issues or hotspots found (named) · 2 could not scan (missing file, scanner failure, nothing
analysed, or a cleanup that left the project or token behind).
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

# Plain HTTP on purpose — the NodePort is the ONLY machine path: the HTTPS ingress (sonarqube.weyland.lab) is behind
# Keycloak forward-auth and answers an API call with a 307 to the browser login. LAN-only; reviewed SAFE in Sonar.
SONAR_URL = os.environ.get("SONAR_URL", "http://mother.weyland.lab:30969").rstrip("/")
PROJECT = "weyland-lab"
HOTSPOTS = "hotspots/search"
ISSUES = "issues/search"


class CannotRead(Exception):
    pass


def _call(method: str, path: str, params: dict) -> dict:
    pw = os.environ.get("SONAR_ADMIN_PW")
    if not pw:
        raise CannotRead("SONAR_ADMIN_PW is not set — load scripts/.env first (set -a && . scripts/.env && set +a)")
    query = urllib.parse.urlencode(params)
    url = f"{SONAR_URL}/api/{path.strip('/')}" + (f"?{query}" if method == "GET" else "")
    auth = base64.b64encode(f"admin:{pw}".encode()).decode()
    data = query.encode() if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return json.loads(body) if body else {}   # a POST answers 204 with no body
    except urllib.error.HTTPError as exc:
        raise CannotRead(f"{method} /api/{path} -> HTTP {exc.code}: {exc.read()[:300]!r}") from exc
    except (OSError, ValueError) as exc:   # OSError covers urllib.error.URLError
        raise CannotRead(f"{method} /api/{path} failed: {exc}") from exc


def get(path: str, params: dict) -> dict:
    return _call("GET", path, params)


def review_safe(path: str, reason: str, project: str = PROJECT) -> int:
    """Mark every new-code TO_REVIEW hotspot in `path` REVIEWED/SAFE, with `reason` as the review comment."""
    hs = get(HOTSPOTS, {"projectKey": project, "inNewCodePeriod": "true", "status": "TO_REVIEW", "ps": 100})
    mine = [h for h in hs.get("hotspots", []) if h["component"].split(":", 1)[-1] == path]
    if not mine:
        print(f"sonar_api: no new-code hotspots to review in {path}", file=sys.stderr)
        return 2
    for h in mine:
        _call("POST", "hotspots/change_status",
              {"hotspot": h["key"], "status": "REVIEWED", "resolution": "SAFE", "comment": reason})
        print(f"reviewed SAFE {path}:{h.get('line', '?')} {h['key']}")
    return 0


def gate(project: str) -> int:
    st = get("qualitygates/project_status", {"projectKey": project})["projectStatus"]
    print(f"gate {project}: {st['status']}")
    for c in st.get("conditions", []):
        print(f"  {c['status']} {c['metricKey']} {c.get('actualValue')} ({c.get('comparator')} {c.get('errorThreshold')})")
    iss = get(ISSUES, {"componentKeys": project, "inNewCodePeriod": "true", "resolved": "false", "ps": 100})
    print(f"new-code issues: {iss['total']}")
    for i in iss["issues"]:
        where = f"{i['component'].split(':', 1)[-1]}:{i.get('line', '?')}"
        print(f"  {i['severity']} {i['rule']} {where} — {i['message'][:120]}")
    hs = get(HOTSPOTS, {"projectKey": project, "inNewCodePeriod": "true", "status": "TO_REVIEW", "ps": 50})
    print(f"hotspots to review: {hs['paging']['total']}")
    for h in hs.get("hotspots", []):
        print(f"  {h['vulnerabilityProbability']} {h['component'].split(':', 1)[-1]}:{h.get('line', '?')} — {h['message'][:120]}")
    return 0 if st["status"] == "OK" else 1


SCANNER_IMAGE = "sonarsource/sonar-scanner-cli:latest"   # the image the CI sonar-gate step runs
# File types the server's analysers never index (no shell/bats/Markdown/data analyser on this Community server).
NOT_ANALYSED = frozenset({".sh", ".bash", ".bats", ".md", ".txt", ".tsv", ".csv", ".service", ".timer", ".conf"})


def _run_scanner(src: str, key: str, token: str) -> tuple:
    """sonar-scanner over `src` as project `key`; returns (exit code, output). Host network: the container must resolve
    mother.weyland.lab (on the default bridge it could not, 2026-10-12). Runs as the invoking user; token via env."""
    cmd = ["docker", "run", "--rm", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}",
           "-e", "SONAR_TOKEN", "-e", "HOME=/tmp", "-v", f"{src}:/usr/src", SCANNER_IMAGE,
           f"-Dsonar.projectKey={key}", f"-Dsonar.host.url={SONAR_URL}", "-Dsonar.python.version=3.12",
           "-Dsonar.working.directory=/tmp/.scannerwork"]
    r = subprocess.run(cmd, env=dict(os.environ, SONAR_TOKEN=token), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def _await_analysis(key: str, timeout: int = 300, poll: int = 3) -> str:
    """Wait for Sonar to PROCESS the uploaded report: the scanner returns at upload, and a read before processing finds
    a project with 0 files (2026-10-13). Returns the final task status, or "TIMEOUT"."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ce = get("ce/component", {"component": key})
        current = ce.get("current") or {}
        if not ce.get("queue") and current.get("status"):
            return current["status"]
        time.sleep(poll)
    return "TIMEOUT"


def _scan_and_report(src: str, key: str, token: str) -> int:
    rc, output = _run_scanner(src, key, token)
    if rc != 0:
        errors = [ln for ln in output.splitlines() if "ERROR" in ln] or output.splitlines()[-5:]
        print("sonar_api: precheck scanner failed (exit %d):\n  %s" % (rc, "\n  ".join(errors)), file=sys.stderr)
        return 2
    status = _await_analysis(key)
    if status != "SUCCESS":
        print(f"sonar_api: precheck analysis did not complete: {status}", file=sys.stderr)
        return 2
    measures = get("measures/component", {"component": key, "metricKeys": "files"})["component"]["measures"]
    scanned = int(next((m["value"] for m in measures if m["metric"] == "files"), "0"))
    if scanned == 0:
        print("sonar_api: precheck scanned 0 files — analysed nothing, which is not clean", file=sys.stderr)
        return 2
    new_iss, open_iss = _split_open(get(ISSUES, {"componentKeys": key, "resolved": "false", "ps": 500})
                                    .get("issues", []))
    for i in new_iss:
        print(f"  {i['severity']} {i['rule']} {_path(i)}:{i.get('line', '?')} — {i['message'][:120]}")
    for i in open_iss:
        print(f"  already open on {PROJECT}: {_path(i)}:{i.get('line', '?')} — {i['rule']} {i['message'][:100]}")
    new_hs, known, open_hs = _split_reviewed(get(HOTSPOTS, {"projectKey": key, "ps": 500}).get("hotspots", []))
    for h in new_hs:
        print(f"  {h['vulnerabilityProbability']} {_path(h)}:{h.get('line', '?')} — {h['message'][:120]}")
    for h in known:
        print(f"  already reviewed SAFE on {PROJECT}: {_path(h)}:{h.get('line', '?')} — {h['message'][:120]}")
    for h in open_hs:
        print(f"  already open on {PROJECT}: {_path(h)}:{h.get('line', '?')} — {h['message'][:120]}")
    verdict = "clean" if not new_iss and not new_hs else "FINDINGS"
    tail = "".join(f", {n} {what}" for n, what in ((len(open_iss) + len(open_hs), "already open"),
                                                  (len(known), "already reviewed")) if n)
    print(f"precheck: {verdict} ({scanned} files scanned, {len(new_iss)} issues, {len(new_hs)} hotspots{tail})")
    return 0 if verdict == "clean" else 1


def _path(finding: dict) -> str:
    return finding["component"].split(":", 1)[-1]


def _split_open(issues: list) -> tuple:
    """(new, already open on the real project). A scratch project has no new-code period, so an edit to a big file
    reports every finding the file already has — 19 for a 3-line change to one service (2026-10-13, B207). Those are
    the CI gate's OLD code, not this change's; matched on file + rule + message (lines move)."""
    if not issues:
        return [], []
    keys = ",".join(sorted({f"{PROJECT}:{_path(i)}" for i in issues}))
    live = get(ISSUES, {"componentKeys": keys, "resolved": "false", "ps": 500}).get("issues", [])
    seen = {(_path(i), i.get("rule"), i.get("message")) for i in live}
    new = [i for i in issues if (_path(i), i.get("rule"), i.get("message")) not in seen]
    return new, [i for i in issues if i not in new]


def _split_reviewed(hotspots: list) -> tuple:
    """(new, already reviewed SAFE, already open TO_REVIEW) against the real project. A scratch project knows no
    review history, so a hotspot reviewed SAFE on weyland-lab comes back every time, and one still TO_REVIEW there is
    old code, not this change's (11 on one service, 2026-10-13). Lines move, so the match is file + rule + message;
    a second identical hotspot added to the same file is masked here, and the CI gate still sees it."""
    if not hotspots:
        return [], [], []
    files = ",".join(sorted({_path(h) for h in hotspots}))

    def keys(params):
        return {(_path(h), h.get("ruleKey"), h.get("message"))
                for h in get(HOTSPOTS, {"projectKey": PROJECT, "files": files, "ps": 500, **params}).get("hotspots", [])}
    safe, to_review = keys({"status": "REVIEWED", "resolution": "SAFE"}), keys({"status": "TO_REVIEW"})
    new, known, open_ = [], [], []
    for h in hotspots:
        k = (_path(h), h.get("ruleKey"), h.get("message"))
        if k in safe:
            known.append(h)
        elif k in to_review:
            open_.append(h)
        else:
            new.append(h)
    return new, known, open_


def precheck(files: list) -> int:
    """Scan `files` in a throwaway project with the server's default profiles (the ones weyland-lab uses) and report
    every finding. The verdict is the findings, never the scratch project's gate: a first analysis has no new-code
    period, so that gate passed with a CRITICAL issue open (2026-10-12). Project and token are always removed."""
    if not files:
        print("sonar_api: precheck <file> [file ...] — name the changed files", file=sys.stderr)
        return 2
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        print(f"sonar_api: precheck: not a file: {', '.join(missing)}", file=sys.stderr)
        return 2
    # Only KNOWN non-analysed types skip the scan; anything else is scanned, and 0 files analysed then fails closed.
    # A shell + Markdown change otherwise could never print `clean` (2026-10-13).
    exts = {os.path.splitext(f)[1].lower() for f in files}
    if exts <= NOT_ANALYSED:
        print(f"precheck: nothing for Sonar to analyse ({len(files)} files: {' '.join(sorted(exts))})")
        return 0
    key = f"{PROJECT}-precheck-{os.getpid()}"
    with tempfile.TemporaryDirectory(prefix="sonar-precheck-") as src:
        for f in files:                            # keep repo-relative paths so findings name the real file
            rel = os.path.relpath(f)
            rel = os.path.basename(f) if rel.startswith("..") else rel
            os.makedirs(os.path.join(src, os.path.dirname(rel)), exist_ok=True)
            shutil.copy(f, os.path.join(src, rel))
        token = _call("POST", "user_tokens/generate", {"name": key})["token"]
        try:
            result = _scan_and_report(src, key, token)
        finally:
            cleaned = _precheck_cleanup(key) == 0
    return result if cleaned else 2


def _precheck_cleanup(key: str) -> int:
    """Delete the scratch project (absent is fine: a failed scan never created it) and revoke the token (must work)."""
    try:
        _call("POST", "projects/delete", {"project": key})
    except CannotRead as exc:
        if "404" not in str(exc):
            print(f"sonar_api: precheck could not delete project {key}: {exc}", file=sys.stderr)
            return 2
    try:
        _call("POST", "user_tokens/revoke", {"name": key})
    except CannotRead as exc:
        print(f"sonar_api: precheck could not revoke token {key} — revoke it in Sonar (My Account → Security): {exc}",
              file=sys.stderr)
        return 2
    return 0


def main(argv: list) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        if argv[0] == "gate":
            return gate(argv[1] if len(argv) > 1 else PROJECT)
        if argv[0] == "precheck":
            return precheck(argv[1:])
        if argv[0] == "review-safe":
            if len(argv) < 3 or not argv[2].strip():
                print("sonar_api: review-safe <file> <reason> — a reason is required (it is the review record)",
                      file=sys.stderr)
                return 2
            return review_safe(argv[1], " ".join(argv[2:]))
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
