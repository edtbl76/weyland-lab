# Demo: Emdash — parallel coding agents, one worktree per task (B104)

**Emdash** (`generalaction/emdash`, MIT, YC W26) is a $0 desktop supervisor over the coding-agent CLIs the
lab already runs (Claude Code · codex · opencode). It gives each task its **own git worktree + branch +
agent**, runs several **in parallel**, and lets you compare diffs / open PRs / merge from **one board** —
with ticket intake from Linear/GitHub and SSH to remote machines. Flow + the "why / why-not":
[../diagrams/flow-emdash-parallel-agents.md](../diagrams/flow-emdash-parallel-agents.md).

This is a **UI deliverable**, so the demo is a **UI walkthrough with eyes-on UAT** (a desktop app — there
is no CLI form to run).

## Install (rogueone, verified v1.2.4)

**Use the `.deb` or AppImage — NOT the npm `emdash`** (that's an unrelated Astro CMS — name collision).

```
# .deb (recommended — system-wide, no FUSE/sandbox):
curl -L -o /tmp/emdash.deb https://github.com/generalaction/emdash/releases/download/v1.2.4/emdash-amd64.deb
sudo apt install /tmp/emdash.deb && emdash
```

## UI walkthrough + UAT (RUN 2026-09-10, eyes-on)

1. **Launch Emdash** → left sidebar shows **Projects**.
2. **Add a project** (folder icon) → point it at a local git repo (used the **weyland** repo) or an SSH
   remote. → *UAT: the project appears in the sidebar.* ✓
3. **Create a task** (+ / new task) → Emdash names it (e.g. `sweet-rabbits-greet`) and opens a tab.
   → *UAT: Emdash creates a **fresh git worktree + branch** for the task — it does NOT run the agent in
   your working tree.* ✓
4. **Watch the agent run** → the task tab shows a live **Claude Code** session executing inside that
   worktree (in the run, it loaded the repo's `/aidlc` orchestrator and printed its phase/scope tables).
   → *UAT: an agent is live in the isolated worktree, driven from the Emdash board — not a separate manual
   terminal.* ✓
5. **(the point) create a second/third task** → each opens its **own** worktree + agent, running
   concurrently; the board lists them side by side. Pick the agent per task in **Providers** (it reuses
   the operator's already-configured CLIs, so the lab's $0 gateway routing applies unchanged).
6. **Review** → per-task diff, open a PR, or merge the ones that worked.

**Result:** installed clean (v1.2.4 `.deb`), added the weyland project, created a task, and Emdash spun up
a git worktree with a live Claude agent inside it — project → task → isolated worktree → agent, exactly as
claimed. **Emdash works.**

## Honest scope note

For a **solo** lab this is **convenience, not a capability gap** — the worktree-per-task isolation is
achievable directly with the CLIs (`git worktree add` + point an agent at it), and one person can only
babysit so many parallel agents. The survey rated the category "optional / low for a solo lab" and it was
delivered as an **operator recipe, not a deployed service**. Adopt it when parallel agent work is actually
the bottleneck (e.g. trying three approaches to one problem and keeping the best).

## Cleanup

Read-only to the lab — Emdash is a workstation app; nothing is deployed to the cluster. The test task's
worktree is isolated on its own branch; discard it in the Emdash UI when done (or `git worktree remove`).
No lab state is touched.
