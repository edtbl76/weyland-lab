# AIDLC v2 Migration — shitcan the Method workflow, adopt AWS v2 clean

**Status:** DESIGN (2026-08-20). **Decision owner:** Ed. **Scope:** the open "AIDLC → v2" High.

## Decision

Stop maintaining a bespoke **Method** fork of AWS AI-DLC. Adopt **AWS `aidlc-workflows` v2 clean**, and
**keep only the knowledge repositories** (decoupled from the workflow), because those are load-bearing DATA that
feed other lab systems — the workflow *overrides* are not.

- ✅ **Drop** the Method **workflow layer** — `.methodaidlc/.method-rule-details/` (54 files), the two-layer
  resolution, the `method-aidlc` installer, and the Method-generated `CLAUDE.md` workflow.
- ✅ **Keep + decouple** the **3 knowledge repositories** — `engineering-knowledge` · `consulting-tools` ·
  `industry-vertical` (517 docs). Relocate them out of `.methodaidlc/`; repoint the generators.
- ✅ **Adopt** AWS v2 (`awslabs/aidlc-workflows` `v2` branch) as the AIDLC workflow, native in Claude Code.

### Why
- The Method workflow layer is a **fork tax**: every AWS release forces a re-port (exactly the pain that triggered
  this). v2's native workflow (32 stages / 14 agents / approval gates / a **learning system** that turns
  corrections into persistent rules) is richer than the overrides added.
- For a **solo, $0 lab**, the Method's consulting framing (mob rituals, team-ownership, engagement archetypes) was
  largely ceremonial. The *substance* that drives quality here is the project's own **DoD 7-pillar gate**, backlog
  process, and memory — none of which are Method (they're `docs/` + the memory system, and survive untouched).

## What v2 is (from the `v2` branch)
- **"One core, many harnesses":** a harness-neutral `core/` (tools/agents/knowledge/memory/scopes/sensors/hooks) →
  `dist/<harness>/` generated trees for 7 harnesses; edits happen in `core/`, `bun scripts/package.ts` regenerates.
- **32-stage / 5-phase** workflow (Initialization · Ideation · Inception · Construction · Operation), **14 agents**
  (11 domain experts + 2 quality-gate reviewers + adaptive-workflows composer), approval gates at every stage.
- **Claude Code install:** `cp -r dist/claude/.claude/ <project>/.claude/`; invoke **`/aidlc`**; verify
  `/aidlc --doctor`. Prereq: **`bun`** (`curl -fsSL https://bun.sh/install | bash`).
- **Caveat:** v2 is a **branch, not a tagged release** (latest tag is v1.0.1). Pin a commit; re-evaluate on a v2 tag.
- **Caveat:** the v2 docs assume Claude Code on **AWS Bedrock**; we run Anthropic-direct. The workflow *rules* are
  provider-neutral — verify at build, but no expected blocker.

## Impact map

| Bucket | Items | Disposition |
|---|---|---|
| **Drop** | `.methodaidlc/.method-rule-details/` (54), two-layer resolution, `method-aidlc` installer, Method `CLAUDE.md` workflow | remove after v2 lands |
| **Keep, decouple** | `engineering-knowledge-repository` · `consulting-tools-repository` · `industry-vertical-repository` (517 docs) | relocate to a stable `knowledge-repos/` path; repoint generators |
| **Survives (project files, not Method)** | `docs/definition-of-done.md` (DoD), `docs/backlog.md`, the memory system, `docs/` conventions | untouched |
| **Re-express** | the weyland-specific bits in the Method `CLAUDE.md`: PRIORITY workflow, DoD gate reference, model-tiering, repository-first | thin project `CLAUDE.md` + v2's learning rules |
| **Lost (conscious call)** | consulting methodology framing — mob rituals, team-ownership, engagement archetypes, per-phase overrides | ceremonial for a solo lab; accept |

## Load-bearing decoupling (do NOT skip — dropping the repos breaks these)
The 3 knowledge repos feed, via generators that read `.methodaidlc/`:
- **`register_aidlc_kb_skills.py`** → 511 Bifrost KB skills (`ek-`/`ct-`/`iv-`)
- **`register_aidlc_prompts.py`** → domain-lens Bifrost prompts (consulting-tools, industry-vertical)
- **`aidlc_glossary.py`** (via `scratchpad/gen_glossary.py`) + **`datahub_emit.py`** → the DataHub glossary
- **`mesh_vocabulary.py`** reference; the **B37 RAG ingest**

→ Relocation must repoint each `ROOT`/path constant, then **re-run + diff** (skills count 517, prompts, glossary
unchanged) before removing `.methodaidlc/`.

## Migration plan (phased — each phase verifiable, reversible until Phase 3)

- **Phase 0 — Prep.** Install `bun` on rogueone. Clone `awslabs/aidlc-workflows`, checkout `v2`, **pin the commit
  SHA** (record it here). Inspect `dist/claude/.claude/` vs the existing weyland `.claude/` (`settings.local.json`,
  `skills/`) for collisions — plan a **merge**, not overwrite.
- **Phase 1 — Decouple the knowledge repos. ✅ DONE 2026-08-20.** Copied the 3 repos to `knowledge-repos/` (repo
  root, tracked; originals kept in `.methodaidlc/` until Phase 3). Added `KB_ROOT` to `register_aidlc_skills.py`
  (`AIDLC_KB_ROOT` env or repo-root `knowledge-repos/`); repointed `register_aidlc_kb_skills.py` (base_dir),
  `register_aidlc_prompts.py` (the 2 repo reads only — rule reads stay on `ROOT`), `aidlc-kb-scrub.py` (`--src`
  default). **Verified:** KB_ROOT resolves; kb skills **511** (matches memory), prompts **144**, scrub **514** — all
  from the new home. `knowledge-repos/README.md` added. **Open for Phase 3:** the *workflow-rule*-derived outputs —
  `register_aidlc_skills.py` (52 stage skills) + `register_aidlc_prompts.py`'s stage prompts + `gen_glossary.py` —
  still read `.methodaidlc` rules; decide their fate when Method is retired (regenerate from v2 stages, or drop).
- **Phase 2 — Install v2.** `cp -r dist/claude/.claude/` merged into the weyland `.claude/` (preserve
  `settings.local.json` + `skills/`). Wire `/aidlc`; `/aidlc --doctor` green. Run a throwaway `/aidlc` workflow on a
  trivial task end-to-end to confirm the engine works native-in-Claude-Code (Anthropic-direct).
- **Phase 3 — Retire Method (point of no return).** Remove `.methodaidlc/.method-rule-details/` + the two-layer
  resolution; delete/retire the `method-aidlc` installer repo usage. **Rewrite `CLAUDE.md`** to a thin project layer:
  keep the weyland-specific PRIORITY conventions (DoD gate, backlog process, lab operating rules) + a pointer to
  `/aidlc`; drop the Method workflow index. Keep a tarball backup of `.methodaidlc/` before deletion.
- **Phase 4 — Validate + DoD.** Re-run the skills/prompts/glossary generators (confirm no regression); run a real
  `/aidlc` workflow; DoD-sweep (backlog B-number, Linear, memory update the AIDLC memories, arch note). Update
  `[[methodaidlc-user-authored]]` + `[[feedback-aidlc-not-superpowers]]` + `[[spec-driven-frameworks-b86]]` memories.

## Open questions (resolve at build, not now)
1. **v2 `.claude/` collision** — does `dist/claude/.claude/` ship a `skills/` or `settings*` that would clobber ours?
   (Phase 0 inspection decides the merge.)
2. **Bedrock assumption** — confirm v2's engine tools don't hard-require Bedrock creds (provider-neutral expected).
3. **Knowledge-repo home** — `knowledge-repos/` in the weyland repo (committed? — they're the user's IP; today they
   live in the gitignored `.methodaidlc`), or a separate repo. Decide before Phase 1.
4. **CLAUDE.md thin layer** — exactly which current conventions are project-critical (DoD, backlog, lab rules) vs
   Method-ceremony to drop. Draft the thin CLAUDE.md in Phase 3 for review.
5. **`bun` on rogueone** — acceptable new toolchain dependency? (yes for a dev workstation; note it.)

## Not doing
- Not migrating the Method workflow overrides onto v2's `core/` (that's the fork tax we're eliminating).
- Not dropping the knowledge repos (load-bearing).
- Not touching the project DoD/backlog/memory (they're not Method).
