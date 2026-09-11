# Flow: code-intelligence / code-graph stack (B166)

The lab's code-intelligence layer, split by the two needs it serves — **agent semantic structure**
(Serena) and **code search/nav** (Sourcebot + standalone Zoekt) — plus an **on-demand security** track
(Joern). Decision (operator, 2026-09-11): adopt Serena + Sourcebot + Zoekt; Joern on-demand; drop
OpenGrok/Hound/Livegrep. Eval: [../concepts/code-intelligence-eval.md](../concepts/code-intelligence-eval.md);
ops: [../runbooks/code-intelligence.md](../runbooks/code-intelligence.md).

```mermaid
flowchart TB
    Dev([developer])
    Agent([coding agent: Claude Code / Codex / OpenCode])
    Repo[(weyland-lab · public GitHub)]

    subgraph Semantic["agent semantic — LSP-accurate, zero lab footprint"]
        Serena["Serena (uvx, MCP over stdio)"]
        LSP["language servers (Python + TS/JS)"]
        Serena --> LSP
    end

    subgraph Search["code search — deployed on k3s (reuse-first)"]
        Sourcebot["Sourcebot (web UI + MCP)<br/>sourcebot.weyland.lab · forward-auth"]
        Zoekt["Zoekt webserver (:6070)<br/>zoekt.weyland.lab · un-authed JSON"]
        IndexCron["zoekt-index CronJob (03:35 NY, daily)"]
        PG[(weyland-postgres · sourcebot DB)]
        Valkey[(valkey.data-mesh)]
        Sourcebot --> PG
        Sourcebot --> Valkey
        IndexCron -->|clone + zoekt-git-index| Shard[(zoekt index PVC)]
        Shard --> Zoekt
    end

    subgraph Security["on-demand security — NOT a service"]
        Joern["Joern (JDK-21 container)<br/>CPG + dataflow/taint queries"]
    end

    Agent -->|find-def / find-refs / symbol-edit| Serena
    Agent -->|MCP search| Sourcebot
    Agent -->|HTTP JSON search| Zoekt
    Dev -->|browse + search UI| Sourcebot
    Dev -->|run when auditing| Joern

    Repo -->|Sourcebot indexes continuously| Sourcebot
    Repo -->|daily shallow clone| IndexCron
    Repo -->|scoped CPG build| Joern
    LSP -->|reads working tree| Repo
```

Why the split:

- **Serena** answers "who calls this / what breaks if I change X" with **symbol accuracy** grep can't —
  it's the lever B104's coding-agent eval measures. Runs beside the agent on the operator box: **no lab
  service, no node RAM**.
- **Sourcebot** is the human + agent **search** surface (Zoekt speed + web UI + MCP + NL Q&A). A 3-service
  deploy (app + Postgres + Redis), so it **reuses** `weyland-postgres` (a dedicated `sourcebot` DB) and
  `valkey.data-mesh` rather than standing up its own — only the app pod is new RAM.
- **Zoekt (standalone)** is the same engine bare: the **un-authed, lightweight JSON endpoint** for
  scripts/agents. Sourcebot indexes continuously (its own job-manager, not a k8s CronJob); Zoekt is the
  **daily** pre-dawn mirror (Design Rule #5), with a manual `create job --from=cronjob/zoekt-index` for
  immediate freshness.
- **Joern** is a **security/dataflow** tool (CPG + taint), run on demand beside Semgrep (B47) — proven with
  9 payload→sink flows on `weyland-guard` — not the agent-context or nav deliverable, so it hosts nothing.
