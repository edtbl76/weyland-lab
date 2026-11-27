"""v2_smoke — the deep contract v2 smoke sequence, framework-neutral (B260; shared by every Python path, B261).

A path's smoke.py starts its own server and calls run(command). The sequence: /ready, /hello, then create → get →
list → 404 envelope → 422 envelope → X-Request-ID echo. Stdlib-only (urllib), so it needs nothing beyond the image.
Exit 0 every step held, or 1 with the first failing step.

SOURCE: golden-paths-shared/python/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = 8080
BASE = f"http://127.0.0.1:{PORT}"


def _call(method, path, body=None, headers=None):
    """(status, headers, json body) for any status: a 4xx is an answer here, not an exception."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:  # nosec B310 — localhost, our own server
            return r.status, r.headers, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.headers, json.loads(e.read().decode())


def _wait_ready(server) -> str | None:
    for _ in range(60):  # up to ~30s for the server to come up
        if server.poll() is not None:
            return "server exited during startup"
        try:
            if _call("GET", "/ready")[0] == 200:
                return None
        except OSError:
            pass
        time.sleep(0.5)
    return "/ready never became ready"


def v2_sequence() -> str | None:
    """The deep contract v2 smoke: the first failing step, or None when every step holds."""
    status, _, hello = _call("GET", "/hello")
    if status != 200 or hello.get("message") != "hello, weyland":
        return f"/hello returned {status} {hello}"
    status, _, item = _call("POST", "/items", {"name": "smoke", "tags": ["v2"]})
    if status != 201 or item.get("name") != "smoke":
        return f"create returned {status} {item}"
    status, _, got = _call("GET", f"/items/{item['id']}")
    if status != 200 or got != item:
        return f"get returned {status} {got}"
    status, _, page = _call("GET", "/items?limit=100")
    if status != 200 or item not in page.get("items", []):
        return f"list returned {status} {page}"
    status, _, missing = _call("GET", "/items/999999999")
    if status != 404 or missing.get("error", {}).get("code") != "not_found":
        return f"unknown item returned {status} {missing}"
    status, _, invalid = _call("POST", "/items", {"name": ""})
    if status != 422 or invalid.get("error", {}).get("code") != "validation_failed":
        return f"invalid body returned {status} {invalid}"
    status, headers, _ = _call("GET", "/health", headers={"X-Request-ID": "smoke-rid"})
    if headers.get("X-Request-ID") != "smoke-rid":
        return f"X-Request-ID was not echoed (got {headers.get('X-Request-ID')!r})"
    return None


def run(command: list[str]) -> int:
    """Start the path's server with `command`, run the v2 sequence against it, stop it; the exit code."""
    server = subprocess.Popen(command)
    try:
        problem = _wait_ready(server) or v2_sequence()
        if problem:
            print(f"SMOKE FAIL: {problem}", file=sys.stderr)
            return 1
        print("SMOKE OK: image serves — /ready, /hello and the deep contract v2 sequence")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()
