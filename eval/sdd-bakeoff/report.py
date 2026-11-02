"""Join results/table.tsv and results/artifacts.tsv into the bake-off's one 15-row trial table (stdout, aligned)."""
import csv
import os

R = os.path.join(os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff"), "results")
TASKS = ["small", "brown", "green"]
ARMS = ["none", "aidlc", "bmad", "openspec", "speckit"]
t = {(r["task"], r["arm"]): r for r in csv.DictReader(open(f"{R}/table.tsv"), delimiter="\t")}
a = {(r["task"], r["arm"]): r for r in csv.DictReader(open(f"{R}/artifacts.tsv"), delimiter="\t")}
cols = ["task", "arm", "judge", "wall_s", "turns", "usd_eq", "out_tok", "subagents", "code_B", "spec_files", "spec_B", "runtime_B"]
print("\t".join(cols))
for task in TASKS:
    for arm in ARMS:
        r, x = t.get((task, arm)), a.get((task, arm), {})
        if not r:
            print(f"{task}\t{arm}\t(no valid run)")
            continue
        judge = "PASS" if r["judge"].startswith("PASS") else "FAIL"
        cost = round(float(r["cost_usd_equiv"]), 2)
        row = [task, arm, judge, r["wall_s"], r["turns"], str(cost), r["out_tokens"], r["subagents"],
               x.get("code_bytes", "-"), x.get("spec_files", "-"), x.get("spec_bytes", "-"), x.get("runtime_bytes", "-")]
        print("\t".join(row))
