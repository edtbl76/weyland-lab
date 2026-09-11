# Runbook — code-intelligence / code-graph stack (B166)

The lab's code-intelligence tools — semantic structure for the coding agents + code search/nav for a
human. Eval + rationale: [../concepts/code-intelligence-eval.md](../concepts/code-intelligence-eval.md).
This runbook grows one section per tool as the bake-off proceeds.

Bake-off set: **Serena** (agent LSP-MCP) · **Sourcebot / Zoekt / OpenGrok / Hound / Livegrep** (search
bake-off) · **Joern** (security CPG). Node-RAM aware: the 5 search engines run as a *sequential* bake-off
(stand up → compare → keep the winner), NOT 5 permanent services (mother has ~4.6Gi headroom).

---

## Serena — agent semantic intelligence (LSP → MCP)

`oraios/serena` (OSS). Turns a language server into **MCP tools** the coding agents call: `find_symbol`,
`find_referencing_symbols`, `get_symbols_overview`, symbol-aware insert/replace, etc. — real LSP accuracy,
not grep. Runs via `uvx` (no install); Python LSP verified on the real code (`serena project index
services/weyland-guard` → indexed 25 files, exit 0).

**Wired into Claude Code** via `.mcp.json` (project-scoped, repo root, `ide-assistant` context, stdio):

```json
"serena": {
  "type": "stdio",
  "command": "uvx",
  "args": ["--from","git+https://github.com/oraios/serena","serena","start-mcp-server",
           "--context","ide-assistant","--project","/home/edwardmangini/IdeaProjects/weyland",
           "--transport","stdio","--enable-web-dashboard","false","--enable-gui-log-window","false"]
}
```

**MCP loads at client startup**, so a running Claude Code session won't see it until restart. To activate +
eyes-on UAT:
1. Restart Claude Code in the repo (it reads `.mcp.json`).
2. Ask it a structural question grep answers badly — the canonical one:
   *"Use serena to find all references to the `Decision` symbol in `guardrails/verdict.py`."*
   Expect it to resolve refs in **both** `services/weyland-tool-server/guardrails/verdict.py` **and**
   `services/weyland-guard/guardrails/verdict.py` — the duplicated wire-contract the DoD Pillar-8 note
   flagged as "kept in sync by nothing". That's the win over grep: symbol-accurate, cross-file, cheap.

`.serena/` (per-project config + LSP symbol cache) is gitignored (regenerable; serena also self-ignores
its cache). No lab service is deployed — Serena runs on the operator's machine alongside the agent.

Promote to the **MCP fleet** (B17/B19) later only if the operator wants it reachable through the gateway
for the B66 operator too; local-in-Claude-Code is the $0 first step.

---

## Sourcebot — human + agent code search (Zoekt + web UI + MCP)

`sourcebot-dev/sourcebot` (OSS) — the $0 Sourcegraph replacement: **Zoekt** trigram search across repos,
a web UI for humans, an MCP server + NL Q&A for agents. **Proven** on the real repo: `GuardrailPipeline`
→ **9 files in 0.19ms** over a single 59.7 MB index shard (see the eval doc's bake-off table).

**v5 is a 3-service deploy, not one container** (it dropped embedded Postgres). The bake-off stood it up
as throwaway containers on an isolated `sb-net` network — Postgres + Redis + the app:

```bash
# secrets — generate once (NEVER paste; keep them out of git)
ENC_KEY=$(openssl rand -base64 24)      # SOURCEBOT_ENCRYPTION_KEY
AUTH_SECRET=$(openssl rand -base64 33)  # AUTH_SECRET
docker network create sb-net
docker run -d --name sb-postgres --network sb-net \
  -e POSTGRES_USER=sourcebot -e POSTGRES_PASSWORD=<pw> -e POSTGRES_DB=sourcebot postgres:16
docker run -d --name sb-redis --network sb-net redis:7
# config.json declares the repo connection (git, local path)
#   {"$schema":".../v3/index.json","connections":{"weyland-local":{"type":"git","url":"file:///repos/weyland"}}}
docker run -d --name sourcebot-bakeoff --network sb-net -p 3939:3000 \
  -e DATABASE_URL="postgresql://sourcebot:<pw>@sb-postgres:5432/sourcebot" \
  -e REDIS_URL="redis://sb-redis:6379" \
  -e SOURCEBOT_ENCRYPTION_KEY="$ENC_KEY" -e AUTH_SECRET="$AUTH_SECRET" \
  -e AUTH_URL="http://<rogueone-host>:3939" \
  -v <data-dir>:/data -v /home/edwardmangini/IdeaProjects/weyland:/repos/weyland:ro \
  ghcr.io/sourcebot-dev/sourcebot:latest
```

**Verify search without the auth wall** (the web UI/API are login-gated — `:3939` 307→login, `/api` 401;
Zoekt itself is not): query the internal `zoekt-webserver` directly inside the container —

```bash
docker exec sourcebot-bakeoff sh -c \
  'curl -s "http://localhost:6070/search?q=<term>&num=20&format=json"' | head -c 400
# FileCount:N + Duration(ns) confirm the index is live over the real repo
```

**Operator eyes-on (the human half — batched to the end):** open `http://<rogueone>:3939`, sign up as the
first user, and run a cross-repo search. `AUTH_URL` must match the host the operator browses from (it was
`localhost` in the bake-off container) or the login redirect breaks. The MCP + NL-Q&A layer needs LLM keys
— point it at the lab gateway if promoting it.

**Fallback if 3 services is too much for the node:** standalone **Zoekt** is Sourcebot's engine minus the
wrapper — one `zoekt-webserver` process + one index shard, no Postgres/Redis/auth, HTTP/JSON search only
(proven: same 9-file/0.19ms result at `:6070`). Keeps search quality; loses the web UI + MCP.

**Not deployed — documented comparison only:** **OpenGrok** (JVM/Tomcat, ctags xref + Lucene, mature human
UI, no MCP), **Hound** (Go trigram, tiny, but unmaintained + regex-only + no symbols/MCP), **Livegrep**
(RE2 regex search, same shape as Hound). All lose to Sourcebot on capability with no offset that matters
here — rationale in the eval doc's bake-off table.

**Teardown** (throwaway bake-off containers): `docker rm -f sourcebot-bakeoff sb-postgres sb-redis;
docker network rm sb-net`.

---

## Joern — security / dataflow code-property graph (on-demand, NOT a service)

`joernio/joern` (OSS, Apache-2.0). A **code-property graph** + Scala query DSL for **dataflow/taint +
call-graph** analysis — the "does this untrusted parameter reach a dangerous sink?" question. **Separate
track** from the agent/search tools: it sits beside **Semgrep (B47)** / the review stack (B106), not in the
MCP fleet. Heavy (JVM + a CPG build per language), no first-class agent MCP → run it **on demand**, not as
a standing deploy.

**No public Docker image** (ghcr/dockerhub are auth-gated). It ships as a release zip + needs a JDK;
Joern v4 targets **JDK ≤ 21**, so run it in a JDK-21 container (the host JDK is 25 and will not work):

```bash
# 1. fetch joern-cli (once; ~1.8 GB) — pick the latest release asset
curl -sL -o /tmp/joern-cli.zip \
  https://github.com/joernio/joern/releases/download/v4.0.626/joern-cli-linux-x86_64.zip
unzip -q /tmp/joern-cli.zip -d /tmp        # → /tmp/joern-cli/ (pysrc2cpg, joern, joern-scan, …)

# 2. build the CPG for a scoped target (whole repo works too, but scope keeps it fast)
docker run --rm -e HOME=/work \
  -v /tmp/joern-cli:/joern \
  -v <repo>/nodes/mother/lab/weyland-platform/services/weyland-guard:/src:ro \
  -v /tmp/joern-work:/work \
  maven:3.9-eclipse-temurin-21 \
  bash -lc '/joern/pysrc2cpg /src -o /work/cpg.bin'      # Python; c2cpg/javasrc2cpg/jssrc2cpg for others

# 3. run a query script (see query.sc below) against the CPG
docker run --rm -e HOME=/work \
  -v /tmp/joern-cli:/joern -v /tmp/joern-work:/work \
  maven:3.9-eclipse-temurin-21 \
  bash -lc '/joern/joern --script /work/query.sc'
```

`query.sc` — the demonstrative queries (call-graph fan-out, risky sinks, request-param→sink dataflow):

```scala
importCpg("/work/cpg.bin")
val risky = cpg.call.name("(system|popen|run|call|check_output|eval|exec|load|loads)").l
risky.foreach(c => println(c.method.filename + ":" + c.lineNumber.getOrElse(-1) + "  " + c.code.take(90)))
// dataflow: does a request parameter reach a risky sink?
val src = cpg.identifier.name("(request|body|payload|data|text|prompt|input|content)")
risky.reachableByFlows(src).take(5).foreach(f => println(f.elements.map(_.code.take(50)).mkString(" -> ")))
```

**Proven 2026-09-11** on `weyland-guard`: CPG of **26 files / 292 methods / 3136 calls**; found the
`exec(compile(path.read_text()))` in `tests/test_verdict_contract.py:48` and **9 taint flows** from the
request `payload` to the async validator sink — reachability grep/Zoekt cannot compute. Also see
`joern-scan` (canned CPG security queries) for a batteries-included pass.

`joern-cli.zip` + `/tmp/joern-work` are throwaway; nothing is committed and no lab service is deployed.
