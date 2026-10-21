# Bifrost — agent edge (MCP + prompts + skill marketplace)

**Bifrost** (`bifrost.weyland.lab`) is the coding-agent MCP front door and closes the MCP-gateway deliverable (B17+B19,
built out as **B111**). One virtual key gives an agent the whole lab tool surface, plus a reusable prompt library and an
installable skill marketplace.

- **MCP:** the `coding-agents` VK aggregates the read fleet (via the FastMCP compositor) plus
  Context7, Linear, GitHub, Perplexity, Playwright, Hugging Face — behind one `/mcp`. Wired into **Claude Code, Codex,
  and OpenCode** with the *same* VK (scope-by-use, not per-agent).
- **Prompt Repository:** hand-authored (skill-aware system prompts + a `skills` orchestration folder) plus
  corpus-derived (`apply-<framework>`, `run-<aidlc-stage>`, industry-lens). Model-agnostic, lane-tagged.
- **Skills Repository:** lab-ops runbooks + the AIDLC stages + knowledge-base entries — served
  as a **Claude Code / Codex plugin marketplace** so any of them installs into an agent with one command.
- **Counts are not written here** (they change with every registrar run; this page carried 232 tools / 241 prompts /
  583 skills long after they moved). The live counts are the nightly `bifrost-backup` log line (2026-10-21: prompts
  280, skills 589, MCP clients 10, virtual keys 6):
  ```
  kubectl -n weyland logs $(kubectl -n weyland get jobs --sort-by=.metadata.creationTimestamp -o name | grep bifrost-backup | tail -1) | grep -o "counts={[^}]*}"
  ```

## How a request flows

```mermaid
sequenceDiagram
  autonumber
  participant A as Coding agent<br/>(Claude Code · Codex · OpenCode)
  participant B as Bifrost<br/>bifrost.weyland.lab
  participant C as Compositor<br/>(FastMCP)
  participant F as Read fleet<br/>(6 MCP servers)

  Note over A,B: MCP tool access
  A->>B: POST /mcp  (header x-bf-vk = coding-agents VK)
  B->>B: resolve VK → 232-tool registry
  B->>C: aggregate weyland_fleet (95 tools)
  C->>F: grafana · trino · k8s · postgres · neo4j · datahub (read-only)
  B-->>A: tools/list (232) → tools/call

  Note over A,B: skill marketplace (git-served plugins)
  A->>B: GET /api/skills/serve/claude-code/.claude-plugin/marketplace.json
  B-->>A: marketplace JSON (584 plugins)
  A->>B: git clone the plugin on install
  B-->>A: bifrost-<skill>  installed
```

## Try it

**Add the MCP** (already wired for the three coding agents — Claude Code shown):
```
# ~/.claude.json → mcpServers.bifrost = { type:"http", url:"https://bifrost.weyland.lab/mcp", headers:{ "x-bf-vk": "<coding-agents VK>" } }
```

**Add the skill marketplace and install one:**
```
claude plugin marketplace add https://bifrost.weyland.lab/api/skills/serve/claude-code/.claude-plugin/marketplace.json
claude plugin install bifrost-weyland-conventions@bifrost-skills
```
(Every skill installs as `bifrost-<name>` — e.g. `bifrost-deploy-via-argo`, `bifrost-systematic-debugging`, `bifrost-ct-bcg-matrix`.)

## v2.3.1 — the upgrade, and stranded MCP sessions now recover (B231, RUN 2026-10-19)

Bifrost moved v2.2.6 → **v2.3.1** after B212 tested 2.3 on throwaway instances
([concepts/bifrost-2-3-evaluation.md](../concepts/bifrost-2-3-evaluation.md)). Nothing changed for callers: the setup
lock, inference auth and the VK scoping behave as in v2.2.6 (the section below still applies). Run, in order:

- **Pre-upgrade backup** (the runbook's command, § Bifrost backup + restore: `kubectl -n weyland create job --from=cronjob/bifrost-backup bifrost-backup-manual-$(date +%s)`): `20261019T190603Z` —
  providers 22, VKs 6, MCP clients 10, prompts 280, skills 589. The rollback point, pinned outside the 7-day rotation
  since 2026-10-21 (`/backup/bifrost-pinned/20261019T190603Z`, runbook § Pinned backups).
- **Baseline on v2.2.6** (watchdog on demand): `Agent_Memory` and `Hugging_Face` **unhealthy**, `ping failed: … Missing
  session ID` — the morning reboot of rogueone had restarted Basic Memory and v2.2.6 kept the dead session (~10 h).
- **After the roll** (Argo, ~5 min): step 1 below → `version v2.3.1`, `no token 401 | wrong 403 | token 200`; the
  watchdog → `checked 10 MCP client(s): 0 alert(s) fired`; `scripts/bifrost-fleet-txn.py` → `TXN_OK`; prompts **280**,
  skills **589**; one `wl-default` call through LiteLLM (fallbacks off) → `ok`, served via `bifrost.weyland.svc:8080/v1`.
- **The negative case, recovered:** `systemctl --user restart basic-memory.service` on rogueone (the event that broke
  v2.2.6) → within 20 s the watchdog shows 0 alerts with **no Bifrost restart**, and an agent's `search_notes` through
  Bifrost answers.

**UAT on v2.3.1 (eyes on):** open `https://bifrost.weyland.lab` and sign in through Keycloak. Bifrost asks for the
**setup token** (once per browser session; paste `BIFROST_SETUP_TOKEN` from `scripts/.env`). The dashboard loads, and
**MCP Catalog** lists **10** clients, each healthy (green). The page footer or Settings shows **v2.3.1**.

## v2.2.6 — the setup lock, inference auth, owned settings (B202, 2026-10-09)

Bifrost moved from v1.6.7 to **v2.2.6**. Three things changed for callers: `/api` needs the setup token (dashboard auth
stays off), every inference call needs a virtual key, and `/metrics` is whitelisted so Prometheus can scrape it.
Flow: [flow-bifrost § Who authenticates how](../diagrams/flow-bifrost.md). Runbook: [mcp-gateway.md](../runbooks/mcp-gateway.md) § Bifrost setup token.

### UI walkthrough (UAT — eyes on)

1. Open `https://bifrost.weyland.lab` and sign in through Keycloak.
2. Bifrost asks for the **setup token** (once per browser session). Paste `BIFROST_SETUP_TOKEN` from
   `/home/edwardmangini/IdeaProjects/weyland/scripts/.env`. Confirm the dashboard loads; a wrong value is refused.
3. **Setup checklist** (bottom right, or the bell): confirm **Restrict CORS origins** and **Enforce auth on inference**
   are ticked and **Add a provider key** is done. **Set up dashboard auth** stays open by decision (the setup token);
   after "I accept the risk - hide for everyone" the checklist no longer shows.
4. **Prompt Repository** shows ~280 prompts (folder `loop-library` has 11); **Skills** ~589; **MCP clients** lists 10,
   each **healthy** (v2's word for v1's "connected").
5. **Observability → Logs**: the newest rows carry the virtual key `realm-llm` (LiteLLM's hosted lanes).

### CLI walkthrough (the test)

Each command runs on rogueone; the token and the key are read inside the pods, never printed.

**1. Version and the setup lock** — expect `version v2.3.1` (v2.2.6 until 2026-10-19), then `401`, `403`, `200`:

[rogueone]
```
kubectl -n weyland exec deploy/weyland-guard -- python -c "import os,httpx;U='http://bifrost.weyland.svc.cluster.local:8080';g=lambda p,h={}:httpx.get(U+p,headers=h).status_code;print('version',httpx.get(U+'/api/version').json());print('no token',g('/api/config'),'| wrong',g('/api/config',{'X-Bifrost-Setup-Token':'wrong'}),'| token',g('/api/config',{'X-Bifrost-Setup-Token':os.environ['BIFROST_SETUP_TOKEN']}))"
```

**2. Inference needs a virtual key** — expect `no key: 401 | realm-llm key: 200` (`GET /v1/models` costs nothing):

[rogueone]
```
kubectl -n weyland exec deploy/litellm -- python -c "import os,urllib.request as u,urllib.error as e
def c(h):
  try: return u.urlopen(u.Request('http://bifrost.weyland.svc.cluster.local:8080/v1/models',headers=h),timeout=15).status
  except e.HTTPError as x: return x.code
print('no key:',c({}),'| realm-llm key:',c({'x-bf-vk':os.environ['BIFROST_REALM_VK']}))"
```

**3. `/metrics` is public and the owned settings hold** — expect `metrics 200`, then `unchanged: client_config already as owned`:

[rogueone]
```
kubectl -n weyland exec deploy/weyland-guard -- python -c "import httpx;print('metrics',httpx.get('http://bifrost.weyland.svc.cluster.local:8080/metrics').status_code)" && kubectl -n weyland exec -i deploy/weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_client_config.py
```

**4. The repositories and the MCP fleet survived the migration** — expect prompts ~280, skills ~589 (the skills list pages at 100, so this reads `total`), MCP 10 all `healthy`:

[rogueone]
```
kubectl -n weyland exec deploy/weyland-guard -- python -c "import os,httpx,collections;c=httpx.Client(base_url='http://bifrost.weyland.svc.cluster.local:8080',headers={'X-Bifrost-Setup-Token':os.environ['BIFROST_SETUP_TOKEN']},timeout=30);p=c.get('/api/prompt-repo/prompts',params={'limit':1000}).json().get('prompts') or [];s=c.get('/api/skills').json().get('total');m=c.get('/api/mcp/clients').json();m=m.get('clients') if isinstance(m,dict) else m;print('prompts',len(p),'| skills',s,'| mcp',dict(collections.Counter(x.get('state') for x in m or [])))"
```

**5. A real call through the gateway chain** — expect `wl-default 200 … bifrost…/v1 fallbacks: 0`:

[rogueone]
```
kubectl -n weyland exec deploy/litellm -- python -c "import os,httpx;r=httpx.post('http://localhost:4000/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ['LITELLM_MASTER_KEY']},json={'model':'wl-default','messages':[{'role':'user','content':'one word'}],'max_tokens':256},timeout=80);print('wl-default',r.status_code,r.headers.get('x-litellm-model-api-base'),'fallbacks:',r.headers.get('x-litellm-attempted-fallbacks'))"
```

Read-only apart from step 3's no-op re-run and step 5's one free-lane call; nothing to tear down.

### Key scoping through the API, and the MCP watchdog (B203, 2026-10-09)

**6. Each key's MCP grants match git** — expect `coding-agents: unchanged (8 client(s))`, `operator: unchanged (3 client(s))`,
`chat-eval: unchanged (0 client(s))`. A change applies live (no Bifrost restart since v2.2.6):

[rogueone]
```
kubectl -n weyland exec -i deploy/weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_vk_mcp.py
```

**7. The watchdog sees every client healthy** — expect `checked 10 MCP client(s): 0 alert(s) fired`; then the drill
(runbooks/mcp-gateway.md § MCP watchdog) sends exactly one Telegram message starting `DRILL`:

[rogueone]
```
kubectl -n weyland create job bifrost-mcp-watchdog-now --from=cronjob/bifrost-mcp-watchdog && kubectl -n weyland wait --for=condition=complete job/bifrost-mcp-watchdog-now --timeout=180s; kubectl -n weyland logs job/bifrost-mcp-watchdog-now; kubectl -n weyland delete job bifrost-mcp-watchdog-now
```
The drill (one labelled alert for a healthy client, so it proves the path to Telegram):
```
kubectl -n weyland create job bifrost-mcp-watchdog-drill --from=cronjob/bifrost-mcp-watchdog --dry-run=client -o json | python3 -c "import json,sys;j=json.load(sys.stdin);c=j['spec']['template']['spec']['containers'][0];c['env']+=[{'name':'DRILL_CLIENT','value':'Context7'}];print(json.dumps(j))" | kubectl create -f - && kubectl -n weyland wait --for=condition=complete job/bifrost-mcp-watchdog-drill --timeout=180s; kubectl -n weyland logs job/bifrost-mcp-watchdog-drill; kubectl -n weyland delete job bifrost-mcp-watchdog-drill
```
**The failing case — no token is exit 2, never "0 alerts":**
```
kubectl -n weyland create job bifrost-mcp-watchdog-notoken --from=cronjob/bifrost-mcp-watchdog --dry-run=client -o json | python3 -c "import json,sys;j=json.load(sys.stdin);s=j['spec'];s['backoffLimit']=0;c=s['template']['spec']['containers'][0];c['env']=[e for e in c['env'] if e['name']!='BIFROST_SETUP_TOKEN']+[{'name':'BIFROST_SETUP_TOKEN','value':''}];print(json.dumps(j))" | kubectl create -f - && kubectl -n weyland wait --for=condition=failed job/bifrost-mcp-watchdog-notoken --timeout=180s; kubectl -n weyland logs job/bifrost-mcp-watchdog-notoken; kubectl -n weyland delete job bifrost-mcp-watchdog-notoken
```
**RUN 2026-10-21:** run now → `checked 10 MCP client(s): 0 alert(s) fired`; drill → `ALERT BifrostMCPClientUnhealthy
client='Context7' :: DRILL — …` and `1 alert(s) fired`; no token → `cannot check Bifrost MCP clients: missing
BIFROST_SETUP_TOKEN/--token`, container exit **2**, Job Failed (deleted at once, so no `KubeJobFailed`).

**UAT:** Telegram shows the `DRILL — Context7 …` message; Argo CD → app **bifrost** lists CronJob `bifrost-mcp-watchdog`
(`50 3 * * *`, America/New_York). Teardown: the commands delete their Jobs; the drill alert resolves on its own.

## The registrars publish what changed, and only that (B204, RUN 2026-10-21)

The prompt and skill registrars are git's copy of the two repositories. A re-run must write nothing when git and
Bifrost agree. A skill changed in git publishes one new version (`PUT /api/skills/{id}`, one patch above
`latest_version`). A prompt edited outside git (Langfuse, the UI) is a `CONFLICT`: reported, never overwritten. Any
failed read or write is exit 1. Flow: [diagrams/flow-prompt-federation.md](../diagrams/flow-prompt-federation.md)
§ The registrars' decisions.

**1. The live re-run writes nothing** (both idempotent; safe to run any time):
```
kubectl -n weyland exec -i deploy/weyland-guard -- python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster/scripts/register_bifrost_skills.py
kubectl -n weyland exec -i deploy/weyland-guard -- python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster/scripts/register_bifrost_prompts.py
```
RUN 2026-10-21: `0 created, 0 updated, 25 unchanged, 0 failed. 25 skills total.` and `0 created, 0 updated, 101
unchanged, 0 conflict, 0 failed. 101 prompts across 12 folders.`, both exit 0.

**2. The update, conflict and failure paths.** These are shown against stubbed Bifrost responses, not live, on
purpose: a live one-byte change would publish a real new version of a skill agents install. The stubs carry the
response shapes observed live (`GET /api/skills/{id}` holds the real body; `PUT` on an existing version is 409):
```
cd /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/services/weyland-dagster/scripts && docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD":"$PWD":ro -w "$PWD" python:3.12-slim sh -c 'pip install -q --user pytest httpx >/dev/null 2>&1; python -m pytest -p no:cacheprovider -rA tests/test_register_bifrost_prompts.py tests/test_bifrost_skills.py'
```
RUN 2026-10-21: 37 passed, among them `test_changed_body_sends_exactly_one_put_with_git_body_and_bumped_patch`
(`1.1.0` → `1.1.1`), `test_equal_skills_send_no_write_even_though_the_list_bodies_are_empty`,
`test_a_failed_put_counts_as_failed[409|500|503]`, `test_main_prints_the_summary_and_exits_1_on_failure`,
`test_a_native_edit_reconciled_from_langfuse_is_a_conflict_never_overwritten` and
`test_unreachable_or_unauthorized_list_raises_before_any_write`.

**UAT:** Bifrost → Skills: open any lab skill and check its Versions list; after step 1 no new version appears.

## The picture

```likec4-view
bifrostEdge
```

**A PVC loss restores from the nightly `bifrost-backup`** (B202; [sqlite-backups.md](sqlite-backups.md), runbook
§ Bifrost backup + restore). Without a backup, rebuild in order: `register_bifrost_client_config.py` →
`register_bifrost_mcp_clients.py` → `register_bifrost_vk_mcp.py` (no restart since B203) → `register_bifrost_prompts.py` /
`register_aidlc_prompts.py` → `register_bifrost_skills.py` → `register_aidlc_kb_skills.py`
(`register_aidlc_skills.py` is retired; its 52 stage skills are only in the backup). Full order in
[runbooks/mcp-gateway.md](../runbooks/mcp-gateway.md).
