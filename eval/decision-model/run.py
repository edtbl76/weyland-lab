"""B174 micro-benchmark: the operator's first tool choice — qwen2.5:7b-operator (current path) vs Clef-flash.

    python3 run.py qwen                 # needs Ollama on rogueone with qwen2.5:7b-operator
    python3 run.py clef --mode gpu4     # needs torch + transformers>=5.10.2 + bitsandbytes; ~8.5 GB VRAM
    python3 run.py score                # prints the comparison table from the result files

Each case in cases.json lists every tool that is a correct FIRST move; a run writes result_<runner>.json beside this
file. A model that answers with no tool, or errors, scores the case wrong — an absent answer is never a pass.
Verdict and context: docs/concepts/decision-models.md.
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen2.5:7b-operator")
# The revision benchmarked 2026-10-07. Pinned because run.py imports and EXECUTES the repo's joint_schema_model.py.
CLEF_REVISION = "17f0b0ad64efb65d273590632833508766b2aae6"
SWEEP = "real-sweep"
SWEEP_DROPS = {"delegate_to_realm"}   # the incident sweep is compiled without it (INCIDENT_SWEEP_ALLOW_PAID=false)
SOURCES = (SWEEP, "real-chat", "written")


def load(name):
    return json.loads((HERE / name).read_text())


def tools_for(case, tools):
    if case["source"] != SWEEP:
        return tools
    return [t for t in tools if t["function"]["name"] not in SWEEP_DROPS]


def qwen_pick(case, system, tools):
    if not OLLAMA_URL.startswith(("http://", "https://")):
        raise ValueError(f"OLLAMA_URL must be http(s): {OLLAMA_URL}")
    body = {"model": QWEN_MODEL, "temperature": 0, "stream": False, "max_tokens": 256,
            "tools": tools_for(case, tools),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": case["request"]}]}
    request = urllib.request.Request(OLLAMA_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310  # nosec B310 — scheme checked above
        reply = json.load(response)
    calls = reply["choices"][0]["message"].get("tool_calls") or []
    return (calls[0]["function"]["name"] if calls else None), None


def clef_runner(mode):
    import torch
    from huggingface_hub import snapshot_download
    path = snapshot_download("Cloudflare/clef-flash", revision=CLEF_REVISION)
    sys.path.insert(0, path)
    from joint_schema_model import load_release_model, systemone
    kwargs = {}
    if mode == "gpu4":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                           bnb_4bit_compute_dtype=torch.bfloat16)
    model, processor = load_release_model(path, device="cpu" if mode == "cpu" else "cuda", **kwargs)

    def pick(case, system, tools):
        criteria = {t["function"]["name"]: " ".join(t["function"]["description"].split())[:400]
                    for t in tools_for(case, tools)}
        answer = systemone(model, processor, {
            "model": "clef-flash", "state": {"operator_rules": system, "request": case["request"]},
            "questions": {"tool": {"type": "choice", "criteria": criteria,
                                   "instructions": "Which ONE tool should the operator call first to handle the request?"}},
        })["answers"]["tool"]
        return answer["choice"], answer.get("confidence")
    return pick


def run(name, pick):
    system, tools, cases = (HERE / "system.txt").read_text(), load("tools.json"), load("cases.json")
    pick(cases[0], system, tools)   # warm-up: model load / first-call compile is not a decision's latency
    results = []
    for case in cases:
        started = time.perf_counter()
        try:
            choice, confidence = pick(case, system, tools)
        except (OSError, ValueError, KeyError) as error:   # an errored call is a miss, recorded with its reason
            choice, confidence = None, None
            print(f"{case['id']}: error {error}", file=sys.stderr)
        row = {"id": case["id"], "pick": choice, "ok": choice in case["ok"],
               "ms": round((time.perf_counter() - started) * 1000), "confidence": confidence}
        results.append(row)
        print(row["id"], row["pick"], row["ok"], row["ms"], flush=True)
    (HERE / f"result_{name}.json").write_text(json.dumps(results, indent=0))


def score():
    sources = {c["id"]: c["source"] for c in load("cases.json")}
    for path in sorted(HERE.glob("result_*.json")):
        rows = json.loads(path.read_text())
        latencies = sorted(r["ms"] for r in rows)
        split = " ".join(f"{s} {sum(r['ok'] for r in rows if sources[r['id']] == s)}/"
                         f"{sum(1 for r in rows if sources[r['id']] == s)}" for s in SOURCES)
        print(f"{path.stem[7:]:<12} {sum(r['ok'] for r in rows)}/{len(rows)}  {split}  "
              f"median {statistics.median(latencies):.0f} ms  p95 {latencies[int(0.95 * len(rows)) - 1]} ms")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runner", choices=("qwen", "clef", "score"))
    parser.add_argument("--mode", choices=("gpu4", "cpu"), default="gpu4", help="clef only")
    args = parser.parse_args()
    if args.runner == "score":
        score()
    elif args.runner == "qwen":
        run("qwen", qwen_pick)
    else:
        run(f"clef_{args.mode}", clef_runner(args.mode))


if __name__ == "__main__":
    main()
