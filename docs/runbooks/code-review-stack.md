# Code-Review Stack — the B106 adopted set (7 tools, $0)

The AI code-review layer, chosen in **B106** and wired here. It sits **on top of** the static-analysis lane
(SonarQube + the 19-tool `scan-suite`, B120) — its job is **LLM contextual review** (diff-aware, cross-file,
natural-language), which SAST can't do. Owner chose **breadth over dedup**: multiple overlapping coverages, all
free. Paid **Qodo is cancelled**; **CodeRabbit** is kept on its **free** tier.

## The two lanes

| Lane | Runs where | Tools | Why |
|---|---|---|---|
| **PR / cloud** | Vendor infra, against the **public `weyland-lab`** GitHub repo | DeepSource · CodeScene · Sourcery · Greptile · CodeRabbit | Cloud GitHub Apps — GitHub pushes events *out* to them, so the LAN-webhook limit doesn't apply. $0 on a public repo. |
| **Local / gateway** | rogueone (reaches GitHub **and** the LAN gateway) | PR-Agent (CLI) · Continue (IDE) | Route through the lab's own **LiteLLM `:30400` / Bifrost** → your models, cost-tracked per-VK, no vendor egress. |

**Why PR-Agent is a CLI, not a GitHub Action:** this repo's Actions run on **GitHub's cloud runners**, which
**cannot reach the LAN gateway** (`:30400`). Running PR-Agent on rogueone keeps it on your $0 gateway. You open a
PR on GitHub, then run the script from rogueone — it reviews via your models and posts comments back.

## Secrets (gitignored `scripts/.env`, never committed — [[feedback-local-dotenv-convention]])
```
LITELLM_API_KEY=<the LiteLLM MASTER key>    # this LiteLLM has NO DB and NO UI → there are no virtual keys; the master key IS the api key
GITHUB_USER_TOKEN=<a repo-scoped GitHub PAT>
```
Continue expands `${{ env.LITELLM_API_KEY }}`; `scripts/pr-agent-review.sh` sources `scripts/.env`. Retrieve the master
key — **mother:** `kubectl -n weyland get secret litellm-secrets -o jsonpath='{.data.LITELLM_MASTER_KEY}' | base64 -d`
(the LAN pattern per `k8s/litellm/README.md`: consumers send `Bearer = LITELLM_MASTER_KEY` to `:30400/v1`).

## Per-tool wiring

Repo config-as-code is **committed** (below). The **account/install steps are yours** — a cloud App has to be
installed from its dashboard against the GitHub repo; I can't do that.

| Tool | Repo config (committed) | Your account / IDE step | $0 basis |
|---|---|---|---|
| **DeepSource** | `.deepsource.toml` | Sign in w/ GitHub → install the App on `weyland-lab` (Open Source plan) → enable **Autofix**. **SaaS/CI only** — the IntelliJ plugin is unavailable/2026.2-incompatible; the App + Autofix PRs cover it. | free public/OSS |
| **CodeScene** | — (dashboard-config) | Add the public repo in CodeScene (web). **In-IDE via the CodeHealth MCP → Claude Code**, NOT the JetBrains plugin (won't launch on IntelliJ 2026.2). | free OSS |
| **Sourcery** | `.sourcery.yaml` | Install the **PyCharm plugin** + the GitHub App. ✓ working. | free public |
| **CodeRabbit** | `.coderabbit.yaml` | **Downgrade the plan to Free** in the CodeRabbit dashboard (App already installed). | free tier |
| **Greptile** | — | Install the App on `weyland-lab` (PR-native). | free OSS/public |
| **PR-Agent** | `.pr_agent.toml` + `scripts/pr-agent-review.sh` | Nothing to install — just `docker` + `scripts/.env`. | $0 via your gateway |
| **Continue** | `.continue/config.yaml` | Use the **Continue CLI** (`npm i -g @continuedev/cli` → `cn`), NOT the JetBrains plugin (deprecated — Cursor acquired Continue, repo read-only). Same config, BYO-LLM → LiteLLM. | $0 via your gateway |
| ~~Qodo~~ | — | **Cancel the paid subscription.** Continue replaces Gen. | — |

## Use it

**PR-Agent on a PR (rogueone):**
```
./scripts/pr-agent-review.sh https://github.com/edtbl76/weyland-lab/pull/<N> review
```
`describe` / `improve` / `ask` are the other commands. Model defaults to `wl-coding` (override with `PR_AGENT_MODEL`).

**Continue (CLI):** `npm i -g @continuedev/cli`, export `LITELLM_API_KEY`, then run `cn` from the repo — it reads
`.continue/config.yaml` and runs on `wl-coding` (LiteLLM). The JetBrains plugin is deprecated (Cursor acquired
Continue; repo read-only at v2.0.0) — the CLI is the maintained path. If you want an *in-IDE* BYO-LLM assistant
instead, **ProxyAI/CodeGPT** (JetBrains plugin, custom OpenAI-compatible provider → `:30400`) is the actively-
maintained alternative — evaluate it if the CLI doesn't fit your flow.

**CodeScene (Claude Code, via MCP):** the JetBrains plugin doesn't launch on IntelliJ 2026.2 — use the
**CodeHealth MCP** (Docker `codescene/codescene-mcp`, mirrored from STUD.io's setup). Wired in the repo-root
**`.mcp.json`** (bind-mounts the weyland tree read-only; exposes `code_health_review` / `analyze_change_set`). The
`CS_ACCESS_TOKEN` is **env-referenced** (`${CS_ACCESS_TOKEN}`) — put the CodeScene PAT in `scripts/.env`, never in
`.mcp.json` (STUD.io committed its PAT and flagged it for rotation — don't repeat that in the public repo). Needs
Docker up + a Claude Code restart (MCP servers load at session start).

**The cloud Apps** review automatically when a PR opens on `weyland-lab`; **DeepSource** also analyses on push
(direct-to-main) and raises its own **Autofix PRs**, so it works without a PR flow.

## Notes / gotchas
- **PR-Agent gotchas (hit + fixed 2026-08-08, validated on PR #6):** the image is **`codiumai/pr-agent:latest`**
  (NOT `qodoai/...`, which 404s); and a **custom/gateway model needs `custom_model_max_tokens`** or PR-Agent errors
  "Model … not defined in MAX_TOKENS" — set via `CONFIG__CUSTOM_MODEL_MAX_TOKENS` in `scripts/pr-agent-review.sh`
  (and `.pr_agent.toml`). Note PR-Agent reads `.pr_agent.toml` from the **committed GitHub repo** (apply_repo_settings),
  not your local edit — so config changes must be pushed, or overridden via env on the docker run.
- **Overlap is intentional.** Tuned so CodeRabbit stays on summaries (`profile: chill`) and Sourcery/DeepSource
  don't re-flag what the scan-suite already owns — but breadth is the goal, not dedup.
- **The gateway is the win** for PR-Agent + Continue: $0 marginal, your models, routed/guardrailed like the rest of
  the LLM lane. Spend is attributed **by model** at LiteLLM (this instance has **no DB → no per-consumer VK
  attribution**); the `wl-*` models still record provider cost via **Bifrost**. If you want per-consumer spend for
  the review tools, mint a dedicated **Bifrost VK** and point the configs at it — optional, not required to work.
  ([[litellm-bifrost-egress]], [[gateway-lane-separation]].)

## Pointers
- Registry: `quality-tools.yaml` (category `ai-code-review`) · Eval decision: `docs/backlog.md` → B106 · CI wiring
  (DeepSource/CodeScene/PR-Agent/Greptile → Port): B118 · static lane: [code-quality.md](code-quality.md).
