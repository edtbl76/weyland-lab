# Demo — Pyroscope continuous profiling (B111; demo by B239)

Pyroscope (ns `monitoring`, monolithic, `:4040`) stores CPU, memory, goroutine, mutex and block profiles. Grafana
Alloy pprof-scrapes Tempo and Loki into it, and Grafana reads it as the `pyroscope` datasource (Profiles Drilldown).
RUN 2026-11-08. Operate: [runbooks/observability.md](../runbooks/observability.md).

## CLI walkthrough

**1. It is up** (read-only, through the API server's service proxy: a single API call, not a port-forward):

```bash
kubectl get --raw '/api/v1/namespaces/monitoring/services/pyroscope:4040/proxy/ready'
```

Seen: `ready`.

**2. It holds profiles.** Through Grafana's Pyroscope datasource (the lab's Grafana MCP tools, `uid pyroscope`), over
the last hour:
- `service_name` values: `loki`, `pyroscope`, `tempo`;
- 12 profile types: `process_cpu` (cpu, samples), `memory` (alloc and in-use, objects and space), `goroutine(s)`,
  `mutex` and `block` (contentions and delay).

That matches the design: Alloy scrapes Tempo and Loki, and Pyroscope profiles itself.

**Negative case.** The legacy HTTP endpoint `/pyroscope/label-values?label=service_name` answers `null` on this
version even with a time range, so it is not a valid check. Use Grafana (above, or the UI below).

## UI walkthrough (eyes-on)

Grafana → Explore → **Profiles Drilldown** (or Explore with the `pyroscope` datasource):
- the service list shows `loki`, `tempo`, `pyroscope`;
- pick `tempo` with `process_cpu` and a flame graph renders for the last hour.

## Cleanup

None: reads only.
