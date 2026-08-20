# knowledge-repos/

Standalone knowledge libraries — moved here out of `.methodaidlc/` during the **AIDLC-v2 migration**
(`aidlc-docs/aidlc-v2-migration.md`). These are **DATA**, decoupled from the retired Method *workflow*:
they feed lab systems independently of any AIDLC workflow.

| Repo | Entries | Prefix | Feeds |
|---|---|---|---|
| `engineering-knowledge-repository/` | ~397 | `ek-` | Bifrost KB skills |
| `consulting-tools-repository/` | ~62 | `ct-` | Bifrost KB skills + domain-lens prompts |
| `industry-vertical-repository/<v>/` | ~58 | `iv-<v>-` | Bifrost KB skills + per-vertical prompts |

**Consumers** (all under `nodes/mother/lab/weyland-platform/scripts/`, read via `KB_ROOT` = this dir):
- `register_aidlc_kb_skills.py` → 511 Bifrost KB skills
- `register_aidlc_prompts.py` → domain-lens Bifrost prompts (also reads workflow stages, separate)
- `aidlc-kb-scrub.py` → scrubbed staging copy (`--src knowledge-repos`)
- the DataHub glossary is **baked** (`aidlc_glossary.py`, generated) → repoint `gen_glossary.py` if ever regenerated

`KB_ROOT` is defined in `register_aidlc_skills.py` (`os.getenv("AIDLC_KB_ROOT")` or the repo-root `knowledge-repos/`).
These docs are the owner's IP; kept verbatim (the scrubbers strip the "Method" brand only in *distributed* copies).
