"""Docs ablation: for each FRAMEWORK arm's round-1 output, build trials3/<task>-<arm>/ — the follow-on repo exactly as in
trials2 (round-1 output committed, .claude/ removed, CLAUDE.md = @AGENTS.md, TASK.md = the follow-on change) but with the
framework's AUTHORED documents deleted: only files the trial itself ADDED (vs the framework-installed commit) whose path
is a framework document (openspec/, specs/ at any depth, _bmad-output/, aidlc-docs/, Markdown under aidlc/spaces/).
The repo's own pre-existing specs folders are never touched. Refuses to overwrite an existing trials3 repo.
usage: build_nodocs.py   → prints, per repo, how many document files and bytes were removed"""
import os
import re
import shutil
import subprocess
import sys

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
DOC = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)|^aidlc/spaces/(?:[^/.][^/]*/)*[^/.][^/]*\.md$")


def git(d, *a, check=True):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=check).stdout


os.makedirs(f"{B}/trials3", exist_ok=True)
for task in ("small", "brown", "green", "vague"):
    for arm in ("aidlc", "bmad", "openspec", "speckit"):
        src, d = f"{B}/trials2/{task}-{arm}", f"{B}/trials3/{task}-{arm}"
        if os.path.exists(d):
            print(f"exists, skipping {d}")
            continue
        if not os.path.isdir(src):
            sys.exit(f"missing follow-on base {src}")
        shutil.copytree(src, d, symlinks=True)
        # trials2 is where the docs-KEPT follow-on already ran: its working tree holds that follow-on's solution. Put
        # the copy back to the follow-on base commit first (found 2026-11-01: without this all 16 ablation repos
        # shipped with the answer already in them, and the agents finished in a minute having changed nothing).
        git(d, "reset", "-q", "--hard", "HEAD")
        git(d, "clean", "-q", "-fd")
        # the follow-on base = HEAD; its parent chain holds base -> framework-installed -> round-1 output
        commits = git(d, "rev-list", "--reverse", "HEAD").split()
        installed = commits[1] if arm != "aidlc" else commits[0]   # aidlc's framework is part of the base commit
        added = git(d, "diff", "--name-only", "--diff-filter=A", installed, "HEAD").split()
        # untracked/ignored round-1 files were committed by build_followon (`add -A`); gitignored ones (aidlc-docs) were not
        ignored = git(d, "ls-files", "--others", "--ignored", "--exclude-standard").split()
        gone, size = 0, 0
        for p in added + ignored:
            full = os.path.join(d, p)
            if DOC.search(p) and os.path.isfile(full):
                size += os.path.getsize(full)
                os.remove(full)
                gone += 1
        git(d, "add", "-A")
        git(d, "-c", "user.name=bakeoff", "-c", "user.email=bakeoff@localhost", "commit", "-q", "-m",
            f"docs ablation: framework documents removed ({gone} files)", check=False)
        print(f"{task}-{arm}: removed {gone} document file(s), {size} bytes")
