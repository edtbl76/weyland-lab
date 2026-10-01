"""Readiness heartbeat for the rag-index consumers (2026-10-01).

The consumers have no HTTP server, so without this `Ready` meant only "PID 1 is alive" — and ship-images' SMOKE gate
refuses a workload whose readiness proves nothing. consumer.py calls `beat()` on every pass of its poll loop (poll
times out every second, so the loop passes even with no traffic), but only AFTER the store handler is ensured and the
topic subscribed. The Deployment's readinessProbe runs `python heartbeat.py check`:

    Ready  = connected + subscribed + the loop passed within MAX_AGE seconds
    not Ready = still starting, or the loop is wedged (stopped polling)

Dependency-free on purpose: the probe runs it every few seconds inside the consumer's container.
"""
import os
import sys
import time
from pathlib import Path

# In the app's own directory (owned by the non-root app user), NOT /tmp: a world-writable directory would let any
# process create or touch the file and fake readiness (Sonar S5443).
PATH = os.environ.get("RAG_INDEX_HEARTBEAT", "/app/.heartbeat")
MAX_AGE = 60


def beat(path=None):
    """Touch the heartbeat file (create it on the first beat)."""
    Path(path or PATH).touch()   # creates on the first beat, bumps the mtime after


def is_fresh(path=None, max_age=MAX_AGE):
    """True when the heartbeat was touched within `max_age` seconds; a missing file is not fresh."""
    try:
        return time.time() - os.path.getmtime(path or PATH) <= max_age
    except OSError:
        return False


def main(argv):
    if argv == ["check"]:
        return 0 if is_fresh(os.environ.get("RAG_INDEX_HEARTBEAT", PATH)) else 1
    print("usage: heartbeat.py check", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
