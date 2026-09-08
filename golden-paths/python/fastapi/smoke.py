"""Ephemeral smoke — proves the BUILT image actually serves, run-to-completion (B153).

The `golden-python-fastapi` k8s Job runs `python smoke.py`: it starts the real uvicorn server the image
ships, polls `/ready`, asserts `/hello`'s known payload, tears the server down, and exits 0 (or 1). This
is the "spin up to exercise, then tear down" loop — it proves the image runs on the platform without
deploying it as a Deployment. Stdlib-only (urllib), so it needs nothing beyond the runtime image.
"""
import json
import subprocess
import sys
import time
import urllib.request

PORT = 8080
BASE = f"http://127.0.0.1:{PORT}"


def _get(path):
    with urllib.request.urlopen(BASE + path, timeout=2) as r:  # nosec B310 — localhost, our own server
        return json.loads(r.read().decode())


def main() -> int:
    server = subprocess.Popen(["uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)])
    try:
        for _ in range(60):  # up to ~30s for the server to come up
            if server.poll() is not None:
                print("SMOKE FAIL: server exited during startup", file=sys.stderr)
                return 1
            try:
                if _get("/ready").get("status") == "ready":
                    break
            except Exception:
                time.sleep(0.5)
        else:
            print("SMOKE FAIL: /ready never became ready", file=sys.stderr)
            return 1

        body = _get("/hello")
        if body.get("message") != "hello, weyland":
            print(f"SMOKE FAIL: /hello returned {body}", file=sys.stderr)
            return 1
        print(f"SMOKE OK: image serves — /ready ok, /hello -> {body}")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except Exception:
            server.kill()


if __name__ == "__main__":
    sys.exit(main())
