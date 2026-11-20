# Realm of Agents evaluation (B253)

**Verdict (owner, 2026-11-20): simplify, on the free lane.** On the local model every automatic caller uses, the Realm's
delegation adds nothing for 3.6 times the tokens, and its specialists lose to one generalist agent even when Gná routes
correctly. Decision record: [ADR-0016](../adr/0016-simplify-the-realm-on-the-free-lane.md). Backlog B253 (Linear EMA-354).

## The question

The Realm of Agents (B17) answers a task in three steps: Gná picks one of 23 agents, the agent may be a lead that hands
sub-tasks to its members, and the lead combines what comes back. Nobody had measured whether routing and delegation beat a
simpler shape on the same model and tools. The lab's last two retrieval experiments found the simpler design winning
(B38, B247).

## Method

Three arms, all run inside the deployed Realm by `POST /eval/run` (free-only: the local `wl-local` lane,
`qwen2.5:7b-operator` on rogueone with a 32,768-token window, LiteLLM fallbacks off, paid tools removed):

| Arm | What runs |
|---|---|
| realm | Gná routes, and a lead delegates (the Realm as it is) |
| routed | Gná routes, and the chosen agent answers alone with its own tools |
| single | one agent with every tool family the roster uses, no routing |

* **Tasks:** 33 in `services/weyland-dagster/weyland_pipeline/eval_sets/realm.json` (20 single-realm, 13 multi-realm).
  Each has a rubric of checkable criteria and the agents a correct router may pick. Facts in the rubrics were read from
  the live estate on 2026-11-20 and are stable across a night (catalog names, dashboard titles, graph labels, table
  names). No task needs web research. CI fails if any task's text appears in the RAG corpus.
* **Runs:** every task in every arm 3 times: 297 runs, interleaved per task in a fixed hash order so a slow period hits
  every arm alike. A failed run is recorded and scores 0.
* **Judge:** `wl-judge-oss` (gpt-oss:20b on rogueone, a different model from the one judged, $0), blind to the arm (an
  opaque reference ties each score back), one answer at a time, fallbacks off. It marks each rubric criterion met or not
  and gives a 1-5 score. The headline metric is the share of rubric criteria met.
* **Measurements:** tokens, model calls, tool calls and delegations, counted by a per-request callback on the same hook
  as Langfuse, so measuring does not change what the agents do.
* **Cost:** $0. Every model call ran on rogueone.
* **Tooling:** `scripts/realm-eval.sh` (run, judge, report), `scripts/realm_eval.py`; raw data in `eval/realm-b253/`
  (results.jsonl, scores.jsonl, report.md). Runbook: [realm-of-agents.md § Evaluation](../runbooks/realm-of-agents.md).

## Results (2026-11-20)

| Arm | Runs | Failures | Rubric met (mean ± sd) | Single-realm | Multi-realm | Judge 1-5 | Tokens per run | Seconds per run | Tool calls | Delegations | Routing accuracy |
|---|---|---|---|---|---|---|---|---|---|---|---|
| realm | 99 | 0 | 0.31 ± 0.36 | 0.39 | 0.19 | 1.88 | 57,809 | 45 | 6.1 | 2.0 | 0.58 |
| routed | 99 | 0 | 0.33 ± 0.35 | 0.42 | 0.19 | 1.95 | 16,132 | 13 | 1.0 | 0.0 | 0.58 |
| single | 99 | 6 | 0.42 ± 0.35 | 0.49 | 0.32 | 2.31 | 78,951 | 31 | 2.1 | 0.0 | n/a |

**Paired by task** (each task's mean over its 3 runs; 95% bootstrap interval, 5,000 resamples):

| Comparison | Mean difference | 95% interval | Tasks won / lost / tied |
|---|---|---|---|
| single minus realm | +0.11 | −0.02 to +0.25 | 18 / 6 / 9 |
| single minus routed | +0.09 | −0.03 to +0.21 | 17 / 8 / 8 |
| routed minus realm | +0.02 | −0.04 to +0.09 | 11 / 7 / 15 |
| single minus realm, on the 19 tasks Gná routes correctly | **+0.22** | **+0.08 to +0.39** | 12 / 2 / 5 |
| single minus routed, on the same 19 tasks | **+0.19** | **+0.06 to +0.34** | 11 / 4 / 4 |

On the 14 tasks Gná misroutes, the three arms score about the same (realm 0.43, routed 0.43, single 0.39): those are
mostly reasoning tasks the model answers whatever persona it wears. Run-to-run spread within a task is small (mean
standard deviation 0.07 to 0.12), so three runs were enough to separate the arms where they differ.

## Findings

1. **Delegation adds nothing on this model.** The full Realm and routing-only score the same, while delegation costs
   3.6 times the tokens and 3.5 times the time. The model does delegate (29 of 99 runs, 2 delegations a run on average),
   so this is not a model that refuses to hand off; the hand-offs do not improve the answer.
2. **Specialists lose to a generalist, even when routed correctly.** On the tasks Gná routes well, mostly tasks that
   need a tool, the single agent scores twice as high. A narrow tool slice plus a persona prompt leads the small model
   to the wrong tool more often than seeing every tool does (example: the Trino question went to the observability lead,
   who searched Grafana instead of handing it to the SQL agent).
3. **Gná routes 58% of tasks correctly.** Two patterns: she picked herself in 18 of 99 dispatches (the dispatcher, with no
   tools or specialty, then answered as a generic persona), and she sent 35% of all tasks to Verðandi, including a
   Postgres lookup and a design question.
4. **The single agent's weakness is context bloat.** Every call carries about 26,000 tokens of tool schemas (mean 26,682
   input tokens a call, averaged per run). **Correction (B255, 2026-11-20):** per-call figures from Langfuse show the
   free lane's largest call at 31,868 input tokens and the 95th percentile at about 27,400, against a 32,768 window. The
   earlier "no truncation" read per-run averages and was wrong to rule it out: the calls nearest the ceiling were
   probably truncated by Ollama (it drops the oldest messages without an error), which would have hurt the single arm
   most. The verdict stands (the single arm won despite it), but its margin may be understated. On the two pure-reasoning tasks
   with no tool to call (v-simplify, w-faithfulness) it returned an empty answer every time. This is the problem B255
   (context engineering) takes on: picking the few relevant tool schemas per request would likely keep the single
   agent's advantage on tool tasks without the bloat.
5. **The judge is trustworthy for this comparison.** A hand check of 10 answers across arms and task types agreed with
   every overall verdict; at the criterion level, one score was too generous (an answer that named two different labels
   "most numerous" got a 5) and two were strict. None of these tilts the comparison between arms.

## What changed because of it

* **Gná is off her own menu** (`router.py`, B253): a reply naming her fails safe to Odin like any unknown key. Measured
  effect: not re-run; of the 18 self-picks, most were on tasks where Odin is an acceptable agent.
* **Free-only drops paid tools** (`fleet.PAID_TOOL_PREFIXES`, Perplexity): found while building the evaluation, so a
  free-only request now really spends nothing.
* **Not changed here:** leads still delegate, and the Realm keeps its shape, A2A front door and the operator's paid path.
  Dropping the delegation mandate, or replacing specialists with one agent using tool retrieval, is a follow-up decision;
  B255 supplies the tool-retrieval half.

## Limits

* **The free lane only.** Production's paid lane (Haiku, the operator's `delegate_to_realm`) was not measured. A stronger
  model chooses tools better, so the single agent's bloat matters less and delegation might pay. Before restructuring the
  operator's paid path, run a paid sample of the realm and single arms (about $5-6 for 33 tasks once; owner decision).
* **One judge, no human panel** beyond the 10-answer check.
* **The answer text can hint at the arm** (a lead's answer may mention who it delegated to); the judge saw no arm label.
* **Live facts drift.** The rubrics' facts were true on 2026-11-20; a re-run later should re-read them.
* **33 tasks is small;** the overall difference is suggestive, and only the correctly-routed subset is clearly separated.
