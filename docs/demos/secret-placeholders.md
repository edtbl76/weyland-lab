# Demo — the sealed placeholder and its guard (B147)

A credential that was perfectly restorable and authenticated to nothing, the fix, and the check that stops
it recurring. **Executed + eyes-on 2026-08-25** (✅) — every output below is from a real run.

- **runbook:** [runbooks/secrets.md](../runbooks/secrets.md) § Rotate / re-seal · § The placeholder guard
- **Flow:** [diagrams/flow-secret-placeholders.md](../diagrams/flow-secret-placeholders.md)

**What it was:** `weyland/port-creds` held the literal strings `YOUR_ID` / `YOUR_SECRET` for **63 days**.
Sealed, committed, Argo-applied, `DATA 2`, mounted by a running pod — every signal green, and it returned
HTTP 401, so the B62 AI-Dev Usage pipeline never wrote a single entity.

## UI walkthrough (eyes-on)

1. **Port → Catalog → AI Sessions** — `https://app.port.io` → Catalog → `ai_session`.
   **UAT — confirm:**
   - **62 entities**, not 37. The 37 were hand-seeded on 2026-06-23 and never grew.
   - Open any entity added today → **Created by** is `piTwgQRQbFmLWMvgpyrmw7RfLmTVwSRm` (the integration's
     own client), **not** a `user_…` id. That distinction *is* the acceptance: a human can create these
     by hand, so a non-zero count proves nothing on its own.
   - Sort by updated — the newest timestamp is today. Before this it was `2026-06-23T20:21:43Z`.
2. **Port → Builder → `ai_user`** — **0 entities, deliberately.** Kept as a provisioned extension point:
   the operator expects to add a second person (their son) to the lab, at which point per-user AI
   attribution becomes meaningful. Codified in `tofu/port/b137_blueprints.tf`, so it costs nothing to
   hold. **UAT:** confirm it still exists and is empty — if it ever gains entities without the feeder
   changing, something else is writing to it.
3. **Argo → `sealed-secrets-manifests`** — **UAT:** Synced/Healthy on a revision that contains the
   re-sealed `weyland__port-creds.yaml`. If the app is Synced to an older revision, the cluster is being
   actively restored *to* the broken credential — see step 3 of the CLI walkthrough.

## CLI walkthrough (the test — RUN against live infra)

**1. The guard, assert mode.**

```
bash scripts/check-secret-placeholders.sh
```

```
OK — 56 allow-listed secret(s), no placeholder or empty values.
```

Before the fix, the same command produced:

```
  ❌ weyland/port-creds key=PORT_CLIENT_ID looks like a PLACEHOLDER: 'YOUR_ID'
❌ 1 placeholder value(s) and 0 unreadable secret(s) across 56 allow-listed secrets.
```

**2. Per-key verdicts, including documented exceptions.**

```
bash scripts/check-secret-placeholders.sh --list
```

```
  ok  weyland/aidlc-kb-minio-secret              access_key                   (5 chars)
  ok  weyland/apisix-secret                      APISIX_ADMIN_KEY             (64 chars)
  ok  weyland/cron-freshness-woodpecker          token                        (120 chars)
  ...
  ACCEPTED data-mesh/trino-metrics-auth           password                     (documented exception)
listed 56 secret(s).
```

The `ACCEPTED` row is Trino's metrics password, which the endpoint genuinely ignores
(`k8s/data-mesh/trino.yaml:154`). Verifying *that* claim is what surfaced **B148** — Trino exports no
metrics to Prometheus at all.

**3. Prove it still catches the real thing.** Feed it a fixture with both a placeholder and the accepted
exception — the exception must be excused and the placeholder must still fail:

```
M=/tmp/ph-demo && mkdir -p "$M" && printf 'SECRETS=(\n  weyland/port-creds\n  data-mesh/trino-metrics-auth\n)\n' > "$M/seal.sh" && python3 -c "
import json
json.dump({'weyland/port-creds':{'PORT_CLIENT_ID':'YOUR_ID'},
           'data-mesh/trino-metrics-auth':{'password':'','username':'prometheus'}}, open('$M/snap.json','w'))
" && SEAL_SCRIPT="$M/seal.sh" SECRET_SNAPSHOT_JSON="$M/snap.json" bash scripts/check-secret-placeholders.sh; echo "EXIT=$?"
```

```
  ❌ weyland/port-creds key=PORT_CLIENT_ID looks like a PLACEHOLDER: 'YOUR_ID'
❌ 1 placeholder value(s) and 0 unreadable secret(s) across 2 allow-listed secrets.
EXIT=1
```

One flagged, one excused. A guard whose accept-list swallows everything is worse than no guard.

**4. The fix, verified the only way that means anything.** Decode the **stored** value and authenticate
with it — never `DATA n`:

```
kubectl -n weyland get secret port-creds -o json | python3 -c "
import sys,json,base64,urllib.request
d=json.load(sys.stdin)['data']
v={k:base64.b64decode(x).decode() for k,x in d.items()}
print('  lengths:', {k:len(x) for k,x in v.items()})
b=json.dumps({'clientId':v['PORT_CLIENT_ID'],'clientSecret':v['PORT_CLIENT_SECRET']}).encode()
r=urllib.request.Request('https://api.port.io/v1/auth/access_token',b,{'Content-Type':'application/json'})
print('  auth -> HTTP 200, token len', len(json.loads(urllib.request.urlopen(r).read())['accessToken']))
"
```

```
  lengths: {'PORT_CLIENT_ID': 32, 'PORT_CLIENT_SECRET': 64}     (was 7 / 11)
  auth -> HTTP 200, token len 561                               (was 401)
```

**5. The pipeline itself — the real acceptance.** Restart the consumer **after** the Argo sync
(`secretKeyRef` injects at pod start), then materialize:

```
kubectl -n weyland rollout restart deploy/dagster-user-code && kubectl -n weyland rollout status deploy/dagster-user-code --timeout=240s
POD=$(kubectl -n weyland get pod -o name | grep dagster-user-code | head -1)
kubectl -n weyland exec "$POD" -- python3 -c "
from dagster import materialize
import weyland_pipeline.assets.ai_session as m
print('SUCCESS:', materialize([m.ai_session_ingest]).success)"
```

```
ai_session: read 62 session summaries from MinIO bucket 'ai-sessions'
ai_session summary: {'sessions_read': 62, 'upserted': 62, 'errors': 0,
                     'by_project': {'weyland-lab': 20, 'stud.io': 15,
                                    'emangini-tailwind': 21, 'midi_real_book': 6}}
SUCCESS: True
```

**6. Assert Port received them, written by the INTEGRATION.**

```
POD=$(kubectl -n weyland get pod -o name | grep dagster-user-code | head -1)
kubectl -n weyland exec "$POD" -- python3 -c "
import os,json,urllib.request,collections
b=json.dumps({'clientId':os.environ['PORT_CLIENT_ID'],'clientSecret':os.environ['PORT_CLIENT_SECRET']}).encode()
t=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.port.io/v1/auth/access_token',b,{'Content-Type':'application/json'})).read())['accessToken']
e=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.port.io/v1/blueprints/ai_session/entities',headers={'Authorization':'Bearer '+t})).read())['entities']
print(' entities:',len(e))
print(' createdBy:',dict(collections.Counter(x.get('createdBy','?') for x in e)))"
```

```
 entities: 62                                                    (was 37)
 createdBy: {'user_LsOqrzfUpyETjoWR': 37,
             'piTwgQRQbFmLWMvgpyrmw7RfLmTVwSRm': 25}             (the integration)
```

**7. The test suite.**

```
docker run --rm -v "$PWD:/code:ro" -w /code --entrypoint sh bats/bats:latest -c 'apk add --no-cache python3 >/dev/null 2>&1; bats scripts/tests/secret-placeholders.bats'
```

Expect **20 ok**, including the cases that broke the first implementation: a multi-line config blob, a PEM
private key, and the `clickhouse-users` XML document.

## Teardown

**Steps 1, 2, 4, 6 and 7 are read-only.** Step 3 writes a throwaway fixture — `rm -rf /tmp/ph-demo`.

**Step 5 is idempotent but not read-only**: it upserts 62 `ai_session` entities into Port. Re-running
overwrites the same identifiers rather than duplicating, and the entities are the real product of the
pipeline — there is nothing to clean up, and deleting them would undo the fix this demo exists to prove.
