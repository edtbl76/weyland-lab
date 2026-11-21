#!/usr/bin/env python3
"""check-harness-budget.py — the instruction text every Claude Code session here loads stays within budget (B255).

Measured 2026-11-20 (docs/concepts/context-engineering.md): a fresh session in this repo starts at ~61k tokens, ~49k
of it ours. That day's trims (memory index split, AI-DLC ambient import cut to team.md + project.md, compact
instructions added) are kept by this guard, which follows Claude Code's own loading rules:
  * CLAUDE.md and its @-imports, recursively (relative to the importing file, each file counted once);
  * every .claude/rules/*.md without a `paths:` scope (path-scoped rules load only when matching files are touched);
  * HTML comments stripped (Claude Code strips them before loading, so they cost nothing);
  * plus the descriptions of project skills (.claude/skills/*/SKILL.md) and agents (.claude/agents/*.md), which list
    in every session.
Sizes are bytes of the text as loaded (deterministic; about 2.5-4 bytes a token). The memory index (MEMORY.md, outside
the repo) has its own budget in scripts/check-shared-memory.py. Over budget: move detail to a file loaded on demand
(a skill, a runbook, a path-scoped rule), or raise the budget here on purpose, with the reason.

  usage: check-harness-budget.py [--root DIR]
  EXIT: 0 within budget · 1 over budget or a dangling import (named) · 2 cannot run (no CLAUDE.md)
"""
import argparse
import glob
import os
import re
import sys

# Today's sizes plus ~15% headroom (2026-11-20). Raise one only on purpose, with the reason in the commit.
BUDGETS = {
    "files": {"CLAUDE.md": 2_000, "AGENTS.md": 11_500, "aidlc/spaces/default/memory/project.md": 10_000,
              "aidlc/spaces/default/memory/team.md": 2_500},
    "instructions_total": 26_000,   # every loaded instruction file together
    "skills": 17_500,               # project skill descriptions
    "agents": 5_000,                # project agent descriptions
}
CLAUDE_MD = "CLAUDE.md"
CLAUDE_DIR = ".claude"
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_KEY = re.compile(r"^[A-Za-z_][\w-]*\s*:")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


def _loaded_text(path: str) -> str:
    return _COMMENT.sub("", open(path, encoding="utf-8").read())


def _entrypoints(root: str) -> list:
    rules = []
    for p in sorted(glob.glob(os.path.join(root, CLAUDE_DIR, "rules", "*.md"))):
        fm = _FRONTMATTER.match(open(p, encoding="utf-8").read())
        if not (fm and re.search(r"^paths\s*:", fm.group(1), re.M)):
            rules.append(os.path.relpath(p, root))
    return [CLAUDE_MD] + rules


def _walk(root: str):
    """Yield (relpath, bytes_loaded_or_None) in load order; None marks an import that does not exist."""
    seen = set()
    stack = list(reversed(_entrypoints(root)))
    while stack:
        rel = stack.pop()
        if rel in seen:
            continue
        seen.add(rel)
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            yield rel, None
            continue
        text = _loaded_text(full)
        yield rel, len(text.encode("utf-8"))
        imports = [ln[1:].strip() for ln in text.splitlines() if ln.startswith("@") and len(ln) > 1]
        base = os.path.dirname(rel)
        for imp in reversed(imports):
            stack.append(os.path.normpath(os.path.join(base, imp)))


def loaded_files(root: str) -> list:
    return [(rel, size) for rel, size in _walk(root) if size is not None]


def _description(frontmatter: str) -> str:
    """The `description:` value, including continuation lines, up to the next top-level key."""
    lines, out = frontmatter.splitlines(), []
    for i, line in enumerate(lines):
        if line.startswith("description:"):
            out.append(line[len("description:"):].strip())
            for nxt in lines[i + 1:]:
                if _KEY.match(nxt):
                    break
                out.append(nxt.strip())
            break
    return " ".join(x for x in out if x)


def description_bytes(root: str, kind: str) -> int:
    pattern = os.path.join(root, CLAUDE_DIR, "skills", "*", "SKILL.md") if kind == "skills" else \
        os.path.join(root, CLAUDE_DIR, "agents", "*.md")
    total = 0
    for p in glob.glob(pattern):
        fm = _FRONTMATTER.match(open(p, encoding="utf-8").read())
        if fm:
            total += len(_description(fm.group(1)).encode("utf-8"))
    return total


def problems(root: str, budgets: dict = BUDGETS) -> list:
    out = []
    files = list(_walk(root))
    for rel, size in files:
        if size is None:
            out.append(f"{rel} is imported but does not exist")
        elif rel in budgets["files"] and size > budgets["files"][rel]:
            out.append(f"{rel} is {size} bytes, over its {budgets['files'][rel]}-byte budget")
    total = sum(s for _, s in files if s is not None)
    if total > budgets["instructions_total"]:
        out.append(f"instructions total {total} bytes, over its {budgets['instructions_total']}-byte budget")
    for kind in ("skills", "agents"):
        b = description_bytes(root, kind)
        if b > budgets[kind]:
            out.append(f"project {kind} descriptions {b} bytes, over their {budgets[kind]}-byte budget")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    a = ap.parse_args(argv)
    if not os.path.isfile(os.path.join(a.root, CLAUDE_MD)):
        print(f"harness-budget: no CLAUDE.md under {a.root}; nothing measured (not a pass)", file=sys.stderr)
        return 2
    found = problems(a.root)
    if found:
        for p in found:
            print(f"harness-budget: OVER — {p}")
        return 1
    total = sum(s for _, s in loaded_files(a.root))
    print(f"harness-budget: OK — instructions {total}/{BUDGETS['instructions_total']} bytes "
          f"({len(loaded_files(a.root))} files), skills {description_bytes(a.root, 'skills')}/{BUDGETS['skills']}, "
          f"agents {description_bytes(a.root, 'agents')}/{BUDGETS['agents']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
