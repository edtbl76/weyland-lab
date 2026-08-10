# Prompt federation — one place to manage prompts, one place to measure them (B103)

Weyland had **three** prompt stores drifting apart — the Bifrost Prompt Repository (the reusable gateway library),
the MLflow Prompt Registry (app-integrated prompts), and now Langfuse. Prompt federation makes **Bifrost the single
source of truth** and flows every prompt OUT to Langfuse + MLflow, then wires the apps to **fetch from Langfuse at
runtime** — so every LLM trace is tagged with the exact prompt version that produced it. Author in one place; measure
the impact of a change in one place. Built + validated 2026-08-10 (Phase 1).

## The loop, in one glance

```
author/edit a prompt in Bifrost (SoT)
        │  sync_prompts.py  (Bifrost → Langfuse + MLflow, normalized, idempotent)
        ▼
Langfuse Prompts  ──fetch at runtime──▶  tool-server / operator / agent  ──LLM call──▶  Langfuse trace
        └───────────────── the trace shows  Prompt: <name> - vN  (clickable) ─────────────┘
```

Because the linkage is created at **fetch time**, the source of truth (Bifrost) is decoupled from where the linkage
lives (Langfuse). That's the whole trick.

## The three stores

| Store | Role | Prompt shape |
|---|---|---|
| **Bifrost** | **Source of truth** — author/manage here (269 prompts, incl. the app prompts in `app-integrated`) | chat messages, `{{var}}` |
| **Langfuse** | **Runtime fetch + linkage** — apps `get_prompt` here; traces link the version | chat, `{{var}}` |
| **MLflow** | **Catalog mirror** — kept in step for MLflow-native workflows | string template, `{var}` |

`sync_prompts.py` is a **normalizer** (it translates `{{var}}`↔`{var}` and flattens chat↔string), idempotent by
content-hash — the first run's `MLflow: … 4 unchanged` was the app prompts round-tripping **byte-identical**, proving
the translation is lossless.

## See it yourself

1. **Sync** (on mother) — mirrors Bifrost → Langfuse + MLflow:
   ```
   kubectl -n weyland exec deploy/dagster-user-code -- python /app/scripts/sync_prompts.py
   ```
2. **Exercise an app** — any of the three; e.g. the RAG endpoint:
   ```
   curl -s http://weyland-tool-server.weyland.svc:<port>/context/ask -d '{"query":"what does the weyland lab do","backend":"qdrant"}'
   ```
3. **Look in Langfuse** → `platform` → Tracing → the generation. Its header shows **`Prompt: rag_system - v1`** (↗).
   Click it → every trace that used that version, with their scores.

## Why it matters — measurable prompt changes

Edit `rag_system` in Bifrost → re-sync → it becomes **v2** in Langfuse → new answers tag **v2** → you compare v1 vs v2
on **real production traffic** (and, once online evals land, their scores). Prompt change tied to outcome, in one
surface. That's the payoff the split stores couldn't give you.

## Coverage (Phase 1)

Linkage is live on the three flagship apps — **tool-server** (`rag_system`), **operator** (`operator_system`),
**agent** (`agent_grade` / `agent_reflect` / `rag_system`) — each tracing to Langfuse **alongside** its existing MLflow
spans (nothing removed). Runbook: [runbooks/prompt-federation.md](../runbooks/prompt-federation.md). Design:
`aidlc-docs/prompt-federation-design.md`.

**Phase 2 (next):** make the sync **automatic** (Dagster `registrations` asset) and **bidirectional** (native
Langfuse/MLflow edits reconcile back to Bifrost).
