#!/usr/bin/env python3
"""Print the lab's command roster, generated from docs/runbooks/*.md (the `lab-commands` / `lab-ask` shortcuts).

  usage: lab_commands.py [--root DIR] [--grep WORD ...]      the roster, or only entries matching every WORD
         lab_commands.py [--root DIR] --prompt QUESTION...  the `claude -p` payload for `lab-ask`

Exit codes: 0 printed; 1 --grep matched nothing (a finding: the runbooks have no such command); 2 could not do the
job (no runbooks, or runbooks with no commands at all). Runbook: docs/runbooks/research-scratch-vault.md § Shortcuts.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import lab_commands as lc  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
EXTRA_SOURCES = ["docs/dr.md"]  # read alongside docs/runbooks/*.md


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=REPO)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--grep", nargs="+", metavar="WORD")
    mode.add_argument("--prompt", nargs="+", metavar="QUESTION")
    a = ap.parse_args()

    files = sorted((a.root / "docs" / "runbooks").glob("*.md"))
    if not files:
        print(f"lab-commands: no runbooks under {a.root / 'docs' / 'runbooks'}", file=sys.stderr)
        return 2
    # The DR catalog holds the restore procedures (B239): without it "how do I restore X" has no answer.
    files += [a.root / rel for rel in EXTRA_SOURCES if (a.root / rel).is_file()]
    entries = []
    for f in files:
        entries.extend(lc.extract(f.read_text(encoding="utf-8"), f.relative_to(a.root).as_posix()))
    if not entries:
        print(f"lab-commands: no commands found in {len(files)} runbook(s); the extractor or the runbooks broke",
              file=sys.stderr)
        return 2

    if a.prompt:
        sys.stdout.write(lc.prompt(" ".join(a.prompt), lc.render(entries)))
        return 0
    if a.grep:
        entries = lc.grep(entries, a.grep)
        if not entries:
            print(f"lab-commands: no command matches {' '.join(a.grep)!r} (try fewer words, or `lab-ask`)",
                  file=sys.stderr)
            return 1
    sys.stdout.write(lc.render(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
