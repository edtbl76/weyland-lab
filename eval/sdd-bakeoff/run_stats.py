"""Print one trial's turns, duration, cost-equivalent and output tokens (tab-separated) from its stream-json log;
'-' fields when the run produced no result event.  usage: run_stats.py <run.jsonl>"""
import json
import sys

r = None
for line in open(sys.argv[1]):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if e.get("type") == "result":
        r = e
if r is None:
    print("-\t-\t-\t-")
else:
    u = r.get("usage") or {}
    print(f'{r.get("num_turns")}\t{round((r.get("duration_ms") or 0) / 1000)}\t{r.get("total_cost_usd")}\t{u.get("output_tokens")}')
