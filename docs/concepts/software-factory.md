# Software factory: Warp Factories, and two free ways to close the lab's orchestration gap (B179, 2026-10-09)

A "software factory" is a repeatable pipeline in which coding agents take a ticket through **triage → spec → implement
→ review → verify** and hand a person a pull request. Warp launched **Warp Factories** on 2026-08-18 (closed beta): the
pipeline is defined as version-controlled config, runs as fleets of cloud agents, is billed per agent run, and reports
cost per PR.

## Verdict

| Option | Verdict | Why |
|---|---|---|
| **Warp Factories** | **DON'T ADOPT — fails the $0 gate** | Metered by design. The $0 "pay as you go" plan bills usage at 20% above API rates, Build is $20/month, and self-hosted agents are Enterprise only (custom pricing). The orchestration layer (Oz) is proprietary and hosted. Bring-your-own-inference does not change that every run is billed. |
| Warp terminal client | not needed | Open source since 2026-04-28 (AGPL-3.0; UI crates MIT) and free, but it is a terminal; the agent and factory features depend on Warp's hosted services. |
| **The factory pattern** | **ADOPT THE CONCEPT** | Two ideas are worth taking: the pipeline as version-controlled config, and cost per PR as a measured number. |
| **Emdash, OpenHands** | **EXPERIMENT (B179)** | The two free routes to the one piece the lab does not have: unattended orchestration (a ticket starts an agent run that ends in a PR with nobody steering). Below. |

**The lab already has every stage except the orchestration.** Triage: `scripts/issue-readiness.sh` (B190). Spec:
AI-DLC v2's stages. Implement: Claude Code / Codex / OpenCode on the subscriptions. Review: PR-Agent, CodeRabbit,
Sourcery, Greptile (B106). Verify: Woodpecker CI, the repo guards and the DoD. Repeatable workflows: the B175 loop
library. What is missing is the conveyor: an issue that starts a run without a person driving each step. B119 found the
same gap and rejected the hosted answers (Linear's agent, Blocks) on cost and data location.

## The two experiments

**Vibe Kanban is out** (owner, 2026-10-09: "Vibe Kanban is dead"). B104 had already rejected it as dead / sunsetting;
it was added here by mistake and removed before any trial ran. Emdash is B104's recommended parallel-agent supervisor
([runbooks/parallel-agent-supervisor.md](../runbooks/parallel-agent-supervisor.md)).

Each runs the SAME real issue — a Low-priority, well-specified one that `issue-readiness.sh` rates READY — and is
measured the same way.

| Tool | What it is | Why it might fit | The question it answers |
|---|---|---|---|
| **Emdash** | Open-source (Apache-2.0) desktop app that runs several coding agents in parallel, each in its own git worktree, provider-agnostic | Drives the CLIs the lab already pays for (Claude Code, Codex, OpenCode) — $0 on the subscriptions | Can one person dispatch several issues at once and come back to reviewable PRs? |
| **OpenHands** | Open-source (MIT core) agent platform: an agent takes a GitHub issue, investigates, fixes, runs tests and opens a PR; local, self-hosted or cloud | The closest open equivalent of a factory, with an issue-to-PR resolver built in | Can it run unattended at $0? It calls a model API, so with Claude or GPT it is metered spend — the only $0 route is a local model (next section). |

**Measured per run:** whether it reached a PR with no human step after the start (and if not, where it stopped); time
to PR; subscription usage or tokens consumed; the PR's quality (CI result, review-bot findings, how much rework it
needed to merge); setup effort; and anything it needed outside the $0 / LAN constraints.

## Trial results

| Run | Tool / agent | Mode | Reached a branch unattended? | Time | Usage | Tests | Spec criteria | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 (2026-10-09) | Emdash 1.2.7 → Claude Code, Opus 5.5, from Linear EMA-291 | Auto-approve on (Claude Code bypass mode) | **Yes, after one human step**: Claude Code's bypass-mode warning must be accepted at launch | 22:59:36 → ~23:05 working (23:08 incl. summary) | 52 turns, 21 shell commands; 46k output tokens, 253k cache-write, 5.7M cache-read (subscription) | 35/35 pass in the CI image (32 new, written Red first); setup-token guard passes; agent ran the full guard suite | Met all six **as written** | Left its worktree once: loaded `scripts/.env` in the main checkout and curled Bifrost `/api` (redirected to Keycloak); tried `ssh mother … kubectl exec` (refused: no key). No commits, no pushes; reverted its own coverage-baseline rewrite. Its summary flagged the one thing it could not verify (the live API shape) |
| 2 (2026-10-09) | Emdash 1.2.7 → Claude Code, Opus 5.5, from Linear EMA-291 (corrected spec) | Auto-approve on | **Yes, after the same one human step** (bypass acceptance) | 23:31:08 → 23:38:09 (7 min) | 79 turns, 33 shell commands; 64k output, 304k cache-write, 9.8M cache-read (subscription) | 24/24 pass in the CI image (21 new, Red first); setup-token guard passes | **Met all seven, including the live one**: an independent read-only dry run (writes refused) gives 25 unchanged / 0 writes; with one byte changed in `bifrost-restore`, exactly one PUT at `1.1.0 → 1.1.1`, and the refused write counts as failed | Checked the live API's VALUES itself (read-only `kubectl exec` from rogueone, after reading the lab's memory notes) — the step run 1 could not take. No live writes, no commits, no pushes by the agent. Also edited the Dagster asset docstring, added a backlog progress note and raised its own project's coverage baseline (28 → 55) — all in scope for the repo's conventions. **Missed the lab's Sonar precheck:** reviewing it on `main`, Sonar found one CRITICAL (`reconcile()` cognitive complexity 19 > 15) that would have failed the CI gate; fixed by hand (per-skill body extracted into `_reconcile_one()`), behaviour proven identical by the tests and both live dry runs |
| 3 (2026-10-10) | Emdash 1.2.7 automation `agent-ready-nightly` ("run now") → Claude Code, Opus 5.5; **no issue given** — the prompt says "find the oldest open `agent-ready` issue" | Auto-approve on | **Yes**: found EMA-292 itself through the Linear MCP (project + label, oldest first), ran `issue-readiness.sh` (READY) before touching code | 13:02:17 → ~13:11 (9 min) | 24 shell commands; 45k output, 206k cache-write, 7.5M cache-read (subscription) | 6/6 architecture tests pass after the fix, 6/6 fail before it, under both a read-only cache and a non-writable one; the CI python lane (`run-lang-tests.sh python`, 18 projects) and the coverage ratchet pass; all 19 `repo-guards` commands exit 0 with output read | **Met all five** (B205) | 12-line fix (`lint-imports --no-cache` plus a why-comment in three `_lint()` helpers). Verified against copies in its scratchpad, never the checkout or the owner's root-owned caches; every container `--user` except one guard run on the scratch copy. **Caught two real defects the spec did not mention:** commit `5a05c8c2`, titled as the fix, changes only `docs/backlog.md`; and `scripts/issue-readiness.sh` is not executable although AGENTS.md calls it directly. No commits, no pushes, issue status untouched |
| 4 (2026-10-11) | Emdash 1.2.7 automation `agent-ready-nightly`, **scheduled 04:00**, nobody at the keyboard (app left open since 10-09) → Claude Code, Opus 5.5 | Auto-approve on | **Yes, fully unattended**: started 04:00:40 with no bypass-warning stop (tool calls ran at once) | 15 s | 5 tool calls; 2k output, 0.8M cache-read (subscription) | n/a | n/a: **queue empty** (EMA-292's label was removed after run 3) | Stopped correctly and **proved the empty result was real, not a failed lookup**: label and project exist, then a workspace-wide search by label ID (archived issues included) also returned nothing. Worktree untouched. **Cost of an empty night:** Emdash still created a worktree (`emdash-4a7fae38`) and pushed an empty branch of the same name to GitHub, so a nightly schedule leaves one stale branch and one worktree per night. **Not yet tested:** a scheduled run with the app CLOSED |
| 5 (2026-10-12) | **OpenHands CLI 1.16.0** (SDK 1.21.0) headless → local `qwen3-coder:30b-32k` (MoE 30.5B/~3B active, Q4, 32K ctx; 11.7 of 22.1 GB on the 16 GB GPU, the rest on CPU), in a container with only a scratch copy of the repo at `8cd485b4^` | Headless = always-approve (no confirmation possible) | **Reached a branch, but a destructive one**: no human step after start | 11:37:57 → 12:55:03 (**77 min**, ~9× Emdash) | 53 actions, 1 context condensation; **$0** (local; the operator answered 0 on Haiku meanwhile) | **No tests written** (only a comment: "not possible without mocking HTTP"); the 3 existing shape tests pass and do not notice | **Failed.** It **deleted 7 of the 25 skills** (`weyland-conventions`, `systematic-debugging`, `verify-before-done`, …) and **rewrote 4 with invented text** (`dod-gate`, `pr-lifecycle-reconcile`, …), which its own update path would publish to every agent. Fell into the trap the spec spelled out (compares the list's always-empty `skill_md_body`, so every skill looks changed every run). Swallows Bifrost errors (empty map → tries to create all), the opposite of the fail-closed edge case. Got right: 409/5xx PUT = failed, malformed version rejected, setup token kept | Its final report **claimed success with ticks**. Left two backup files. Nothing outside the sandbox. **Setup findings:** OpenHands sends `reasoning_effort=high` to every model by default and Ollama rejects it for this model (`does not support thinking`), not overridable by env vars (fixed in its saved agent settings); and **headless exited 0 after that fatal model error**, having done nothing, so its exit code cannot be trusted |

**The spec was wrong, and only a live read caught it.** A read-only dry run of the agent's code against live Bifrost
(589 skills; every `latest_version` a string, as assumed) showed its first real run would publish new versions of all
25 git skills, every week: the skills LIST returns `skill_md_body` empty — only `GET /api/skills/{id}` carries the body.
EMA-291 claimed list items carry the body (the key exists; nobody checked its value), the agent built exactly that,
and its fakes encoded the same assumption. The defect is the spec author's (this lab's), not the tool's — and it is
the stubbed-test lesson again: observe the real contract's VALUES, not its keys, before handing a task to an agent.

**Run 2 settles it: given a correct spec, the same unattended set-up produced code that is right against the live system.** Two runs, same issue, same model: the one variable that changed was the spec, and the result followed it.

**Observed behaviour worth keeping:** Emdash silently disables **Create** when the issue's branch name is already taken (archiving a task does not release it — run 1's worktree and branch had to be removed first); Emdash pushes the task branch to GitHub the moment the task is created (empty,
at `main`), so every task publishes a branch; its Create Task dialog defaults to GitHub issues (Linear is reachable but
not obvious); "auto-approve" maps to Claude Code's bypass mode, which needs one human acceptance per session.

## Is a local model viable?

**Only as one bounded arm of the OpenHands experiment.** The facts:

- **The card is a 16 GB RTX 5000 Ada on rogueone, and it is already spoken for.** The operator's brain
  (`qwen2.5:7b-operator`) lives there; B174 measured that a second model (Clef-flash, 8.5 GB in 4-bit) cannot sit beside
  it, and a second model pushes the operator's model to CPU.
- **Agentic coding needs a larger model and a long context than the operator's.** A coding-capable model in the
  14–24B range at 4-bit takes roughly 9–14 GB before its context window, and an agent working through a repository
  needs tens of thousands of tokens of context. On 16 GB that means a small context, or spilling to CPU (rogueone has
  128 GB of RAM, but the B111 MoE note records that offloaded layers make speed claims misleading). Expect it to be
  markedly slower and weaker than Claude; how much is what the arm would measure.
- **The GPU works; only its management tools are affected.** On 2026-10-09 an unattended upgrade at 06:25 moved the
  driver userspace to 595.99.02 while the loaded kernel module stayed 595.91.07 (rogueone has been up since 2026-09-20).
  `nvidia-smi` (NVML) now refuses to run, but CUDA does not: validated the same day, the operator's model loaded fully
  onto the GPU (29/29 layers, 11.4 GB free) and generated at 91.7 tokens/s warm. The running `dcgm-exporter` still reports
  (it started before the upgrade, with the old library loaded) but would fail if restarted; a reboot clears all of it.

**Measured 2026-10-12 (run 5): not viable on this hardware.** The best local coding model that runs here (`qwen3-coder:30b`, half on CPU) took 77 minutes, wrote no tests, and corrupted the git source of truth it was editing (7 skills deleted, 4 rewritten with invented text) while reporting success. On the same task Claude Code via Emdash took 7 to 9 minutes and met every criterion. A local model is $0, but an unattended agent that silently damages content is worse than none: the cost moves to review. So OpenHands is not a $0 option for this lab today. Earlier plan, kept for the record: one OpenHands run on a local coding model, scheduled when the operator's model can be unloaded. If it cannot reach a PR, the conclusion is that OpenHands is not a $0 option for this lab, and that
is an acceptable result. The owner's B86/B159 deferrals (new hardware) are the longer answer: a larger card changes
this section.

## Re-open when

A paid tier becomes acceptable, or new hardware gives a local coding model room beside the operator's.

## Sources

- [Warp pricing](https://www.warp.dev/pricing) (read 2026-10-09)
- [Warp launches Warp Factories](https://fortune.com/press-releases/warp-launches-warp-factories-automate-software-development-2026-08-18/)
- [Warp Factories — cloud agent pipelines](https://ai-tldr.dev/releases/warp-factories/)
- [Warp open sources its AI terminal client](https://www.helpnetsecurity.com/2026/04/30/warp-open-source-client/)
- [Warp: open-source client, proprietary AI cloud](https://www.opentechhub.io/warp/)
- [Top self-hosted open-source AI coding agents](https://www.openhands.dev/blog/open-source-ai-coding-agents)
- [Open-source Warp alternatives](https://openalternative.co/alternatives/warp)
