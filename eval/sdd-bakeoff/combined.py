"""The bake-off's combined outcome table: round-1 cost/time + pass, layer-1 static quality + test strength (mutation),
layer-2 follow-on change cost/time + pass, per task and arm. Reads results/table.tsv, results/artifacts.tsv,
results/quality/<t>-<a>.txt and results2/table.tsv (run summarize.py on both dirs first). → results/combined.tsv"""
import os
import csv
import json
import re

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
TASKS, ARMS = ["small", "brown", "green", "vague"], ["none", "aidlc", "bmad", "openspec", "speckit"]


def tsv(p):
    return {(r["task"], r["arm"]): r for r in csv.DictReader(open(p), delimiter="\t")}


r1, r2, art = tsv(f"{B}/results/table.tsv"), tsv(f"{B}/results2/table.tsv"), tsv(f"{B}/results/artifacts.tsv")


def quality(t, a):
    q = {}
    for line in open(f"{B}/results/quality/{t}-{a}.txt"):
        m = re.match(r"^(\w+)=(.*)$", line.strip())
        if m:
            q[m.group(1)] = m.group(2)
    for k, v in re.findall(r"(\w+)=([\d.]+)", q.get("ccn_max", "") and line):
        pass
    mut = json.loads(q["mutation"]) if q.get("mutation", "").startswith("{") else {}
    ccn = re.search(r"ccn_max=(\d+)", open(f"{B}/results/quality/{t}-{a}.txt").read())
    return {"ruff": q.get("ruff_findings", "-"), "ccn_max": ccn.group(1) if ccn else "-",
            "mi": q.get("radon_mi", "-"), "mut": mut.get("score"), "mutants": mut.get("mutants")}


cols = ["task", "arm", "r1_pass", "r1_usd", "r1_min", "spec_kB", "ruff", "ccn_max", "mi", "mutation", "f_pass", "f_usd", "f_min"]
rows = ["\t".join(cols)]
for t in TASKS:
    for a in ARMS:
        x, y, z, q = r1[(t, a)], r2[(t, a)], art[(t, a)], quality(t, a)
        rows.append("\t".join([
            t, a,
            "PASS" if x["judge"].startswith("PASS") else "FAIL",
            f'{float(x["cost_usd_equiv"]):.2f}', f'{int(x["wall_s"]) / 60:.1f}',
            f'{int(z["spec_bytes"]) / 1000:.1f}',
            q["ruff"], q["ccn_max"] if t != "small" else "n/a", q["mi"] if t != "small" else "n/a",
            f'{q["mut"]:.2f} ({q["mutants"]})' if q["mut"] is not None else "-",
            "PASS" if y["judge"].startswith("PASS") else "FAIL",
            f'{float(y["cost_usd_equiv"]):.2f}', f'{int(y["wall_s"]) / 60:.1f}',
        ]))
open(f"{B}/results/combined.tsv", "w").write("\n".join(rows) + "\n")
print("\n".join(rows))
