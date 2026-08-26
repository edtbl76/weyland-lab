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

**The 71.5× token-reduction claim — MEASURED 2026-08-26, and the frame is wrong.** Against a fair
baseline (the files a human would actually open, not "the whole repo") one real query gives **~12×**:
`affected GuardrailPipeline` is 992 chars against 12,081 chars of `app.py` + `test_pipeline.py`. One
symbol, one measurement, not a benchmark.

The vendor number is unfalsifiable rather than wrong — 71.5× against an undefined baseline can be
true of almost any retrieval, and it describes `query`, the feature this plan explicitly does not
adopt. Its own budget mechanism concedes the cost: our `--budget 700` run printed *"TRUNCATED:
showing 23 of 133 nodes … the answer may be among the 110 cut nodes."* Compression that drops the
answer is not compression.

**The value is precision, not compression.** `affected` output is not a substitute for reading those
12 KB — it is a set of coordinates (`policy.py:21`, `pipeline.py:27`, `grounding.py:109`). You still
read the code; you read the seven lines that matter instead of skimming two files to find them. That
is a falsifiable claim, which is what `graphify.sh verify` tests. "Fewer tokens" is not.

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

**1. Shell `source` is not a dependency edge — but this matters less than it first appears.**
13 scripts source `scripts/lib/common.sh`; `affected "common.sh"` returns **"No affected nodes
found."** Measured across the whole graph: `.ts` 7,102 edges / **1,029** import-type, `.py` 3,460 /
**448**, `.sh` 192 / **0**. Bash `source` takes a runtime-evaluated string
(`. "$(dirname "$0")/lib/common.sh"`), so resolving it statically means evaluating shell expansion —
genuinely harder than a literal Python or TypeScript import path, which is likely why it is
unimplemented.

**Corrected scope (2026-08-26).** This was first written up as the deciding constraint. It is not.
Shell's dependency structure in this repo is *deliberately* one level deep: `scripts/lib/common.sh`
is a leaf holding two path constants and sources nothing (its only `source` matches are in comments).
So the complete shell dependency graph is `common.sh <- 12 guards`, with no transitive chain, and a
grep answers it exhaustively — but it must match the SOURCE STATEMENT, not the name. A bare
`grep -rln 'lib/common.sh'` returns 14, counting two files whose only mention is a comment; one of
them is `check-servicemonitor-coverage.sh`, whose comment says *"DELIBERATELY DOES NOT SOURCE"* it.
Prose about a dependency is not a dependency, and the better the removal is documented the more
confidently the naive check reports it. `^[[:space:]]*(\.|source)[[:space:]]` is the fix; it is what
`scripts/graphify.sh affected` uses. `affected` earns its
keep where a human cannot hold the chain in their head — 1,029 TypeScript and 448 Python import edges
— not for 13 scripts pointing at one leaf.

**The real risk was never the missing edges.** It is that `No affected nodes found` is byte-identical
to the answer for a genuinely unused file. Compare the `.sql` gap in the same run, which the tool
reported properly: *"16 .sql file(s) contributed nothing … tree_sitter_sql not installed"* — named the
gap, the package and the issue number. Same class of missing coverage, opposite reporting: one is a
warning, the other a clean zero. Knowing shell is uncovered converts a silent wrong answer into a
known blind spot with a one-line substitute.

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

**5. Two dependency gaps — one loud, one silent. RESOLVED 2026-08-26.** 16 `.sql` files
"contributed nothing" without `graphifyy[sql]` — it *did* say so, naming the package and the issue
number. The Leiden gap was the silent one, and it mattered more than expected:

`graspologic` (Leiden) is `requires_python: <3.13,>=3.9` and rogueone's default is 3.13.3, so
graphify caught the ImportError and fell back to `networkx.community.louvain_communities`
(`graphify/cluster.py:67-76`) without a word. **Measured on our own graph rather than argued from the
README:**

| | Communities | Internally disconnected |
|---|---|---|
| Leiden | 1,103 | **0** |
| Louvain | 1,112 | **15**, splitting into 42 fragments |

Louvain's known defect is that it can emit communities which are not connected groups at all, and it
did so 15 times here — mislabelled architectural groupings in `GRAPH_REPORT.md` and the aggregated
view. Leiden's refinement pass is exactly the fix. Everything else was near-identical (same median
community size, same singleton count), so the algorithm choice is worth ~1% of the structure and
100% of its correctness.

`scripts/graphify.sh` now builds the venv with the newest interpreter **below** 3.13
(`venv_python()`, `GRAPHIFY_PYTHON` overrides), adds the `leiden` extra, and — the part that matters
— prints which clustering the built venv will actually use, asserted by IMPORTING graspologic rather
than trusting the pin.

**That status line immediately earned itself.** Re-running install after adding python3.12 printed
`interpreter: python3.12 (Python 3.13.3)` — selected one interpreter, got another. `python -m venv`
over an existing directory REUSES it and will not swap the interpreter, so the install silently
no-opped on the one thing it was run to change. Fixed with `--clear`. Without the status line it
would have looked like a clean install.

**6. `graphify install` touches `~/.claude/CLAUDE.md` — INSPECTED 2026-08-26, and it is benign.**
Read from `graphify/install.py:624-650` rather than inferred:

- It **appends** (`content.rstrip() + registration`), never overwrites. An existing global CLAUDE.md
  keeps everything it had.
- It is **idempotent** — if `"graphify"` already appears it prints `already registered (no change)`.
- The block is **six lines**: a `# graphify` heading, a pointer to the installed SKILL.md, and a
  trigger instruction.
- Two escape hatches: **`CLAUDE_CONFIG_DIR`** redirects the whole registration, and project mode
  writes to `<project>/.claude/CLAUDE.md` instead of `$HOME`. There is also `graphify uninstall`,
  which removes registrations across every detected platform.

**The earlier framing here was wrong and worth correcting explicitly.** This limit read as "edits the
file holding your commit policy", which implied risk to existing content. Skipping the skill install
was still correct for an evaluation — the point was to exercise the deterministic CLI without changing
the machine — but the REASON given was not the real one. We skipped it because we did not need it,
not because it was dangerous. A wrong reason in a design doc outlives the decision it justified.

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

### Stage 1 — structural only, no LLM, no global install — **DONE 2026-08-26**

Shipped as `scripts/graphify.sh` (`install` / `build` / `affected` / `god-nodes`), 15 bats cases,
shellcheck clean at the CI gate.

- Pinned `graphifyy==0.9.50[terraform,neo4j,mcp,pdf,sql]`. Install took 12s; `build` 15.8s for
  **13,682 nodes / 22,980 edges**, and with `sql` present the 16-file warning is gone.
- **Nothing is written inside the repo** — venv, source copy and graph all live under
  `~/.local/share/weyland/graphify/`. The plan originally said to gitignore `graphify-out/`; not
  generating it in the repo at all is strictly better, and `git status` confirms it.
- **Acceptance MET, measured not asserted.** `affected GuardrailPipeline` returned the same
  dependents as `grep -rln`, with exact file:line and relation type, and correctly EXCLUDED
  `guardrails/pipeline.py` — the definition site is not affected by itself.
- **Now a subcommand, not an anecdote: `scripts/graphify.sh verify [symbol]`.** The first write-up
  framed this as a binary — one-time proof versus a bats case that skips in CI — and both were wrong.
  The pin guards drift *while it holds*; the real gap is that **bumping the pin re-verifies nothing**,
  which is precisely when behaviour can change. A subcommand run at the moment of risk is the right
  shape, and it computes its own ground truth so it never goes stale.
- **The invariant is a SUBSET, not equality.** graphify legitimately omits the definition site (a
  symbol is not affected by itself), so demanding equality with grep would fail a correct answer. What
  it must never do is name a file that does not contain the symbol — fabrication. An empty result is
  also a failure, not a trivially-satisfied subset: without that, a completely broken upgrade would
  verify clean.
- Proven to fail, both ways: unit cases cover fabrication and emptiness, and end-to-end
  `verify ZzNotARealSymbolZz` exits **1** with `graphify returned nothing - that is not a pass`.

<details><summary>Original Stage 1 checklist</summary>

### Stage 1 — structural only, no LLM, no global install (do first)

- Isolated venv, `graphifyy[terraform,neo4j,mcp,pdf,sql]`. **Add `sql`** — 16 files are being dropped.
- Feed it `git ls-files`, never the working tree.
- `graphify-out/` into `.gitignore`.
- Wrap `god-nodes` + `affected` in a thin script so they are callable without remembering the venv path.
- **Acceptance:** `affected` on a Python or TypeScript symbol returns the same set as a hand grep.
  It already does for `Verdict`; make it a test, not an anecdote.

</details>

### Stage 2 — the actual reason to adopt: DoD Pillar 8 — **DONE 2026-08-26**

Wired into `docs/definition-of-done.md` § 8 as an **advisory** aid: a new trigger-cascade row for
**a shared type / function / module**, plus a short section giving the commands and — the part that
matters — the three reasons it is not a gate (blind to shell, unanswerable on duplicated symbols, an
empty answer is not evidence of no impact).

**The gap it fills is real and was not obvious.** Every existing Pillar 8 row is about an
*infrastructure* surface — a service, an endpoint, a timer, an image, a repo — and none of them ask
about **code** cascade. That is why the duplicated `guardrails/verdict.py` could sit between two
services with `Hook` values acting as URL paths and nothing in the DoD would have raised it.

**Limit 2 also got smaller.** `affected Decision` returns `No unique node match` because two nodes
share that label — one per copy of the duplicated file. The wrapper now catches that string and lists
the colliding files with their sources, so the unactionable message becomes a disambiguation aid. It
doubles as a duplication signal: two nodes with the same label in different services is itself a
finding.

<details><summary>Original Stage 2 plan</summary>

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

</details>

### Stage 2b — make the wrapper refuse where the graph is blind — **DONE 2026-08-26**

Implemented in `scripts/graphify.sh`: `is_shell_target()` short-circuits before any graph
precondition, so a shell target never reaches the graph even when the graph is healthy (there is a
bats case for exactly that). Two defects were found building it, both the house pattern:

- **`grep --include` is not portable here.** `grep` on PATH on rogueone is **ugrep 7.8.4**, not GNU
  grep (`/usr/bin/grep` is GNU 3.11, shadowed), and its `--include='*.sh'` returned a `.bats` file —
  a phantom dependency. CI runs alpine, a third implementation. File selection is now `find -name`,
  which is unambiguous in all three.

  **AUDITED, and it does NOT generalise (2026-08-26).** This was first written up as "worth a wider
  look" at the other ten guards. Measured instead of assumed: all six file-analysis guards were run
  under BOTH implementations — locally on ugrep and inside `node:24-alpine` where CI's `/bin/grep` is
  a **busybox** symlink — and their output is **byte-identical**, not merely same-exit-code. The
  reason is structural: the guards use only the portable core (`-c -q -v -E -F -o -x -l`, all POSIX)
  and do the real parsing in Python. `--include` is the one non-portable flag, and after this fix it
  appears nowhere in the repo except the comment describing it. No wider problem exists.
- **Matching the NAME counts prose.** The first version reported `graphify.sh` as depending on
  `common.sh` because its comments discuss it — and reported `check-servicemonitor-coverage.sh`,
  whose comment says *"DELIBERATELY DOES NOT SOURCE"* it. The better the removal is documented, the
  more confidently the naive check reports the dependency. Now anchored to
  `^[[:space:]]*(\.|source)[[:space:]]`.



The risk is not the missing shell edges. It is that `No affected nodes found` is byte-identical to the
answer for a genuinely unused file, so a reader takes it as authoritative. Fix that at the boundary
where we consume the tool, in the Stage 1 wrapper — roughly ten lines:

    affected <target>
      target is *.sh -> say "shell deps are not in the graph", run grep -rln '<basename>' scripts/
      otherwise      -> graphify affected

**An earlier draft of this plan proposed the opposite and it was wrong.** It would have enforced an
invariant — "shell sourcing must stay one level deep" — so the grep substitute stayed valid. That
constrains how this repo writes shell *forever* to preserve a workaround for a third-party parser
gap, in a tool not yet installed. When a tool has a blind spot, the fix belongs where you consume it,
not in the system it is looking at.

**And the underlying question answers itself: shell should not have a dependency chain at all.**
Sourcing has no namespacing — every sourced file lands in one global scope, so collisions are silent;
ordering is implicit; `set -e` semantics shift across the boundary. There is no import graph to build,
which is precisely why no tool builds one.

This is already how the repo behaves, for its own reasons rather than for graphify's. From
`scripts/lib/common.sh`'s own header: *"Paths only, on purpose. `say`/`ok`/`warn`/`die` status helpers
were added here 2026-08-21 and removed the same day: nothing called them … Add a helper here when it
has a caller."*

So the rule worth stating is not "shell stays shallow" but:

> **If a shell script needs a real dependency chain, it has outgrown shell — rewrite that piece in
> Python.** Do not build a shell module system, and do not build a resolver to understand one.

That makes the gap a non-issue by construction. Shell that is correctly scoped — orchestrating
external commands, sourcing at most one file of constants — has nothing for `affected` to find. Shell
that would benefit from `affected` is shell that should not have been shell. The tool's blind spot
lands on an architectural boundary that already exists for better reasons.

### Stage 3 — close the shell gap, or scope around it

Given Stage 2b, the shell blind spot is no longer a deciding factor — it aligns with a boundary we
want anyway. Two options remain, in order of cost:

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
