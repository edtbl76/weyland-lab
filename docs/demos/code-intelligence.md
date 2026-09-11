# Demo — code-intelligence / code-graph stack (B166)

Ledger row **#68**. The lab's code-intelligence layer: semantic structure for the coding agents (**Serena**),
human+agent code **search** (**Sourcebot** + standalone **Zoekt**), and on-demand security **dataflow**
(**Joern**). Eval + rationale: [../concepts/code-intelligence-eval.md](../concepts/code-intelligence-eval.md);
operations: [../runbooks/code-intelligence.md](../runbooks/code-intelligence.md).

Decision (operator, 2026-09-11): **adopt Serena + Sourcebot + Zoekt; Joern on-demand; drop
OpenGrok/Hound/Livegrep.** Each keeper below is shown with what was actually verified.

## 1. Serena — agent semantic intelligence (LSP → MCP)

Proves symbol-accurate structure the agents can call, not grep.

```bash
# LSP index proven on real code (2026-09-11):
uvx --from git+https://github.com/oraios/serena serena project index \
  nodes/mother/lab/weyland-platform/services/weyland-guard
# → "indexed 25 files", exit 0
```

Wired into Claude Code via `.mcp.json` (stdio, `ide-assistant`). **Eyes-on (operator):** restart Claude
Code, then ask *"use serena to find references to the `Decision` symbol in `guardrails/verdict.py`"* — it
resolves refs in **both** the `weyland-guard` and `weyland-tool-server` copies of the byte-duplicated
contract (the Pillar-8 "kept in sync by nothing" case), which grep cannot tie together.

## 2. Sourcebot — human + agent code search (Zoekt + web UI + MCP)

Zoekt search **proven on the real repo** during the bake-off (throwaway Docker):

```
curl "http://localhost:6070/search?q=GuardrailPipeline&num=20&format=json"
# → FileCount:9, Duration ≈ 0.19ms — guard pipeline.py/app.py/test_pipeline.py + graphify.sh + docs,
#   over a single 59.7 MB index shard of the whole tree.
```

Deployed for real as a standing GitOps service (`k8s/sourcebot/`, Argo app `sourcebot`) — reuses
`weyland-postgres` (a dedicated `sourcebot` DB) + `valkey.data-mesh`; UI behind Keycloak forward-auth.
**Post-deploy eyes-on (operator):** open `https://sourcebot.weyland.lab`, sign up as first user, run a
cross-repo search. Verify the engine without the auth wall: `kubectl -n weyland exec deploy/sourcebot --
curl -s 'http://localhost:6070/search?q=<term>&format=json' | head -c 200`.

## 3. Zoekt — standalone lightweight search (the un-authed JSON endpoint)

The same engine minus the wrapper — deployed bare (`k8s/zoekt/`, Argo app `zoekt`) as the open
programmatic search for scripts/agents. Daily pre-dawn re-index CronJob (03:35 NY) + a webserver on
`zoekt.weyland.lab` (no forward-auth by design).

```bash
# once deployed — the same JSON search, no auth:
curl "https://zoekt.weyland.lab/search?q=GuardrailPipeline&num=20&format=json"
# immediate re-index after a push (on-demand, no waiting for the daily cron):
kubectl -n weyland create job --from=cronjob/zoekt-index zoekt-index-now
```

## 4. Joern — security / dataflow CPG (on-demand, not a service)

Proves the CPG value no search engine can give — taint/dataflow reachability. **Proven 2026-09-11** on
`weyland-guard`:

```
pysrc2cpg /src -o cpg.bin        # CPG: 26 files / 292 methods / 3136 calls
joern --script query.sc
# → risky sinks (9): incl. exec(compile(path.read_text())) in test_verdict_contract.py:48 + json.loads in policy.py
# → 9 taint flows: request `payload` → run_in_executor → verdict → verdict.decision → return
```

Reproducible build+query in the runbook (release zip + JDK-21 container; no public image). Sits beside
Semgrep (B47) / the review stack (B106), run when a security question needs it — not hosted.

## Cleanup / data

Serena runs on the operator box (0 lab footprint; `.serena/` gitignored). Sourcebot + Zoekt are standing
GitOps services (Sourcebot reuses existing PG/Valkey — its `sourcebot` DB is the only new state; Zoekt's
60 MB index is a regenerable PVC). Joern's `joern-cli.zip` + CPG are throwaway. The bake-off Docker
containers were torn down; nothing from the bake-off is left running.
