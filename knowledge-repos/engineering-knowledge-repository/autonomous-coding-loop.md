---
id: autonomous-coding-loop
tags: [pattern, ai-ml, agent, orchestration, long-horizon]
surfaces-at: [application-design, nfr-requirements]
related: [harness-engineering, harness-guides-and-sensors, multi-agent-systems, context-window-management, human-in-the-loop, planner-generator-evaluator, agent-patterns, structured-prompt-driven-development]
complexity: advanced
---

# Autonomous Coding Loop

## What It Is
An orchestration pattern for long-horizon AI coding tasks — work that spans multiple context windows, multiple sessions, or many sequential steps. Standard agent loops terminate when the model decides it is done or when the context window fills. Autonomous coding loops replace that termination behavior with continuation logic: the harness intercepts the agent's attempt to stop, evaluates whether the actual completion goal has been met, and resets or continues the session if it has not. The loop runs until a verifiable done condition is satisfied, not until the model feels finished.

The pattern is also called the "Ralph Loop" in practitioner usage. It is the infrastructure primitive that separates single-session agents from agents that can complete multi-hour or multi-day tasks. Several components work together: the loop controller, plan files on disk for state persistence, self-verification hooks, planner/executor decomposition, and full context resets for very long tasks.

## When to Apply
- Tasks that reliably exceed a single context window — large refactors, multi-file feature implementations, codebase-wide changes
- Work with a verifiable done condition that can be checked programmatically — "all tests pass," "all files in the plan are complete," "no type errors"
- Automated batch coding work where human supervision at each step is impractical
- Any situation where the agent currently stops short of completion or declares itself done with broken output

## When Not to Apply
- Interactive development where the human wants to review and redirect after each meaningful step
- Tasks without a clear, checkable completion criterion — the loop needs a termination signal
- Exploratory work where the right output is discovered through iteration, not defined in advance

## Key Concepts
- **Loop Controller**: The harness component that intercepts session termination and decides whether to continue. When the agent signals completion, the controller runs the done check. If it fails, the controller re-injects the original prompt (or a continuation prompt) into a fresh or continuing context and the agent resumes. This is the minimum mechanism required for the pattern
- **Plan Files**: The agent's working memory across loop iterations, persisted on disk. The agent writes a decomposed plan (list of tasks with completion status) to a file at the start of work. After each iteration, it reads the plan, marks completed steps, determines the next step, and continues. Plan files give the loop durable state that survives context resets — the agent always knows where it is, even in a fresh context
- **Self-Verification Hooks**: Computational sensors that run after each agent edit or after each plan step completes. The hook output (test results, type errors, lint failures) is injected back into the agent context. When verification passes, the agent proceeds to the next step. When it fails, the agent self-corrects before marking the step complete. Self-verification closes the quality loop inside the autonomous run, before human review
- **Completion Goal Injection**: The original task description and done criteria are injected at the start of every context window — not just the first one. As context resets occur, the agent must have the goal available to orient itself. Goal injection prevents the agent from drifting into local optimization (fixing the next failing test) at the expense of global completion (shipping the feature)
- **Full Context Reset**: For very long tasks, compaction alone is insufficient. The harness tears down the session completely and rebuilds it from a compact hand-off file — a structured brief containing: completed steps, current plan state, key decisions made, and the original goal. The next session starts clean but fully oriented. This is closer to how a human engineer hands off work than to how conversation history is normally managed
- **Planner / Executor Decomposition**: Long autonomous runs benefit from separating planning from execution. A planner agent receives the goal and produces a structured plan (steps, acceptance criteria, dependencies). An executor agent receives individual plan steps and implements them. The separation prevents the executor from re-planning mid-task and keeps each agent's context focused. See Planner-Generator-Evaluator entry for the full three-role pattern
- **Sprint Contracts**: Before execution begins, the planner and evaluator negotiate the done condition for each plan step — what specifically must be true for the step to be considered complete. Writing down the done condition before starting catches scope ambiguity that would otherwise surface as a stalled loop. The sprint contract is committed to disk alongside the plan file

## In Practice
Method implements autonomous coding loops for large-scale refactors and batch migration work. The loop controller is a hook registered on agent session end. The done check runs the full test suite and typecheck; the loop only terminates when both pass with no failures. Plan files are written to a `.agent-plan/` directory at the workspace root and committed to git so state survives process restarts. Self-verification hooks run after every file edit. Context resets occur when the context window reaches 80% utilization; the hand-off file is written by the agent before reset and read by the new session at start.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Autonomous Coding Loop**: The reason agents stop before finishing isn't usually a model capability problem — it's that the harness has no mechanism to enforce completion. A loop controller that intercepts termination and checks a real done condition turns "mostly done" into "actually done." Plan files give the loop durable state across context resets; without them, each new context window starts over. Self-verification hooks close the quality loop inside the run so humans aren't reviewing broken output. The key design question is: what is the verifiable done condition? If you can't express it as a check the harness can run, the loop has no termination signal. → `engineering-knowledge-repository/autonomous-coding-loop.md`

## Related Entries
- [Harness Engineering](harness-engineering.md) — the autonomous coding loop is a harness pattern; the loop controller, hooks, and plan files are harness components
- [Harness Guides and Sensors](harness-guides-and-sensors.md) — self-verification hooks are sensors operating inside the loop; completion goal injection is a guide
- [Multi-Agent Systems](multi-agent-systems.md) — planner/executor decomposition within the loop is a multi-agent pattern
- [Context Window Management](context-window-management.md) — context resets and compaction are context management strategies specific to long-horizon loops
- [Human in the Loop](human-in-the-loop.md) — autonomous loops reduce human checkpoints; HITL gates should be placed at plan-step boundaries for high-risk actions
- [Planner-Generator-Evaluator](planner-generator-evaluator.md) — the three-role pattern that extends planner/executor decomposition with a dedicated evaluator
- [Agent Patterns](agent-patterns.md) — the ReAct loop is the foundation; the autonomous coding loop extends it with continuation and state persistence
- [Structured-Prompt-Driven Development](structured-prompt-driven-development.md) — SPDD's Canvas-driven generation runs on the same "durable spec on disk before execution" principle; SPDD governs the loop's input; the autonomous coding loop governs its continuation
