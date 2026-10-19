# Bifrost 2.3 evaluation (B212, 2026-10-19)

Production runs Bifrost **v2.2.6** (B202, digest-pinned in `k8s/bifrost/bifrost.yaml`, dashboard auth off by decision,
the admin API behind the setup token). v2.3.0 shipped 2026-10-13 and **v2.3.1 on 2026-10-19**; this is what they mean
for the lab, decided from tests on throwaway instances, not from the release notes alone.

**Version tested: v2.3.1.** v2.3.0 is ruled out on its own: its A2A push relay leaks one goroutine every 3 s (~1,200/h,
until OOM — bifrost#8709), fixed in 2.3.1.

## How it was tested

Every test ran on a **throwaway instance on rogueone** — `127.0.0.1:18080`, host network, its own scratch data
directory, a fresh random setup token, dashboard auth off (the lab's setting), no production state and no provider keys.
Restoring the production `config.db` was attempted first and refused by the session's permissions: the backup holds
the provider keys in the clear and would have left the cluster. Production was only READ (two config reads through
`kubectl exec` with the pod's own token, values not printed). Scripts kept in the job scratch dir, not the repo.

## Verdicts

| Question | Verdict | Evidence |
|---|---|---|
| Does 2.3 cut off our **private MCP targets** (Agent_Memory `192.168.1.230:8765`, the in-cluster compositor)? | **No.** | A client registered on 2.2.6 (production's digest) to Agent_Memory stayed `healthy` with 21 tools after the same data dir was upgraded to 2.3.1 and after a restart. A client registered **on 2.3.1 with the setup token** also connected; `require_public_target` = **0** for both (read from the scratch DB — the API does not expose it). Without the setup token the registration is refused (`401 … send the setup token`), so the "admitted only because auth is off" path the release notes restrict does not exist here: **the setup token counts as authentication.** |
| **Upgrade 2.2.6 → 2.3.1?** | **Now** (as its own change, below). No new settings needed. | The private-target rule does not bind us (above). The 2.3.1 `PUT /api/config` rejects `log_retention_days: 0` — production is **365**. The new browser-origin rule (`/api/*` from an unlisted origin → 403 while auth is off) — production's `allowed_origins` already holds `https://bifrost.weyland.lab`. The 2.3.x DB migrations seen on the scratch DB are additive (new columns); 2.3.1's two non-reversible ones touch only Agent Gateway registrations, of which production has none. **Not proven:** the migration of production's own `config.db` (280 prompts, 589 skills) — covered by the standard path: a manual `bifrost-backup` first, roll back by reverting the digest pin in git (Argo `selfHeal` would revert a live edit) and restoring that backup. |
| **Agent Gateway (A2A)** as the Realm's front door | **DON'T ADOPT (now).** | The Realm image, run locally, serves a valid card — but Bifrost refuses it: `upstream agent card has no strict A2A v1 interface the gateway can proxy (JSON-RPC, HTTP+JSON, or gRPC)`. The Realm publishes **A2A 0.3.0** cards (`protocolVersion` 0.3.0, `preferredTransport`); the gateway takes **A2A v1** only. It also blocks private destinations by default (`blocked connection to non-public address … add it to the Private Network Allowlist`) — production would need `client.a2a_private_allowlist` for the in-cluster Realm. Revisit if the Realm moves to A2A v1; until then B209's forward-auth + NetworkPolicy stays the front door. |
| Does 2.3 **re-initialize a stranded MCP session** (the 2026-10-16 compositor-rollout incident)? | **Yes — shown in production after the upgrade (B231, 2026-10-19).** Keep the ship's `rollout restart deploy/bifrost` step only until one compositor rollout confirms it for the fleet path too. | **Production, before/after:** on 2.2.6 the owner's rogueone reboot (09:28) restarted Basic Memory and Bifrost kept the dead session — the on-demand watchdog at 19:06 showed Agent_Memory (and Hugging_Face) unhealthy, `Missing session ID`, ~10 h unseen. On 2.3.1, restarting Basic Memory → Bifrost reconnected within 20 s with no Bifrost restart (watchdog 0 alerts) and a real `search_notes` through Bifrost answered. **Locally (before the upgrade):** the incident did not reproduce on either version through the production compositor image — the live case is what proved it. |
| **App label on metrics** (per-harness usage for B62/B185) | **Not needed; unverified.** | 2.3.1's request metrics carry an `app` label, but it stayed `app=""` for the real Claude Code and Codex User-Agents on every request recorded (all failed before the model — the throwaway's Ollama key setup was not resolved within the time box). B185 lane 1 already attributes agent time per harness from session logs, so nothing depends on it. |
| Per-VK content logging, auto-delete expired keys, MCP "Refresh tools" + captured server instructions, `x-bifrost-request-id` | **Take as they come with the upgrade; no work.** | Additive, off by default or passive. `POST /api/mcp/client/{id}/refresh-tools` is a useful manual step for the B203 watchdog runbook after the upgrade. |
| Cloudflare Workers AI provider, semantic cache per identity, guardrail detections, Decisions API | **No.** | Provider lanes and routing live in LiteLLM by decision (gateway-lane separation); guardrails live at the agent edge (weyland-guard); Decisions/decision models stay DON'T ADOPT (B174). |
| Enterprise features (Access Profiles, Org Chart, adaptive-routing incidents, audit-log options) | **Out** ($0). | — |

## The upgrade, as its own change

1. Manual backup: `kubectl -n weyland create job --from=cronjob/bifrost-backup bifrost-backup-manual-$(date +%s)` (runbook
   `mcp-gateway.md` § Bifrost backup + restore).
2. Bump the digest pin in `k8s/bifrost/bifrost.yaml` to the v2.3.1 digest (list it, never take a tag).
3. After Argo rolls it: every MCP client `healthy` (`bifrost-mcp-watchdog` run on demand), the ship transaction
   (`scripts/bifrost-fleet-txn.py`) OK, one `wl-default` call through LiteLLM, the Prompt/Skills counts unchanged.
4. Roll back: revert the pin in git and restore the manual backup (the restore section of the runbook).
