# Demo — Plannotator (plan + diff review for coding agents) (B167)

Ledger row **#69**. Plannotator is the **human review/steer layer** over the coding-agent stack B104 (Emdash —
parallel agents) and B166 (Serena — agent structural context) built: review an agent's **plan** before it runs,
annotate its **git diff**, push feedback back in one click. Local, OSS, LAN-hardened. Eval:
[../concepts/plannotator-eval.md](../concepts/plannotator-eval.md); ops: [../runbooks/plannotator.md](../runbooks/plannotator.md);
flow: [../diagrams/flow-plannotator.md](../diagrams/flow-plannotator.md).

## Setup shown (RUN 2026-09-11)

- Installed the pinned binary (v0.27.14) — the installer verified a checksum + GitHub attestation, user-space
  `~/.local/bin`; hardened with `PLANNOTATOR_AI=disabled` + `PLANNOTATOR_SHARE=disabled`.
- Wired Claude Code: `/plugin marketplace add backnotprop/plannotator` → `/plugin install plannotator@plannotator`
  → restart. Plugin active (skills + the `ExitPlanMode` plan-review hook).

## 1. Plan-review round-trip (the flagship — hooks `ExitPlanMode`)

The agent planned the B167 keep-artifacts and called `ExitPlanMode`; the `PermissionRequest` hook fired, a local
server opened the **plan-review UI in the browser**, the operator reviewed the plan markdown and **approved** —
the agent then executed the approved plan. (Deny would have returned the annotations as structured feedback and
the agent would have revised.) This is the differentiator: Claude Code's native plan gate becomes an annotatable
page instead of terminal text.

## 2. Diff-review round-trip (`/plannotator-review`)

The operator runs `/plannotator-review` on the uncommitted diff → a browser diff viewer opens → annotate a line,
**send** → the feedback returns to the agent session and the agent addresses it. (A review closed without
annotating returns "Review session closed without feedback", exit 0 — nothing to address.)

```text
/plannotator-review
```

## Honest scope

A **workstation tool**, not a lab service — it runs beside the agent on rogueone, deploys nothing to the cluster
(no Argo app, no `applications.yaml`, no ServiceMonitor). Its value is a solo dev's review ergonomics: a real
annotation surface over plans and diffs with a one-click round-trip, versus scrolling terminal text. Kept for
that; `/plannotator-review` being user-invocation-only means the diff-review launch is always the human's, by
design.
