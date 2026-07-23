#!/usr/bin/env python3
"""B66 brain bake-off — operator TOOL-SELECTION: Haiku vs local models.

The operator agent's core job is agentic tool-use: given a natural-language ops request, pick the ONE right
tool-server tool with correct args. This harness scores exactly that — correctness + latency — across both brains.
Haiku runs via `claude -p --model haiku` (subscription, ~$0 for the test); local runs via Ollama. The claude
subprocess runs from $HOME so it does NOT load the weyland dev CLAUDE.md/AIDLC context (which would skew it).

Usage (on rogueone):  python b66-brain-bakeoff.py [local_model ...]
  e.g.  python b66-brain-bakeoff.py gpt-oss:20b qwen3-coder:30b
Env:  HAIKU_MODEL (default "haiku") · OLLAMA_BASE_URL (default http://localhost:11434/v1)
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
HAIKU_MODEL = os.environ.get("HAIKU_MODEL", "haiku")
LOCAL_MODELS = sys.argv[1:] or ["gpt-oss:20b"]
HOME = os.path.expanduser("~")

TOOLS = """Available tools (choose exactly ONE):
- status               : consolidated health of the whole lab (server + model + all backends). args: none
- context_search       : vector retrieval of raw chunks from the knowledge base. args: {"query": str, "backend"?: str}
- context_ask          : RAG — answer a question using the knowledge base. args: {"query": str, "backend"?: str}
- pipeline_trigger     : fire a Dagster pipeline job. args: {"job_name": str}  (default: "weyland_ingestion_job")
- evals_run            : run the full model-eval matrix. args: none
- evals_score          : judge-panel scoring of the latest eval run. args: none
- evals_leaderboard    : panel-averaged eval leaderboard. args: {"run_id"?: int}
- none                 : no tool fits / just answer conversationally. args: none"""

SYSTEM = (
    "You are the weyland homelab operator. Given the user's request, choose the single best tool.\n"
    + TOOLS
    + '\n\nRespond with ONLY a JSON object on one line: {"tool": "<name>", "args": {...}}. No prose, no markdown.'
)

# (request, expected_tool)
CASES = [
    ("How's the cluster doing right now?", "status"),
    ("Search the knowledge base for how the data mesh works.", "context_search"),
    ("What does our documentation say about the guardrail architecture?", "context_ask"),
    ("Kick off the document ingestion pipeline.", "pipeline_trigger"),
    ("Run the full model evaluation matrix.", "evals_run"),
    ("Score the latest eval run with the judge panel.", "evals_score"),
    ("Which RAG model scored most faithful?", "evals_leaderboard"),
    ("What's the weather in Tokyo right now?", "none"),
]


def parse_tool(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0)).get("tool")
    except Exception:
        # last resort: find a "tool": "x" pair
        m2 = re.search(r'"tool"\s*:\s*"([^"]+)"', text)
        return m2.group(1) if m2 else None


def ask_haiku(req):
    prompt = SYSTEM + "\n\nUser request: " + req
    t0 = time.time()
    out = subprocess.run(
        ["claude", "-p", prompt, "--model", HAIKU_MODEL, "--output-format", "text"],
        capture_output=True, text=True, timeout=180, cwd=HOME,
    )
    return (out.stdout or out.stderr).strip(), time.time() - t0


def ask_local(model, req):
    body = json.dumps({"model": model, "stream": False, "messages": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": req}]}).encode()
    r = urllib.request.Request(OLLAMA + "/chat/completions", data=body,
                               headers={"Content-Type": "application/json"})
    t0 = time.time()
    resp = json.loads(urllib.request.urlopen(r, timeout=300).read())
    return resp["choices"][0]["message"]["content"].strip(), time.time() - t0


def run(name, asker):
    print(f"\n=== {name} ===")
    correct = 0
    total_t = 0.0
    for req, expected in CASES:
        try:
            text, dt = asker(req)
        except Exception as e:
            print(f"  ERR {req[:42]:44} -> {e}")
            continue
        tool = parse_tool(text)
        ok = tool == expected
        correct += ok
        total_t += dt
        print(f"  {'OK ' if ok else 'XX '} {req[:42]:44} -> {str(tool):18} (exp {expected}, {dt:.1f}s)")
    print(f"  SCORE {correct}/{len(CASES)}   avg {total_t/len(CASES):.1f}s/req")


if __name__ == "__main__":
    run(f"Haiku ({HAIKU_MODEL})", ask_haiku)
    for m in LOCAL_MODELS:
        run(f"local: {m}", lambda req, m=m: ask_local(m, req))
