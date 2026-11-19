#!/usr/bin/env python3
"""adr-verdict-reminder.py — Claude Code PostToolUse hook (Edit|MultiEdit|Write), B250 (2026-11-19).

When an edit ADDS a decision verdict to docs/backlog.md or docs/concepts/*, return additionalContext reminding the
agent that AGENTS.md wants an ADR for it (/adr:new, or /adr:supersede for a reversal). A reminder only: it never
blocks, calls no model and starts no agent. Not part of the AI-DLC engine (those hooks are aidlc-*.ts).

"Adds" is a count, before against after, so editing an item that already carries its verdict stays silent:
  Edit/MultiEdit — old_string against new_string; Write — the git HEAD version against the new content.
In the backlog a verdict is a marker in an item's DONE status (scripts/lib/adr_verdicts.py, shared with
scripts/check-adr.sh so the two cannot drift); a concept doc has no DONE status, so any marker word counts there.
Every failure (bad input, no git, no HEAD copy) is silent, exit 0: the CI guard still catches the missing ADR.
Edits made through Bash (python3/sed) never reach this hook; the guard covers those too. Tests:
scripts/tests/adr-verdict-reminder.bats. Runbook: docs/runbooks/adr.md § The verdict reminder hook.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "lib"))
import adr_verdicts  # noqa: E402

REMINDER = ("This edit records a decision verdict in {path}. AGENTS.md: a spike or investigation that reaches an "
            "ADOPT or DON'T ADOPT verdict gets an ADR in docs/adr/ (/adr:new; /adr:supersede if it reverses an "
            "existing ADR), naming {what} under '## More Information', and the shared-memory note adr-log-b248 lists "
            "it. scripts/check-adr.sh fails CI on a post-2026-11-13 verdict that no ADR names.")


def target(path, root):
    """'backlog', 'concept' or None for the file being edited (relative to the project)."""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")
    if rel == "docs/backlog.md":
        return "backlog"
    if rel.startswith("docs/concepts/") and rel.endswith(".md"):
        return "concept"
    return None


def count(kind, text):
    if kind == "backlog":
        return adr_verdicts.verdict_count(text)
    return len(adr_verdicts.MARKER.findall(text or ""))


def head_version(path, root):
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")
    r = subprocess.run(["git", "-C", root, "show", f"HEAD:{rel}"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def added(tool, tin, kind, path, root):
    if tool == "Edit":
        return count(kind, tin.get("new_string")) > count(kind, tin.get("old_string"))
    if tool == "MultiEdit":
        edits = tin.get("edits") or []
        return (sum(count(kind, e.get("new_string")) for e in edits)
                > sum(count(kind, e.get("old_string")) for e in edits))
    if tool == "Write":
        return count(kind, tin.get("content")) > count(kind, head_version(path, root))
    return False


def main():
    try:
        data = json.load(sys.stdin)
        tool, tin = data.get("tool_name"), data.get("tool_input") or {}
        path = tin.get("file_path") or ""
        root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
        kind = target(path, root) if path else None
        if not kind:                         # every other file: return before reading anything else
            return 0
        if added(tool, tin, kind, path, root):
            rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
            what = "the item's B-number" if kind == "backlog" else "this concept doc and its backlog item"
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                     "additionalContext": REMINDER.format(path=rel, what=what)}}))
    except Exception:  # noqa: BLE001 — a reminder hook must never break or block an edit
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
