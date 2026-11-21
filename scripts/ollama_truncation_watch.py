#!/usr/bin/env python3
"""ollama_truncation_watch.py — alert when Ollama on rogueone silently truncates a prompt (B255, 2026-11-20).

Ollama cuts a prompt longer than the model's window and returns a normal answer: no error reaches the caller. Its only
reliable trace is a WARN line in its journal, `truncating input prompt limit=<kept> prompt=<sent> ...`; the request's
closing `truncated = 0|1` is NOT reliable (it read 0 on a request that had just lost 2,593 of 4,643 tokens). Found by
B255: the tool-server RAG ran at the 4,096 default for months (fixed with gpt-oss:20b-rag), and the Langfuse judge cuts
large RAG traces. Fix a hit with a Modelfile variant per caller (docs/runbooks/model-serving-ollama.md § Window
variants); the front door's access log (`docker logs ollama-proxy`) names the caller.

Run by the user timer nodes/rogueone/systemd/ollama-truncation-watch.timer every 15 min over the last 16 min, pushing
the verdict to an Uptime Kuma push monitor (KUMA_OLLAMA_TRUNC_PUSH_URL, read from scripts/.env and nothing else from it):
any truncation is DOWN; an unreadable journal is DOWN, never UP; no heartbeat (URL unset, Kuma unreachable, timer dead)
alerts as a missed heartbeat. Runbook: docs/runbooks/model-serving-ollama.md § Truncation watch.

  usage: ollama_truncation_watch.py [--window MINUTES] [--dry-run]
  EXIT: 0 up · 1 down (named) · 2 could not report
"""
import argparse
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ENV_FILE = os.path.expanduser("~/IdeaProjects/weyland/scripts/.env")
ENV_KEY = "KUMA_OLLAMA_TRUNC_PUSH_URL"
_CUT = re.compile(r'msg="truncating input prompt".*?\blimit=(\d+)\s+prompt=(\d+)')


def parse(text: str) -> list:
    """Every truncation in the journal text: the tokens sent and the tokens the model kept."""
    return [{"prompt": int(m.group(2)), "kept": int(m.group(1))} for m in _CUT.finditer(text)]


def verdict(cuts: list, window_min: int) -> tuple:
    if not cuts:
        return "up", f"no prompt truncated in the last {window_min} min"
    worst = max(cuts, key=lambda c: c["prompt"] - c["kept"])
    return "down", (f"{len(cuts)} prompt(s) truncated in the last {window_min} min; worst: {worst['prompt']} tokens sent, "
                    f"{worst['kept']} kept. Caller: docker logs ollama-proxy at that time")


def read_journal(window_min: int) -> str:
    out = subprocess.run(["journalctl", "-u", "ollama", "--since", f"-{window_min}min", "--no-pager", "-o", "cat"],
                         capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise OSError(f"journalctl exited {out.returncode}: {out.stderr.strip()[:200]}")
    return out.stdout


def check(window_min: int) -> tuple:
    try:
        text = read_journal(window_min)
    except Exception as exc:   # an unreadable journal verifies nothing: report it as down, never as up
        return "down", f"could not read the ollama journal: {exc}"
    return verdict(parse(text), window_min)


def push_url() -> str:
    try:
        for line in open(ENV_FILE, encoding="utf-8"):
            if line.startswith(ENV_KEY + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--window", type=int, default=16)
    ap.add_argument("--dry-run", action="store_true", help="print the verdict; push nothing")
    a = ap.parse_args(argv)
    status, msg = check(a.window)
    print(f"{status}: {msg}")
    if a.dry_run:
        return 0 if status == "up" else 1
    url = push_url()
    if not url:
        print(f"{ENV_KEY} unset in {ENV_FILE}: verdict NOT reported; the Kuma heartbeat will go missing", file=sys.stderr)
        return 2
    try:
        urllib.request.urlopen(f"{url}?status={status}&msg={urllib.parse.quote(msg[:250])}", timeout=15).read()
    except Exception as exc:
        print(f"could not reach Kuma ({exc}); the push monitor will alert on the missed heartbeat", file=sys.stderr)
        return 2
    return 0 if status == "up" else 1


if __name__ == "__main__":
    sys.exit(main())
