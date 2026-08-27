# Flow — Graphify code-cascade analysis (EMA-191)

How `scripts/graphify.sh` answers DoD Pillar 8's code half, and where it deliberately refuses to
answer. Evaluation and staged plan: `docs/concepts/graphify-adoption.md`.

## Build — tracked source, minus build output

```mermaid
flowchart LR
    REPO["weyland repo<br/>927 MB working tree"] -->|git ls-files| TRACKED["1,914 tracked files<br/>24 MB"]
    TRACKED --> FILTER{"is_build_artifact?"}
    FILTER -->|"*.min.js · */assets/javascripts/*"| DROP["42 dropped<br/><b>653 nodes of noise</b>"]
    FILTER -->|authored source| KEEP["1,872 files"]
    KEEP --> CLEAN["clean_stage<br/><i>REPLACE, not merge</i>"]
    CLEAN --> AST["tree-sitter AST<br/>28 workers, ~16s"]
    AST --> GRAPH["graph.json<br/>13,051 nodes · 21,163 edges<br/>1,076 Leiden communities"]

    style DROP fill:#ffe8cc,stroke:#cc8800
    style CLEAN fill:#e8f0ff,stroke:#3366cc
```

**`clean_stage` is load-bearing.** `rsync --files-from` copies the listed files and deletes nothing
else — `--delete` is ignored because the transfer is not recursive. Without it the staged tree only
grows, so a file deleted from the repo keeps its nodes forever and `affected` can name a dependency
on a file that no longer exists.

**Build output is tracked too.** `git ls-files` keeps out provider binaries and venvs, but mkdocs
output is committed. Minification renames every identifier to one letter, manufacturing the label
collisions that make `affected` ambiguous.

## Query — and where it refuses

```mermaid
flowchart TD
    Q["graphify.sh affected &lt;target&gt;"] --> SH{"target is<br/>*.sh / *.bash?"}
    SH -->|yes| GREP["<b>refuse the graph</b><br/>say so, grep source statements<br/>^[[:space:]]*(\.|source)[[:space:]]"]
    SH -->|no| PRE{"venv + graph<br/>present?"}
    PRE -->|no| E2["<b>exit 2</b><br/>guard could not run"]
    PRE -->|yes| RUN["graphify affected --graph"]
    RUN --> AMB{"'No unique<br/>node match'?"}
    AMB -->|yes| CAND["list colliding files<br/><i>doubles as a duplication signal</i>"]
    AMB -->|no| OUT["file:line per dependent"]

    style GREP fill:#fff4dd,stroke:#cc8800
    style E2 fill:#ffe8cc,stroke:#cc8800
    style OUT fill:#ddffdd,stroke:#00aa00
```

**Why the shell branch exists.** Bash `source` is not a dependency edge — `.ts` 1,029 import edges,
`.py` 448, `.sh` **0**. Raw graphify answers `No affected nodes found`, byte-identical to the answer
for a genuinely unused file, while 12 scripts source `lib/common.sh`. The wrapper refuses to pass
that silence through.

**Why matching the source statement matters.** A bare name match counts prose: the first version
reported `graphify.sh` as a dependent because its comments discuss `common.sh`, and reported
`check-servicemonitor-coverage.sh`, whose comment says *"DELIBERATELY DOES NOT SOURCE"* it.

## verify — what guards a pin bump

```mermaid
flowchart LR
    V["graphify.sh verify"] --> A["affected &lt;symbol&gt;"]
    A --> F["graph_files:<br/>strip :L&lt;n&gt;"]
    F --> E{"empty?"}
    E -->|yes| FAIL1["<b>exit 1</b><br/>'returned nothing<br/>is not a pass'"]
    E -->|no| S{"every file really<br/>contains the symbol?"}
    S -->|no| FAIL2["<b>exit 1</b><br/>FABRICATED"]
    S -->|yes| OK["<b>exit 0</b><br/>+ clustering in use"]

    style FAIL1 fill:#ffdddd,stroke:#cc0000
    style FAIL2 fill:#ffdddd,stroke:#cc0000
    style OK fill:#ddffdd,stroke:#00aa00
```

**A SUBSET, not equality.** graphify legitimately omits the definition site — a symbol is not
affected by itself — so demanding equality with grep would fail a correct answer. What it must never
do is name a file that does not contain the symbol. An empty result trivially satisfies "subset", so
it is failed explicitly; otherwise a completely broken upgrade would verify clean.

**The invariant:** every answer is either a real dependency set, an explicit refusal, or a loud
failure. There is no path where the wrapper checks nothing and reports success.
