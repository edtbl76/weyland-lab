# AI-DLC v2 — the development workflow (B133)

The lab's structured-development workflow: **AWS AI-DLC v2**, invoked on demand with **`/aidlc`** inside Claude Code.
33 stages / 5 phases / 14 agents, an approval gate at every stage, and a learning loop that promotes corrections into
persistent rules.

**It is opt-in.** Ordinary conversational work is unaffected — v2 does not ambiently govern every request the way the
retired Method's `CLAUDE.md` claimed to. You reach for it when a change deserves process.

Architecture + the "why this over the alternatives" decision matrix: [arch.md §8c](../arch.md#8c-development-lifecycle-ai-dlc-v2-b133).
Flow: [flow-aidlc-workflow.md](../diagrams/flow-aidlc-workflow.md). Demo: [demos/aidlc-workflow.md](../demos/aidlc-workflow.md).

---

## Pieces

- **Engine + content:** `.claude/` — `tools/` (TypeScript CLI, run via bun), `hooks/` (17), `agents/` (14),
  `aidlc-common/` (stages + protocols), `scopes/`, `sensors/`, `knowledge/`, `skills/aidlc/`
- **Project surface:** `AGENTS.md` (repo root) + a **thin** `CLAUDE.md` (19 lines: `@AGENTS.md` + lab conventions)
- **Workspace (state + artifacts):** `aidlc/spaces/default/` — `memory/` (the org/team/project rule layers),
  `intents/<record>/` (per-workflow artifacts), audit shards
- **Upstream pin:** `awslabs/aidlc-workflows`, **`v2` branch, commit `4d0968f`** — internal version **`2.6.18`**
- **Prereq:** `bun` at `/home/edwardmangini/.bun/bin/bun`

> **Not `aidlc-docs/`.** That directory holds hand-written design docs and is **gitignored**. v2 artifacts land in
> `aidlc/spaces/<space>/intents/<record>/` and **are** tracked.

---

## Everyday commands

All of these are typed **in the Claude Code session on rogueone** (not a shell):

```
/aidlc
```
```
/aidlc --status
```
```
/aidlc --doctor
```
```
/aidlc Fix the login timeout bug
```
```
/aidlc --scope infra
```

Bare `/aidlc` resumes an existing workflow, or starts a fresh one. A freeform description auto-detects the scope.

### Scopes — how much process the change gets

| Scope | Stages | Depth | For |
|---|---|---|---|
| `bugfix` | 7 / 33 | minimal | a specific bug |
| `poc` | 8 / 33 | minimal | prove feasibility fast |
| `refactor` | 8 / 33 | minimal | clean up existing code |
| `express` | 10 / 33 | minimal | requirements → deploy, no design pass |
| `security-patch` | 10 / 33 | minimal | CVE response |
| `infra` | 13 / 33 | standard | infrastructure changes |
| `mvp` | 23 / 33 | standard | skip operations, ship the core |
| `classic` | 26 / 33 | standard | V1-style lifecycle, no ideation ceremony *(implicit default)* |
| `workshop` | 26 / 33 | standard, minimal tests | facilitated session, mandatory gates |
| `feature` | 33 / 33 | standard | full lifecycle, practical depth |
| `enterprise` | 33 / 33 | comprehensive | full audit trail |

Don't see a fit? `/aidlc compose "<task>"` proposes a tailored stage grid and asks you to approve it before anything runs.

---

## Direct tool invocations (shell, on rogueone)

The skill wraps these; you rarely need them, but they are the ground truth when debugging.

**Health check:**
```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts doctor
```

**Version:**
```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts version
```

**Full command surface:**
```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts help
```

**Redacted diagnostic bundle** (timeline + findings, no work product — safe to share upstream):
```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts doctor --export
```

A healthy `doctor` ends with a line like `47 passed, 0 failed`.

---

## Lab-specific configuration — do NOT undo these

Three deliberate deviations from stock v2. Each has bitten once; each is load-bearing.

1. **Bedrock env stripped.** Stock v2 ships `CLAUDE_CODE_USE_BEDROCK=1`, `AWS_REGION`, and Bedrock model IDs in
   `.claude/settings.json`. The lab is **$0 Anthropic-direct, not Bedrock** — those keys are removed. The workflow
   rules themselves are provider-neutral, so nothing else needed changing. **Never re-add them.**

2. **`bun` referenced by absolute path.** Every hook command uses `/home/edwardmangini/.bun/bin/bun`, not bare `bun`.
   Hook subprocesses run under `/bin/sh` and do **not** inherit the interactive shell's `PATH`, so a bare `bun`
   resolves to `bun: not found` and the hook silently drops.

3. **Permissions hardened.** The stock bare `"Bash"` auto-allow was removed (a permission bypass flagged in security
   review). What remains: a narrow allow for `Bash(/…/bun ".claude/tools/"*)` plus a **deny** list — `rm -rf`, `sudo`,
   `chmod`, `curl|sh`, `|bash`, `eval`, `base64 -d`, `dd`, `mkfs`. Arbitrary Bash prompts for approval as normal.

---

## Upgrading the pin

v2 is a **branch, not a tagged release** (upstream's latest tag is v1.0.1), so we pin a commit and move deliberately.

1. Pull the upstream repo and check out the new `v2` commit.
2. Regenerate the harness tree: `bun scripts/package.ts` (in the upstream clone) — **never hand-edit `dist/`**.
3. Copy `dist/claude/.claude/` over the lab's `.claude/`, **preserving** `settings.local.json` and any local `skills/`.
4. **Re-apply all three lab deviations above** — an upgrade will re-introduce the Bedrock env, the bare-`bun` hook
   commands, and the broad Bash permission. This is the step that gets forgotten.
5. `/aidlc --doctor` must return `0 failed` before you trust the upgrade.
6. Update the pinned commit + version in this runbook and in [arch.md §8c](../arch.md#8c-development-lifecycle-ai-dlc-v2-b133).

Re-evaluate the whole pinning approach if upstream ever cuts a real **v2 tag**.

---

## Accepted gaps

Retiring the Method cost three generated corpora. These are **known and accepted**, not bugs — recorded here so a
future reader doesn't mistake them for breakage or try to "fix" them.

| Artifact | Count | State | Regenerable? |
|---|---|---|---|
| AIDLC stage/ritual skills (Bifrost) | 52 | **registered, frozen** | ❌ not from weyland |
| `aidlc-stages` prompts (Bifrost) | 28 | **registered, frozen** | ❌ not from weyland |
| DataHub AIDLC glossary — *stage* nodes | part of 17 nodes / 480 terms | **baked into `aidlc_glossary.py`** | ❌ not from weyland |

**Why:** all three derive from the Method rule tree (`.methodaidlc/.method-rule-details/`), which the migration
removed. **What still works:** every one of these remains *registered/baked and serving* — nothing broke at runtime.
Only regeneration is lost.

**The guards** (added at B133 close-out, because silent zero-output is how frozen corpora rot unnoticed):

- `register_aidlc_skills.py` now **exits 1** with an explanation instead of emitting a valid zero-skill loader that
  printed `0 created` and looked like a clean no-op.
- `register_aidlc_prompts.py` now **warns on stderr** that the `aidlc-stages` lane is skipped and that the correct
  expected total is **116, not 144**. It still exits 0 — its other 116 prompts are genuinely regenerable.

**Not affected — explicitly:** `register_aidlc_kb_skills.py` (**511 KB skills**) and the 116 corpus prompts read
`knowledge-repos/`, which was decoupled *before* the retirement precisely so this would hold. Verified at close-out:
511 skills / 116 prompts / brand scrub clean.

**To un-freeze** any of the three, restore a Method source and point `AIDLC_ROOT` at it:

```
cd /home/edwardmangini/IdeaProjects/weyland && AIDLC_ROOT=~/methodaidlc-retired python3 nodes/mother/lab/weyland-platform/scripts/register_aidlc_skills.py --dry
```

---

## Recovering the retired Method

Three independent copies survive — this was deliberate, since Phase 3 was the point of no return:

| Where | What |
|---|---|
| `~/methodaidlc-retired/` | the live tree, moved not deleted |
| `~/methodaidlc-retired-20260820.tgz` | a tarball snapshot |
| `~/IdeaProjects/method-aidlc` | the **source** installer repo (re-installable via `install.sh`) |

---

## Troubleshooting

**`bun: not found` in hook output** — a hook is using bare `bun`. Fix it to the absolute path
(`/home/edwardmangini/.bun/bin/bun`) in `.claude/settings.json`. Most often this is an upgrade that overwrote the
lab's settings; see step 4 of *Upgrading the pin*.

**Stale hook behaviour after editing `settings.json`** — hooks are loaded at session start. Start a fresh Claude Code
session; an existing session keeps the old commands.

**`doctor` reports uncommitted changes under `aidlc/`** — advisory, not a failure. The workspace records travel by
git so the next session (and any teammate) sees the same state. Commit and push them.

**`doctor` reports a scope/graph mismatch** — the compiled stage graph drifted from the stage files. Recompile:
```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-graph.ts compile
```

**A workflow is half-finished and you need to stop** — it parks cleanly at a stage boundary; resume later with
`/aidlc --resume`. Never let a stage be marked complete that didn't actually run.

---

## Related

- [aidlc-kb-ingest.md](aidlc-kb-ingest.md) — the knowledge-repo → RAG ingest (source moved to `knowledge-repos/` here)
- [mcp-gateway.md](mcp-gateway.md) — Bifrost registration steps, incl. the retired step 8
- [code-review-stack.md](code-review-stack.md) — the AI code-review lane the DoD's pillar 7 invokes
- [../concepts/spec-driven-frameworks.md](../concepts/spec-driven-frameworks.md) — B86 eval (incumbent updated by B133)
- [../definition-of-done.md](../definition-of-done.md) — the 8-pillar gate this workflow serves
