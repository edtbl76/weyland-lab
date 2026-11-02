"""B86 bake-off: the statistics for the scaled plan → results/analysis.txt (+ results/runs-all.tsv).
Data: every VALID round-1 run and replicate (results/<task>-<arm>[-rN].*), the layer-1 quality reports
(results/quality/), the follow-ons with docs (results2/) and without (results3/), and the oracle scores.

Tests (exact, no normal approximation; 3 runs per cell is far too few for one):
- Framework vs none, STRATIFIED by task: within each task the arm labels are permuted among that task's runs, every
  combination enumerated; the statistic is the mean over tasks of (framework mean - none mean). Run on log cost (so the
  effect reads as a cost ratio), wall time, pass rate, and mutation score. Holm-corrected over the 4 frameworks.
- Docs ablation: paired per (task, framework), exact sign-flip test on log(follow-on cost without docs / with docs),
  and the pass-count change.
- Oracle: read from results/oracle/scores.tsv (score_reviews.py).
usage: analyze.py"""
import glob
import itertools
import json
import math
import os
import re
import statistics
import sys
from datetime import datetime

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
R = f"{B}/results"
sys.argv = ["summarize", R]
_src = open(f"{C}/summarize.py").read()
exec(_src[:_src.index("\nrows = []")])  # run_stats() — one definition of what a run cost, shared with summarize.py
B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo          # after the exec: summarize.py rebinds B (to the results dir),
TASKS = ("small", "brown", "green", "vague")   # and defines its own TASKS/ORDER dicts
ARMS = ("none", "aidlc", "bmad", "openspec", "speckit", "aidlc211")   # aidlc = AI-DLC 2.6.18, aidlc211 = 2.11.2
FRAMEWORKS = ARMS[1:]


def wall(meta_path):
    m = re.search(r"start=(\S+) end=(\S+)", open(meta_path).read())
    t = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in m.groups()]
    return (t[1] - t[0]).total_seconds()


def quality(name):
    p = f"{R}/quality/{name}.txt"
    if not os.path.exists(p):
        return {}
    txt = open(p).read()
    q = {}
    m = re.search(r"^mutation=(\{.*\})$", txt, re.M)
    if m:
        q["mutation"] = json.loads(m.group(1)).get("score")
    for key in ("ruff_findings", "radon_mi"):
        m = re.search(rf"^{key}=([\d.]+)", txt, re.M)
        if m:
            q[key] = float(m.group(1))
    m = re.search(r"^ccn_max=(\d+)", txt, re.M)
    if m:
        q["ccn_max"] = float(m.group(1))
    return q


def load(res_dir, pattern):
    runs = []
    for jl in sorted(glob.glob(f"{res_dir}/{pattern}.jsonl")):
        name = os.path.basename(jl)[:-6]
        m = re.fullmatch(r"(\w+)-(\w+?)(-r\d)?", name)
        if not m or m.group(1) not in TASKS or m.group(2) not in ARMS or not os.path.exists(f"{res_dir}/{name}.meta"):
            continue
        judge = open(f"{res_dir}/{name}.judge").read().strip().splitlines()[-1] if os.path.exists(f"{res_dir}/{name}.judge") else ""
        s = run_stats(jl) or {}
        runs.append({"name": name, "task": m.group(1), "arm": m.group(2), "rep": (m.group(3) or "-r1")[1:],
                     "pass": int("PASS" in judge), "cost": s.get("cost") or 0.0, "wall": wall(f"{res_dir}/{name}.meta"),
                     "out_tok": s.get("out_tok") or 0, "procs": s.get("procs") or 1, **quality(name)})
    return runs


def strat_perm(runs, arm, metric, transform=lambda v: v, base="none"):
    """Exact stratified permutation test of `arm` vs none on `metric`. → (effect, p, n_arm, n_none) or None."""
    strata = []
    for t in TASKS:
        a = [transform(r[metric]) for r in runs if r["task"] == t and r["arm"] == arm and r.get(metric) is not None]
        n = [transform(r[metric]) for r in runs if r["task"] == t and r["arm"] == base and r.get(metric) is not None]
        if a and n:
            strata.append((a + n, len(a)))
    if not strata:
        return None

    def stat(splits):
        return statistics.mean(statistics.mean(x) - statistics.mean(y) for x, y in splits)

    observed = stat([(v[:k], v[k:]) for v, k in strata])
    per = []
    for v, k in strata:  # every way to label k of this task's runs as the framework
        opts = []
        for idx in itertools.combinations(range(len(v)), k):
            s = set(idx)
            opts.append(([v[i] for i in idx], [v[i] for i in range(len(v)) if i not in s]))
        per.append(opts)
    total = extreme = 0
    for combo in itertools.product(*per):
        total += 1
        if abs(stat(combo)) >= abs(observed) - 1e-12:
            extreme += 1
    return observed, extreme / total, sum(k for _, k in strata), sum(len(v) - k for v, k in strata)


DOC = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)|^aidlc/spaces/(?:[^/.][^/]*/)*[^/.][^/]*\.md$")


def doc_files(repo):
    """Framework-document paths (build_nodocs.py's rule) present in a repo's working tree."""
    found = set()
    for root, dirs, files in os.walk(repo):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            p = os.path.relpath(os.path.join(root, f), repo)
            if DOC.search(p):
                found.add(p)
    return found


def base_passes(judge_path):
    """True when a follow-on base already passes its judge (the pair measures nothing). Reads the LAST verdict line:
    a follow-on judge prints round-1 sub-verdicts first (found 2026-11-02: matching any PASS excluded valid pairs).
    A missing file is False, so a pair is only ever excluded on positive evidence."""
    if not os.path.exists(judge_path):
        return False
    verdicts = [ln for ln in open(judge_path).read().splitlines() if ln.startswith("JUDGE:")]
    return bool(verdicts) and verdicts[-1].startswith("JUDGE: PASS")


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def sign_flip(diffs):
    """Exact two-sided paired sign-flip test on the mean difference."""
    if not diffs:
        return None
    obs = abs(statistics.mean(diffs))
    hits = sum(1 for signs in itertools.product((1, -1), repeat=len(diffs))
               if abs(statistics.mean(d * s for d, s in zip(diffs, signs))) >= obs - 1e-12)
    return hits / 2 ** len(diffs)


out = []
say = out.append
runs = load(R, "*")
with open(f"{R}/runs-all.tsv", "w") as f:
    cols = ("task", "arm", "rep", "pass", "cost", "wall", "out_tok", "mutation", "ruff_findings", "ccn_max", "radon_mi")
    f.write("\t".join(cols) + "\n")
    for r in sorted(runs, key=lambda r: (TASKS.index(r["task"]), ARMS.index(r["arm"]), r["rep"])):
        f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")

say(f"VALID RUNS: {len(runs)} (round 1 + replicates); per cell n, passes, median cost (USD equiv), median wall (min)")
say("task    " + "".join(f"{a:>22s}" for a in ARMS))
for t in TASKS:
    cells = []
    for a in ARMS:
        c = [r for r in runs if r["task"] == t and r["arm"] == a]
        cells.append(f"{len(c)} {sum(r['pass'] for r in c)}/{len(c)} ${statistics.median([r['cost'] for r in c]):.2f} "
                     f"{statistics.median([r['wall'] for r in c]) / 60:.0f}m" if c else "-")
    say(f"{t:8s}" + "".join(f"{x:>22s}" for x in cells))

for metric, label, tf, fmt in (("cost", "COST (effect = framework/none cost ratio)", math.log, lambda e: f"x{math.exp(e):.2f}"),
                               ("wall", "WALL TIME (effect = framework/none ratio)", math.log, lambda e: f"x{math.exp(e):.2f}"),
                               ("pass", "PASS RATE (effect = framework - none)", float, lambda e: f"{e:+.2f}"),
                               ("mutation", "MUTATION SCORE of own tests (effect = framework - none)", float, lambda e: f"{e:+.3f}")):
    say("")
    say(f"{label}; exact stratified permutation, Holm over {len(FRAMEWORKS)} arms")
    res = {a: strat_perm(runs, a, metric, tf) for a in FRAMEWORKS}
    have = [a for a in FRAMEWORKS if res[a]]
    adj = dict(zip(have, holm([res[a][1] for a in have])))
    for a in FRAMEWORKS:
        if not res[a]:
            say(f"  {a:9s} no data")
            continue
        e, p, na, nn = res[a]
        say(f"  {a:9s} {fmt(e):>8s}  p={p:.4f}  holm={adj[a]:.4f}  (n {na} vs {nn})")
    v = strat_perm(runs, "aidlc211", metric, tf, base="aidlc")
    if v:
        say(f"  AI-DLC 2.11.2 vs 2.6.18: {fmt(v[0]):>8s}  p={v[1]:.4f}  (n {v[2]} vs {v[3]}; one planned comparison)")

say("")
say("AI-DLC 2.11.2 GATE REPLIES per run (click-through driver; counted up to the first final status)")
for t in TASKS:
    reps = [r["procs"] - 1 for r in runs if r["task"] == t and r["arm"] == "aidlc211"]
    if reps:
        say(f"  {t:6s} {sorted(reps)}")

say("")
say("DOCS ABLATION: follow-on by plain Claude Code, framework documents kept (results2) vs removed (results3)")
with_docs = {(r["task"], r["arm"]): r for r in load(f"{B}/results2", "*")}
no_docs = {(r["task"], r["arm"]): r for r in load(f"{B}/results3", "*")}
diffs, pass_w, pass_n = [], 0, 0
for a in FRAMEWORKS:
    for t in TASKS:
        w, n = with_docs.get((t, a)), no_docs.get((t, a))
        # a pair measures nothing when its base already passes the follow-on judge (nothing to do) or when the
        # framework wrote no documents (nothing removed): reported, never counted
        if base_passes(f"{B}/results3/{t}-{a}.base.judge"):
            say(f"  {t:6s} {a:9s} EXCLUDED: base already passes the follow-on judge")
            continue
        # documents present with docs kept but absent with docs removed (a commit count misses gitignored aidlc-docs)
        removed = len(doc_files(f"{B}/trials2/{t}-{a}") - doc_files(f"{B}/trials3/{t}-{a}"))
        if removed == 0:
            say(f"  {t:6s} {a:9s} EXCLUDED: the framework wrote no documents")
            continue
        if not (w and n):
            continue
        diffs.append(math.log(n["cost"] / w["cost"]))
        pass_w += w["pass"]
        pass_n += n["pass"]
        say(f"  {t:6s} {a:9s} docs ${w['cost']:.2f} {'PASS' if w['pass'] else 'FAIL'}   nodocs ${n['cost']:.2f} {'PASS' if n['pass'] else 'FAIL'}")
if diffs:
    say(f"  pairs {len(diffs)}: nodocs/docs cost ratio x{math.exp(statistics.mean(diffs)):.2f} (geo-mean), "
        f"sign-flip p={sign_flip(diffs):.4f}; passes docs {pass_w}/{len(diffs)} vs nodocs {pass_n}/{len(diffs)}")
else:
    say("  (no paired results yet)")

say("")
say("SPEC AS ORACLE: read-only reviewer finds a planted defect, framework documents present vs removed")
sp = f"{R}/oracle/scores.tsv"
if os.path.exists(sp):
    rows = [ln.rstrip("\n").split("\t") for ln in list(open(sp))[1:]]
    for variant in ("docs", "nodocs"):
        for arm in ARMS:
            v = [r for r in rows if r[2] == variant and r[1] == arm and r[5] != "-"]
            if v:
                say(f"  {variant:7s} {arm:9s} hit {sum(int(r[5]) for r in v)}/{len(v)}  "
                    f"mean docs read {statistics.mean(int(r[8]) for r in v):.1f}  mean cost ${statistics.mean(float(r[6]) for r in v):.2f}")
else:
    say("  (scores.tsv not written yet)")

text = "\n".join(out)
open(f"{R}/analysis.txt", "w").write(text + "\n")
print(text)
