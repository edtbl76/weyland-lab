# Demo: AI-DLC v2 workflow (B133)

Demonstrates the lab's structured-development workflow — **AWS AI-DLC v2**, invoked with `/aidlc` — is installed,
healthy, correctly de-Bedrocked for a $0 Anthropic-direct lab, and that retiring the Method did **not** break the
decoupled knowledge-repo generators.

Runbook [runbooks/aidlc-workflow.md](../runbooks/aidlc-workflow.md) ·
flow [diagrams/flow-aidlc-workflow.md](../diagrams/flow-aidlc-workflow.md) ·
arch [§8c](../arch.md#8c-development-lifecycle-ai-dlc-v2-b133).

> ### ⚠ Status: 🟡 PARTIAL — engine validated, full workflow run OUTSTANDING
>
> Part A (below) was **RUN live on rogueone 2026-08-20** and is the executed test. **Part B — a real gated `/aidlc`
> workflow end-to-end — has NOT been run.** It was Phase 2's acceptance criterion in the migration plan and is still
> open: the workspace has **zero intent records** (`aidlc/spaces/default/intents/` contains only the hooks-health
> directory), and `aidlc-utility.ts status` reports *"No active AI-DLC workflow found."*
>
> Part B **cannot be executed unattended** — every stage ends in a human turn-stop (the pre-generation summary
> confirmation and the approval gate), and the framework forbids self-answering them. It needs a person at the
> keyboard. Until then this demo is **🟡, not ✅**, per the DoD's "a demo written but not executed is not done."

---

## Environment

| | |
|---|---|
| Host | **rogueone** (the workstation this Claude Code session runs on) |
| Repo | `/home/edwardmangini/IdeaProjects/weyland` |
| Runtime | `bun` at `/home/edwardmangini/.bun/bin/bun` |
| Version | `aidlc 2.6.18` (upstream `awslabs/aidlc-workflows` `v2` @ `4d0968f`) |

---

## Part A — Engine validation (RUN 2026-08-20, rogueone)

### A1. Health check — the gate for the whole install

```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts doctor
```

Expected (abridged) — the last line is what matters:

```
AI-DLC Health Check
─────────────────────────────────────
✓  bun installed (required for CLI tools and hooks)
✓  aidlc-continue-workflow.ts present
   … 17 hook files …
✓  settings.json present
✓  AWS_AIDLC_DEFAULT_SCOPE (unset — no project default)
✓  Enabled plugins: all enabled (no selection); enabled stage counts: aidlc=30, bootstrap=3
✓  workspace shell ready (.claude/ + aidlc/spaces/default/memory/)
✓  Hooks last fired: log-subagent …, reviewer-scope …, continue-workflow …
✓  Hook drops: none recorded
✓  Cycle detection: 0 cycles
✓  Schema validation: 33/33 stages validated
✓  Graph references: 122 artifacts + edges resolved
✓  Scope validation: 11 scopes valid (37 advisories)
✓  Rule drift: no team/project rule overlaps org policy
─────────────────────────────────────
47 passed, 0 failed
```

**✅ Actual: `47 passed, 0 failed`.** Note `Hooks last fired` carries real timestamps — an installed-but-never-firing
hook is the common failure, and only that line catches it.

### A2. Version + pin

```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts version
```

**✅ Actual: `aidlc 2.6.18`.**

### A3. Stage graph integrity

```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-graph.ts cycles; echo "EXIT=$?"
```

**✅ Actual: no output, `EXIT=0`** (a cycle in the stage DAG would deadlock routing).

```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-graph.ts topo | wc -l
```

**✅ Actual: `33`** — all 33 stages topologically orderable.

```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts scope-table --check; echo "EXIT=$?"
```

**✅ Actual: `EXIT=0`** — the scope table in the orchestrator skill matches the compiled grid (this is the CI drift guard).

### A4. Bedrock strip — the $0 deviation holds

Stock v2 ships Bedrock env in `settings.json`. Confirm it is absent:

```
cd /home/edwardmangini/IdeaProjects/weyland && grep -c -E "CLAUDE_CODE_USE_BEDROCK|AWS_REGION|anthropic\.claude-.*-v1:0" .claude/settings.json
```

**✅ Actual: `0`.** A non-zero count means an upgrade re-introduced Bedrock — see the runbook's *Upgrading the pin* step 4.

### A5. bun is absolute in hooks — the PATH trap

```
cd /home/edwardmangini/IdeaProjects/weyland && grep -o '"command": "[^"]*bun[^"]*"' .claude/settings.json | grep -c -v '/home/edwardmangini/.bun/bin/bun'
```

**✅ Actual: `0`** — every hook `bun` reference fully qualified. Hook subprocesses run under `/bin/sh` and don't
inherit the interactive `PATH`; a bare `bun` silently drops the hook.

### A6. Decoupling regression — the migration's real risk

Retiring the Method must NOT have broken the knowledge-repo generators (511 Bifrost KB skills + the corpus prompts),
which read `knowledge-repos/` via `KB_ROOT`:

```
cd /home/edwardmangini/IdeaProjects/weyland && python3 nodes/mother/lab/weyland-platform/scripts/register_aidlc_kb_skills.py --dry | tail -3
```

**✅ Actual:**
```
511 KB skills across 13 categories.
residual 'Method' brand: NONE
```

```
cd /home/edwardmangini/IdeaProjects/weyland && python3 nodes/mother/lab/weyland-platform/scripts/register_aidlc_prompts.py --dry 2>&1 | tail -6
```

**✅ Actual** — note the warning is the *designed* behaviour, not a fault:
```
WARNING: Method rule source absent under .methodaidlc — skipping the 'aidlc-stages' lane (28 prompts).
         Those prompts stay REGISTERED in Bifrost but are FROZEN (B133). Expect 116, not 144.
         Set AIDLC_ROOT to a restored Method tree to regenerate them.
  60  consulting-frameworks
  56  industry-lens

116 corpus prompts across 2 folders. residual brand: NONE
```

### A7. Retired generator fails loudly (regression guard)

The retired stage-skills generator must refuse to emit an empty artifact:

```
cd /home/edwardmangini/IdeaProjects/weyland && python3 nodes/mother/lab/weyland-platform/scripts/register_aidlc_skills.py --dry; echo "EXIT=$?"
```

**✅ Actual: `EXIT=1`** with the RETIRED explanation. Before B133 close-out this printed a valid zero-skill loader and
exited 0 — indistinguishable from a clean no-op re-sync. See [accepted gaps](../runbooks/aidlc-workflow.md#accepted-gaps).

---

## Part B — Full gated walkthrough (⬜ NOT YET RUN — needs a human at the gates)

Part A proves the engine is healthy. Part B proves the **gated loop** works: questions → pre-generation stop →
artifacts → reviewer → learnings → approval → advance.

### Why this uses a disposable fixture

A demo must **demonstrate**, reproducibly, on demand — it is not a vehicle for doing real work, and it must not
depend on a real initiative happening to be available. That rules out two tempting shortcuts:

- **Don't run a discovery-led scope on an invented task.** `intent-capture` (scopes `enterprise`/`feature`/`mvp`/`poc`)
  asks *what business problem is this solving, who are the stakeholders, what does success look like*. Those questions
  have no honest answers for a task invented to exercise the tool, and a first attempt at this demo stalled there.
- **Don't wait for real work.** That makes the demo non-reproducible — a reader cannot follow it — and turns the
  demo pillar into a promise rather than a demonstration.

So Part B uses **`bugfix` scope** (7 stages: `reverse-engineering` → `requirements-analysis` → `code-generation` →
`build-and-test`), which **skips the discovery stages entirely**. Its questions are about *the defect and the expected
behaviour* — which a fixture can answer truthfully — not about business intent. The demo then creates its own subject,
fixes it, and deletes it.

### B1. Create the fixture (a script with one real, obvious defect)

```
mkdir -p /tmp/aidlc-demo && cat > /tmp/aidlc-demo/avg-line-length.sh <<'EOF'
#!/usr/bin/env bash
# Prints the average line length of a file.
set -euo pipefail
f="$1"
lines=$(wc -l < "$f")
chars=$(wc -c < "$f")
echo $(( chars / lines ))
EOF
```

Reproduce the defect — division by zero on an empty file (invoked via `bash`, so no `chmod` is needed; `chmod` is on
the `settings.json` deny list):

```
printf 'a\nb\n' > /tmp/aidlc-demo/two.txt && : > /tmp/aidlc-demo/empty.txt && bash /tmp/aidlc-demo/avg-line-length.sh /tmp/aidlc-demo/two.txt; bash /tmp/aidlc-demo/avg-line-length.sh /tmp/aidlc-demo/empty.txt
```

**Verified output** (run 2026-08-20, rogueone):

```
2
avg-line-length.sh: line 6: chars / lines : division by 0 (error token is "lines ")
```

exit `0` then exit `1`. That failing second call is the demo's subject — a real defect with an unambiguous expected
behaviour, and no business case to invent.

### B2. Run the workflow

In the Claude Code session on rogueone:

```
/aidlc --scope bugfix avg-line-length.sh divides by zero on an empty file
```

**What to confirm at each step:**

1. **Scope + record** — reports `bugfix` (7 of 33 stages, Minimal depth) and creates an intent record:
   ```
   cd /home/edwardmangini/IdeaProjects/weyland && ls aidlc/spaces/default/intents/
   ```
2. **No discovery questions** — it does NOT ask for stakeholders, success metrics, or a business case. First real
   stage is `reverse-engineering` (it reads the script), then `requirements-analysis` (what should happen on empty
   input). This is the check that the scope choice was right.
3. **Questions render as a structured picker** — options A–E plus an "Other" escape, not free prose.
4. **Pre-generation summary stop** — it asks *"Does this all look correct before I generate the artifact?"* and
   **stops**. Confirm **no artifact exists yet** at that moment. This is the anti-fabrication seam.
5. **Answer `Looks correct`** → artifacts appear under the intent record.
6. **Approval gate** — Approve / Request Changes, presented as a separate turn. Exercise **Request Changes** at least
   once and confirm the Keep/Modify/Redo loop re-runs instead of advancing.
7. **The fix is real** — after `code-generation` + `build-and-test`, re-run the reproducer; the empty-file call should
   now return `0` (or a stated error) instead of a division-by-zero crash.
8. **Audit trail is tool-written**:
   ```
   cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts status
   ```
   should report the current phase/stage, and the audit shards should carry `STAGE_COMPLETED`.
9. **Park + resume** — park mid-run, confirm `status` shows it parked, then `/aidlc --resume` continues from the same
   boundary with nothing skipped.

**Eyes-on (terminal UI).** `/aidlc` has **no web UI** — the rendered surface is the Claude Code terminal: the
statusline (`aidlc-statusline.ts`) and the gate prompts. Confirm visually that the statusline shows the active
scope/stage while a workflow is live, and that gates render as a selectable choice rather than a wall of text. There
is no dashboard, catalog page, or Port entity for this capability — it is dev-side tooling, not a deployed service.

---

## Cleanup / teardown

**Part A is read-only.** Every command is `--dry`, `--check`, or a health read; nothing is written, no cluster
resource is touched, no Bifrost skill or prompt is registered (the `--dry` forms print instead of emitting the
loader that `kubectl exec` would consume).

**Part B creates data in two places**, both disposable by design:

1. **The fixture** — lives entirely in `/tmp`, outside the repo, and is removed with:
   ```
   rm -r /tmp/aidlc-demo
   ```
2. **The intent record** under `aidlc/spaces/default/intents/<record>/` plus audit shards. List, then remove:
   ```
   bun .claude/tools/aidlc-utility.ts intent list
   ```
   ```
   cd /home/edwardmangini/IdeaProjects/weyland && mv aidlc/spaces/default/intents/<record> /tmp/aidlc-demo-record
   ```
   Then clear the pointer and registry so `doctor` reconciles cleanly:
   ```
   cd /home/edwardmangini/IdeaProjects/weyland && rm -f aidlc/spaces/default/intents/active-intent && echo '[]' > aidlc/spaces/default/intents/intents.json
   ```

Verify teardown left the workspace healthy — expect `No active AI-DLC workflow found.` and a passing health check:

```
cd /home/edwardmangini/IdeaProjects/weyland && bun .claude/tools/aidlc-utility.ts status && bun .claude/tools/aidlc-utility.ts doctor | tail -3
```

Because the fixture lives in `/tmp` and the record is removed, a completed Part B leaves **no trace in the repo** —
which is what makes it repeatable on demand rather than a one-off. Note `rm -rf` is on the settings.json deny list;
the `mv`-aside form above is both permitted and reversible.
