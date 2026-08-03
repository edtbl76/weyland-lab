# NeMo Guardrails trial (B32 evaluation)

**Question:** does NeMo Guardrails' Colang **dialog/topical** control add enough value over our **edge I/O scanning**
(weyland-guard — injection / toxicity / grounding / PII at the agent edge + the MCP gateway) to justify adopting a whole
framework and a new DSL (Colang)?

## Run — throwaway venv (nemoguardrails deps are HEAVY; NEVER add them to a prod image)

Run on a host that (a) has internet for `pip` and (b) can reach Ollama on rogueone (`192.168.1.230:11434`) — the
workstation or mother:

```
python3 -m venv /tmp/nemo-venv && . /tmp/nemo-venv/bin/activate && pip install nemoguardrails
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/nemo-guardrails-trial && python run_trial.py
```

## What it exercises
- **Input rail** (`self check input`, prompt in `config/config.yml`) — an LLM-judged block for jailbreak / off-domain.
- **Topical rail** (`config/rails.co`, Colang) — NeMo's distinctive dialog control: refuse off-domain requests
  conversationally (embedding-matched, generalizes beyond the literal examples).
- The rails' LLM is the operator's own brain (`gpt-oss:20b`), so the trial reflects the real operator loop.

## How to read the result
- **on-topic → answered · off-topic → the topical refusal · jailbreak → blocked** ⇒ the rails work as advertised.
- Then weigh **value** (topical/dialog control we currently lack) against **cost** (a framework + the Colang DSL to
  maintain + extra per-turn rail LLM calls = latency), and whether the operator's own system prompt + our edge scan
  already cover the need. → **decision on B32** (adopt / skip), recorded in the backlog + Linear EMA-56.

First run may need a tweak — NeMo config + Colang are version-sensitive; paste the output and we iterate.
