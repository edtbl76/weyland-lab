"""The per-cell trial table (task x arm, every valid run): passes, and the MEDIAN over the cell's runs of cost, wall
time, output tokens, questions asked and framework documents authored -> B/results/cells.tsv, and the same as a
Markdown table on stdout (pasted into docs/concepts/spec-driven-frameworks.md).
Questions = AskUserQuestion calls in the main thread + gate replies the click-through driver sent (AI-DLC 2.11.2).
Documents = files the trial authored that are framework documents (build_review.py's rule), counted in the trial repo.
usage: cell_table.py"""
import os
import re
import statistics
import subprocess
import sys

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
R = f"{B}/results"
sys.argv = ["summarize", R]
_src = open(f"{C}/summarize.py").read()
exec(_src[:_src.index("\nrows = []")])   # run_stats(): one definition of what a run cost, shared with summarize.py
B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # again: the exec rebinds B to results/
TASKS = ("small", "brown", "green", "vague")
ARMS = ("none", "aidlc", "aidlc211", "bmad", "openspec", "speckit")
LABEL = {"none": "plain Claude Code", "aidlc": "AI-DLC 2.6.18", "aidlc211": "AI-DLC 2.11.2", "bmad": "BMAD 6.12.4",
         "openspec": "OpenSpec 1.16.0", "speckit": "Spec Kit 1.2.5"}
DOC = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)|^aidlc/spaces/(?:[^/.][^/]*/)*[^/.][^/]*\.md$")


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=False).stdout


def docs_authored(d, arm):
    """Framework documents the trial added after the framework-installed commit (AI-DLC 2.6.18: after the base)."""
    commits = git(d, "rev-list", "--reverse", "HEAD").split()
    if not commits:
        return None
    since = commits[1] if (arm not in ("none", "aidlc") and len(commits) > 1) else commits[0]
    files = set(git(d, "diff", "--name-only", "--diff-filter=A", since).split())
    files |= set(git(d, "ls-files", "--others", "--exclude-standard").split())
    files |= set(git(d, "ls-files", "--others", "--ignored", "--exclude-standard").split())
    return sum(1 for p in files if DOC.search(p))


def wall_s(meta):
    m = re.search(r"start=(\S+) end=(\S+)", open(meta).read())
    from datetime import datetime
    t = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in m.groups()]
    return (t[1] - t[0]).total_seconds()


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


rows = []
for t in TASKS:
    for a in ARMS:
        runs = []
        for suf in ("", "-r2", "-r3"):
            n = f"{t}-{a}{suf}"
            if not (os.path.exists(f"{R}/{n}.jsonl") and os.path.exists(f"{R}/{n}.meta")):
                continue
            s = run_stats(f"{R}/{n}.jsonl") or {}
            judge = open(f"{R}/{n}.judge").read().strip().splitlines()[-1] if os.path.exists(f"{R}/{n}.judge") else ""
            runs.append({"pass": "PASS" in judge, "cost": s.get("cost"), "wall": wall_s(f"{R}/{n}.meta") / 60,
                         "out": (s.get("out_tok") or 0) / 1000, "q": (s.get("asks") or 0) + (s.get("procs") or 1) - 1,
                         "docs": docs_authored(f"{B}/trials/{n}", a)})
        if runs:
            rows.append((t, a, len(runs), sum(r["pass"] for r in runs), med([r["cost"] for r in runs]),
                         med([r["wall"] for r in runs]), med([r["out"] for r in runs]), med([r["q"] for r in runs]),
                         med([r["docs"] for r in runs])))

with open(f"{R}/cells.tsv", "w") as f:
    f.write("task\tarm\truns\tpasses\tcost_usd\twall_min\tout_ktok\tquestions\tframework_docs\n")
    for r in rows:
        f.write("\t".join(str(round(x, 2) if isinstance(x, float) else x) for x in r) + "\n")
print("| Task | Arm | Pass | Cost (USD equiv) | Wall (min) | Output tokens (k) | Questions | Framework docs |")
print("|---|---|---|---|---|---|---|---|")
for t, a, n, p, cost, wall, out, q, docs in rows:
    print(f"| {t} | {LABEL[a]} | {p}/{n} | {cost:.2f} | {wall:.0f} | {out:.0f} | {q:g} | {'-' if docs is None else f'{docs:g}'} |")
