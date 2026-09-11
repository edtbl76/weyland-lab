# Code-intelligence / code-graph — evaluation (B166)

> B166's eval half (2026-09-11). Goal: give the lab's **AI coding agents** (Claude Code · Codex ·
> OpenCode) real **structural context** — symbols, go-to-definition, find-references, call graphs —
> instead of grep + whole-file reads, and give a developer code search/nav. **$0 / OSS / self-hostable /
> LAN-only** lens. Ties to [[b104]] (coding-agent quality), the **B17/B19 MCP fleet** (the agents already
> consume read-only MCP servers), and `graphify.sh` (the lab's advisory dep graph — [[graphify-code-cascade]]).

## Headline — the space moved; the classic answer is now the wrong one

The category the original B166 note listed (Sourcegraph, SCIP, …) has **shifted under our feet**, and the
$0 answer in 2026 is a **new class**: **MCP-native code-intelligence servers built *for* LLM agents**.
Two facts drive the whole recommendation:

1. **Sourcegraph is no longer a $0 self-host option** — verified: it relicensed Code Search from Apache to
   its enterprise license (2023), took the core **private** (Aug 2024), **discontinued Cody Free/Pro**
   (July 2025), and is now **enterprise-only, custom-quote, not source-available**; self-hosting means an
   enterprise contract + a multi-service cluster. It is **out** for this lab.
2. The agents don't need a code-search *website* — they need a **tool they can call**. In 2026 that is an
   **MCP server** that answers "definition of X", "references to Y", "symbol overview of this file" over
   LSP or tree-sitter. The agents (Claude Code, Codex, OpenCode) already speak MCP and already consume the
   fleet — a code-intelligence MCP drops straight in.

## Per-tool finding

| Tool | $0 + self-hostable? | What it uniquely gives | Weight | Agent-consumable? | Verdict |
|---|---|---|---|---|---|
| **Serena** (`oraios/serena`) | ✅ OSS | **LSP-backed** semantic retrieval + symbol-aware *editing* as **MCP tools** (go-to-def, find-refs, symbol overview, insert/replace-at-symbol) — real language-server accuracy, multi-language | Python host + one **language server per language** (auto-managed) | ✅ **MCP** — documents Claude Code / Codex / Claude Desktop | **BUILD — primary** |
| **Codebase-Memory MCP** (`DeusData/codebase-memory-mcp`) | ✅ OSS | tree-sitter **knowledge graph** (defs/calls/imports) as **MCP**, persistent, **single static binary**, 158 langs, token-frugal ("~99% fewer tokens") | **single binary, zero deps** — lightest | ✅ **MCP** | **BUILD — lighter alt** |
| **Sourcebot** (`sourcebot-dev/sourcebot`) | ✅ OSS | the actual **$0 Sourcegraph replacement** — **Zoekt** fast code **search** across repos + a **web UI for humans**, PLUS an **MCP server** + agentic NL Q&A for agents; self-hosted Docker, no data leaves | one **Docker** service (index + web) | ✅ **MCP** (+ web UI) | **BUILD — the search/nav half** |
| **Aider RepoMap** | ✅ OSS (Apache-2.0) | tree-sitter **ranked repo map** (a compact "here's the codebase" for an LLM prompt) | light (Python + tree-sitter) | ⚠️ coupled to Aider; usable standalone but no MCP — you'd wire the file into context yourself | comparison / fallback |
| **Joern** | ✅ OSS (Apache-2.0) | **code-property graph** + a Scala query DSL — deep **security/dataflow** queries | heavy (**JVM**, CPG build) | ⚠️ query DSL / export; no first-class agent MCP | **niche** — a *security-analysis* tool (complements B47/B106), not the agent-context win |
| **SCIP** + OSS indexers | ⚖️ index format OSS | a precise defs/refs **index** | per-language indexer | ✗ its main consumer (Sourcegraph) is now enterprise — you'd have to build the nav/MCP server yourself | comparison — not worth a custom consumer vs Serena |
| **Sourcegraph** | ❌ enterprise-only (2024+) | code search/nav website | multi-service cluster | — | **OUT** (not $0, not source-available) |
| **CodeQL** | ❌ engine proprietary (CLI free for OSS only) | semantic security queries | DB build per language | ⚠️ | comparison — not $0 for private code |
| **CodexGraph · RepoGraph** | research | LLM↔code-graph *papers* | — | — | not production tools; ideas, not installs |

**Newer entrant worth naming:** the **LSP-to-MCP bridge** pattern (Serena is the leading example) and
single-binary tree-sitter KGs (Codebase-Memory) are the 2025-2026 shape of this problem — purpose-built to
cut the token/tool-call cost of an agent exploring a repo by grep alone.

## Bake-off results — observed, not asserted (2026-09-11)

The set the operator picked (**Serena** + **Sourcebot / Zoekt / OpenGrok / Hound / Livegrep** search
bake-off + **Joern** on a separate track) was run as a sequential stand-up on the RAM-tight node. What was
actually verified vs. read-off-the-box:

| Tool | Stood up? | Observation | Deploy weight (measured) |
|---|---|---|---|
| **Serena** | ✅ ran via `uvx` | `serena project index services/weyland-guard` → **25 files indexed, exit 0** — the Python LSP path is real, not claimed. Wired into `.mcp.json` (stdio, `ide-assistant`). | 0 lab services — runs beside the agent on the operator box |
| **Sourcebot** | ✅ 3 containers | Zoekt search **proven on the real repo**: `GuardrailPipeline` → **9 files in 0.19ms** (guard `pipeline.py`/`app.py`/`test_pipeline.py` + `graphify.sh` + docs), over a single **59.7 MB** index shard of the whole tree. | **3 services** — Postgres 16 + Redis 7 + the Sourcebot web/app container; needs `DATABASE_URL` + `SOURCEBOT_ENCRYPTION_KEY` + `AUTH_SECRET`; web UI + API are **auth-gated** (307→login / 401) |
| **Zoekt** (standalone) | ✅ (it *is* Sourcebot's engine) | The `zoekt-webserver` I queried directly at `:6070` **is** standalone Zoekt — same 9-file/0.19ms result, no Postgres/Redis/auth touched on the search path. So "Zoekt alone" is the **search minus the wrapper**: one index shard + one webserver, HTTP/JSON only. | **1 process + 1 index shard**, no DB — the lightest real search deploy |
| **OpenGrok** | ⚪ documented, not deployed | Apache-2.0, ctags/universal-ctags **cross-reference + Lucene** search + a mature web UI; **JVM (Tomcat)** service + a periodic indexer cron. Venerable, heavy-ish, human-facing xref is its strength; **no MCP, no agent story**. | JVM/Tomcat + Lucene index — heavier than Zoekt, lighter than Sourcebot's stack, but a servlet container to babysit |
| **Hound** | ⚪ documented, not deployed | Etsy's Go **trigram** search server, single small binary + `config.json` of repos, tiny web UI. Simple and light — but **unmaintained** (last meaningful release years stale), regex-only, **no symbols, no MCP**. | single Go binary — as light as Zoekt, but a dead project |
| **Livegrep** | ⚪ documented, not deployed | Google-lineage **regex** search (RE2 + a codesearch index), fast interactive UI. Same shape as Hound — **regex-only, no symbols, no MCP**, and also low-activity. | small Go/C++ service |

**Verdict from the run:** the two engines worth keeping are the two I proved — **Serena** for agent
*semantic* work (LSP-accurate refs/defs the others can't do) and **Sourcebot** for human+agent *search*
(Zoekt speed + web UI + MCP). **OpenGrok / Hound / Livegrep** are all **regex/xref search with no symbol
resolution and no MCP** — they lose to Sourcebot on capability (Sourcebot *is* Zoekt + more) with no offset
that matters here; Hound and Livegrep additionally look under-maintained. If Sourcebot's 3-service weight
ever proves too much for the node, **standalone Zoekt** (proven: 1 process, 59.7 MB shard, sub-ms) is the
$0 fallback that keeps the search quality and drops the Postgres/Redis/auth tax — at the cost of the web UI
and the MCP/NL-Q&A layer.

**A real cost finding:** Sourcebot **v5** dropped its embedded Postgres — it now demands an external
Postgres **and** Redis **and** two generated secrets, and gates the UI/API behind login. That's a heavier,
more operationally-real deploy than the "one Docker service" the box implies; budget for it (or run
standalone Zoekt) rather than assuming a single container.

**Joern (separate track) — also proven, and it earns its niche.** Ran `joern-cli` v4.0.626 (no public
Docker image — it ships as a 1.8 GB `joern-cli.zip` + a JDK; ran it in a JDK-21 container since Joern v4
targets ≤21 and the host JDK is 25). Scoped the CPG build to `weyland-guard` (25 Python files): `pysrc2cpg`
→ **CPG of 26 files / 292 methods / 3136 calls** in seconds. The queries returned what *no* search engine
above can: (1) **call-graph fan-out** — top callers ranked by out-edges (`check` validators, `_build_guardrails`);
(2) **risky-sink inventory** — 9 hits incl. a genuine one, `exec(compile(path.read_text()))` in
`tests/test_verdict_contract.py:48` (it executes the *sibling's* `verdict.py` source to compare — the exact
byte-duplication Pillar 8 flagged) plus `json.loads(raw)` in `policy.py`; (3) **dataflow/taint** —
`reachableByFlows` traced **9 flows** from the request `payload` parameter through `run_in_executor` → the
async validator → `verdict.decision` → return. That parameter-to-sink reachability is Joern's whole point
and is structurally impossible for trigram/regex/xref search. **Verdict holds: Joern is a security/dataflow
tool** (sits beside B47 Semgrep / B106), **not** the agent-context or nav deliverable — heavy (JVM + CPG
build per language), no first-class agent MCP. Keep it as an on-demand analysis track, not a standing
service.

## Free/OSS options for the "closed & research" tools

Every closed or research entry above has a $0/OSS path — so nothing forces an enterprise contract:

- **Aider RepoMap (the concept, in detail).** Aider (Apache-2.0) parses the repo with **tree-sitter**,
  extracts definitions + references, builds a symbol graph, ranks it with **PageRank-style centrality**,
  and renders a compact "here are the important files + their key symbols/signatures" map sized to a token
  budget — fed to the LLM so it knows the structure without reading every file. It IS free/OSS, but it's
  **coupled to Aider** (its model/token/IO plumbing); usable standalone with wiring, **no MCP**. Its idea
  is exactly what the MCP-native tools (Codebase-Memory) reimplement as a callable server — so prefer
  those over extracting RepoMap by hand.
- **Sourcegraph → free/OSS.** **Sourcebot** is the direct replacement (Zoekt search + web UI + MCP,
  self-hosted Docker). Lower-level OSS search engines if you want to build your own: **Zoekt** (the
  trigram engine Sourcebot/Sourcegraph use), **OpenGrok** (Apache-2.0, ctags xref + web UI, venerable),
  **hound**, **livegrep**.
- **SCIP → free/OSS.** The protocol + the indexers (`scip-python`/`-typescript`/`-java`/`-clang`) are OSS,
  but the polished consumer was Sourcegraph — there's no first-class OSS SCIP nav server, so for the lab
  the **LSP path (Serena)** gives the same go-to-def/refs with less bespoke plumbing. (Sourcebot uses
  Zoekt, not SCIP.)
- **CodeQL → free/OSS.** **Joern** is the closest OSS equivalent (code-property graph + query DSL for
  dataflow/security); **Semgrep** — already in the lab (B47) — covers a large share of the pattern-based
  cases. CodeQL's engine stays proprietary and is free only for public repos.
- **CodexGraph / RepoGraph → the research code IS open-source**, just not a maintained product:
  - **RepoGraph** (`ozyyshr/RepoGraph`, ICLR 2025) — `python construct_graph.py <repo>` builds a
    repo-level code graph; reported +32.8% relative on SWE-bench as a plug-in context module. Runnable,
    research-grade, no service/MCP.
  - **CodexGraph** (`modelscope/modelscope-agent/apps/codexgraph_agent`, NAACL 2025) — extracts a code
    graph into a **graph database** the LLM agent queries. Notably lab-adjacent: the lab already runs
    **Neo4j** ([[neo4j-graph-loader-b1]]), so the *approach* (code graph in Neo4j, agent queries Cypher) is
    borrowable even though the artifact isn't a drop-in.
  So: usable as **ideas/experiments**, not installs — mine the approach (esp. CodexGraph-on-Neo4j) if the
  MCP tools ever prove too shallow, rather than deploying the papers' code as-is.

## Recommendation — two halves, pick by which need is real

The work splits into two distinct needs; pick by which one bites:

1. **Agent semantic intelligence + editing → Serena (MCP, primary for agents).** Real **LSP-grade**
   go-to-def / find-refs / symbol overview / symbol-aware edits as MCP tools — the "who calls `verdict.py`'s
   `Decision`?" / impact question grep answers badly, and the lever [[b104]]'s coding-agent eval measures.
   Documents Claude Code + Codex, so it drops into the agent config. Cost: a language server per language
   (Python + TS/JS = the lab's real code; auto-managed).
   - **Lighter alt: Codebase-Memory MCP** — single static binary, tree-sitter KG, MCP, token-frugal; less
     precise (no type-aware refs) but near-zero ops on the RAM-tight node.
2. **Developer + agent code SEARCH/nav → Sourcebot (the $0 Sourcegraph).** Zoekt-backed fast search across
   the repos with a **web UI** (the thing a human actually wants for "where is X used across everything"),
   **plus** an MCP server so agents get the same search. Self-hosted Docker, LAN-only. This is the
   Sourcegraph-shaped hole, filled at $0.
3. **Deep security/dataflow → Joern (optional, separate track)** beside B47/B106 — a different job, not the
   agent-context deliverable.

**Start cheap:** wire **Serena into Claude Code locally** (`.mcp.json` / `claude mcp add`) and prove it on
a real query (find-refs on the duplicated `guardrails/verdict.py` `Decision`) BEFORE committing node
resources; promote to the MCP fleet if it earns it. **Sourcebot** is the natural second step (a deployed
Docker service + web UI) once the agent half is proven. Everything else — Sourcegraph, SCIP without a
consumer, CodeQL, the RepoGraph/CodexGraph papers — is **comparison-only** (OSS paths noted above if ever
needed).

## Overlap — do not build a third graph

`graphify.sh` stays as the **advisory dep-graph / Pillar-8 cascade helper** (TS/Py, shell-blind). Serena
is the **agent-facing semantic layer** (symbol resolution over LSP). Different layers, one each — the MCP
tool does NOT replace graphify and graphify does NOT try to be an agent tool. Wire Serena where the agents
already look (the fleet), not as a parallel graph.

## Bounded impl plan (for the pick)

- Stand up **Serena** as a read-only MCP server (its own container/venv on the LAN), pointed at the
  weyland repo (and stud.io later), language servers for **Python + TypeScript/JS** first.
- Register it in the **MCP fleet** the way the other read-only servers are (B17/B19) so Claude Code / the
  operator reach it through the gateway; add it to `.mcp.json` for local Claude Code.
- Prove it with a real query the lab cares about (e.g. find-references on the duplicated
  `guardrails/verdict.py` `Decision` — the exact wire-contract-kept-in-sync-by-nothing case Pillar 8
  flagged), and note the token/tool-call reduction vs grep.
- DoD as repo-tooling + one deployed MCP service (runbook · demo · MCP-fleet registration · ServiceMonitor
  if it exposes `/metrics`, else N/A with reason).
