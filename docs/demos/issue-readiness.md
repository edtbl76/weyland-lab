# Demo — issue readiness: the check that replaced SpecBot (B190)

Before an issue is handed to a coding agent, `AGENTS.md` requires it to be implementation-ready — per kind, every
section of its Linear template, at least one real acceptance criterion, a priority. `scripts/issue-readiness.sh`
checks exactly that, by rule, and keeps one comment on the issue naming what is missing. It replaced SpecBot (25
checks a month, cloud-only, no CI gate). Why it is rules and not an LLM score:
[concepts/issue-readiness.md](../concepts/issue-readiness.md). All RUN 2026-10-07 on rogueone.

## Sequence diagram
See [../diagrams/flow-issue-readiness.md](../diagrams/flow-issue-readiness.md).

## Prerequisites
`scripts/.env` with `LINEAR_API_KEY` (write — it comments; `--no-comment` needs only the read key).

## CLI walkthrough

**1. A ready issue — and the comment is idempotent** (run twice):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh EMA-249
```
```
EMA-249  READY  (Backlog item)
  comment: updated
EMA-249  READY  (Backlog item)
  comment: unchanged
```
The first run took over the comment the dropped 0-100 scorer had posted there (pipeline #278); the second wrote
nothing. Exactly one readiness comment exists on EMA-249 (counted through the API).

**2. A not-ready issue names every gap** (exit 1):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh EMA-216 --no-comment
```
```
EMA-216  NOT READY  (Backlog item)
  missing: Why
  missing: Scope
  missing: Technical context
  missing: Acceptance criteria
  missing: Edge cases & failure modes
  missing: Out of scope
```

**3. The sweep CI runs** — every open High issue in Weyland Lab, in under a second (`real 0m0.795s`):
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh --sweep --no-comment
```
12 issues: EMA-249 READY; the other 11 predate the 2026-09-26 templates and are NOT READY, each with its kind's
missing sections listed (the Spikes miss Questions to answer / Constraint gate / Overlap / Deliverable; EMA-258 is
labelled Bug but written on the Backlog item template, so it misses Observed / Expected / Repro).

**4. Negative — Linear unreachable is exit 2, never READY:**
```
ISSUE_READINESS_ENV=/nonexistent ISSUE_READINESS_LINEAR_URL=http://127.0.0.1:9/graphql LINEAR_API_KEY=dummy bash /home/edwardmangini/IdeaProjects/weyland/scripts/issue-readiness.sh EMA-249 --no-comment
```
```
issue-readiness: linear unavailable — http://127.0.0.1:9/graphql: <urlopen error [Errno 111] Connection refused>
exit=2
```
Also proven by `scripts/tests/issue-readiness.bats` (unreachable · no key · usage) and the pytest suite (a 429 backed
off then retried; a persistent 429, a 401 or a GraphQL error all exit 2; an untouched template of every kind is NOT
READY with every section listed).

## UI walkthrough (UAT — eyes on)
1. **Linear → EMA-249** — one comment, **Issue readiness (weyland check) — READY**.
2. **Linear → Settings → Templates → Backlog item** — the closing line says to run `scripts/issue-readiness.sh
   EMA-###` (it said "Run @SpecBot" until 2026-10-07).
3. **Woodpecker** (`https://woodpecker.weyland.lab`) → a lean run → step `issue-readiness` lists the sweep.

## Expected result
- Each open High issue carries one readiness comment, current with its text; READY only when every section its kind
  requires is present with real content, a real acceptance criterion exists, and priority is set.
- Any failure to read Linear is exit 2 and writes nothing.

## Cleanup / teardown
Nothing to clean up: the check writes only its one comment per issue, updated in place.
