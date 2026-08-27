# Demo — Graphify code-cascade analysis (EMA-191)

Impact analysis for the code half of DoD Pillar 8: *what breaks if I change this symbol?*
**Executed 2026-08-26** (DONE).

- **Plan + evaluation:** [concepts/graphify-adoption.md](../concepts/graphify-adoption.md)
- **Flow:** [diagrams/flow-graphify.md](../diagrams/flow-graphify.md)
- **Gate:** [definition-of-done.md](../definition-of-done.md) § 8
- **Wrapper:** `scripts/graphify.sh` · **Tests:** `scripts/tests/graphify.bats` (32 cases)

## The point

Pillar 8 asks what a change *implies*, and every row in its trigger-cascade table is an
**infrastructure** surface — a service, an endpoint, a timer, an image, a repo. None of them asked
about **code** cascade. That is why `guardrails/verdict.py` could sit duplicated byte-for-byte between
`weyland-guard` and `weyland-tool-server` — with `Hook` values acting as URL paths and `Decision`
values parsed from the response — and no pillar would have raised it.

`affected` is that question as a command. It is **advisory, never a gate**: it is blind to shell, it
cannot answer for a duplicated symbol, and an empty answer is not evidence of no impact.

## CLI walkthrough (the test — RUN against the real repo)

**Prerequisite (once).** Creates a venv under `~/.local/share/weyland/graphify/`. Nothing is written
inside the repo:

```
bash scripts/graphify.sh install
```

Expected: `interpreter: python3.12 (Python 3.12.3)` then `clustering: Leiden (graspologic present)`.
The interpreter must be **below 3.13** — `graspologic` is `requires_python: <3.13`, and on 3.13
graphify silently falls back to networkx louvain.

**1. Build the graph** from tracked source minus build output:

```
bash scripts/graphify.sh build
```

Expected: `staging 1872 tracked file(s); excluded 42 build artifact(s)` then
`Rebuilt: 13051 nodes, 21163 edges, 1076 communities`, in ~16s with no network access.

**2. The adopted query** — what depends on a symbol, with file:line:

```
bash scripts/graphify.sh affected GuardrailPipeline
```

Expected: `app.py:L26 [imports]`, `test_pipeline.py:L2 [imports]`, `lifespan() ... app.py:L90 [calls]`.
Note it correctly EXCLUDES `guardrails/pipeline.py` — the definition site is not affected by itself.

**3. Architectural hubs** — where a change is most likely to ripple from:

```
bash scripts/graphify.sh god-nodes 10
```

**4. The shell refusal (Stage 2b)** — the graph is blind here and says so instead of returning a
misleading zero:

```
bash scripts/graphify.sh affected lib/common.sh
```

Expected: `shell dependencies are not in the graph (bash 'source' is not an edge) - grepping instead.`
followed by the **12** scripts that really source it. Raw `graphify affected common.sh` returns
`No affected nodes found`, which is byte-identical to the answer for an unused file.

**5. The ambiguity aid** — an unactionable message turned into a disambiguation, which doubles as a
duplication detector:

```
bash scripts/graphify.sh affected Decision
```

Expected: `No unique node match for Decision` then the two colliding files — the `weyland-guard` copy
and the duplicated `weyland-tool-server` copy. That is how the duplication was confirmed.

**6. verify — run after any `GRAPHIFY_PIN` bump:**

```
bash scripts/graphify.sh verify
```

Expected: `OK - every file the graph named really contains 'GuardrailPipeline'.`

**7. Prove verify can fail** — a guard nobody has watched fail is not a guard:

```
bash scripts/graphify.sh verify ZzNotARealSymbolZz; echo "EXIT=$?"
```

Expected: `FATAL: graphify returned nothing for 'ZzNotARealSymbolZz' - that is not a pass.` and
**`EXIT=1`**.

**8. The test suite** — 32 cases, including every defect found while building it:

```
docker run --rm --entrypoint sh -v "$PWD":/w -w /w bats/bats:latest -c "apk add --no-cache python3 >/dev/null 2>&1; bats scripts/tests/graphify.bats"
```

Expected: `32 tests, 0 failures`.

## What it found

- **A duplicated wire contract.** `guardrails/verdict.py` byte-identical across two services, kept in
  sync by nothing. Now pinned by 6 pytest cases in `weyland-guard/tests/test_verdict_contract.py`.
- **653 nodes of build-output noise** (4.8% of the graph) from 42 committed mkdocs assets. Minification
  renames identifiers to single letters, manufacturing the collisions that made `affected` ambiguous.
- **A staging bug in this wrapper**: `rsync --files-from` deletes nothing, so a file removed from the
  repo kept its graph nodes forever — a phantom dependency. Fixed by `clean_stage`.

## Teardown

Read-only with respect to the repo — the venv, source copy and graph live under
`~/.local/share/weyland/graphify/`. Step 1 creates that tree; `graphify.sh build` replaces the staged
copy on every run. To remove everything: `find ~/.local/share/weyland/graphify -mindepth 1 -delete`.
No skill is registered, `~/.claude/CLAUDE.md` is untouched, and no git hook is installed.
