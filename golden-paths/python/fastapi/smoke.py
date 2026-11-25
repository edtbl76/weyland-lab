"""Ephemeral smoke — proves the BUILT image actually serves, run-to-completion (B153; deep contract v2, B260).

The `golden-python-fastapi` k8s Job runs `python smoke.py`: it starts the real uvicorn server the image ships, polls
`/ready`, asserts `/hello`, then the deep contract v2 sequence (create → get → list → 404 envelope → 422 envelope →
X-Request-ID echo), tears the server down, and exits 0 (or 1 with the failing step). Stdlib-only (urllib), so it
needs nothing beyond the runtime image.
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


def main() -> int:
    server = subprocess.Popen(["uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)])
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


if __name__ == "__main__":
    sys.exit(main())
