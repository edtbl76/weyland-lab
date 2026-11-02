"""Spec-as-oracle v2, step 2: build trials5/<task>-<arm>-{docs,nodocs}/ for every PICK in results/oracle2/defects.tsv.
Same rules as build_review.py (TASK.md removed, .claude/ removed and CLAUDE.md = @AGENTS.md, no .git, -nodocs deletes the
framework's authored documents), but the defect is select_intent.py's intent defect: the value is changed in the code AND
in the trial's own tests, re-derived here by its description with the same functions.
→ results/oracle2/cases.tsv: task, arm, variant, target, defect, line"""
import os
import shutil

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
_src = open(f"{C}/select_intent.py").read()
exec(_src[:_src.index("\nids = ")])   # target(), own_tests(), framework_docs(), candidates(), apply() — one definition

os.makedirs(f"{B}/trials5", exist_ok=True)
cases = open(f"{B}/results/oracle2/cases.tsv", "w")
cases.write("task\tarm\tvariant\ttarget\tdefect\tline\n")
for row in open(f"{B}/results/oracle2/defects.tsv"):
    task, arm, tgt, desc = row.rstrip("\n").split("\t")[:4]
    if desc == "none":
        continue
    src = f"{B}/trials/{task}-{arm}"
    docs = framework_docs(src, arm)
    doc_text = "\n".join(open(f"{src}/{p}", errors="ignore").read() for p in docs)
    tests = own_tests(src, task, tgt)
    c = next(c for c in candidates(open(f"{src}/{tgt}").read(), tgt, doc_text) if c["desc"] == desc)
    for variant in ("docs", "nodocs"):
        d = f"{B}/trials5/{task}-{arm}-{variant}"
        if os.path.exists(d):
            shutil.move(d, f"{B}/trash/trials5-{task}-{arm}-{variant}-{os.getpid()}")
        shutil.copytree(src, d, symlinks=True)
        apply(d, tgt, tests, c)
        if os.path.exists(f"{d}/TASK.md"):
            os.remove(f"{d}/TASK.md")
        if os.path.isdir(f"{d}/.claude"):
            shutil.move(f"{d}/.claude", f"{B}/trash/trials5-{task}-{arm}-{variant}-claude-{os.getpid()}")
        with open(f"{d}/CLAUDE.md", "w") as f:
            f.write("@AGENTS.md\n")
        removed = 0
        if variant == "nodocs":
            for p in docs:
                if os.path.isfile(f"{d}/{p}"):
                    os.remove(f"{d}/{p}")
                    removed += 1
        shutil.move(f"{d}/.git", f"{B}/trash/trials5-{task}-{arm}-{variant}-git-{os.getpid()}")
        cases.write(f"{task}\t{arm}\t{variant}\t{tgt}\t{desc}\t{c['line']}\n")
        print(f"{task}-{arm}-{variant}: {desc} at {tgt}:{c['line']}; documents removed {removed}/{len(docs)}")
cases.close()
