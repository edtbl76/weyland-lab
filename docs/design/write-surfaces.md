# Write surfaces — who may change state, and what refuses everyone else (B209)

**Status: APPROVED and BUILT (2026-10-14)** — the owner approved it as written. Runbook:
[runbooks/write-surfaces.md](../runbooks/write-surfaces.md). The inventory in §2.7 found 11 more open write surfaces;
they are tracked as **B211** (EMA-298), each an `accepted_gap` the guard lists on every run.
Linear EMA-296. Found by the B207 act-surface audit. The goal is the one B207 left open: **every surface that
changes state is either authenticated and guarded, or unreachable by agents and arbitrary pods.**

## 1. What the audit found (verified 2026-10-14)

Three read-only research passes, each checked against the live cluster, not just the manifests.

| Surface | What it can change | Who can reach it today | Mesh? |
|---|---|---|---|
| Dagster GraphQL (`dagster-webserver:3000`) | launch any job | any pod; the browser UI via Traefik | meshed, but only through an **untracked live patch** (`kubectl-patch`, 2026-06-18) |
| store-scaler `/scale` (`data-mesh`) | scale cockroachdb / mongodb / mysql / gizmosql to 0 or 1 | any pod | **not meshed** (`inject: "false"`, deliberate) |
| Bifrost `/mcp`, VK `coding-agents` | GitHub push/merge/delete/create-repo, all Linear writes, memory writes, Playwright `browser_run_code_unsafe` | anyone holding the VK; the pod has no sidecar | no |
| Playwright (stdio **inside the Bifrost pod**) | anything an HTTP POST can do | every ClusterIP, the LAN and the internet; no egress policy | no |
| realm-of-agents (`realm.weyland.lab` + Service) | spends paid Haiku (`allow_paid` defaults to **true**); holds the `coding-agents` VK, Bifrost's admin setup token, LiteLLM's master key | anyone on the LAN (no forward-auth, CORS `*`) and any pod | meshed |
| Operator Telegram confirm | fires an act | **any member** of an allowlisted chat: the allowlist matches `chat.id`, never `from.id` | n/a |
| Incident sweep → Telegram | sends LLM text summarising untrusted pod logs | — | n/a |

**Legitimate callers, from code, manifests and 14 days of `istio_requests_total`:**

- **Dagster API:** `dagster-user-code` (the ship loop's FR-DRAIN and TXN, via `kubectl exec`), `weyland-tool-server`
  (`_launch_dagster_job`; no traffic in the window but a live code path), and Traefik for the browser UI. The daemon
  doesn't call it; runs execute inside the user-code pod. One stray call from `weyland-guard` (2026-10-09) has no
  code behind it.
- **store-scaler:** `port-agent` only (the Port "Scale data-mesh store" action). Zero `/scale` calls in 30 days.
- **Realm (in-cluster):** the operator (`/route`), the ship loop's TXN (from `dagster-user-code`), Dagster
  registrations (`GET /prompts`), the a2a-inspector, `api-drift` (`spec_source`). Through the ingress: blackbox
  (accepts 302/401/403) and external A2A clients.

**Two facts that decide the mechanism:**

1. **Istio identity rules can't see unmeshed callers.** Traefik and port-agent are not meshed and store-scaler isn't
   either, so a principal-based `AuthorizationPolicy` would break the Dagster UI and enforce nothing on store-scaler.
2. **NetworkPolicy is enforced here.** k3s's built-in controller enforces the two compositor policies. Re-proved
   2026-10-14: a call from `weyland-guard` to the memory compositor is refused at once. From a meshed pod a refusal
   shows as an instant `503 envoy … remote connection failure`, not a timeout.

## 2. Proposed fixes

### 2.1 Dagster API — a NetworkPolicy front door (+ put the sidecar label in git)

```yaml
# k8s/dagster/netpol-webserver.yaml (sketch)
podSelector: { matchLabels: { app: dagster-webserver } }
ingress:
  - from:
      - podSelector: { matchLabels: { app: dagster-user-code } }
      - podSelector: { matchLabels: { app: weyland-tool-server } }
      - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } }
        podSelector: { matchLabels: { app.kubernetes.io/name: traefik } }
    ports: [{ port: 3000 }]
```

| Option | Verdict |
|---|---|
| **NetworkPolicy (recommended)** | admits Traefik and the two in-cluster callers by label, meshed or not; the same mechanism as the compositors |
| Istio ALLOW by principal | breaks the UI: Traefik has no principal (plaintext, unmeshed) |
| Istio ALLOW + Traefik `ipBlocks` | Traefik's pod IP changes on restart |
| Mesh Traefik | right long-term, but a front-door change for 21 forward-auth'd hosts; out of scope |

The webserver's `sidecar.istio.io/inject: "true"` label goes into `k8s/dagster/webserver.yaml`, so the live patch
stops being drift. Kubelet probes are admitted by the controller.

### 2.2 store-scaler — a NetworkPolicy admitting only port-agent

`podSelector: app=store-scaler`, ingress from `namespaceSelector: kubernetes.io/metadata.name=port-agent`, port 8080.
Meshing both ends plus a STRICT PeerAuthentication would be stronger, but it would change port-agent (Helm-managed)
for a surface called zero times in 30 days.

### 2.3 Bifrost — split the key: unattended callers get no write tools

- **New VK `agents-read`:** weyland_fleet (already read-only by construction), Context7, Perplexity, Hugging Face,
  GitHub_Remote **read tools only**, Agent_Memory **read tools only** (the `MEMORY_READ` tuple form already exists).
  **No** Playwright, no Linear writes. It's one `SCOPING` line in `register_bifrost_vk_mcp.py`, applied live with no
  restart (B203). Creating the VK itself is a UI/API step (yours); its value replaces `BIFROST_VK` in `realm-of-agents-secret`
  (created with `kubectl`, never committed).
- **Realm moves to `agents-read`.** Today its roster's name filter matches no write tool, but the whole write set is
  loaded in-process; the key, not the filter, should be the control.
- **`coding-agents` stays for the interactive harnesses** (Claude Code / Codex / OpenCode), where a human approves
  tool calls. Write tools do **not** go through the act guard: the guard's actor model is "an agent acting on the
  platform", and putting a human's own coding session behind it adds a refusal path with no safety gain.
- **Playwright can no longer reach the unguarded services:** the 2.1 / 2.2 policies don't admit the Bifrost pod.
  General egress limits on Bifrost (providers, SaaS MCPs, rogueone, the compositors) are deferred; the repo guard
  (2.7) is what stops the next unguarded service.

### 2.4 Realm — forward-auth on the host, a front door in-cluster, free by default

- **Ingress:** the standard `weyland-traefik-forward-auth@kubernetescrd` middleware on the **whole host**. Browser-only
  forward-auth would be cosmetic (`/route` and `/a2a` would stay open on the LAN). The cost: external A2A clients and
  discovery from outside the cluster get a 302 to Keycloak. Today the only external caller is blackbox, which already
  accepts 302.
- **In-cluster NetworkPolicy:** admit the operator, `dagster-user-code` (TXN + registrations), the a2a-inspector,
  `api-drift` (ns `monitoring`), Prometheus (its ServiceMonitor) and Traefik. **Built:** the a2a-inspector relayed to
  `/a2a` for any caller, so it got its own policy too (Traefik only), or it would have been a way around this one.
- **`allow_paid` defaults to `false`**; a caller that wants Haiku asks for it. CORS is narrowed from `*` to the Realm
  host.
- **The admin setup token stays** (Realm reads its role prompts from Bifrost's `/api`, and Bifrost has a single admin
  token); recorded as a known over-grant, not hidden.

### 2.5 Operator — the confirmer must be an allowed person

- Check `message.from.id` against the allowlist on **every** message, especially the "yes" that fires an act.
  Missing `from` (channel posts) or an anonymous admin (`sender_chat`) fails closed.
- The allowlist becomes **user ids**. In a private chat `chat.id == user.id`, so if today's entry is your private chat
  with the bot, nothing changes for you. Group chats are admitted by a separate `TELEGRAM_ALLOWED_CHATS`, and the
  sender must still be on the user list.
- New `tests/test_ingress.py` (none exists): a stranger's "yes" in an allowed group is refused; your own works; a
  message with no `from` is refused.

### 2.6 Incident sweep — a check that actually blocks

Every OUTPUT validator is in SHADOW, so calling `/guard/output` would only **record**. And the output chain has no
secrets detector. So the sweep gets:

1. **A deterministic secrets redaction inside the operator, failing closed** (the gitleaks-style token, key and
   password patterns, plus `-----BEGIN`): a match redacts the value, and an unexpected error drops the message
   rather than sending raw text.
2. **The `/guard/output` call too** (actor `operator:incident-sweep`), for the PII and safety record, like the chat
   path. Promoting any OUTPUT validator to `block` is a separate, lab-wide decision; it's not taken here.

### 2.7 Keep it closed — a declared registry field and a guard

- `applications.yaml` gains a **required** field on every deployed service: `writes: true|false`. It's true when
  callers can change state through it, and it's declared the way `metrics` and `ingress` are (declare and account,
  B154).
- **`scripts/check-write-surfaces.sh`** (repo-guards, exit 0/1/2) fails when a `writes: true` service has no
  NetworkPolicy or AuthorizationPolicy selecting its pods, unless it carries a reasoned
  `front_door: <how it is authenticated>` (e.g. "MinIO: S3 signatures", "Keycloak: its own login").
- The first pass classifies all 61 deployed services. Any others it finds unguarded are listed for your call, never
  silently passed.

### 2.8 Mesh path normalization — not now

The `%2F` class is already closed in the two apps that had exact-path rules. Mesh-wide `DECODE_AND_MERGE_SLASHES`
would touch the 48 meshed pods (not 83, as the B207 note said), including DataHub (URNs with `/`) and lakeFS (branch
names with `/`), with no access logs to show what uses encoded slashes. **Recommendation:** leave the mesh at `BASE`.
If it's wanted later, turn on Envoy access logging first, then decide on evidence.

## 3. Order of work (each step is shippable and checked live)

1. Telegram `from.id` (2.5) and the sweep redaction (2.6): code, tests first, ship the operator.
2. Dagster + store-scaler NetworkPolicies (2.1, 2.2) and the sidecar label: live negative checks (an unlisted pod is
   refused) and positive checks (the UI loads; a ship's FR-DRAIN and TXN pass; the Port scale action reaches
   `/scale`).
3. The Bifrost `agents-read` VK + Realm on it (2.3), then Realm forward-auth, NetworkPolicy and `allow_paid` (2.4).
4. The registry field + `check-write-surfaces.sh` (2.7), with every deployed service classified.

## 4. Open questions for the owner

1. ~~The Telegram allowlist entry~~ — **answered 2026-10-14: the owner's private chat**, so 2.5 needed no secret change.
2. **`.claude/settings.local.json` auto-allows** GitHub_Remote `create_branch` / `create_or_update_file` /
   `create_pull_request` / `update_pull_request`, plus `postgres_execute_sql` and `trino_execute_query`, through
   Bifrost with no prompt. That's your local file; keep, narrow, or drop those entries?
3. ~~External A2A discovery of Realm~~ — accepted with the design's approval (no such caller exists).

## 5. Acceptance (from EMA-296, mapped)

| Criterion | Proved by |
|---|---|
| Unauthorized Dagster `launchRun` refused; daemon, tool-server and UI still work | 2.1 negative + positive checks |
| Unauthorized `/scale` refused; Port action still works | 2.2 checks |
| Realm and unattended agents hold no write tools (VK checked live) | 2.3, the VK's live tool list |
| `realm.weyland.lab` refuses an unauthenticated request | 2.4, `curl` → 302 |
| A stranger's Telegram confirm in an allowed chat is refused | 2.5 test |
| The sweep's messages pass the output check | 2.6 tests (redaction + guard call) |
| A new state-changing Service without a front door fails CI | 2.7 guard + bats, shown failing |

DoD for each step: docs (`arch.md`, runbooks for Dagster, store-scaler, Bifrost, Realm and operator), the demo
(`act-guard.md` grows a write-surfaces section), Pillar 8 cascades, and N/A for DR (no new state).
