# Demo — research scratch vault (B187)

A throwaway claude-obsidian vault answers research questions from cited notes, and keeps answering after the session
is compacted. RUN 2026-11-07 on rogueone against B22's question (self-hosted metasearch). Runbook:
[runbooks/research-scratch-vault.md](../runbooks/research-scratch-vault.md). Flow:
[diagrams/flow-research-scratch-vault.md](../diagrams/flow-research-scratch-vault.md).

## CLI walkthrough

**1. Create the vault** (preview, then apply with the plan's hash; runbook § 1). Preview: `"status": "dry-run"`, 14
`changed_paths`, all inside the folder. Apply: `"status": "complete"`.

**2. Fill the inbox** with 10 text sources, each starting with its `Source:` URL: SearXNG's README, search API,
Docker install, search settings and bot-detection pages; the searxng-docker README; the Whoogle, LibreY and YaCy
READMEs; the B22 backlog entry.

[rogueone]
```bash
ls /home/edwardmangini/Documents/scratch-vaults/metasearch/inbox
```

Expected: the 10 files.

**3. Ingest** in a session started from the vault:

[rogueone]
```bash
cd /home/edwardmangini/Documents/scratch-vaults/metasearch && claude --plugin-dir /home/edwardmangini/claude-obsidian
```

`/claude-obsidian:wiki-ingest` showed the plan before writing anything: 6 pages to create (4 projects, 1 comparison,
1 question), 17 claims (14 accepted, 2 provisional, 1 contested), and one partial source (the bot-detection page is
only module stubs). After `yes`, operation `ingest-20261107-metasearch` applied, and the lint found 0 issues across 10
pages and 43 links.

**4. Ask.** `/claude-obsidian:wiki-query Which option has a JSON API an agent can call, and how does it limit
requests?` Answer: SearXNG; JSON must be added to `search.formats` or the call returns 403 (claim
`clm-searxng-format-403`, two sources); the upstream-engine back-off (5 to 120 s, 1 h after HTTP 429). It also gave
the expected answer for a missing source: limits on callers are **not in the vault**, because the bot-detection
source is partial. It named the gap rather than inventing an answer, and labelled its own guess as a guess. Vault
hashes unchanged after the query.

**5. Compaction.** After `/compact`, the same question got the same facts and the same claim IDs: the session
re-read the vault rather than relying on what it remembered.

**Negative case (the vault refuses to guess).** The caller-limit half of question 4 above: the answer reports the gap
and how to fill it (ingest SearXNG's `searx/botdetection` comments), and does not answer from general knowledge.

## UI walkthrough (eyes-on, done by the owner 2026-11-07)

Obsidian on rogueone: vault switcher, **Open folder as vault**, `/home/edwardmangini/Documents/scratch-vaults/metasearch`.

- `wiki/comparisons/Self-hosted metasearch options.md` renders a table of the four options; each project name links
  to its page.
- Graph view (Ctrl+G) shows the 10 pages linked, with no orphans.
- `wiki/entities/Whoogle.md` shows the contested JSON-API claim with both sources.

## Part 2 — the shortcuts (RUN 2026-11-07)

Load them in the current shell (permanently: the `source` line in `~/.bashrc`, runbook § Shortcuts):

[rogueone]
```bash
source /home/edwardmangini/IdeaProjects/weyland/scripts/lab-shortcuts.sh
```

**Roster.** `lab-commands` printed 884 commands in 413 sections from the 98 runbooks (about 225 KB). This finds the
canonical CI trigger, which the lab RAG (`context_search "how do I trigger a CI pipeline run on demand"`) did not return:

[rogueone]
```bash
lab-commands pipeline create weyland-lab
```

Expected first lines: `## B56 — Woodpecker CI Runbook … (docs/runbooks/woodpecker.md#weyland-image-ci--cd-b57a)` and
`[any] woodpecker-cli pipeline create edtbl76/weyland-lab --branch main`.

**Ask.** In about 14 s, this answered with that command, its source section, the smoke-only variant and the
nightly-cron alternative:

[rogueone]
```bash
lab-ask "I want to kick off a CI run for the weyland repo"
```

**Negative case.** `lab-ask "how do I reset my Spotify password"` answered "Not in the index … it's a runbook gap"
and did not answer from general knowledge.

**Vaults.** `vault` creates the vault, then opens Claude in it. Below, the create step runs on its own, followed by
the refusal and the delete:

[rogueone]
```bash
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/scratch-vault.py create shortcut-smoke; vault B22; echo "exit=$?"; vault-rm shortcut-smoke
```

Expected: the vault path, then `vault: topic 'B22' must be lowercase letters, digits and hyphens` with `exit=2`,
then `deleted /home/edwardmangini/Documents/scratch-vaults/shortcut-smoke`.

## Cleanup

[rogueone]
```bash
rm -r /home/edwardmangini/Documents/scratch-vaults/metasearch
```

The vault is volatile by design; nothing outside the folder was written. The shared agent memory was checksummed
before and after the spike: unchanged.
