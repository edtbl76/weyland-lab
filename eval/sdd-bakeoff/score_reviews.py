"""Spec-as-oracle, step 4: score every review in results/oracle/cases.tsv → results/oracle/scores.tsv + a summary.
A review HITS when its last `DEFECT LINE: N` is within 2 lines of the planted defect's true line. A review with no such
line, or no result at all, is a MISS (fail closed: an absent answer is never a hit). Also recorded per review: cost,
turns, and how many framework documents it Read (the -docs variant can only gain from documents it actually opened).
Summary: hit rate per variant, and the paired docs-vs-nodocs comparison per (task, arm) — discordant pairs are what an
exact McNemar test counts.
usage: score_reviews.py"""
import json
import math
import os
import re

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
O = f"{B}/results/oracle" if os.environ.get("ORACLE", "1") == "1" else f"{B}/results/oracle2"   # ORACLE=2: v2
DOC = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)|/aidlc/spaces/.*\.md$")
ANSWER = re.compile(r"DEFECT LINE:\s*\**\s*(\d+)")


def review(path):
    """(answered line or None, cost, turns, doc files read) from one review log; None if the log is missing."""
    if not os.path.exists(path):
        return None
    results, docs = [], set()
    for raw in open(path):
        try:
            e = json.loads(raw)
        except ValueError:
            continue
        if e.get("type") == "result":
            results.append(e)
        elif e.get("type") == "assistant":
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use" and c.get("name") == "Read":
                    p = (c.get("input") or {}).get("file_path", "")
                    if DOC.search(p):
                        docs.add(p)
    if not results:
        return (None, 0.0, 0, len(docs))
    found = ANSWER.findall(results[-1].get("result") or "")
    return (int(found[-1]) if found else None, results[-1].get("total_cost_usd") or 0.0,
            sum(r.get("num_turns") or 0 for r in results), len(docs))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


rows, out = [], open(f"{O}/scores.tsv", "w")
out.write("task\tarm\tvariant\ttrue_line\tanswer\thit\tcost_usd\tturns\tdocs_read\n")
for line in list(open(f"{O}/cases.tsv"))[1:]:
    task, arm, variant, _tgt, _defect, true_line = line.rstrip("\n").split("\t")
    r = review(f"{O}/{task}-{arm}-{variant}.jsonl")
    if r is None:
        out.write(f"{task}\t{arm}\t{variant}\t{true_line}\tNOT RUN\t-\t-\t-\t-\n")
        continue
    ans, cost, turns, docs = r
    hit = ans is not None and true_line.isdigit() and abs(ans - int(true_line)) <= 2
    rows.append((task, arm, variant, hit))
    out.write(f"{task}\t{arm}\t{variant}\t{true_line}\t{ans if ans is not None else 'none'}\t{int(hit)}\t{cost:.4f}\t{turns}\t{docs}\n")
out.close()

print(f"scored {len(rows)} review(s) → {O}/scores.tsv")
for variant in ("docs", "nodocs"):
    v = [h for _, _, var, h in rows if var == variant]
    if v:
        print(f"{variant:7s} hit {sum(v)}/{len(v)}")
hits = {(t, a, var): h for t, a, var, h in rows}
pairs = [(hits[(t, a, "docs")], hits[(t, a, "nodocs")]) for t, a, var, _ in rows
         if var == "docs" and (t, a, "nodocs") in hits]
b = sum(1 for d, n in pairs if d and not n)   # docs found it, nodocs missed
c = sum(1 for d, n in pairs if n and not d)   # nodocs found it, docs missed
print(f"paired framework cases {len(pairs)}: docs-only hits {b}, nodocs-only hits {c}, "
      f"exact McNemar p = {mcnemar_exact(b, c):.3f}")
