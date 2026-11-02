"""Spec-as-oracle, step 1: pick ONE planted defect per round-1 output, by rule. Candidates = EVERY mutant of the
output's main file, in source order (mutate.py --list); the pick = the first whose mutated copy the hidden reference
judge REJECTS (a real behaviour bug). Equivalent or harmless mutants are skipped by that rule, never by hand. The review
is read-only (no shell), so whether the trial's own tests would catch the defect does not matter.
→ results/oracle/defects.tsv
usage: select_defects.py [task-arm ...]   (default: all 20)"""
import json
import os
import re
import shutil
import subprocess
import sys

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
TARGET = {"small": "scripts/tests/alert-rules.bats", "brown": "scripts/check-private-lanes.py",
          "green": "nodes/mother/lab/weyland-platform/services/store-scaler/app.py"}
os.makedirs(f"{B}/results/oracle", exist_ok=True)
os.makedirs(f"{B}/trash", exist_ok=True)


def target(task, arm):
    if task != "vague":
        return TARGET[task]
    m = re.search(r"^checker=(\S+)", open(f"{B}/results/quality/{task}-{arm}.txt").read(), re.M)
    return m.group(1) if m else None


def survivors(task, arm):  # (name kept for the loop below) every mutant of the target, in source order
    tgt = target(task, arm)
    p = subprocess.run(["python3", f"{C}/quality/mutate.py", f"{B}/trials/{task}-{arm}", tgt, "--list"],
                       capture_output=True, text=True)
    return json.loads(p.stdout) if p.returncode == 0 else []


ids = sys.argv[1:] or [f"{t}-{a}" for t in ("small", "brown", "green", "vague") for a in ("none", "aidlc", "bmad", "openspec", "speckit")]
out = open(f"{B}/results/oracle/defects.tsv", "a")
for ident in ids:
    task, arm = ident.split("-", 1)
    tgt = target(task, arm)
    pick = None
    for n, desc in enumerate(survivors(task, arm)):
        work = f"{B}/trials/{task}-{arm}-mut"
        if os.path.exists(work):
            shutil.move(work, f"{B}/trash/{task}-{arm}-mut-{os.getpid()}-{n}")
        shutil.copytree(f"{B}/trials/{task}-{arm}", work, symlinks=True)
        ap = subprocess.run(["python3", f"{C}/quality/mutate.py", work, tgt, "--apply", desc], capture_output=True, text=True)
        if ap.returncode != 0:
            continue
        line = json.loads(ap.stdout).get("line")
        verdict = subprocess.run(["bash", f"{C}/judge_trial.sh", task, arm, "-mut"], capture_output=True, text=True).stdout.strip().splitlines()[-1:]
        verdict = verdict[0] if verdict else ""
        print(f"{ident}: {desc} -> {verdict[:70]}", flush=True)
        if "FAIL" in verdict:
            pick = (desc, line, verdict)
            break
    if os.path.exists(f"{B}/trials/{task}-{arm}-mut"):
        shutil.move(f"{B}/trials/{task}-{arm}-mut", f"{B}/trash/{task}-{arm}-mut-{os.getpid()}-final")
    row = [task, arm, tgt or "-", *(pick[:2] if pick else ("none", "-")), (pick[2] if pick else "no surviving mutant the judge catches")]
    out.write("\t".join(str(x) for x in row) + "\n")
    out.flush()
    print(f"== {ident}: {'PICK ' + pick[0] + ' (line ' + str(pick[1]) + ')' if pick else 'no qualifying defect'}", flush=True)
