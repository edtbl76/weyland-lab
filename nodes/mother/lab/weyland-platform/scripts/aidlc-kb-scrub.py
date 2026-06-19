#!/usr/bin/env python3
"""B37 prep — brand-neutral scrub of the AIDLC knowledge repos for RAG ingestion.

Reads the three knowledge repos out of `.methodaidlc/`, writes a SCRUBBED staging copy
(brand "Method" removed), and uploads that copy to MinIO (step 3, done separately). The
live `.methodaidlc/` source is never touched — it intentionally references "Method" to
drive the workflow; only the staging copy that feeds the vector store is genericized.

Why a curated map and not `s/Method//g`: capital-M "Method" is the firm brand in ~500
places, but ~28 occurrences are established TECHNICAL terms (the GoF "Template Method" /
"Factory Method" patterns, the "USE"/"RED" perf methods, ATAM's "...Analysis Method").
A blind delete would corrupt those, so we protect them first, then genericize the brand.

Usage:
    python3 aidlc-kb-scrub.py [--src .methodaidlc] [--dest /tmp/aidlc-kb-staging]

Output is brand-neutral markdown under <dest>/<repo>/... ready to upload to MinIO.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The three knowledge repos (entry files get scrubbed + copied; READMEs are pure
# brand/navigation and are skipped — they are not ingested. index.md IS kept: it's
# machine-readable and may feed the Phase-2 graph; the Dagster asset decides what to chunk).
REPOS = [
    "engineering-knowledge-repository",
    "consulting-tools-repository",
    "industry-vertical-repository",
]
SKIP_FILENAMES = {"README.md"}

# Technical terms that contain capital-M "Method" but are NOT the brand. Protected via a
# placeholder before brand substitution, then restored verbatim. Longest-first so e.g.
# "Abstract Factory Method" is handled before "Factory Method".
PRESERVE = [
    "Template Method",
    "Factory Method",
    "USE Method",
    "RED Method",
    "Analysis Method",   # catches "...Tradeoff Analysis Method" (ATAM)
    "Clone Method",
]

# Ordered brand replacements (specific -> general). Applied AFTER preserve-list protection.
# The final rule genericizes any remaining standalone brand "Method" to a grammatically
# safe noun ("the team") so "Method recommends X" -> "the team recommends X".
BRAND_RULES: list[tuple[str, str]] = [
    (r"^## Method Application\s*$", "## In Practice"),     # the dominant section header (~61x)
    (r"\bMethod Engagement Archetypes\b", "Engagement Archetypes"),
    (r"\bMethod Mob\b", "the Mob"),
    (r"\bMethod AI-DLC\b", "AI-DLC"),
    (r"\bMethod AIDLC\b", "AIDLC"),
    (r"\bMethod's\b", "our"),
    (r"\bMethod engagements\b", "client engagements"),
    (r"\bMethod engagement\b", "client engagement"),
    (r"\bIn Method\b", "In our practice"),
    (r"\bMethod\b", "the team"),                            # catch-all: remaining brand "Method"
]

_PLACEHOLDER = "\x00PRES{}\x00"
_RESIDUAL = re.compile(r"\bMethod\b")  # post-scrub sanity check (should be 0 outside preserved spans)


def scrub(text: str) -> tuple[str, int, list[str]]:
    """Return (scrubbed_text, brand_replacement_count, residual_lines).

    residual_lines is computed BEFORE restoring the preserved terms, so the protected
    technical terms (Template Method, etc.) are still placeholders and can't false-trigger
    the check — any `\\bMethod\\b` left at that point is genuine leftover brand.
    """
    # 1) Protect technical terms behind placeholders so brand rules can't touch them.
    protected = text
    for i, term in enumerate(PRESERVE):
        protected = protected.replace(term, _PLACEHOLDER.format(i))

    # 2) Apply brand rules (the header rule is multiline-anchored).
    count = 0
    for pattern, repl in BRAND_RULES:
        flags = re.MULTILINE if pattern.startswith("^") else 0
        protected, n = re.subn(pattern, repl, protected, flags=flags)
        count += n

    # 3) Residual check while preserved terms are still hidden.
    residual = [ln.strip()[:100] for ln in protected.splitlines() if _RESIDUAL.search(ln)]

    # 4) Restore the protected technical terms.
    for i, term in enumerate(PRESERVE):
        protected = protected.replace(_PLACEHOLDER.format(i), term)
    return protected, count, residual


def main() -> int:
    ap = argparse.ArgumentParser(description="Brand-neutral scrub of the AIDLC knowledge repos (B37).")
    ap.add_argument("--src", default=".methodaidlc", help="path to the .methodaidlc root")
    ap.add_argument("--dest", default="/tmp/aidlc-kb-staging", help="staging output dir")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    dest = Path(args.dest).resolve()
    if not src.is_dir():
        print(f"ERROR: src not found: {src}", file=sys.stderr)
        return 1

    files = total_repl = residual_files = 0
    for repo in REPOS:
        repo_root = src / repo
        if not repo_root.is_dir():
            print(f"WARN: missing repo {repo_root}", file=sys.stderr)
            continue
        for md in sorted(repo_root.rglob("*.md")):
            if md.name in SKIP_FILENAMES:
                continue
            scrubbed, n, residual = scrub(md.read_text(encoding="utf-8"))
            out = dest / repo / md.relative_to(repo_root)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(scrubbed, encoding="utf-8")
            files += 1
            total_repl += n
            if residual:
                residual_files += 1
                for line in residual:
                    print(f"  RESIDUAL BRAND {out}: {line}", file=sys.stderr)

    print(f"scrubbed {files} files -> {dest}")
    print(f"brand replacements: {total_repl}")
    print(f"files with residual standalone 'Method': {residual_files} (want 0; preserved terms are exempt)")
    return 0 if residual_files == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
