# Decision-model benchmark: the operator's first tool choice (B174)

Does a "System One" decision model pick the operator's first tool better than the operator's own model does? This is
the measurement behind [docs/concepts/decision-models.md](../../docs/concepts/decision-models.md), which holds the
verdict.

| File | What |
|---|---|
| `cases.json` | 59 cases: 23 real incident-sweep prompts (one per alert name, 2026-09-07 to 10-07), 6 real chat requests, and 30 written requests (two per tool). `ok` lists every tool that is a correct first move. |
| `system.txt`, `tools.json` | The operator's system prompt and its 21 local tool schemas, copied from a live MLflow `operator` trace (2026-10-07) |
| `run.py` | The runners and the scorer |
| `result_qwen.json`, `result_clef_gpu4.json`, `result_jev.json` | Run 2026-10-07 on rogueone (qwen re-run through `run.py`; it varies by about 3 picks between runs at temperature 0) |

All commands run on **rogueone**. Score the saved runs:
```
python3 /home/edwardmangini/IdeaProjects/weyland/eval/decision-model/run.py score
```

## Re-run the baseline

This is the operator's current path: `qwen2.5:7b-operator` through Ollama, about 1 minute. It shares the GPU with the
live operator, so run it outside an incident.
```
python3 /home/edwardmangini/IdeaProjects/weyland/eval/decision-model/run.py qwen
```

## Re-run Clef-flash

Clef-flash needs about 8.5 GB of graphics memory, so unload the operator's model first; Ollama reloads it on the
operator's next request. Clef-flash runs under `transformers` 5.10+ because its decision layer is custom code that
Ollama can't run. The 19 GB of weights download to the Hugging Face cache on first use.

**1. Set up the environment.** Install the tools into a scratch venv (here, `/tmp/clef-venv`):
```
uv venv --system-site-packages /tmp/clef-venv && uv pip install -p /tmp/clef-venv "transformers>=5.10.2" accelerate bitsandbytes pillow safetensors huggingface_hub
```

**2. Unload the operator's model:**
```
curl -s http://localhost:11434/api/generate -d '{"model":"qwen2.5:7b-operator","keep_alive":0}'
```

**3. Run it:**
```
/tmp/clef-venv/bin/python /home/edwardmangini/IdeaProjects/weyland/eval/decision-model/run.py clef --mode gpu4
```

**4. Clean up.** Delete the venv and the cached weights:
```
rm -rf /tmp/clef-venv /home/edwardmangini/.cache/huggingface/hub/models--Cloudflare--clef-flash
```

A case with no tool, or an error, scores as wrong. The qwen runner caps output at 256 tokens: uncapped, it once
generated about 20K tokens instead of a tool call.

## Re-run Jev (paid)

This uses the TypeSafe credit: about 119K input tokens, roughly $0.005 a run. The key comes from `scripts/.env` and
is never printed.
```
cd /home/edwardmangini/IdeaProjects/weyland && set -a && . scripts/.env && set +a && python3 eval/decision-model/run.py jev
```
