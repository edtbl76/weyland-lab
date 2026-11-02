"""Spec-as-oracle, step 2: build the review repos trials4/<task>-<arm>-{docs,nodocs}/ from each round-1 output that has a
picked defect (results/oracle/defects.tsv). Both variants: the round-1 output with the defect applied (text-preserving
splice; the line is recomputed here), TASK.md removed (the reviewer must not be handed the original intent), .claude/
removed and CLAUDE.md = @AGENTS.md, and NO .git (the defect cannot be diffed out). The -nodocs variant also deletes the
framework's authored documents (the same rule as the docs ablation). `none` gets only -nodocs (it wrote none).
→ results/oracle/cases.tsv: task, arm, variant, target file, defect, true line"""
import json
import os
import re
import shutil
import subprocess

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
DOC = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)|^aidlc/spaces/(?:[^/.][^/]*/)*[^/.][^/]*\.md$")
os.makedirs(f"{B}/trials4", exist_ok=True)
os.makedirs(f"{B}/trash", exist_ok=True)
cases = open(f"{B}/results/oracle/cases.tsv", "w")
cases.write("task\tarm\tvariant\ttarget\tdefect\tline\n")


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True).stdout


for row in open(f"{B}/results/oracle/defects.tsv"):
    task, arm, tgt, desc = row.rstrip("\n").split("\t")[:4]
    if desc == "none":
        continue
    src = f"{B}/trials/{task}-{arm}"
    # files the framework AUTHORED in round 1 (added since the framework-installed commit; aidlc installs in the base)
    commits = git(src, "rev-list", "--reverse", "HEAD").split()
    since = commits[1] if (arm not in ("none", "aidlc") and len(commits) > 1) else commits[0]
    authored = set(git(src, "diff", "--name-only", "--diff-filter=A", since).split())
    authored |= set(git(src, "ls-files", "--others", "--exclude-standard").split())
    authored |= set(git(src, "ls-files", "--others", "--ignored", "--exclude-standard").split())
    docs = sorted(p for p in authored if DOC.search(p))
    for variant in (("nodocs",) if arm == "none" else ("docs", "nodocs")):
        d = f"{B}/trials4/{task}-{arm}-{variant}"
        if os.path.exists(d):
            shutil.move(d, f"{B}/trash/{task}-{arm}-{variant}-{os.getpid()}")
        shutil.copytree(src, d, symlinks=True)
        ap = subprocess.run(["python3", f"{C}/quality/mutate.py", d, tgt, "--apply", desc], capture_output=True, text=True)
        if ap.returncode != 0:
            print(f"{task}-{arm}-{variant}: could not apply {desc}: {ap.stdout.strip()}")
            continue
        line = json.loads(ap.stdout)["line"]
        for junk in ("TASK.md",):
            if os.path.exists(f"{d}/{junk}"):
                os.remove(f"{d}/{junk}")
        if os.path.isdir(f"{d}/.claude"):
            shutil.move(f"{d}/.claude", f"{B}/trash/{task}-{arm}-{variant}-claude-{os.getpid()}")
        with open(f"{d}/CLAUDE.md", "w") as f:
            f.write("@AGENTS.md\n")
        removed = 0
        if variant == "nodocs":
            for p in docs:
                if os.path.isfile(f"{d}/{p}"):
                    os.remove(f"{d}/{p}")
                    removed += 1
        shutil.move(f"{d}/.git", f"{B}/trash/{task}-{arm}-{variant}-git-{os.getpid()}")
        cases.write(f"{task}\t{arm}\t{variant}\t{tgt}\t{desc}\t{line}\n")
        print(f"{task}-{arm}-{variant}: defect {desc} at {tgt}:{line}; docs kept {len(docs) - removed}/{len(docs)}")
cases.close()
