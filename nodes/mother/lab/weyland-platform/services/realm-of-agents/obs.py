"""Live step logging → stdout, so `kubectl logs -f deploy/realm-of-agents` shows the delegation moving in real time.

Until the streaming UI exists, this is how you 'hear the bytes move': every routing decision, every delegation, and
every agent's start/finish prints the moment it happens (flushed). Run the request in one pane and tail logs in another."""
import sys


def log(msg: str) -> None:
    print(f"[realm] {msg}", flush=True, file=sys.stdout)
