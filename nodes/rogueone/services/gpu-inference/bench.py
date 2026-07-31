#!/usr/bin/env python3
"""Throughput bench for the on-demand vLLM GPU server (B111, use case b — continuous batching).
Fires N concurrent fixed-length completions DIRECT at vLLM (localhost:8001, not through Bifrost, to measure the engine)
and reports aggregate tok/s per concurrency level. tok/s should RISE with concurrency as vLLM batches — that's the point.
Stdlib only (no httpx/requests needed). Run on rogueone while the vllm bench is up:
    python3 nodes/rogueone/services/gpu-inference/bench.py
"""
import json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://localhost:8001/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"
MAXTOK = 128
PROMPT = "Write a detailed technical paragraph about distributed consensus algorithms."

def one(_):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAXTOK,
        "ignore_eos": True,      # force a full MAXTOK generation so token counts are comparable across runs
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    resp = urllib.request.urlopen(req, timeout=180)
    dt = time.perf_counter() - t0
    return json.loads(resp.read())["usage"]["completion_tokens"], dt

def run(conc):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        res = list(ex.map(one, range(conc)))
    elapsed = time.perf_counter() - t0
    toks = sum(c for c, _ in res)
    lat = [d for _, d in res]
    return toks, elapsed, toks / elapsed, sum(lat) / len(lat)

print(f"{'conc':>5} {'out_tok':>8} {'elapsed_s':>10} {'tok/s':>9} {'avg_lat_s':>10}")
for conc in [1, 4, 8, 16]:
    toks, elapsed, tps, avglat = run(conc)
    print(f"{conc:>5} {toks:>8} {elapsed:>10.2f} {tps:>9.1f} {avglat:>10.2f}")
