---
id: eval-run
title: The RAG eval run
category: Evaluation
description: Run the RAG eval harness end to end (generate and run, then score), watch it to completion, and report the leaderboard against the previous run.
terminal_condition: The newest eval_runs row is complete and scored and the leaderboard is reported against the previous run, or a job fails twice (stop and report the error).
pacing: One check per expected stage time (run about 40-60 minutes, scoring about 15-60 minutes). The eval holds rogueone's Ollama, so incident sweeps defer while it runs.
source: docs/runbooks/eval-harness.md (Operating — trigger & query; Golden question set)
---

## Prompt

Run the RAG eval and report the result.

1. Trigger `weyland_eval_job` with the trigger in `docs/runbooks/eval-harness.md` § "Operating". It generates the
   questions and runs the model matrix.
2. Check progress with the runbook's progress queries once per expected stage time. Count errors per model, not just
   the run's status.
3. When the run completes, trigger `weyland_eval_score_job` and watch it the same way.
4. Run the leaderboard query for this run and the previous one. Report each model's faithfulness, answer relevancy
   and context relevancy, and the change from the previous run.
5. A judge score is not ground truth: say which judge scored it and flag any model with errors or empty answers.

Stop when the terminal condition holds.
