# Demo — Port IaC coverage (B137)

Port's schema under OpenTofu, and the guard that proves it — because `tofu plan` structurally cannot.
**Executed + eyes-on 2026-08-25** (✅). Every output below was captured from a live run, not written from memory.

- **arch:** §6 (OpenTofu row) · **runbook:** [runbooks/port.md](../runbooks/port.md) § What is deliberately UI-managed · [runbooks/opentofu.md](../runbooks/opentofu.md) § Port lane
- **Flow:** [diagrams/flow-port-iac-coverage.md](../diagrams/flow-port-iac-coverage.md)

**The thing to understand before clicking anything:** `tofu plan` compares the code to the resources **tofu knows
about**. A blueprint created in Port's UI is not one of them, so "No changes." and "half the catalog is
unversioned" are byte-identical outputs. That is how this org reached 51 live blueprints against 13 codified over
two months with a clean plan the whole time, discovered by accident from an unrelated scan.

## UI walkthrough (eyes-on)

1. **Port → Builder → Data model** — `https://app.port.io` → gear icon → **Builder**.
   **UAT — confirm:**
   - **51 blueprints** are listed. `service`, `workload`, `deployment`, `environment`, `organization`, `backup`,
     `ai_session`, `ai_user` are all present — these eight existed **only here** until B137 and are now in
     `tofu/port/b137_blueprints.tf`.
   - Open **`component`** → **Relations** → `Repo / Service (DORA)` targets **`service`**. Before B137 that target
     existed only in Port, so reading the IaC alone made the relation look broken.
   - Open **`k8s_workload`** → **Entities** → the list now contains **CronJob** rows (`lancedb-sync`, `pg-backup`,
     `minio-backup`, `code-scan-suite`, `cron-freshness-check`, …). There were **zero** before 2026-08-25 — the
     mapping dereferenced `.spec.template.spec` on a CronJob, whose pod template is at
     `.spec.jobTemplate.spec.template.spec`, so no entity was ever built and **nothing reported it**.
   - Still on `k8s_workload` → sort by **isHealthy**. A handful read **Unhealthy**. Those are genuinely `Failed`
     Jobs in Kubernetes. Until B137 every Job read `Healthy`, because the copied expression compared
     `.spec.replicas` to `.status.availableReplicas` and a Job has neither field — `null == null`.
2. **Port → Scorecards** — Builder → `service` → **Scorecards**: `delivery_performance` (14 rules),
   `production_readiness` (10), `quality_maturity` (5), `reliability_health` (5), `dora_lead_time` (3),
   `dora_deploy_freq` (3). **UAT:** open `delivery_performance` and confirm the rules render with their levels —
   44 rules across all 8 scorecards had no source of truth anywhere before B137; losing the org lost all of it.
3. **Port → Data sources** — the **4 integrations**: `github-weyland` (repository **+ pull-request**),
   `weyland-cluster` (13 kinds), `linear`, `sonarqube-direct`. **UAT:** open `weyland-cluster` → its mapping →
   confirm `batch/v1/jobs` and `batch/v1/cronjobs` are present and that the `v1/pods` non-ReplicaSet resource's
   `k8s_workload` relation begins `if ((.metadata.ownerReferences // []) | length) > 0 then …`. Without that guard
   Woodpecker's owner-less step pods produced **176 audit failures in a single nightly run**.

## CLI walkthrough (the test — RUN against live infra)

**1. The guard, assert mode.** This is the whole point: it asks what is LIVE that the code does not describe.

```
bash scripts/check-port-iac-coverage.sh
```

```
KIND             LIVE   CODE  EXCUSED  MISSING
blueprints         51     21       30        0
scorecards          8      8        0        0
integrations        4      4        0        0

ℹ  rebuild order: these codified relations target integration-owned blueprints, so the
   integrations must be installed BEFORE a from-scratch `tofu apply`:
     component.k8sWorkload -> k8s_workload
     deployment.github_pull_request -> githubPullRequest
     environment.k8s_cluster -> k8s_cluster
     service.sonar_project -> sonarQubeProject
     service.github_repository -> githubRepository
     workload.k8s_workload -> k8s_workload

OK -- every live blueprint, scorecard and integration is either codified or documented as UI-managed.
```

Exit `0`. The rebuild-order block prints on **every** run on purpose — it is the from-scratch restore order, and an
unstated order is one somebody rediscovers mid-restore.

**2. The documented decision, in full.** `--list` prints the three excuse groups and exits 0 without asserting.

```
bash scripts/check-port-iac-coverage.sh --list
```

Expect **11** Port system blueprints (`_ai_agent`, `_ai_conversation`, `_ai_invocations`, `_ai_plan`,
`_mcp_server`, `_rule`, `_rule_result`, `_scorecard`, `_team`, `_user`, `_workflow`), **15** integration-owned
(`githubPullRequest`, `githubRepository`, 2×`istio_*`, 6×`k8s_*`, 3×`linear*`, 2×`sonarQube*`), and **4** dormant,
each printed with its reason. The integration-owned list is **derived from the live mappings**, not hardcoded — so
retiring an integration stops excusing its blueprints automatically, instead of leaving a dead exception behind.

**3. Prove it can actually fail — do not take the green on faith.** Hide the scorecards from a copy of the tree:

```
M=/tmp/port-iac-demo && mkdir -p "$M" && cp nodes/mother/lab/weyland-platform/tofu/port/*.tf "$M/" && mv "$M/b137_scorecards.tf" "$M/hidden.bak" && PORT_TF_DIR="$M" bash scripts/check-port-iac-coverage.sh; echo "EXIT=$?"
```

```
❌ live scorecards with NO definition in /tmp/port-iac-demo:
     service:delivery_performance
     service:dora_deploy_freq
     service:dora_lead_time
     service:production_readiness
     service:quality_maturity
     service:reliability_health
     sonarQubeProject:services_connected
     workload:availability
EXIT=1
```

**4. `tofu plan` — clean, and that proves less than it looks.**

```
cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && tofu plan
```

```
OpenTofu has compared your real infrastructure against your configuration and
found no differences, so no changes are needed.
```

Read step 3 again before trusting this line. A clean plan proves the code matches the code.

**5. What the code holds.**

```
cd nodes/mother/lab/weyland-platform/tofu/port && for t in port_blueprint port_scorecard port_integration port_action; do printf '%-18s %s\n' "$t" "$(grep -ch "^resource \"$t\"" *.tf | paste -sd+ | bc)"; done
```

```
port_blueprint     21
port_scorecard     8
port_integration   4
port_action        1
```

**6. Live assertions — the ones a plan can never make.**

```
cd nodes/mother/lab/weyland-platform/tofu/port && set -a && . ./.env && set +a && TOK=$(curl -sS -X POST https://api.port.io/v1/auth/access_token -H 'Content-Type: application/json' -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["accessToken"])') && curl -sS https://api.port.io/v1/blueprints/component -H "Authorization: Bearer $TOK" | python3 -c "import sys,json;r=json.load(sys.stdin)['blueprint']['relations']['service'];print('component.service ->',r['target'],'|',r.get('title'))" && curl -sS https://api.port.io/v1/blueprints/k8s_workload/entities -H "Authorization: Bearer $TOK" | python3 -c "
import sys,json,collections
e=json.load(sys.stdin)['entities']
def k(i):
    for t in ('-CronJob-','-Job-','-Deployment-','-StatefulSet-','-DaemonSet-'):
        if t in i: return t.strip('-')
    return '?'
print('k8s_workload by kind:', dict(collections.Counter(k(x['identifier']) for x in e)))"
```

```
component.service -> service | Repo / Service (DORA)
k8s_workload by kind: {'Deployment': 113, 'CronJob': 10, 'DaemonSet': 2, 'Job': 27, 'StatefulSet': 14}
```

The `CronJob: 10` is the acceptance for the mapping fix — it was `0`, and the 10 matches exactly what
`bash scripts/check-cron-freshness-budgets.sh` counts in the cluster.

**7. The test suite behind the guard.**

```
docker run --rm -v "$PWD:/code:ro" -w /code --entrypoint sh bats/bats:latest -c 'apk add --no-cache python3 py3-yaml >/dev/null 2>&1; bats scripts/tests/port-iac-coverage.bats'
```

Expect `18` tests, all `ok`. Each was verified by mutation — breaking the guard must break a test, and on the first
pass one of them did **not** (the nested-identifier fixture put its decoy after the real value, so deleting the
parser's depth check kept it green). Fixed and re-mutated.

## Teardown

**Steps 1, 2, 4, 5, 6, 7 are read-only** — they issue `GET`s and parse local files; nothing is created in Port.

Step 3 writes a throwaway copy of the `.tf` files. Remove it:

```
rm -rf /tmp/port-iac-demo
```
