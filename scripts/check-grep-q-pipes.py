#!/usr/bin/env python3
"""check-grep-q-pipes.py — no `producer | grep -q` in shell that sets pipefail (B271, 2026-11-27).

The race: `grep -q` exits at its first match; the producer, still writing, dies of SIGPIPE; `pipefail` then fails the
pipeline although the match WAS found. Timing decides it, so it shows up as a CI-only flake: the dagster-watchdog-budgets
guard reported a scheduled job as "no schedule" (B211, #399, #746), and run-lang-tests.sh could read a test failure as
a pass. Read the whole input instead: a here-string (`grep -q pattern <<<"$x"`), `awk`, or capture the producer's
output first.

Scans every .sh and every .yaml/.yml (embedded shell) under scripts/, nodes/ and eval/ that sets pipefail; flags a
`| grep` whose options include -q (any short-option cluster, or --quiet/--silent), never `||`, a here-string, -c/-l or
a comment. Exit 0 none · 1 a finding (file:line and the fix) · 2 nothing scanned (checking nothing is not a pass).
Tests: scripts/tests/test_check_grep_q_pipes.py. Rule: docs/runbooks/code-quality.md § Shell.
"""
import argparse
import pathlib
import re
import sys

ROOTS = ("scripts", "nodes", "eval")
SUFFIXES = {".sh", ".yaml", ".yml"}
SKIP = {".git", "node_modules", ".venv", "__pycache__", "charts"}
_PIPE_GREP = re.compile(r"(?<!\|)\|\s*grep\b(?P<rest>.*)")
_TAKES_ARG = {"-e", "-f", "-m", "-A", "-B", "-C", "--regexp", "--file", "--max-count"}


def _code(line: str) -> str:
    """The line without a leading comment (inline comments after code are rare and left in)."""
    return "" if line.lstrip().startswith("#") else line


def offending(line: str) -> bool:
    """True when the line pipes into grep with a quiet option."""
    for m in _PIPE_GREP.finditer(_code(line)):
        words = m.group("rest").split()
        i = 0
        while i < len(words) and words[i].startswith("-") and words[i] != "--":
            w = words[i]
            if w in ("--quiet", "--silent") or (not w.startswith("--") and "q" in w[1:]):
                return True
            i += 2 if w in _TAKES_ARG else 1          # the pattern after -e is not an option
        # first non-option word: the pattern; the pipe into grep has no -q before it
    return False


def _files(root: pathlib.Path):
    for top in ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in SUFFIXES and not (SKIP & set(p.relative_to(root).parts)):
                yield p


def scan(root: pathlib.Path) -> tuple:
    """(["path:line: text", ...], files scanned). Only files that set pipefail are checked."""
    findings, scanned = [], 0
    for p in _files(root):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "pipefail" not in text:
            continue
        scanned += 1
        for n, line in enumerate(text.splitlines(), 1):
            if offending(line):
                findings.append(f"{p.relative_to(root)}:{n}: {line.strip()[:120]}")
    return findings, scanned


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    root = pathlib.Path(ap.parse_args(argv).root)
    findings, scanned = scan(root)
    if scanned == 0:
        print("grep-q-pipes: no shell that sets pipefail found under " + ", ".join(ROOTS) + "; nothing was checked")
        return 2
    if findings:
        print(f"grep-q-pipes: {len(findings)} pipe(s) into `grep -q` under pipefail (a SIGPIPE race: a found match can "
              "fail the pipeline). Read the whole input instead: `grep -q PATTERN <<<\"$x\"`, awk, or capture first.")
        for f in findings:
            print(f"  {f}")
        return 1
    print(f"grep-q-pipes: OK, {scanned} file(s) that set pipefail, no pipe into `grep -q`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
