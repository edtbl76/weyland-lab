# AI dev-tooling landscape — survey refresh (B104)

> B104's survey half, refreshed 2026-09-10 (the list was written ~mid-2026 and the landscape moved). Lens:
> **$0 / LAN-only** — OSS · self-hostable · genuinely-free = a *build candidate*; enterprise-SaaS-only =
> *comparison note, no build*. "DONE" = already running in the lab. The perf-baseline (load/perf category)
> shipped separately — see [runbooks/perf-baseline.md](../runbooks/perf-baseline.md).

## Headline

For a lab this AI-mature — CLI coding agents, a 5-tool code-review stack, SAST/SCA, a deep RAG/vector
estate, an MCP fleet, LiteLLM/Bifrost gateways, k6 load testing — **another hosted reviewer or another
coding CLI adds little.** The genuine 2026 gaps are *new categories*: **coding-agent evaluation**, **parallel-
agent orchestration**, and **Git-native API + regression tooling**. Everything else refreshes to "covered,
or desk-note."

## The seven original categories, refreshed

| Category | Lab state | 2026 refresh | $0 verdict |
|---|---|---|---|
| **Coding assistants / CLIs** | ✅ Claude Code · opencode · Codex (B15) | Harness↔model split is now explicit; OSS harnesses (Goose, OpenHands, Aider, Continue, Cline) matured, but the *model* stays paid unless served locally (have: Ollama/vLLM, B79/B111) | **Covered.** Cursor/Devin/Copilot = comparison-only |
| **AI code review** | ✅ CodeRabbit·Sourcery·DeepSource·CodeScene·PR-Agent (B106/B118) | Field is narrower than marketing: **PR-Agent is the only truly self-hostable** engine (already have it); the rest are SaaS | **Covered.** Next experiment is *depth* — PR-Agent fully in-LAN against a local model — not a new tool |
| **Security SAST/SCA** | ✅ Semgrep·Trivy·SonarQube·OSV (B47/B89/B120) | Stable; Snyk free-tier marginal, Veracode/Checkmarx/Wiz enterprise | **Covered.** Enterprise scanners = comparison-only |
| **AI test gen / automation** | Playwright-class only when a UI exists (gated on stud.io/B46) | No OSS breakthrough that replaces deterministic runners; **Keploy** (API traffic→mock/regression, OSS) + **Testkube** (k8s test orchestration, OSS) are the new self-hostable entrants | **Keploy = a real $0 candidate** (see shortlist). Diffblue/Mabl/Qodo = paid |
| **Load / perf** | ✅ **k6** (B104 this pass) | — | **DONE** |
| **API** | MkDocs/OpenAPI (`api.md`); no API client tooling | **Bruno** (Git-native, files-as-collections, OSS) is the clean $0 fit; Hoppscotch/Yaak OSS alternatives | **Bruno = a real $0 candidate** (see shortlist); Postman-AI = comparison-only |
| **Docs / knowledge (AI)** | ✅ MkDocs `docs.weyland.lab`; deep RAG (B1/B70/B113) + Langfuse (B103) | Onyx/AnythingLLM/RAGFlow are OSS local-RAG portals — but the lab's RAG is already far richer | **Covered** (would duplicate the mesh); keep MkDocs canonical |

## New categories worth adding (didn't really exist at the last pass)

1. **Coding-agent evaluation harness — the biggest real gap.** The lab evaluates *RAG* (B84/B96 golden set)
   but has **nothing that scores its coding agents**: task completion, patch correctness, test pass/regression
   rate, human interventions, tool-call count, token cost, unsafe actions. OSS building blocks: **SWE-bench +
   runners · Inspect AI · OpenHands eval · Langfuse/LangWatch traces**. High value because the lab already
   *runs* coding agents and even meters their usage (B62 AI-dev usage → Port) — it just can't say if one is
   *better*. **Top shortlist pick.**
2. **Parallel-agent orchestration** — a supervisor layer over the existing CLIs: one worktree per task, several
   agents concurrently, a board to compare/approve. OSS: **Emdash · Proliferate** (Vibe Kanban is dead — sunset). Medium value
   for a solo lab (nice-to-have, not a gap).
3. **Git-native API + regression** — **Bruno** (API client, collections as committed files) **+ Keploy** (record
   real traffic → generated regression tests). Pairs with **B155** (API lifecycle) and **B152** (contract tests).

## Overlaps — do NOT double-track (already owned elsewhere)

- **Spec-driven dev** (spec-kit OSS; Kiro paid) → this is **B86**'s scope (spec-driven frameworks vs the Method); survey it there, not here.
- **MCP governance** (per-agent allowlists, read/write scopes, tool-call audit, contract + prompt-injection tests) → already the lab's **B17/B19** MCP gateway + **B115** guardrails + **weyland-guard** act-gate; a governance-hardening pass belongs to those, not a new tool.
- **Local-model dev tooling** (Ollama/llama.cpp/vLLM) → **B79/B111**, done.
- **Local knowledge RAG** (Onyx/AnythingLLM/RAGFlow) → the **B1/B70/B113** mesh already exceeds these.

## Recommendation — the 2–3 to actually stand up ($0, OSS, non-duplicative)

1. **Coding-agent evaluation harness** (SWE-bench-style task repo + Inspect AI + Langfuse traces) — the one true gap; highest leverage given the lab's agent usage. *Its own item.*
2. **Bruno + Keploy** — Git-native API client + API regression capture; small, complements B155/B152. *Its own item.*
3. *(optional)* **Emdash** — parallel-agent supervisor (`generalaction/emdash`, MIT); low-risk trial, lower priority solo.

Comparison-only (recorded, not built): Cursor · Devin · Copilot · Qodo · Mabl · Diffblue · Snyk/Veracode/Checkmarx/Wiz · Mintlify · GitBook · Kiro · Postman-AI.
