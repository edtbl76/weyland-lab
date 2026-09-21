# Reading complexity — deep vs tangled vs shallow (B162)

How the lab decides whether a function's complexity is **a problem to fix** or **acceptable** — and does it the
same way a machine can, on every real-code language, adjustably. This is the concept behind
`scripts/lib/complexity_triage.py` (engine), `scripts/check-complexity.sh` (lane), and
`scripts/complexity-triage.json` (the knobs). Runbook: [runbooks/complexity-triage.md](../runbooks/complexity-triage.md).

## The problem

Conventional scan thresholds grade a method by **length and cyclomatic complexity** and penalise a long method
*per se*. Ousterhout's *A Philosophy of Software Design* argues the opposite: the best modules are **deep** — a
**simple interface over substantial implementation** (depth ≈ functionality ÷ interface surface). Penalising
length pushes toward the failure mode Ousterhout names: **shallow modules** and reflexive over-decomposition
("classitis", "temporal decomposition") that multiply interface cost — passing files, threading state, splitting
a coherent operation across many tiny methods — for no information-hiding gain. So a length rule flags exactly the
deep functions we want to keep, and is **blind** to the shallow ones we don't.

## The reading: length nominates, structure and the codebase decide

Length is not a verdict. It is a cheap **nominator** — a first-pass screen — and a nominated function then earns
or loses the flag in two further passes. Three stages, and the inverse smell in the other direction:

1. **Nominate (adjustable).** A function over the length line (`length_warn` / `nloc_warn`) is a *candidate*,
   never a defect. Set low on purpose — it only nominates.
2. **Structure (adjustable).** On each candidate, read the depth-vs-tangle signal: **cyclomatic density**
   (CCN ÷ logical lines) and **true max control-nesting**. Low density + shallow nesting = a clean signature over
   sequential work → **deep**. High density, or a deep pyramid → **tangled**.
3. **Codebase-relative (adjustable, self-calibrating).** Is the candidate an **outlier for how *this* codebase
   writes**, or typical for its style? A z-score over the codebase's own per-language distribution. "Long" is
   judged relative to the norm, not an absolute — and the bar moves as the codebase's style shifts, with no
   hardcoded number to drift against.

The **verdict is the stop-or-accept decision**, per finding:

| Verdict | Meaning | Action |
|---|---|---|
| `DEEP` | long but a clean signature over sequential work | **acceptable** — stays silent |
| `TANGLED` | long AND dense/deeply-nested control flow | **stop and fix** |
| `OUTLIER_REVIEW` | long AND unusual for this codebase, but not clearly tangled | a **human glance** |
| `SHALLOW` | pass-through / over-split delegation (the inverse smell) | **stop and fix** |

Every threshold is a field in `scripts/complexity-triage.json`, so the reading is **pragmatically adjustable** —
a triage, not a hardcoded line count.

## How it's built

- **Numeric metrics — `lizard`** (one dep, ~20 languages incl. the Flink Java): LOC, cyclomatic complexity,
  parameters. Uniform across every real-code language on day one, and it feeds the stage-3 z-score.
- **Structural shapes — `tree-sitter`** (grammars via `tree-sitter-language-pack`): the shapes a metric can't see
  — **true max control-nesting** (lizard's own nesting metric inflates on flat sibling `if`s, double-counting CCN,
  so we compute real depth from the AST), **delegation / pass-through**, and **decorator-awareness** (a dagster
  `@op`/`@job`/`@asset` or a FastAPI route is idiomatic, never classitis — excluded).
- **The verdict + stage-3 + config — our code.** The engine recomputes the numeric stages itself rather than
  bolting stage 3 onto CodeScene's output, so it is self-contained, unit-testable, and emits one graded verdict.

The inverse direction (`SHALLOW`) catches **delegation duplication**: N sibling modules re-declaring the same
pass-through to a shared target — over-split wrappers that a single shared helper would collapse.

## Posture: advisory, with a promotion path

The engine is **advisory** — `scripts/check-complexity.sh` prints the graded findings and exits 0, exactly like
Graphify's Pillar-8 wiring. The verdict *is* the stop-or-accept call; a human reads it. `--gate` flips it to a
blocking check (any `TANGLED`/`SHALLOW` → exit 1) once the thresholds are trusted — the documented promotion path,
deliberately off by default. **The gate posture is decided *from* a run, not up front:** you cannot honestly set a
block line until you have seen the verdict distribution and its false-positive rate.

## Where CodeScene and SonarQube fit

They stay as independent second opinions; the lab's *reading* lives in this engine.

- **CodeScene** is already partly Ousterhoutian — its Code Health is a composite (Large Method weighed against
  Complex Method / Bumpy Road / nesting), not a length verdict — and it runs advisory (github-app + MCP), not a
  merge gate. We leave its length rule alone; the triage is where the real reading happens.
- **SonarQube** is the enforcing gate. The lab's stance: gate on **cognitive complexity**, not raw method length —
  a long, low-density function is not a defect. (The repo customises no Sonar rules today; the enforced profile is
  server-side and is confirmed in-cluster.)

## What the first run found (grounding)

Run across the real-code services (weyland-dagster, weyland-guard, weyland-tool-server, scripts, the Flink Java):
**20 TANGLED · 2 SHALLOW · 7 OUTLIER-REVIEW · 2 DEEP.**

- The reading works: `_build_vectors` (CCN 35, density 0.42) and `emit_mesh_glossary` (CCN 33, 0.41) are `TANGLED`;
  a raw-length rule would have lumped them with the clean writers.
- **True nesting earned its place.** `neo4j_write` (CCN 9, density **0.08** — reads as deep) is `TANGLED` because it
  hides a **6-level pyramid**; same for `weaviate_write`/`pgvector_write`/`eval_scores`. That is the case density
  alone misses — a clean signature over deeply-nested guts.
- **Hotspot:** `datahub_emit.py` (the largest cluster of dense emitters) and `datasets_lib/loaders.py`.
- **SHALLOW:** `finance_common.py` / `music_common.py` / `health_common.py` each re-declare the same `download()`
  and `client()` pass-throughs → collapse to one shared `_io`.
- Stage 3 is visibly self-calibrating — z_loc up to 6.7 on `neo4j_write`, because this codebase's mean function is
  small.

The confident `TANGLED`/`SHALLOW` findings from that run were remediated to deep modules under B162 (see the
runbook's remediation log); the engine is the standing check that keeps the reading honest going forward.
