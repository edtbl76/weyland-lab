# Demo — OpenCost on-prem cost allocation (B55; demo and pricing fix by B239)

OpenCost (ns `opencost`) prices the k8s workloads with a custom on-prem model and allocates cost per namespace. RUN
2026-11-08, before and after the pricing fix. Operate: [runbooks/opencost.md](../runbooks/opencost.md).

## CLI walkthrough

**1. The prices OpenCost actually uses:**

```bash
kubectl -n opencost exec deploy/opencost -c opencost -- sh -c 'grep -o "\"CPU\":\"[^\"]*\",\"spotCPU\":\"[^\"]*\",\"RAM\":\"[^\"]*\"" /tmp/custom-config/default.json'
```

- Before: `"CPU":"0.000001","spotCPU":"0.000001","RAM":"0"`. The ConfigMap held hourly rates; OpenCost reads them as
  monthly and divides by 730.
- After (rates written monthly, synced by Argo): `"CPU":"0.001029","spotCPU":"0.001029","RAM":"0.000343"`.

**2. Allocation by namespace** (read-only, through the API server's service proxy):

```bash
kubectl get --raw '/api/v1/namespaces/opencost/services/opencost:9003/proxy/allocation/compute?window=1h&aggregate=namespace&includeIdle=true' | python3 -c "import json,sys; a=json.load(sys.stdin)['data'][0]; t=sum(v['totalCost'] for v in a.values()); print(f'last hour \${t:.5f} -> \${t*730:.2f}/month')"
```

- Before: every namespace `$0.0000`.
- After: `last hour $0.02458 -> $17.94/month`, with `weyland` and `data-mesh` the largest. That is in line with the
  model's ~$15/month for mother's k3s slice.

**Negative case.** The check in step 1 is what tells the two states apart: `0.000001` / `0` means the rates were
written hourly. The runbook names that failure.

**The exported metric needs a restart.** Right after the fix, the Prometheus metric `node_cpu_hourly_cost` still read
`0.000001` (the allocation API was already correct). After `kubectl -n opencost rollout restart deploy/opencost` it
reads 0.00103 per core-hour, and `node_ram_hourly_cost` 0.000343 per GB-hour.

## UI walkthrough

<https://opencost.weyland.lab> (forward-auth): the Allocations view, last 24 hours, by namespace, shows non-zero costs
from the fix onward.

## Cleanup

None: reads only.
