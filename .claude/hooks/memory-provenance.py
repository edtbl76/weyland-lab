#!/usr/bin/env python3
"""memory-provenance.py — Claude Code PostToolUse hook (Write|Edit|MultiEdit), B256 (2026-11-23).

Claude Code writes its memory as plain files straight into the shared store (its memory path is a symlink to
~/agent-memory/weyland), so those writes bypass the governed gateway that stamps every other agent's (shared-context
design, ADR-0019). This hook gives them the same provenance: after a write to a note in the store it adds
`created_by` / `created_at` / `author_kind` / `source` when the note has no author yet, and always sets `updated_by`,
`updated_at` and `on_behalf_of`. The owner chose this (option A, 2026-11-23): your own agent on your own machine is
stamped locally; everyone else goes through the gateway.

Skipped: the two index files (MEMORY.md, MEMORY-catalog.md), the health check's `_check/` notes, non-Markdown files and
anything outside the store. Every failure is silent, exit 0 (a hook must never break a write): check-shared-memory.py
flags any note changed after provenance began without `updated_by`, which also catches writes made around this hook
(Bash edits never reach it). Tests: scripts/tests/test_memory_provenance.py. Runbook: docs/runbooks/shared-agent-memory.md.
"""
import datetime
import json
import os
import re
import sys

STORE = "/home/edwardmangini/agent-memory/weyland"
PERSON = "emangini"   # the owner's Keycloak username: the same identity the gateway stamps
AGENT = "agent:claude-code"
INDEX_FILES = {"MEMORY.md", "MEMORY-catalog.md"}
_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def should_stamp(path: str, store: str) -> bool:
    real, root = os.path.realpath(path), os.path.realpath(store)
    if not real.endswith(".md") or not real.startswith(root + os.sep):
        return False
    rel = os.path.relpath(real, root)
    return rel not in INDEX_FILES and not rel.startswith("_check" + os.sep)


def _upsert(lines: list, key: str, value: str) -> None:
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[i] = f"{key}: {value}"
            return
    lines.append(f"{key}: {value}")


def stamp(text: str, *, now: str, session: str, person: str) -> str:
    m = _FRONT.match(text)
    lines = m.group(1).splitlines() if m else []
    body = text[m.end():] if m else text
    if not any(line.startswith("created_by:") for line in lines):
        _upsert(lines, "created_by", AGENT)
        _upsert(lines, "created_at", f"'{now}'")
        _upsert(lines, "author_kind", "agent")
        _upsert(lines, "source", f"session:{session}")
    _upsert(lines, "updated_by", AGENT)
    _upsert(lines, "updated_at", f"'{now}'")
    _upsert(lines, "on_behalf_of", f"user:{person}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def main() -> int:
    try:
        event = json.load(sys.stdin)
        path = (event.get("tool_input") or {}).get("file_path") or ""
        store = os.environ.get("MEMORY_PROVENANCE_DIR", STORE)
        if not path or not should_stamp(path, store) or not os.path.isfile(path):
            return 0
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        new = stamp(text, now=now, session=event.get("session_id") or "unknown", person=PERSON)
        if new != text:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
    except Exception:   # a hook must never break a write; the watchdog check catches an unstamped note
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
