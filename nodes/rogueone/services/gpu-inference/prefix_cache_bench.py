#!/usr/bin/env python3
"""Prefix-cache (RadixAttention) bench for SGLang — B111, SGLang's distinct value.

Demonstrates SGLang's automatic prefix caching: a long SHARED prefix (a fat system prompt / RAG context)
is prefilled ONCE (first request = cache miss) then REUSED across later requests (cache hits), so their
TTFT (time-to-first-token) drops sharply. Baseline = the SAME workload with a UNIQUE prefix per request
(diverges at token 1 → all misses). The gap between the two IS the prefix-cache win — and it maps exactly
onto the lab's agent/RAG workloads (repeated system prompts + context).

Stdlib only. Hits SGLang DIRECT on :8002 (measures the engine, not the gateway). Run on rogueone while sglang is up:
    python3 nodes/rogueone/services/gpu-inference/prefix_cache_bench.py
"""
import json, time, urllib.request

BASE = "http://localhost:8002/v1/chat/completions"
MODEL = "unsloth/Llama-3.2-1B-Instruct"
N = 8

# ~2.5K-token shared prefix — a realistic fat system prompt + context block, the thing agents/RAG repeat.
SHARED_PREFIX = "You are the Weyland platform assistant. Context follows.\n" + \
    ("The weyland lab is a zero-budget homelab data and AI platform running on a single bare-metal MS-A2 "
     "plus one GPU laptop, LAN-only, treating constraints as design. " * 120)

def ttft_ms(system, question):
    """Return time-to-first-token in ms (streams, stops at the first content delta)."""
    body = json.dumps({"model": MODEL,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": question}],
                       "max_tokens": 8, "stream": True, "temperature": 0}).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    resp = urllib.request.urlopen(req, timeout=120)
    for raw in resp:
        line = raw.decode("utf-8").strip()
        if line.startswith("data:") and line != "data: [DONE]":
            delta = json.loads(line[5:].strip())["choices"][0].get("delta", {}).get("content")
            if delta:
                return (time.perf_counter() - t0) * 1000
    return None

def run(label, prefix_fn):
    tts = [ttft_ms(prefix_fn(i), f"In one word, answer request number {i}.") for i in range(N)]
    rest = tts[1:]
    print(f"{label:16} first={tts[0]:7.1f}ms  avg-of-rest={sum(rest)/len(rest):7.1f}ms  "
          f"all={[round(x, 1) for x in tts]}")

print(f"model={MODEL}  N={N}  shared-prefix≈2.5K tokens  (TTFT = time to first token)\n")
# SHARED: identical prefix → request 0 is a MISS (warms the cache), 1..N-1 are RadixAttention HITS
run("shared-prefix", lambda i: SHARED_PREFIX)
# UNIQUE: divergent prefix per request (a unique tag at position 0) → every request is a MISS = the baseline
run("unique-prefix", lambda i: f"[unique request {i}] " + SHARED_PREFIX)
print("\nRead: shared-prefix avg-of-rest << unique-prefix avg = the RadixAttention prefix-cache win.")
