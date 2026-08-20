# Code-Review Stack — the B106 adopted set (7 tools, $0)

The AI code-review layer, chosen in **B106** and wired here. It sits **on top of** the static-analysis lane
(SonarQube + the 19-tool `scan-suite`, B120) — its job is **LLM contextual review** (diff-aware, cross-file,
natural-language), which SAST can't do. Owner chose **breadth over dedup**: multiple overlapping coverages, all
free. Paid **Qodo is cancelled**; **CodeRabbit** is kept on its **free** tier.

## The two lanes

| Lane | Runs where | Tools | Why |
|---|---|---|---|
| **PR / cloud** | Vendor infra, against the **public `weyland-lab`** *and* **`edtbl76/stud.io`** repos | DeepSource · CodeScene · Sourcery · Greptile · CodeRabbit | Cloud GitHub Apps — GitHub pushes events *out* to them, so the LAN-webhook limit doesn't apply. $0 on a public repo. |
| **Local / gateway** | rogueone (reaches GitHub **and** the LAN gateway) | PR-Agent (CLI) · ProxyAI (IDE) | Route through the lab's own **LiteLLM `:30400` / Bifrost** → your models, cost-tracked per-VK, no vendor egress. |

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
| **ProxyAI** (CodeGPT) | IDE settings (see **Use it**) | **Adopted in-IDE assistant** (replaces paid Qodo Gen): JetBrains plugin → **Custom OpenAI** provider at `http://192.168.1.243:30400/v1`, key = LiteLLM master key, model `wl-coding`. Verified 2026-08-08. | $0 via your gateway |
| Continue (fallback) | `.continue/config.yaml` | Terminal-only fallback — **Continue CLI** (`npm i -g @continuedev/cli` → `cn`), same BYO-LLM → LiteLLM config. Its JetBrains *plugin* is deprecated (Cursor acquisition) → ProxyAI is the in-IDE pick. | $0 via your gateway |
| ~~Qodo~~ | — | **Cancel the paid subscription** — ProxyAI replaces Gen. | — |

## Use it

**PR-Agent on a PR (rogueone):**
```
./scripts/pr-agent-review.sh https://github.com/edtbl76/weyland-lab/pull/<N> review
```
`describe` / `improve` / `ask` are the other commands. Model defaults to `wl-coding` (override with `PR_AGENT_MODEL`).

**ProxyAI (CodeGPT) — the adopted in-IDE assistant, replacing paid Qodo Gen:** install the ProxyAI JetBrains plugin,
then **Settings → Tools → ProxyAI → Providers → Custom OpenAI** and set: **Base/URL** `http://192.168.1.243:30400/v1`
(if it asks for the full chat path instead: `…/v1/chat/completions`), **API key** = your LiteLLM master key (the
`LITELLM_API_KEY` value in `scripts/.env`), **Model** `wl-coding`. Verified working 2026-08-08. Field labels vary by
version, but those three values are what matter — the gateway path is the same one the Step-1 curl proves.

**Continue CLI (fallback — terminal, not in-IDE):** `npm i -g @continuedev/cli`, export `LITELLM_API_KEY`, then `cn`
reads `.continue/config.yaml` on `wl-coding`. Continue's JetBrains *plugin* is deprecated (Cursor acquired Continue,
repo read-only at v2.0.0) — that's why ProxyAI is the in-IDE pick and Continue survives only as the CLI fallback.

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
- **The gateway is the win** for PR-Agent + ProxyAI: $0 marginal, your models, routed/guardrailed like the rest of
  the LLM lane. Spend is attributed **by model** at LiteLLM (this instance has **no DB → no per-consumer VK
  attribution**); the `wl-*` models still record provider cost via **Bifrost**. If you want per-consumer spend for
  the review tools, mint a dedicated **Bifrost VK** and point the configs at it — optional, not required to work.
  ([[litellm-bifrost-egress]], [[gateway-lane-separation]].)

## STUD.io parity (B118)

The **same cloud stack also runs on the public `edtbl76/stud.io` repo** — it's the other half of the "breadth"
decision, wired under **B118**. Verified live on **stud.io PR #121** (2026-08-19) via `gh pr checks 121`:
**DeepSource** (7 analyzers), **CodeScene** (Code Health Review, project **78184**), and **Sourcery** all post
checks; **CodeRabbit** + **Qodo Merge** (STUD.io's `.pr_agent.toml`) review in the PR conversation. STUD.io carried
its own configs before B106 (`.deepsource.toml`/`.coderabbit.yaml`/`.pr_agent.toml`/`.mcp.json`); the weyland
CodeHealth-MCP setup was mirrored **from** STUD.io.

- **Greptile** is the one member **not yet installed** on `edtbl76/stud.io` (browser App-install, your step).
- **CI → Port** for STUD.io runs is **B63** (`ci_pipeline` → `weyland_ci_reliability`), not a review-tool feed.
- STUD.io-side doc (in the STUD.io repo): `docs/arch/code-review-stack.md` (+ `workflow.md` / `github.md`).

## Pointers
- Registry: `quality-tools.yaml` (category `ai-code-review`) · Eval decision: `docs/backlog.md` → B106 · CI wiring
  (DeepSource/CodeScene/PR-Agent/Greptile → Port): B118 · static lane: [code-quality.md](code-quality.md).
