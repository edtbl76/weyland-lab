"""Rebuild the bake-off table from the raw run logs (results/<task>-<arm>.{jsonl,meta,judge}) → results/table.tsv.
A run can emit SEVERAL result events (a continuation after background sub-agents finish), so turns and API time are
summed across them; cost and modelUsage are cumulative, so the LAST result's values are used. Tokens come from
modelUsage, which (unlike `usage`) includes sub-agent spend. Wall time comes from the run's own start/end stamps."""
import glob
import json
import os
import re
from datetime import datetime

import sys
B = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff"), "results")
ORDER = {"none": 0, "aidlc": 1, "bmad": 2, "openspec": 3, "speckit": 4, "aidlc211": 5}
TASKS = {"small": 0, "brown": 1, "green": 2, "vague": 3}


def _final(result):
    text = result.get("result") or ""
    return "TRIAL DONE" in text or ("TRIAL BLOCKED" in text and "Reply with" not in text)


def run_stats(path):
    # cost and modelUsage are cumulative over the whole SESSION, also across `--resume` (the aidlc211 click-through
    # driver: verified 2026-11-02, process 4's modelUsage growth equalled its own output exactly), so the LAST result
    # holds the run's total. num_turns and duration_ms are per process/continuation, so those are summed.
    # A DRIVEN log (has {"type": "bakeoff_process"} markers) is counted only up to its first final status (TRIAL DONE,
    # or TRIAL BLOCKED that is not a gate question): replies the driver sent after that were a harness bug (fixed
    # 2026-11-02), not the framework's cost. An undriven log is counted whole, as before.
    results, spawns, asks, driven, procs = [], 0, 0, False, 1
    for line in open(path):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "bakeoff_process":
            if driven and results and _final(results[-1]):
                break
            if driven:
                procs += 1
            driven = True
        if e.get("type") == "result":
            results.append(e)
        elif e.get("type") == "assistant" and not e.get("parent_tool_use_id"):
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") == "tool_use" and c.get("name") in ("Task", "Agent"):
                    spawns += 1
                if c.get("type") == "tool_use" and c.get("name") == "AskUserQuestion":
                    asks += 1
    if not results:
        return None
    last = results[-1]
    mu = last.get("modelUsage") or {}
    return {
        "turns": sum(r.get("num_turns") or 0 for r in results),
        "api_s": round(sum((r.get("duration_ms") or 0) for r in results) / 1000),
        "cost": round(last.get("total_cost_usd") or 0, 2),
        "out_tok": sum(v.get("outputTokens", 0) for v in mu.values()),
        "in_tok": sum(v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0) + v.get("cacheCreationInputTokens", 0) for v in mu.values()),
        "subagents": spawns,
        "asks": asks,
        "results": len(results),
        "procs": procs,   # processes counted (driven runs: gate replies + 1)
        "subtype": last.get("subtype"),
    }


rows = []
for jl in glob.glob(f"{B}/*-*.jsonl"):
    name = os.path.basename(jl)[:-6]
    task, arm = name.split("-", 1)
    if task not in TASKS or arm not in ORDER:
        continue
    if not os.path.exists(f"{B}/{name}.meta"):  # still running: meta is written when the run ends
        print(f"(skipping {name}: still running)")
        continue
    meta = open(f"{B}/{name}.meta").read()
    m = re.search(r"start=(\S+) end=(\S+) exit=(\d+)", meta)
    wall = int((datetime.fromisoformat(m.group(2).replace("Z", "+00:00")) - datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))).total_seconds())
    judge = open(f"{B}/{name}.judge").read().strip().splitlines()[-1] if os.path.exists(f"{B}/{name}.judge") else "JUDGE: (not judged)"
    s = run_stats(jl) or {}
    rows.append((TASKS[task], ORDER[arm], task, arm, judge.replace("JUDGE: ", ""), wall, s, m.group(3)))
rows.sort()
with open(f"{B}/table.tsv", "w") as out:
    out.write("task\tarm\tjudge\twall_s\tapi_s\tturns\tcost_usd_equiv\tout_tokens\tin_tokens_incl_cache\tsubagents\tasks\tresult_events\texit\n")
    for _, _, task, arm, judge, wall, s, rc in rows:
        out.write(f'{task}\t{arm}\t{judge}\t{wall}\t{s.get("api_s")}\t{s.get("turns")}\t{s.get("cost")}\t{s.get("out_tok")}\t{s.get("in_tok")}\t{s.get("subagents")}\t{s.get("asks")}\t{s.get("results")}\t{rc}\n')
print(open(f"{B}/table.tsv").read())
