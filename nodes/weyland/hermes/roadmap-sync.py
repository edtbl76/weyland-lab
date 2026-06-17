#!/usr/bin/env python3
"""Sync docs/backlog.md (public repo) -> the Hermes `weyland-roadmap` Kanban board. One-way.

B27 (b) roadmap co-pilot. This is a **tracking mirror, not an execution queue**: every item is parked
`blocked` so the board dispatcher NEVER spawns a worker on a backlog item; DONE items are marked complete.
Re-runnable — `--idempotency-key <item_id>` dedups, so a second run updates status without creating
duplicates. The human owns backlog.md; Hermes reads/annotates the board. It never edits backlog.md.

Usage (on CT 104):  ./roadmap-sync.py            # fetch raw from GitHub
                    ./roadmap-sync.py <file>     # parse a local file instead (offline/testing)

Design: aidlc-docs/construction/b27-kanban-design.md.  Status detection is heuristic (the human's
backlog is the source of truth); the board is approximate tracking.
"""
import json
import re
import shutil
import subprocess
import sys
import urllib.request

RAW_URL = "https://raw.githubusercontent.com/edtbl76/weyland-lab/main/docs/backlog.md"
BOARD = "weyland-roadmap"
HERMES = shutil.which("hermes") or "/usr/local/bin/hermes"

# Matches the per-item detail headings only: '### B27 — Title', '### U13 — Title', '### B17+B19 — Title'.
# Non-item '### ' headings (Immediate, Platform Foundation, mother (k3s)...) don't match — they lack B/U<n>.
HEADING = re.compile(r"^###\s+((?:B|U)\d+(?:\+[A-Z]?\d+)?)\s+[—–-]\s+(.+?)\s*$")
# Status lives in the top "## DONE" bullets and the priority-list lines — where the item is the *subject*
# of a bullet/numbered line: '- **B5** — …' / '6. **B26** — …'. Only those count (an inline '→ **B34**'
# cross-reference on some other item's DONE line must NOT mark B34 done).
ID_SUBJECT = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\*\*((?:B|U)\d+(?:\+[A-Z]?\d+)?)\*\*\s*[—–-]")


def fetch(src: str) -> str:
    if src and src != "-":  # local-file override
        with open(src, encoding="utf-8") as fh:
            return fh.read()
    with urllib.request.urlopen(RAW_URL, timeout=30) as resp:
        return resp.read().decode("utf-8")


def sections(md: str):
    """Yield (item_id, title, body) for each detail section."""
    cur, buf = None, []
    for line in md.splitlines():
        m = HEADING.match(line)
        if m:
            if cur:
                yield cur[0], cur[1], "\n".join(buf)
            cur, buf = (m.group(1), m.group(2)), []
        elif cur is not None:
            buf.append(line)
    if cur:
        yield cur[0], cur[1], "\n".join(buf)


def _line_mark(line: str):
    if "DROPPED" in line:
        return "dropped"
    if "✅" in line or re.search(r"\bDONE\b", line):
        return "done"
    return None


def build_status_map(md: str) -> dict:
    """Resolve each item's status from every bold **id** mention across the doc (dropped > done)."""
    found: dict[str, set] = {}
    for line in md.splitlines():
        m = ID_SUBJECT.match(line)
        if not m:
            continue
        mark = _line_mark(line)
        if mark:
            found.setdefault(m.group(1), set()).add(mark)
    return {iid: ("dropped" if "dropped" in marks else "done") for iid, marks in found.items()}


def status_of(item_id: str, title: str, body: str, smap: dict) -> str:
    if item_id in smap:                       # doc-wide signal wins (top DONE list, priority markers)
        return smap[item_id]
    return _line_mark(title + "\n" + body[:400]) or "active"   # fallback to the detail body


def hk(*args, board=True):
    cmd = [HERMES, "kanban"] + (["--board", BOARD] if board else []) + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def upsert(item_id: str, title: str, status: str):
    full = f"{item_id} — {title}"
    # Parked blocked: a tracking card the dispatcher won't action. idempotency-key => re-run is an upsert.
    r = hk("create", "--idempotency-key", item_id, "--initial-status", "blocked", "--json", full)
    if r.returncode != 0:
        print(f"  ! create {item_id} failed: {r.stderr.strip()[:120]}")
        return
    try:
        task_id = json.loads(r.stdout).get("id")
    except Exception:
        task_id = None
    if status == "done" and task_id is not None:
        c = hk("complete", str(task_id))
        if c.returncode != 0:
            print(f"  ! complete {item_id} failed: {c.stderr.strip()[:120]}")


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    md = fetch(src)
    smap = build_status_map(md)
    hk("boards", "create", BOARD, board=False)  # idempotent: tolerate already-exists
    counts = {"done": 0, "active": 0, "dropped": 0}
    for item_id, title, body in sections(md):
        st = status_of(item_id, title, body, smap)
        counts[st] += 1
        if st == "dropped":
            continue  # don't mirror dropped items onto the board
        upsert(item_id, title, st)
        print(f"  {item_id:8} {st:7} {title[:60]}")
    print(f"synced -> board '{BOARD}': {counts}")


if __name__ == "__main__":
    main()
