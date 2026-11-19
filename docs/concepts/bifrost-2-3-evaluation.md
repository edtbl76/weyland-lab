# Bifrost 2.3 evaluation (B212, 2026-10-19)

Production ran Bifrost **v2.2.6** when this was written (B202, digest-pinned in `k8s/bifrost/bifrost.yaml`, dashboard
auth off by decision, the admin API behind the setup token); it has run **v2.3.1** since 2026-10-19 (B231, the upgrade
this evaluation recommended). v2.3.0 shipped 2026-10-13 and **v2.3.1 on 2026-10-19**; this is what they mean
for the lab, decided from tests on throwaway instances, not from the release notes alone.

**Version tested: v2.3.1.** v2.3.0 is ruled out on its own: its A2A push relay leaks one goroutine every 3 s (~1,200/h,
until OOM — bifrost#8709), fixed in 2.3.1.

## How it was tested

Every test ran on a **throwaway instance on rogueone** — `127.0.0.1:18080`, host network, its own scratch data
directory, a fresh random setup token, dashboard auth off (the lab's setting), no production state and no provider keys.
Restoring the production `config.db` was attempted first and refused by the session's permissions: the backup holds
the provider keys in the clear and would have left the cluster. Production was only READ (two config reads through
`kubectl exec` with the pod's own token, values not printed). Scripts kept in the job scratch dir, not the repo.

**Re-test on a later 2.3.x** (rebuilt and RUN 2026-10-21 on the v2.3.1 digest; the original scripts were not kept). A
throwaway instance with its own scratch data and a fresh setup token, no production state, nothing leaves rogueone:
```
D=$(mktemp -d) && T=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))') && docker run -d --rm --name bifrost-eval -p 127.0.0.1:18080:8080 -e BIFROST_SETUP_TOKEN="$T" -v "$D":/app/data maximhq/bifrost@sha256:fe323e244998e1a40b87be87f60d023746eae40dd69baae8f7f42728a5e16149 && sleep 10; curl -s http://127.0.0.1:18080/api/version; for h in "" "X-Bifrost-Setup-Token: wrong" "X-Bifrost-Setup-Token: $T"; do curl -s -o /dev/null -w '%{http_code} ' ${h:+-H "$h"} http://127.0.0.1:18080/api/governance/virtual-keys; done; echo
```
Expect `"v2.3.1"` and `401 403 200` (the setup lock). Swap the digest for the version under test, then repeat the tests
in the verdicts below against `127.0.0.1:18080`. Remove it with `docker rm -f bifrost-eval`; `$D` holds only the
scratch `config.db`.

## Verdicts

| Question | Verdict | Evidence |
|---|---|---|
| Does 2.3 cut off our **private MCP targets** (Agent_Memory `192.168.1.230:8765`, the in-cluster compositor)? | **No.** | A client registered on 2.2.6 (production's digest) to Agent_Memory stayed `healthy` with 21 tools after the same data dir was upgraded to 2.3.1 and after a restart. A client registered **on 2.3.1 with the setup token** also connected; `require_public_target` = **0** for both (read from the scratch DB — the API does not expose it). Without the setup token the registration is refused (`401 … send the setup token`), so the "admitted only because auth is off" path the release notes restrict does not exist here: **the setup token counts as authentication.** |
| **Upgrade 2.2.6 → 2.3.1?** | **Now** (as its own change, below). No new settings needed. | The private-target rule does not bind us (above). The 2.3.1 `PUT /api/config` rejects `log_retention_days: 0` — production is **365**. The new browser-origin rule (`/api/*` from an unlisted origin → 403 while auth is off) — production's `allowed_origins` already holds `https://bifrost.weyland.lab`. The 2.3.x DB migrations seen on the scratch DB are additive (new columns); 2.3.1's two non-reversible ones touch only Agent Gateway registrations, of which production has none. **Not proven:** the migration of production's own `config.db` (280 prompts, 589 skills) — covered by the standard path: a manual `bifrost-backup` first, roll back by reverting the digest pin in git (Argo `selfHeal` would revert a live edit) and restoring that backup. |
| **Agent Gateway (A2A)** as the Realm's front door | **DON'T ADOPT (now).** | The Realm image, run locally, serves a valid card — but Bifrost refuses it: `upstream agent card has no strict A2A v1 interface the gateway can proxy (JSON-RPC, HTTP+JSON, or gRPC)`. The Realm publishes **A2A 0.3.0** cards (`protocolVersion` 0.3.0, `preferredTransport`); the gateway takes **A2A v1** only. It also blocks private destinations by default (`blocked connection to non-public address … add it to the Private Network Allowlist`) — production would need `client.a2a_private_allowlist` for the in-cluster Realm. Revisit if the Realm moves to A2A v1; until then B209's forward-auth + NetworkPolicy stays the front door. |
| Does 2.3 **re-initialize a stranded MCP session** (the 2026-10-16 compositor-rollout incident)? | **Yes — shown in production after the upgrade (B231, 2026-10-19).** A compositor rollout confirmed it for the fleet path too (2026-10-22: both compositors restarted, Bifrost untouched, `bifrost-fleet-txn.py` → `TXN_OK`), so no compositor ship needs a Bifrost restart. | **Production, before/after:** on 2.2.6 the owner's rogueone reboot (09:28) restarted Basic Memory and Bifrost kept the dead session — the on-demand watchdog at 19:06 showed Agent_Memory (and Hugging_Face) unhealthy, `Missing session ID`, ~10 h unseen. On 2.3.1, restarting Basic Memory → Bifrost reconnected within 20 s with no Bifrost restart (watchdog 0 alerts) and a real `search_notes` through Bifrost answered. **Locally (before the upgrade):** the incident did not reproduce on either version through the production compositor image — the live case is what proved it. |
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

## 2.5 re-evaluation (B249, in progress since 2026-11-19)

B249 re-asks B212's questions on 2.5.x and adds the 2.4/2.5 agent features (Relays, agents declared in config,
agent-mode governance, caller identity on logs). Same method: a throwaway instance on rogueone first, production only
read, then the upgrade as its own change.

**Versions (read 2026-11-19).** Releases after 2.3.1: 2.3.2 (10-20), 2.4.0 (10-29), 2.5.0 (11-06), 2.5.1 (11-10),
2.6.0 (11-19). Under the 14-day rule 2.5.0 qualifies on 2026-11-20 and 2.5.1 on 2026-11-24; 2.5.1 fixes gateway
crashes (a panic in a provider stream or a hook took the gateway down; an empty `messages` request crashed it).
Digests (Docker Hub, `maximhq/bifrost`): v2.5.0 `sha256:b5258c5f11c79064fc8280e49513f54c0b1da81c78bd11d3b4c1f62f8926d1ab`,
v2.5.1 `sha256:5ec9873acaf1687556b6e4dd854b92b539d9debf87a5a683b66338648b84d3c8`.

**From the release notes, before testing:**
- **A2A 0.3 is still not accepted.** No release from 2.3.2 to 2.6.0 adds it; 2.6.0 says "Valid A2A v1 agent cards
  register". B212's first Agent Gateway blocker most likely stands; the throwaway test confirms it against the Realm's
  real card. Nothing in the notes changes the private-destination rule (`a2a_private_allowlist`).
- **Breaking in 2.4.0:** GitHub Copilot keys set up through the GitHub App are refused (a PAT or OAuth token is
  needed), and each provider gets a passthrough-route allowlist. The repo and the harness configs use neither: the
  harnesses reach Bifrost only on `/mcp` and the skills marketplace. Production's provider list lives in Bifrost's
  database, so it is read once before the upgrade (no Copilot provider means the first change does not apply).
- **One-way migrations:** 2.4.0 adds the passthrough-allowlist column and the relay, relay-route, relay-grant and
  relay-log tables; 2.5.0 adds relay-log columns. All additive (older binaries ignore them), none reversible: a
  rollback is a backup restore, never an image downgrade.
- **Agents in config (2.4.0):** declare a grant on the agent (`agents[].virtual_key_ids`), not on the key; a grant
  naming something not yet stored is now skipped with a warning instead of failing startup.

**Relays candidates (inventory 2026-11-19, from the key names in `scripts/.env` and the code that reads them):**

| API with a stored key | Called by | Candidate? |
|---|---|---|
| TypeSafe Jev (`api.typesafe.ai`) | the operator's decision-model shadow (`decide.py`, after every incident sweep; paid, ~$0.0001 a sweep, owner-approved) | **Yes, the strongest:** an agent's paid call, which a relay would log per call and charge to the operator's virtual key. To test on 2.5 |
| FRED | a Dagster finance asset | Weak: a free API called by a pipeline, not an agent |
| Clockify | `scripts/owner_time.py` | Weak, and B235 may replace it |
| Runware, Runway, Replicate, ElevenLabs, Perplexity, Cohere, Fireworks | already in Bifrost as providers or MCP clients | No: already governed |
| `QASPHERE_API_KEY` | nothing (no code reads it) | Not a relay: an unused credential, left from a past evaluation, to revoke |

### Throwaway results on v2.5.1 (2026-11-19)

`maximhq/bifrost` v2.5.1 by digest on rogueone: host network bound to `127.0.0.1:18080` only (`APP_HOST`/`APP_PORT`;
the bridge cannot reach Basic Memory through rogueone's firewall), scratch data, its own setup token, no production
state. The Realm ran from its production image (`realm-of-agents:git-1cef29b5`) on `127.0.0.1:18090`. Everything was
removed afterwards.

| Question | Result |
|---|---|
| Setup-token lock | Unchanged from 2.3.1: no token 401, a wrong one 403, the right one 200. Fresh-database migrations ran clean |
| Private MCP targets | Unchanged: Agent_Memory at its production URL `http://192.168.1.230:8765/mcp` registered with the setup token and came up `healthy`, 21 tools; without the token 401 "send the setup token". (The in-cluster fleet compositor is checked by the MCP watchdog after the production upgrade) |
| Agent Gateway, blocker 2 (private destinations) | **Solved by configuration.** The card fetch was refused ("blocked connection to non-public address … add it to the Private Network Allowlist"); with `client_config.a2a_private_allowlist` set it went through |
| Agent Gateway, blocker 1 (A2A version) | **Still there.** With the allowlist set, the Realm's real 0.3.0 card is refused: "upstream agent card has no strict A2A v1 interface the gateway can proxy". The gateway's rule (`core/agent/manager.go`, `isStrictV1Interface`): a `supportedInterfaces` entry with the A2A v1 protocol version and a JSON-RPC or HTTP+JSON binding |
| What A2A v1 would cost the Realm | Measured with a separate v1-shaped stub card pointing at the unchanged Realm (the Realm's cards were not touched): the gateway registered it (it also needs `credential_origins` when the card and the endpoint differ in origin) and, with a granted virtual key, forwarded a v1 `SendMessage` call to the Realm, which answered "Method not found: SendMessage" (its own error; it knows only 0.3's `message/send`). The gateway speaks only v1 to callers (`message/send` refused at the gateway). So the cost is the Realm accepting v1: a `supportedInterfaces` entry in `cards.py` and `SendMessage` with v1 message parts in `a2a.py` (69 and 78 lines today), kept alongside 0.3 for the a2a-inspector. Production also needs the External Client URL set (unset, the agent endpoints answer 503) |
| Relays | **Work as described.** A relay to a local echo stub standing in for `api.typesafe.ai`: routes must be declared (an undeclared path is 404); no virtual key is 401; a granted key reaches the upstream with `Authorization: Bearer <stored credential>` and the caller's key is not forwarded; both calls (the refused one too) are in the relay logs with route, status, latency and the virtual key's id and name. A relay accepted a private base URL with no allowlist. A relay update must resend the credential |
| Caller identity on logs | Email is recorded only for signed-in users, so agent traffic (virtual keys, dashboard auth off) has none; the virtual key's name already identifies the caller. `capture_client_ip` is a startup log-store setting (`logs_store`, `framework/logstore/config.go`); production has no `config.json` (its config is in the database) and the addresses would mostly be in-cluster proxies. **Leave it off** |
| Agent mode / code mode governance | Nothing in the lab asks Bifrost to run tools in agent mode or code mode (LiteLLM sends some model traffic through Bifrost; the harnesses use `/mcp`). Nothing to turn on; confirmed on real traffic after the upgrade |

### Verdicts on 2.5 (owner, 2026-11-19) — [ADR-0014](../adr/0014-dont-adopt-bifrost-agent-gateway-or-relays.md)

| Feature | Verdict | Why |
|---|---|---|
| Upgrade 2.3.1 → 2.5.1 | **Yes, as its own change** | The setup-token lock and private MCP targets behave as on 2.3.1; the migrations are additive but one-way (a rollback is a backup restore). Before it: read production's provider names to rule out the 2.4.0 Copilot-key change |
| Agent Gateway as the Realm's front door | **DON'T ADOPT** | The A2A version mismatch stands (fixable for ~150 lines in the Realm), but the Realm's callers are already pinned to three in-cluster services by a NetworkPolicy and traced in Langfuse; per-caller keys alone don't justify another gateway |
| Relays (TypeSafe, FRED, Clockify) | **Skip all three** | TypeSafe: one consumer, a temporary experiment, capped by prepaid credit and alerted, key in git; in Bifrost it would live only in its database. FRED and Clockify: no agent calls them |
| Caller identity on logs (`capture_client_ip`) | **Leave off** | Virtual-key names already identify agent callers; client IPs here are mostly in-cluster proxies; it would need a `config.json` |
| Agent-mode and code-mode governance | **Nothing to turn on** | No lab client uses Bifrost's agent or code mode |

Found along the way: `QASPHERE_API_KEY` in `scripts/.env` is read by nothing (left from a past evaluation): revoke it
at QA Sphere.
