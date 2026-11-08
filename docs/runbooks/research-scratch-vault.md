# Research scratch vault (claude-obsidian)

A throwaway knowledge folder for one research task. Claude reads the task's sources, writes linked notes that cite
them, and answers questions from those notes while the task runs. Delete the folder when the task is done. It is a
local, file-only stand-in for RAG: no database, no embeddings, no service.

Kept as a working habit by B187 (EMA-245, 2026-11-07). Demo: `docs/demos/research-scratch-vault.md`. Flow:
`docs/diagrams/flow-research-scratch-vault.md`.

## Shortcuts

Shell functions for an interactive shell on rogueone, from `scripts/lab-shortcuts.sh`. Install once by adding this
line to `~/.bashrc`, then open a new terminal:

[rogueone]
```bash
source /home/edwardmangini/IdeaProjects/weyland/scripts/lab-shortcuts.sh
```

| Command | What it does |
|---|---|
| `lab-commands` | Prints the lab's command roster: every command in `docs/runbooks/*.md` and the DR catalog `docs/dr.md` (about 900), grouped by section, each line `[host] command` |
| `lab-commands WORD ...` | Only the entries containing every word, e.g. `lab-commands pipeline create`. Exit 1 when nothing matches |
| `lab-ask "QUESTION"` | Asks Claude (Sonnet, no tools, about 15 s) which runbook command does a job. Answers with the command, the host and the runbook section, or says "not in the index" |
| `vault TOPIC` | Creates the scratch vault `~/Documents/scratch-vaults/TOPIC` (or reopens it) and starts Claude in it with claude-obsidian loaded |
| `vault-rm TOPIC` | Deletes that vault. Refuses anything that is not a scratch vault |

- **The roster is never stored.** `lab-commands` and `lab-ask` rebuild it from the runbooks on every call, so it is
  always current. When `lab-ask` says "not in the index", the runbook is missing the command: add it there.
- **Host `any`** means the runbook did not label the command with a host.
- **Topic names** are lowercase letters, digits and hyphens, named by topic. A B-number (`b22`) is refused.
- The decisions are in tested Python (`scripts/lib/lab_commands.py`, `scripts/lib/scratch_vault.py`); the shell
  functions only connect them to `claude` and `rm`. Override paths with `WEYLAND_REPO`, `CLAUDE_OBSIDIAN_HOME`,
  `SCRATCH_VAULTS`, and the model with `LAB_ASK_MODEL`.

The sections below are what `vault` and `vault-rm` do, step by step, for when the shortcuts are not loaded.

## When to use it

- A research question spans several sources (project docs, READMEs, a backlog entry) and the session is long
  enough to be compacted. The notes outlive `/compact`: after one, the session re-reads the vault and answers with
  the same facts and the same citations (measured in the B187 run).
- You want disagreements kept visible. The claim ledger records a claim with both its supporting and its
  contradicting source (status `contested`) instead of silently picking one.

Not for: anything that must be kept (it is deleted at the end), the backlog or status (Linear and
`docs/backlog.md` stay the source of truth), PDFs (claude-obsidian 3.0.1 captures only a PDF's metadata), or the
shared agent memory (see Safety).

## What is installed

| What | Where | Pin |
|---|---|---|
| Obsidian desktop (optional, for browsing the notes) | snap `obsidian` on rogueone | whatever the snap ships (1.15.0 at adoption) |
| claude-obsidian (Claude Code plugin + Python CLI) | `/home/edwardmangini/claude-obsidian` (git checkout) | tag `v3.0.1`, commit `6414e1a2`, files verified against its `SHA256SUMS` |
| Scratch vaults | `/home/edwardmangini/Documents/scratch-vaults/<topic>` | one folder per task, named by topic |

The plugin loads only in a session started with `--plugin-dir`, so ordinary Claude Code sessions never see it. Its
two hooks are read-only: SessionStart injects nothing unless `CLAUDE_OBSIDIAN_SESSION_CONTEXT=1` is set, and Stop only
warns about unfinished vault transactions. Neither hook makes network calls.

Upgrading is a change: pick a tag at least 14 days old, ask the owner first, verify `SHA256SUMS`, and re-run the demo.

## 1. Create the vault

Every write is previewed first. The preview prints a plan and its `approved_plan_sha256`; the apply must repeat the
same command with that hash.

[rogueone]
```bash
cd /home/edwardmangini/claude-obsidian && python3 scripts/claude-obsidian.py init /home/edwardmangini/Documents/scratch-vaults/metasearch --generated-at 2026-11-07T00:00:00Z --operation-id metasearch-init
```

Check that every path in `changed_paths` sits inside the new folder (14 paths), then apply:

[rogueone]
```bash
cd /home/edwardmangini/claude-obsidian && python3 scripts/claude-obsidian.py init /home/edwardmangini/Documents/scratch-vaults/metasearch --generated-at 2026-11-07T00:00:00Z --operation-id metasearch-init --approved-plan-sha256 <hash-from-the-preview> --apply
```

The output ends with `"status": "complete"`. Replace `metasearch` with the task's topic.

## 2. Fill the inbox

Put text or Markdown sources in `inbox/`. Start every file with the URL it came from, so the source ledger points at
the real page rather than a local path:

```text
Source: https://github.com/searxng/searxng/blob/master/docs/dev/search_api.rst
Fetched: 2026-11-07

---
```

Only public material. Never put secrets, `scripts/.env` values or private notes in a vault: the session sends what
it reads to the model.

## 3. Ingest and ask

Start a second Claude Code session from the vault, in a new terminal:

[rogueone]
```bash
cd /home/edwardmangini/Documents/scratch-vaults/metasearch && claude --plugin-dir /home/edwardmangini/claude-obsidian
```

Then, inside that session:

1. `/claude-obsidian:wiki`: checks that the vault is ready.
2. `/claude-obsidian:wiki-ingest`: drafts the notes, shows the plan (files to create, claims and their status), and
   applies only after you say yes. A lint runs afterwards; expect 0 dead links and 0 orphans.
3. `/claude-obsidian:wiki-query <question>`: answers from the notes, citing pages and claim IDs, and confirms the
   vault was not changed.
4. `/claude-obsidian:save`: keeps one answer as a note, if it is worth keeping for the rest of the task.

Keep the files in `inbox/` until the task ends: the ledgers point at them.

To browse the result, open the folder as a vault in Obsidian (vault switcher, **Open folder as vault**).

## 4. Delete it

When the task is done, copy anything worth keeping into its real home (the Linear issue, the backlog entry, a
runbook), then delete the folder:

[rogueone]
```bash
rm -r /home/edwardmangini/Documents/scratch-vaults/metasearch
```

Also remove it from Obsidian's vault list if you opened it there.

## Safety

- **Never point it at `/home/edwardmangini/agent-memory/weyland`** (the shared agent memory) or at the owner's own
  `ObsidianVault`. B182 recorded Basic Memory rewriting 207 of 213 notes on its defaults; a vault tool that rewrites
  frontmatter would do the same. Scratch folders only.
- claude-obsidian writes in transactions: each operation journals backups under `.vault-meta/transactions/<id>/` and
  restores the previous state if an apply fails. That covers its own writes, not edits made at the same time in
  Obsidian or another editor.

## What B187 rejected (do not re-propose)

- **Obsidian as the owner's window onto the agent memory.** The memory store opens fine as a vault (Obsidian resolves
  `[[links]]` by file name, which matches the frontmatter `name:` for all but 3 of 260 notes), but the owner cannot
  judge whether agent-written technical notes are right, and browsing them does nothing chat does not. Link health is
  better checked by script: 64 links to 33 missing notes, measured 2026-11-07.
- **graphify's Obsidian export** (`graphify export obsidian --dir <path>`). 22,685 notes (97 MB) for weyland, too many
  for Obsidian's graph view. The notes also drop edge direction, which `scripts/graphify.sh affected` keeps, along
  with depth and `file:line`.

## Gotchas

- The bundled skills read a source in full and say when a source is partial. A source that is only an
  auto-generated stub page gets recorded as `partial`, and questions that depend on it get a stated gap, not an
  invented answer. Choose sources with real prose.
- A query answer can include the session's own inference. claude-obsidian labels it ("my inference, not in the
  vault"); read those labels.
