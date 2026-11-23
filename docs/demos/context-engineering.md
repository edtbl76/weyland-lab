# Demo: context engineering (B255)

Three things B255 left running, each checkable in a minute: the Ollama truncation watch, the always-loaded harness
budget, and the Realm's context-engineering trial arms. All three are read-only (no data created, nothing to tear
down). Decision record: [ADR-0017](../adr/0017-context-engineering-for-the-harness-and-services.md); evidence:
[docs/concepts/context-engineering.md](../concepts/context-engineering.md). Run 2026-11-22 against live infra; the
outputs below are from that run.

## 1. Ollama truncation watch

Flow: [flow-ollama-truncation-watch](../diagrams/flow-ollama-truncation-watch.md).

**UI (UAT, eyes on).** Open Uptime Kuma at `http://192.168.1.243:30301` and find the monitor **ollama-truncation**.
Confirm: it is green, its heartbeat bar has a beat about every 15 minutes, and the history shows the red beat of
2026-11-21 01:44 (the real event below) followed by green.

**CLI.** Run the watch once and read its verdict:

[rogueone]
```
systemctl --user start ollama-truncation-watch.service && journalctl --user -u ollama-truncation-watch.service -n 3 --no-pager -o cat
```

Expected (2026-11-22 22:27):

```
up: no prompt truncated in the last 16 min
```

It fired on a real event: on 2026-11-21 at 01:41 and 01:42 the Langfuse judge's evaluator prompts (10,208 and 10,314
tokens) were cut to 4,098, and the 01:44:31 run reported

```
down: 2 prompt(s) truncated in the last 16 min; worst: 10314 tokens sent, 4098 kept. Caller: docker logs ollama-proxy at that time
```

then `up` again at 02:00 (after the evaluator inputs were trimmed). Unit tests: `scripts/tests/test_ollama_truncation_watch.py`.

## 2. Always-loaded harness budget

**CLI** (also a CI repo-guard):

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/check-harness-budget.py
```

Expected (2026-11-22):

```
harness-budget: OK — instructions 20124/26000 bytes (5 files), skills 15043/17500, agents 3971/5000
```

**UI:** none of its own; in a Claude Code session in this repo, `/context` shows what these files cost in tokens.

## 3. The Realm's context-engineering trial arms

`POST /eval/run` on the Realm takes the arms `single-rt` (static tool retrieval, top 8), `single-rs` (per-step
retrieval) and `single-ce` (context editing) beside B253's three. The committed results reproduce their report:

[rogueone]
```
REALM_EVAL_DIR=/home/edwardmangini/IdeaProjects/weyland/eval/context-b255-rs bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/realm-eval.sh report && cat /home/edwardmangini/IdeaProjects/weyland/eval/context-b255-rs/report.md
```

Expected: `wrote .../report.md` and the table with `single` 0.39 (72,413 tokens a run), `single-rs` 0.35 (11,143) and
`single-rt` 0.37 (9,591). The file is unchanged (it is regenerated from the committed results). To re-run a trial (about
2 hours, free), see [realm-of-agents.md § Context-engineering trials](../runbooks/realm-of-agents.md).

**UI:** each trial run is traced in Langfuse (the Realm's session per request); the console at the Realm's UI shows the
same agents, but the arms are reached only through `/eval/run`.
