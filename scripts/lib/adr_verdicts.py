"""adr_verdicts.py — what counts as a decision verdict in docs/backlog.md (B250, 2026-11-19).

ONE source for both readers, so they cannot drift apart:
  - scripts/check-adr.sh fails a backlog item closed after CUTOFF with a verdict and no ADR naming it;
  - .claude/hooks/adr-verdict-reminder.py reminds Claude Code the moment an edit adds a verdict.

A verdict is a marker word inside an item's closing status, "DONE <date> — <status>**", never in prose elsewhere:
"we rejected two designs" in a paragraph is not a decision record. The words are matched case-insensitively because
the backlog's real verdicts use both forms: "DONE 2026-11-03 — DON'T ADOPT" (B236) and "DONE 2026-11-14 — the `adr`
plugin; `git-adr` rejected" (B248). KEPT counts (B187 "scratch vault KEPT as a habit"): a partial adoption is still a
decision. Concept docs (docs/concepts/*) are covered through the backlog spike that produced them: their verdict tables
carry no date to scope by, and every concept verdict closes a backlog item.
"""
import os
import re

CUTOFF = "2026-11-13"   # B248 seeded the log from every decision closed before this date
MARKER = re.compile(r"(?i)\b(?:don['’]t adopt|won['’]t do|adopt(?:ed)?|reject(?:ed)?|kept)\b")
STATUS = re.compile(r"DONE (\d{4}-\d{2}-\d{2})([^*\n]*)")
ITEM = re.compile(r"^(?:### |- \*\*)(B\d+)\b")
B_REF = re.compile(r"\bB\d+\b")
HEAD_CHARS = 600         # an item's status sits in its heading; later text in the same line is history, not status


def verdict_count(text: str) -> int:
    """How many DONE statuses in `text` carry a verdict marker (the hook compares this before and after an edit)."""
    return sum(1 for m in STATUS.finditer(text or "") if MARKER.search(m.group(2)))


def closed_items(backlog_text: str):
    """(item, date, status, is_verdict) for every backlog item whose heading says DONE <date>."""
    out = []
    for line in backlog_text.splitlines():
        item = ITEM.match(line)
        if not item:
            continue
        done = STATUS.search(line[:HEAD_CHARS])
        if done:
            out.append((item.group(1), done.group(1), done.group(2).strip(" —:-"), bool(MARKER.search(done.group(2)))))
    return out


def adr_refs(adr_dir: str) -> set:
    """B-numbers each ADR names under '## More Information' (where an ADR links the decision it records)."""
    refs = set()
    for f in sorted(os.listdir(adr_dir)):
        if not re.match(r"^\d{4}-.*\.md$", f):
            continue
        section = False
        for line in open(os.path.join(adr_dir, f), encoding="utf-8"):
            if line.startswith("## "):
                section = line.strip() == "## More Information"
            elif section:
                refs.update(B_REF.findall(line))
    return refs


def missing_adrs(backlog_text: str, adr_dir: str):
    """(closed since CUTOFF, verdicts among them, the verdict items no ADR names)."""
    recent = [c for c in closed_items(backlog_text) if c[1] >= CUTOFF]
    verdicts = [c for c in recent if c[3]]
    named = adr_refs(adr_dir)
    return recent, verdicts, [c for c in verdicts if c[0] not in named]
