# Graphify — evaluation and adoption plan (EMA-191)

**Verdict: adopt narrowly.** Take the deterministic structural half — `affected`, `god-nodes`, the AST
graph — and wire it to DoD Pillar 8 (cascading changes). Do **not** adopt it as a retrieval layer; it
has no embeddings by design and our graph-RAG already covers that. $0, Apache-2.0, runs local.

Evaluated 2026-08-26 against `graphifyy` 0.9.50 in an isolated venv, no global install.

---

## What it is

An AI-coding-assistant skill (`/graphify .`) that turns a folder into a queryable knowledge graph:
tree-sitter AST for code, an LLM pass for docs/PDFs/images, Leiden community detection, and outputs
`graph.json` / `graph.html` / `GRAPH_REPORT.md`. Repo: `Graphify-Labs/graphify` (110,928 stars,
Apache-2.0, active — pushed 2026-08-25).

> **The issue's link is stale.** It was filed against `safishamsi/graphify`, which now 301s to
> `Graphify-Labs/graphify`. The README's own manual-install `curl` still points at the old org.
> PyPI name is `graphifyy` (double y) — `graphify` 404s; the README says the name is being reclaimed.

## Measured on this repo, not claimed

| | |
|---|---|
| Full tracked source | 1,910 files / 24 MB |
| Extraction | **13,623 nodes · 22,861 edges · 1,093 communities in 14.5s** (28 workers) |
| Subset (62 files) | 324 nodes / 642 edges in **0.56s** |
| Network calls | **zero** on the AST path |
| Coverage | `.md` 8,693 · `.ts` 2,149 · `.py` 1,578 · `.js` 673 · `.sh` 155 · `.tf` 90 · `.java` 12 |

**The 71.5× token-reduction claim was NOT tested** and is not repeated here as fact.

### Accuracy — spot-checked against source, not trusted

- `god-nodes` ranked `Hook` first. Verified: real class at `weyland-guard/guardrails/verdict.py:11`,
  79 references. `Decision`, `Mode`, `Verdict` likewise real classes in that file.
- `affected "Verdict"` returned **exact** file:line for every `Verdict(...)` construction site —
  `policy.py:21` and `:77`, `pipeline.py:27`, `grounding.py:109`, plus 4 test files. Not one was
  approximate.
- `.tf` nodes are genuine resources: `github_repository.weyland_lab`,
  `port_action.scale_data_mesh_store`, `provider.github`.

### It found a real defect we did not know about

`weyland-tool-server/guardrails/verdict.py` is **byte-identical** to the `weyland-guard` copy, with
one importer still pointing at it — a duplicated module surviving the B70 extraction. Surfaced by
label collision while querying, not by looking for it.

---

## Limits found (these bound the adoption)

**1. Shell `source` is not a dependency edge.** 13 scripts source `scripts/lib/common.sh`;
`affected "common.sh"` returns **"No affected nodes found."** Shell nodes carry only `calls` (71),
`contains` (33), `defines` (105) — **zero `imports`**. Python and TypeScript get 1,200 `imports`
edges, so this is bash-specific. **This repo's guard surface is shell**, so the single most useful
query on the most safety-critical code is the one that does not work.

**2. Ambiguous labels break `affected` at repo scale.** `affected "Verdict"` works on a subset and
returns `No unique node match for Verdict` on the full repo — 12 nodes share that label. The tool
warns about this itself (`pre-#1504 node-ID scheme … fixes same-name-file collisions`) and says
`extract --force` produces path-qualified IDs. **Untested** — that path needs an LLM backend.

**3. `query` is fuzzy string matching, not semantic.** Asking *"how does a guardrail decision get
recorded"* pulled in `_get()` from `scripts/brain-bakeoff/full-loop.py:61` — an HTTP helper with zero
occurrences of `Decision`/`Verdict`/`Hook`. `rapidfuzz` matched "get" from "get recorded". This is
the cost of the no-embeddings design, not a bug, and it is why this does **not** replace graph-RAG.

**4. Point it at tracked files only.** The working tree is 927 MB; tracked source is 24 MB. The rest
is `.terraform/` provider binaries and venvs under `weyland-platform/scripts/`. Feed it
`git ls-files`, never the raw directory.

**5. Two dependency gaps are silent-ish.** 16 `.sql` files "contributed nothing" without
`graphifyy[sql]` — it *did* say so, naming the package and issue number, which is better behaviour
than most. And `graspologic` (Leiden) requires `python_version < "3.13"`; **rogueone runs 3.13.3**, so
Leiden is unavailable and clustering silently falls back.

**6. `graphify install` edits `~/.claude/CLAUDE.md`** — the global instructions file holding the
commit policy — and writes `~/.claude/skills/graphify/SKILL.md`. Not run during this evaluation.

### On "source never leaves the machine"

Half true, and the half that matters is configurable. Code is tree-sitter, entirely local. Docs, PDFs
and images use an LLM — by default *the Claude Code session hosting the skill*, so graphing `docs/`
would send it to Anthropic. But `graphify extract --backend openai` honours `OPENAI_BASE_URL`, and
`--backend ollama` exists, so the semantic pass can run against **LiteLLM / Ollama / vLLM in-lab with
zero egress**. Markdown *structure* is already extracted locally — 8,693 `.md` nodes with no LLM at
all; the model only adds concepts on top.

---

## Adoption plan

Staged so each step is independently useful and reversible. Nothing here is a framework build.

### Stage 1 — structural only, no LLM, no global install (do first)

- Isolated venv, `graphifyy[terraform,neo4j,mcp,pdf,sql]`. **Add `sql`** — 16 files are being dropped.
- Feed it `git ls-files`, never the working tree.
- `graphify-out/` into `.gitignore`.
- Wrap `god-nodes` + `affected` in a thin script so they are callable without remembering the venv path.
- **Acceptance:** `affected` on a Python or TypeScript symbol returns the same set as a hand grep.
  It already does for `Verdict`; make it a test, not an anecdote.

### Stage 2 — the actual reason to adopt: DoD Pillar 8

Pillar 8 asks "what does this change imply?" and is answered by hand today. It was answered *wrong*
tonight — B148 shipped a CronJob whose schedules row, freshness budget and failure rule were all
missed until `check-cron-freshness-budgets.sh` caught them, and the servicemonitor guard's own
`lib/common.sh` dependency broke it in a container.

`graphify affected "<changed symbol>"` is that question as a command. Wire it as an **advisory**
reviewer aid, not a gate — limit 1 above means it cannot see shell dependencies, and a gate that is
blind to the guard surface would be the exact "control that measures nothing" this estate keeps
building.

- **Acceptance:** on a real change, the affected set is a superset of what the author touched.

### Stage 3 — close the shell gap, or scope around it

The shell blind spot is the deciding factor for how far this goes. Two options, in order of cost:

1. **Scope around it** — declare graphify a Python/TypeScript/HCL tool, keep shell dependencies
   tracked by the existing `scripts/lib/common.sh` convention plus shellcheck. Cheapest, honest.
2. **Contribute upstream** — a `source`/`.` handler in the bash extractor. The project is Apache-2.0
   and active; this is a small, well-defined patch.

Do **not** build a local fork. This is a lab.

### Stage 4 — in-lab semantic pass (only if Stages 1-2 earn it)

`graphify extract --backend openai` with `OPENAI_BASE_URL` pointed at LiteLLM. This unlocks
path-qualified node IDs (limit 2) and doc/concept extraction with no egress.

- **Acceptance:** `affected "Verdict"` resolves uniquely at full-repo scale, and no request leaves
  the LAN — verified by watching the gateway, not by trusting the flag.

### Stage 5 — integrations, each independently optional

- `--neo4j` emits `cypher.txt` → our existing Neo4j graph store.
- `--mcp` is a stdio MCP server → the B17/B19 gateway, making the graph agent-queryable.
- `graphify hook install` adds a **post-commit git hook**. The operator owns all git operations here;
  **do not install it.**

---

## What would make this a bad idea

Recorded so the decision can be re-checked rather than trusted:

- If Stage 2's affected-set proves to be a *subset* of real impact on anything but shell, the tool is
  worse than grep and should be dropped.
- 0.9.x, ~5 months old, **1,130 open issues**. A pin is mandatory; treat upgrades as changes.
- The value here is one command (`affected`). If wiring it costs more than a few hours, the honest
  answer is that `grep -rn` already does most of it and the graph is a nicety.
