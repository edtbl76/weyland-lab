# Software factory: Warp Factories, and three free ways to close the lab's orchestration gap (B179, 2026-10-09)

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
| **Emdash, Vibe Kanban, OpenHands** | **EXPERIMENT (B179)** | The three free routes to the one piece the lab does not have: unattended orchestration (a ticket starts an agent run that ends in a PR with nobody steering). Below. |

**The lab already has every stage except the orchestration.** Triage: `scripts/issue-readiness.sh` (B190). Spec:
AI-DLC v2's stages. Implement: Claude Code / Codex / OpenCode on the subscriptions. Review: PR-Agent, CodeRabbit,
Sourcery, Greptile (B106). Verify: Woodpecker CI, the repo guards and the DoD. Repeatable workflows: the B175 loop
library. What is missing is the conveyor: an issue that starts a run without a person driving each step. B119 found the
same gap and rejected the hosted answers (Linear's agent, Blocks) on cost and data location.

## The three experiments

Each runs the SAME real issue — a Low-priority, well-specified one that `issue-readiness.sh` rates READY — and is
measured the same way.

| Tool | What it is | Why it might fit | The question it answers |
|---|---|---|---|
| **Emdash** | Open-source desktop app that runs several coding agents in parallel, each in its own git worktree, provider-agnostic | Drives the CLIs the lab already pays for (Claude Code, Codex, OpenCode) — $0 on the subscriptions | Can one person dispatch several issues at once and come back to reviewable PRs? |
| **Vibe Kanban** | Open-source (Apache-2.0, Rust) self-hosted board: tasks are cards, each assigned to a coding agent in an isolated workspace | Same $0 property; the board is the conveyor | Does a board make the hand-off from issue to agent to PR the default path? Note: its maintainers are sunsetting it into community maintenance, so longevity is part of the verdict. |
| **OpenHands** | Open-source (MIT core) agent platform: an agent takes a GitHub issue, investigates, fixes, runs tests and opens a PR; local, self-hosted or cloud | The closest open equivalent of a factory, with an issue-to-PR resolver built in | Can it run unattended at $0? It calls a model API, so with Claude or GPT it is metered spend — the only $0 route is a local model (next section). |

**Measured per run:** whether it reached a PR with no human step after the start (and if not, where it stopped); time
to PR; subscription usage or tokens consumed; the PR's quality (CI result, review-bot findings, how much rework it
needed to merge); setup effort; and anything it needed outside the $0 / LAN constraints.

## Is a local model viable?

**Only as one bounded arm of the OpenHands experiment, and it is not available today.** The facts:

- **The card is a 16 GB RTX 5000 Ada on rogueone, and it is already spoken for.** The operator's brain
  (`qwen2.5:7b-operator`) lives there; B174 measured that a second model (Clef-flash, 8.5 GB in 4-bit) cannot sit beside
  it, and a second model pushes the operator's model to CPU.
- **Agentic coding needs a larger model and a long context than the operator's.** A coding-capable model in the
  14–24B range at 4-bit takes roughly 9–14 GB before its context window, and an agent working through a repository
  needs tens of thousands of tokens of context. On 16 GB that means a small context, or spilling to CPU (rogueone has
  128 GB of RAM, but the B111 MoE note records that offloaded layers make speed claims misleading). Expect it to be
  markedly slower and weaker than Claude; how much is what the arm would measure.
- **The GPU is unusable right now.** On 2026-10-09 rogueone's NVIDIA management library reported a driver/library
  version mismatch: the loaded kernel module is 595.91.07, the installed userspace is 595.99.02 (a driver upgrade
  without a reboot). Until rogueone reboots, no local-model arm can run.

So: one OpenHands run on a local coding model, scheduled when the operator's model can be unloaded, after the driver
mismatch is fixed. If it cannot reach a PR, the conclusion is that OpenHands is not a $0 option for this lab, and that
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
- [Vibe Kanban](https://www.vibekanban.com/) · [SourceForge mirror (status)](https://sourceforge.net/projects/vibe-kanban.mirror/)
- [Open-source Warp alternatives](https://openalternative.co/alternatives/warp)
