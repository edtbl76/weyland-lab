# Demo — STUD.io code-review stack (B118)

The lab-wide AI code-review stack runs on the **public `edtbl76/stud.io`** repo (the B118 parity half of B106).
Because the repo is public, the review Apps are GitHub-hosted and event-driven — no LAN reach needed. This demo
**verifies the live state** (read-only). Validated 2026-08-19 on **PR #121**: DeepSource (7 analyzers), CodeScene
(project 78184), and Sourcery all posting passing checks; CodeRabbit + Qodo reviewing in the conversation.

## Sequence diagram

See [../diagrams/flow-studio-code-review.md](../diagrams/flow-studio-code-review.md).

## Prerequisites
- `edtbl76/stud.io` is **public** (free OSS/public tier for every App).
- Committed configs on the STUD.io repo: `.deepsource.toml` · `.coderabbit.yaml` · `.pr_agent.toml` · `.mcp.json`.
- The GitHub Apps installed on the repo: DeepSource, CodeScene (project 78184), Sourcery, CodeRabbit, Qodo.
  (Greptile is **not** installed yet — see the STUD.io repo `docs/arch/code-review-stack.md`.)

## UI walkthrough (eyes-on UAT)
1. **GitHub** → `edtbl76/stud.io` → **Pull requests** → an open/recent PR (e.g. #121) → the **Checks** tab.
   **UAT — confirm** these check-runs are present and green: `DeepSource: Python/JavaScript/Go/SQL/Secrets/Shell/Docker`,
   `CodeScene Code Health Review`, `Sourcery review`. Click one DeepSource check → its `app.deepsource.com/gh/edtbl76/stud.io`
   run page renders; click the CodeScene check → its `codescene.io/projects/78184` delta page renders.
2. In the same PR's **Conversation**, confirm **CodeRabbit** (summary + line comments) and **Qodo Merge**
   (`/describe` + `/review` + `/improve`) have posted.
3. **Port** → **Catalog → `component`** → the code-review entities (`deepsource`, `codescene`, `sourcery`,
   `coderabbit`, `greptile`, `pr-agent`). **UAT — confirm** each description reflects both repos (e.g. DeepSource:
   "Live on weyland-lab + stud.io (7 analyzers)").

## CLI walkthrough
[rogueone] Confirm the stack posted on the latest STUD.io PR:
```
gh pr checks "$(gh pr list --repo edtbl76/stud.io --state all --limit 1 --json number -q '.[0].number')" --repo edtbl76/stud.io
```
[rogueone] List the check-run apps + conclusions on the default branch's latest reviewed commit (any recent PR head):
```
gh api repos/edtbl76/stud.io/commits/main/check-runs --jq '.check_runs[] | {name, app: .app.slug, conclusion}'
```
[rogueone] Confirm the Port component catalog reflects both repos (client-creds in `scripts/.env`; secret never printed):
```
cd /home/edwardmangini/IdeaProjects/weyland; set -a; . ./scripts/.env; set +a; TOKEN=$(curl -sf -X POST https://api.getport.io/v1/auth/access_token -H "Content-Type: application/json" -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])'); curl -s "https://api.getport.io/v1/blueprints/component/entities/deepsource" -H "Authorization: Bearer $TOKEN" | python3 -c 'import sys,json;print(json.load(sys.stdin)["entity"]["properties"]["description"])'
```

## Expected result
- Every open STUD.io PR carries DeepSource (7) + CodeScene + Sourcery checks and CodeRabbit/Qodo reviews.
- The Port `component` entities describe the tools as covering **weyland-lab + stud.io**.
- The one gap is **Greptile** (App not installed on `edtbl76/stud.io`).

## Cleanup / teardown
Read-only — inspects existing PR checks + Port entities; creates nothing.
