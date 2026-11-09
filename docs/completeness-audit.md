# Completeness / Gap Audit — 2026-06-26

Multi-agent audit (9 domain auditors + synthesis) of the weyland platform for **completeness gaps** —
artifacts that "run once" but aren't operationally complete. Graded each against 5 gap types:
**trigger · lineage · gitops (reproducibility) · monitoring · docs**, and cross-checked the backlog's
"✅ done" claims. 56 raw gaps → 42 deduped.

- **data-mesh-now: 14** (8 high / 4 medium / 2 low) — solved as part of B1 (this register's top section).
- **platform-later: 28** (9 high / 14 medium / 5 low) — **B69**, cleared immediately after B1.

---

## 2026-11-07 — Docs, diagrams, runbooks and maps audit (B239, EMA-338) — pass 1 findings

**Why now.** `lab-ask` (B187) answered "I want to see why a Dagster run failed" with "not in the index": there is no
Dagster runbook. That raised the question of what else is missing.

**Method.** The inventory is the B82 application registry (`applications.yaml`): 61 deployed apps plus 41 stores
and plumbing entries, which `check-app-registry.sh` keeps complete against all 83 Argo apps. For each system:
- runbook coverage, and whether its commands answer five operator questions (health, logs, why did it fail, restart,
  restore), measured on the runbook command roster (`scripts/lab-commands.py`, 885 commands);
- demo ledger rows, diagrams, and maps;
- runbook hygiene: host labels, dead paths, retired systems.

The scripts produce signals only. **Every finding below was checked by hand**, and the false positives are listed at
the end. Baseline: the full repo-guards suite was green the same day (`ALL_GUARDS_OK`).

### Tier 1 — core systems you cannot operate from the docs

1. **Dagster has no runbook.** It runs most of the lab's scheduled work. Its commands are scattered: the freshness
   watchdog is in `observability.md`, and per-job reruns are in `linear-backup.md` and others. Nothing says how to
   find out why a run failed.
   **RESOLVED 2026-11-08** by the new `docs/runbooks/dagster.md` and `flow-dagster-runs.md`, with demo row 122. The
   read-only diagnostic `scripts/lib/dagster_runs.py` covers health, failed runs and why they failed (17 tests).
   `lab-ask` now answers the question.
15. **A daily job had been failing for 9 days with no incident, found by the new runbook's demo (2026-11-08).**
    `datahub_catalog_emit_job` failed every night from at least 2026-11-04, always at its 30-minute
    `dagster/max_runtime`, cut off in a different step each time (`emit_tag_assignments_op`,
    `emit_source_terms_op`). Its last success was 824,247 s ago. The watchdog fired `DagsterJobFailed` and
    `DagsterJobStale` correctly, but at warning severity, and U14 files Linear incidents for critical alerts only. So
    the alerting worked, and the routing let it sit.
    **Diagnosis (2026-11-08).** Not a sudden break:
    - the job ran 23-31.5 min every night from 2026-10-02 against the 30-min cap, and failed whenever it ran long
      (10-04, 10-09..11, 10-13, 10-22..23), then every night from 10-31;
    - every large step slowed by about the same ~20% (applications 4.6 to 5.5 min, domains 4.3 to 5.4, structured
      properties 4.2 to 5.5);
    - it makes one synchronous DataHub write per aspect, 33 steps in sequence. It runs sequentially on purpose:
      parallel ops each re-imported ~1.1 GB of definitions and ran the pod out of memory;
    - DataHub reads are fast (GET median 4 ms), so the cost is the volume of synchronous writes.

    **Fix:** `dagster/max_runtime` raised 1800 to 4200, with the reason in `definitions.py`.
    `tests/test_job_runtime_limits.py` keeps the cap at least 2x the measured runtime (written red first; it also
    caught my first choice, 3600, as too small). A one-off run with a 4200 launch tag (`35c66452`, owner-launched)
    **succeeded in 33.2 min** on 2026-11-08. It would have been stopped under the old cap, and the catalog is current
    again. The watchdog's next run (19:30 UTC) read `status=SUCCESS last_success_age=582s` and fired 0 alerts. The
    nightly schedule has the new cap since the ship of `git-97855d2a` (2026-11-08, `ship-images.sh`, PR #316, all
    gates including FR-DRAIN, SMOKE and TXN). Dagster reports `dagster/max_runtime: 4200` for the job.

    **Follow-ups, both done on the owner's decisions (2026-11-08):**
    - **Faster.** Measurement showed reads, not writes, dominated: 11,823 datasets at 13 ms per `get_aspect`, about
      8 full passes. Each read loop now batch-prefetches with `get_entities` (`_AspectReader`, 3.6x faster with
      identical results on 200/200), and writes go in batches (`BatchingEmitter`, flushed by `_safe_emit` after every
      step; a structural test makes every caller flush). Shipped as `git-bc18e3c3`. Run `5d9ef454`: **7.0 min, down
      from 33.2**, all 33 steps SUCCESS, 0 warnings, slowest step 1.3 min (was 5.5).
    - **Louder.** `DagsterJobStale` escalates to critical one day past budget (see finding 16).
2. **weyland-tool-server has no runbook.** It is the core RAG/MCP API. All that exists is a perf baseline
   (`perf-baseline.md`) and one guardrails section.
   **RESOLVED 2026-11-08** by the new `docs/runbooks/tool-server.md`: health in one call, a retrieval check, guard
   counters, a symptom-to-cause table, logs and restart. Demo row 123. Writing it corrected an assumption: the
   NodePort has no NetworkPolicy (reads are open on the LAN), and the act routes are protected by the Istio policy
   `toolserver-act-gateway-only`.
16. **The tool-server has no service-specific down alert, found 2026-11-08 while writing its runbook.** Only the
    generic `TargetDown` and `KubePodNotReady` (both warning) cover it, although every agent act goes through it.
    That is a monitoring gap (Pillar 6). **FIXED 2026-11-08 (owner decision):** `ToolServerDown`, critical, 5 minutes
    of a failed or vanished scrape, in the tool-server's PrometheusRule, with four `promtool test rules` cases. Also on
    the owner's decision, `DagsterJobStale` now rises from warning to critical once a job is more than a day past
    its budget, so finding 15's nine silent days would have opened an incident on day one (two bats cases on the real
    numbers). The same runbook confirmed that
    natural-language retrieval misses documents that wording-matched search finds (the known B74 limit). It is
    documented in the runbook and is not a new item.
3. **The RAG streaming indexer has no runbook**: the `rag_stream_produce` producer, the `rag.chunks` topic, and five
   `rag-index-*` consumers that write the live index.
   **RESOLVED 2026-11-08** by `docs/runbooks/rag-stream.md`: topology, health (5 consumers, embedder, all five
   groups' lag, index size), symptom to cause, logs, launching the producer through Dagster, restart, and the
   destructive rebuild. Live state that day: every group `Stable`, lag 0; 10,540 points in `weyland_chunks`.
   Also corrected the producer's own description, which still said embedding ran "on the rogueone GPU service" (CPU
   since 2026-09-27).
17. **Docs run Dagster through the throwaway CLI, found 2026-11-08.** About 15 docs use `dagster asset materialize` or
    `dagster job execute` through `kubectl exec`. That runs on a throwaway in-memory instance (the pod has no
    `DAGSTER_HOME`), so the run is never recorded and the watchdog never sees it. This is fine for checking side
    effects, wrong where a run must count.
    - Fixed:
      - `demos/rag-stream.md` now launches through Dagster, and its `TODO: verify` on this exact question is
        answered;
      - `remote-training.md` and `model-gateway.md` now say the run is not recorded;
      - `linear-backup.md` already said so.
    - Left for B240, which runs these walkthroughs live: the E2E demos, two of which carry the same `TODO: verify`
      (`rag-e2e.md`, `streaming-cdc-e2e.md`, also `streaming.md`).
    - Acceptable as side-effect checks: the remaining demos.
4. **The DR catalog admits a gap.** `docs/dr.md` line 55: "Not yet catalogued (unverified coverage): Keycloak realm
   and users, Grafana state outside provisioned dashboards, the Uptime Kuma PVC, DataHub metadata, and each app's
   PVCs." This is Pillar 9 for those systems.
5. **The roster cannot answer restore questions.** `lab-ask` reads only `docs/runbooks/`, but the restore commands
   live in `docs/dr.md` (13 commands).

14. **Infrastructure-as-code drift, found while fixing Tier 2 on 2026-11-08.** `tofu/proxmox/` still declares
    OpenClaw (`openclaw.tf`, VM 100) and Ollama (`ollama.tf`, CT 102). Proxmox runs only mother (101) and whisper
    (103), checked through `pve_guest_info` in Prometheus. A `tofu apply` in that directory would try to recreate both
    retired guests. `opentofu.md` also still listed Hermes (CT 104) among the imported guests.
    **RESOLVED 2026-11-08:**
    - both `.tf` files were deleted, and the owner ran `tofu state rm` for both resources; the state now lists
      exactly mother and whisper;
    - `opentofu.md` now says what the lane really is: a record only, never applied, with guests managed by hand on
      weyland and no tofu token stored (the Port, GitHub and Keycloak lanes are the applied ones).

    Follow-up, small: the owner's `tofu plan` printed a bpg deprecation warning for `enabled = false` on a
    `network_device` in `mother.tf`. It is harmless today and will break on a future provider release.

18. **APISIX is deployed but unused, and its reseed path is broken (found 2026-11-08 writing its runbook).**
    - Zero requests on any of its five routes in 7 days, although `api.md` called it the "Active API/data-plane
      gateway" (corrected).
    - Its routes live only in etcd. The documented reseed (`deploy-apisix.sh` running `routes-init.sh` in the pod)
      cannot work: the image has no `curl`, and the script expects `APISIX_ADMIN_KEY` in `.env`, which no longer holds
      it.
    - There is no `dr.md` row for its etcd.

    Recorded in `runbooks/apisix.md`; the DR row is B240's.
    **Owner decision 2026-11-08: keep it (a lab gateway, idle but working) and fix the restore. FIXED:**
    - the routes are now defined in git, in `scripts/lib/apisix_routes.py` (8 tests);
    - `scripts/apisix-routes.py check` compares them with etcd (read-only, live: in sync, 6 records), and `restore`
      writes back only what drifted, through `etcdctl` in the etcd pod;
    - `deploy-apisix.sh` calls `restore`, and the broken `routes-init.sh` is removed.

    **The live write path was proven on 2026-11-08 with the owner's go:** route 5 was backed up and deleted (the
    gateway answered 404), `check` flagged it missing, `restore` wrote back exactly that record, and the route served
    200 on the first try. The other routes were unaffected.

### Tier 2 — stale docs that mislead

6. **Retired systems described as live.** Each of these was checked; it is a current-tense instruction or claim,
   not history:
   - `model-gateway.md` § 4 "Wire Hermes (CT 104)" (Hermes retired 2026-07-23);
   - `argocd.md`:33/38, which lists `keda` and `keda-http-add-on` among the Helm apps (KEDA retired 2026-08-22);
   - `datasets-hydration.md`:28 ("Always-on or KEDA'd?" with a `scaledobject` check);
   - `trino.md`:5 ("revisit KEDA");
   - the Hermes consumer and bot-owner claims in `unleash.md`:5-6, `model-serving-ollama.md`:29,
     `service-mesh-istio.md`:9, `glitchtip.md`:75, `cube.md`:27 and `uptime-kuma.md`:89-91;
   - demo row **E11**, whose agent walkthrough runs through Hermes.
7. **A removed component is still documented.** `k8s/lightdash/trino-noauth-proxy.yaml` was deleted 2026-10-23
   (B233), but `lightdash.md` and `write-surfaces.md` still describe Lightdash reaching Trino through it.
8. **Wrong paths: 1 real, 8 cleared on reading (corrected 2026-11-08 in pass 2).** The real one is `cube.md`'s
   follow-up, which still said Cube was `kubectl apply`-ed and not in Argo (it is: `subdir-apps.yaml`). It also
   listed MetricFlow as not done (it is). The other 8 read fine in context:
   - already described as gone: `flink.md` ("it was …") and `mcp-gateway.md` ("obsolete (removed)");
   - deliberately not in the repo: `uptime-kuma.md`'s `kuma-backup.json` is gitignored on purpose (it holds a dev
     password);
   - paths in other repos: `package.ts` (the upstream AI-DLC clone) and `docs/arch/…` (the STUD.io repo);
   - a hypothetical: `woodpecker-step-menu.md`'s `.woodpecker/build.yml`;
   - prose, not a path: "scripts/agents" in `code-intelligence.md`.

   Lesson for the path guard (Closing Gaps below): a path in prose is not a claim that it exists. The guard must
   check only paths written as instructions, or allow a marker.

### Tier 3 — coverage gaps in smaller systems

9. **No runbook:**
   - Realm of Agents (24 agents);
   - lakeFS (only a secret-escrow note);
   - APISIX;
   - Neo4j (sections in hydration and mesh docs only);
   - Kokoro (a demo only);
   - six thin UIs: OpenSearch Dashboards, Headlamp, NeoDash, A2A Inspector, Promptfoo, docs-site.
    **RESOLVED 2026-11-08 (batch D):** new runbooks `realm-of-agents.md`, `lakefs.md`, `apisix.md`, `kokoro.md`,
    `neo4j.md`, and `lab-uis.md` for the six UIs. Each was checked against the live system. The registry has **zero
    runbook gaps**: all 61 deployed apps name a runbook.
    - Writing them corrected `data-mesh-secrets.md`: the lakeFS `encrypt-key` "escrow NOW" warning was stale, since
      the key has been sealed since B69.
    - It corrected `hosts.md`: Neo4j's PVC is 20Gi, not 5Gi.
    - It found finding 18 (APISIX) and the Kokoro image still on `:latest`.
10. **Thin runbooks.** `keycloak.md` has no health, log or troubleshooting command (the IdP for every UI), and
    `cube.md` has a single command.
    **Keycloak RESOLVED 2026-11-08:** a health and troubleshooting section, with discovery, in-pod readiness, a
    symptom table and restart impact, all checked live. `cube.md` is unchanged (low traffic).
19. **OpenCost allocates $0 to everything (found 2026-11-08 while preparing its demo).** The 1-day allocation API
    shows `totalCost $0.0000` for every namespace.
    - `node_cpu_hourly_cost` is 0, and the RAM cost metric does not exist.
    - The `custom-pricing-model` ConfigMap holds the right prices ($0.001029 per core-hour, $0.000343 per GB-hour,
      `provider: custom`).
    - The exporter logs `node pricing has illegal CostPerRAMHr; replacing with custom pricing: weyland-cluster/mother 0`.
    So the lab's Cloud Cost numbers (Port `cost`, the Cost dashboard) have been zero.
    **Diagnosed 2026-11-08 (owner decision: fix it).** The file OpenCost actually uses, `/tmp/custom-config/default.json`,
    held `CPU "0.000001"`, `RAM "0"`. OpenCost reads the ConfigMap's rates as **monthly** and divides by 730 hours
    (six decimals): `0.001029 / 730` rounds to `0.000001`, and `0.000343 / 730` rounds to `0`. The values had been
    written as hourly rates.
    **Fix:** the same model written as monthly rates (CPU 0.751406, RAM 0.250469, storage 0.000292), with the rule in
    the values file and in `runbooks/opencost.md` § Are costs being allocated? (both checks run live: the "before" state
    reads 0.000001 / 0 and $0.0000).
    **VERIFIED 2026-11-08 after the push and Argo's sync:**
    - `default.json` reads `CPU 0.001029`, `RAM 0.000343`;
    - allocations are non-zero for the first time, and the last hour runs at **$17.94/month**, in line with the
      model's ~$15 for mother's slice.

    The exported Prometheus metric kept the old `0.000001` until an OpenCost restart (owner-authorized, 2026-11-08).
    After it, `node_cpu_hourly_cost` reads 0.00103 and `node_ram_hourly_cost` 0.000343.
11. **Not on any map:** Sourcebot, Zoekt, Promptfoo, Pyroscope, Sealed Secrets. `check-maps.sh` checks CI steps and
    external systems only, so nothing catches this.
    **RESOLVED 2026-11-08 (batch C).** The exact guard found two more the fuzzy audit had passed: the A2A Inspector
    and OpenSearch Dashboards.
    - All seven are now on a map: rows on the Platform Map, and the A2A Inspector in the Realm map's A2A line.
    - Four apps that were on maps under other names carry a `map_label:`: Dagster, the LanceDB Viewer, the MCP server
      fleet and the k8s exporter.
12. **Demos.**
    - No demo at all: Headlamp, OpenCost, Pyroscope.
    - The 12 end-to-end walkthroughs (E1–E12) are all PARTIAL and have never had a live run.
    - Rows 36, 47 and 48 are PARTIAL.

### Tier 4 — mechanical hygiene

13. **Host labels: mostly not a finding (corrected 2026-11-08).** 350 fenced command blocks have no host label. But
    the owner ruled on 2026-10-03 that kubectl-only commands get **no** label, because kubectl works from either host
    (memory `feedback-kubectl-runs-on-mother`). So an unlabelled kubectl block is correct. Only blocks that depend on
    a host's files or tools need a label. The remaining gap is a subset of the 350, not all of them, and it should be
    counted with kubectl-only blocks excluded before anything is changed. The roster prints these as `[any]`, which
    is accurate.

### What would keep these gaps closed (Closing Gaps: the audit question)

- **DONE 2026-11-08 (batch C):** one guard, `scripts/check-doc-coverage.py`, in CI repo-guards, with its logic in
  `scripts/lib/doc_coverage.py` (12 tests). It covers both of the planned checks, a `runbook:` field per deployed app
  and every deployed app on at least one map, in one place instead of extending two scripts.
  - Every deployed app in `applications.yaml` now names its runbook, or carries `runbook: null` + `runbook_gap:`.
    That is 10 recorded gaps, batch D's list.
  - Every deployed app appears on a map by name, key or `map_label:`.
  - The DoD (Pillar 2) and the registry's schema comment describe it.
  - The tool-server, Port and DataHub consumers read registry fields explicitly, so the new fields do not leak.
- ~~A runbook path guard~~: dropped on evidence. 8 of the 9 hits were legitimate prose (other repos, gitignored files,
  history, hypotheticals), so a guard would mostly block correct docs. The two guards above cover the gaps that
  matter.

### False positives (checked and cleared)

- `keda.md` and `agent-hermes.md` mention retired systems, but both are bannered RETIRED at the top.
- Some "dead paths" are short forms that exist under a service directory (`scripts/feast_setup.py` is in
  `services/weyland-dagster/scripts/`), or are stems of real files (`machine-inv-drift` → `.service`/`.timer`).
  `docs/code` in `embedding-model-swap.md` is prose. `scripts/claude-obsidian.py` is in the external checkout.
- Grafana, LiteLLM, Bifrost, SonarQube, n8n, Sourcebot/Zoekt, Ray, the scan suite, the store-scaler, the guard
  services, Port's exporter and forward-auth all looked runbook-less by name. Each has its home in a runbook under
  another name (`observability.md`, `model-gateway.md`, `mcp-gateway.md`, `code-quality.md`, `alert-to-linear.md`,
  `code-intelligence.md`, `remote-training.md`, `port-agent-easy-button.md`, `guardrails.md`, `port.md`,
  `keycloak.md`).
- History is not drift: `observability.md`'s 2026-06 Jaeger phase and `code-quality.md`'s old Hermes scan results
  are dated records.

---

## B69 CURRENT REGISTER — re-audit 2026-07-17 (supersedes the 2026-06-26 snapshot below)

Fresh 3-agent sweep (secrets+gitops · monitoring · backup/trigger/docs) graded against the DoD **operational-completeness** pillar (reproducible · secret-restorable · monitored · backed-up · triggered). The 2026-06-26 register below is kept for history; several items are now RESOLVED (data-mesh backups, all schedules `RUNNING`, Kuma backup committed, Grafana recipe codified) or OBSOLETE (Ollama→rogueone B79, OpenClaw dropped). Current open gaps, prioritized into waves:

> **▶ RE-VERIFIED 2026-07-20** — every Wave 1/4/5 item re-checked against git AND the live cluster. Result: the
> register had drifted **in both directions**. Now-CLOSED (see per-wave ✅ marks below): data-mesh alert loading,
> `telegram-test`, cube plaintext key, backup coverage, Argo onboarding, code-quality/sonar schedules, SPOF probes,
> dead-man's-switch, and the whole 07-18 "still uncommitted" push list.
>
> **The instructive miss:** the "data-mesh alerts silently dead" item — flagged here as the single biggest live risk —
> was fixed by setting `ruleSelectorNilUsesHelmValues: false` **once**, NOT by the prescribed "add `release: monitoring`
> to 17 files". All 14 rule files still lack that label and load fine (52 PrometheusRules live). Following the register
> literally would have meant 17 pointless edits; trusting its status would have meant believing data-mesh alerting was
> dead when it isn't. A stale register is worse than none precisely because it is specific.
>
> **STILL OPEN after this pass:** ~~LGTM self-monitoring~~ (✅ done 2026-07-20) · ~~Hermes heartbeat~~ (⏸ gated on B66 — Hermes is off) · 2 uncodified triggers (docs-site rebuild, eval
> harness/leaderboard, roadmap-sync `.timer`, ai_session producer crontab — 7 CronJobs live, none of these) · GitOps
> misc (n8n workflows→git, LiteLLM `main-stable`→digest, DataHub recipes UI→reconciled) · Wave 5 docs-drift (Argo app
> count drifted again: backlog says 48, live is **59** / 58 in git) · ~~`weyland-image-prune.timer`~~ (✅ installed 2026-07-20, next Sun 15:09 UTC) · delete CT-102 + `hosts.md` cleanup · Prometheus/Loki retention caps.
> Disk pressure is NOT a concern anymore: `/` 63%, `/mnt/minio` 9%.

> **▶ AM PICKUP — 2026-07-18** (historical; the PUSH list below is now fully committed).
>
> **DONE:** drift cleanup — every Argo app back to **Synced/zero-drift**; `b69-onboarding.yaml` deleted, its 9 apps redistributed to `loose-apps`/`subdir-apps`/`helm-apps` (no batch-named files); dedup'd the double-owned `data-mesh/traefik-forward-auth` Middleware (dropped from cube.yaml) + `minio/minio` ServiceMonitor (dropped from data-mesh); targeted `ignoreDifferences` for the CRD `preserveUnknownFields`+printer-column `priority` (gatekeeper/flink), STS `volumeClaimTemplates` (opensearch/datahub-prereq), and datahub-gms-secret. Deleted the **live `qdrant-fault-demo` VirtualService** (a fault-injector still adding 3s latency to qdrant). **Wave 4 Slice 1** (SPOF probes: traefik-forward-auth tcpSocket, cube `/livez`+`/readyz`, n8n `/healthz`) + **Slice 2** (blackbox synthetic monitoring for the 16 uncovered hosts + `WeylandEndpointDown` alert — verified). **DNS OUTAGE fully fixed** — weyland-lan-dns `hostPort:53` via k3s ServiceLB captured the node's own `127.0.0.53` resolver → node DNS black-holed on pod death → cascade; fix = `hostPort` pinned to `hostIP: 192.168.1.243` + Service `ClusterIP` (no svclb) + a systemd-resolved drop-in so mother resolves weyland.lab via LAN DNS while external stays on the router. **mother disk +400G** (92% → 61%). node-disk alert + image-prune timer authored.
>
> **PUSH (still uncommitted):** `nodes/mother/host/systemd/resolved.conf.d/weyland-lab.conf`, `nodes/mother/host/systemd/weyland-image-prune.{service,timer}`, `k8s/monitoring/node-disk-alerts.yaml`, `docs/runbooks/lan-dns.md`, `docs/schedules.md`. (The node-disk alert is the priority — Argo syncs it → early-warning live.)
>
> **TODO (AM):** install the prune timer (rsync + `systemctl enable --now`); move **minio-backup (51G) → `/mnt/minio`**; **de-Argo + drop the spent musicbrainz-dbdump (25G)**; **Prometheus/Loki retention caps**; **delete CT-102 (ollama)** + clean rogueone `/etc/hosts` (`.244` stale) + hosts.md "decommissioned"→"deleted"; finish **Wave 4** (code-quality CronJobs, Hermes heartbeat, LGTM self-monitoring).

### Wave 1 — quick high-value fixes (small edits, real safety) — ✅ ALL DONE (verified 2026-07-20)
- ✅ **RESOLVED DIFFERENTLY** — `ruleSelectorNilUsesHelmValues: false` in `kube-prometheus-stack-values.yaml` makes the
  operator load rules regardless of label; 52 PrometheusRules live. The label fix below was never needed.
  **[monitoring] data-mesh alert rules NOT loaded** — all 17 `k8s/data-mesh/*.yaml` PrometheusRules are labeled `app:` not `release: monitoring`, and the stack sets no `ruleSelectorNilUsesHelmValues: false`. Every data-mesh down-alert (Nessie/lakeFS/DataHub/MinIO/Trino/GizmoSQL/Feast/Superset/all 10 Tier-2) is **silently dead**. Fix: add `release: monitoring` to each (or set the selector). Confirm live: `kubectl get prometheusrule -A -l release=monitoring`.
- ✅ **DONE** (Watchdog → `healthchecks-watchdog` webhook, `url_file` from the `watchdog-healthcheck` secret, `repeat_interval: 5m`). **[monitoring] no dead-man's-switch** — Alertmanager Watchdog → `receiver: 'null'`. Route to an external heartbeat (healthchecks.io / Kuma push) so a dead Prometheus/Alertmanager is noticed.
- ✅ **DONE** (sealed into `cube-secret` during SEC-1). **[secrets] cube JWT signing key in PLAINTEXT in git** — `k8s/cube/cube.yaml` (`CUBEJS_API_SECRET: weyland_cube_dev_secret`). Move to a sealed/imperative secret.
- ✅ **DONE** (file deleted from git). **[monitoring] `telegram-test` always-firing alert** — `k8s/monitoring/telegram-test-rule.yaml` (`expr: vector(1)`), self-healed by `monitoring-extras`; pages every 4h forever. Delete / exclude.
- ✅ **DONE** (`mlflow` + `tofu-state` added to the mc-mirror; `postgres-backup.yaml` full-instance `pg_dumpall`; both live). **[backup] extend the two backup CronJobs** — add `mlflow` + `tofu-state` (+`registry`) to `k8s/minio/backup.yaml` mc-mirror (IRREPLACEABLE: trained models, all IaC state); extend `k8s/data-mesh/backup.yaml` to `pg_dumpall` the FULL `weyland-postgres` (only nessie/lakefs of its 12 DBs are dumped — keycloak realm/superset/weyland-core are irreplaceable and unbacked).
- ✅ **DONE** (`k8s/istio/` + `k8s/code-quality/` in `subdir-apps`; loose root files in `loose-apps`; 59 apps live). **[gitops] Argo-onboard the un-reconciled dirs** — `k8s/istio/` (8 manifests incl STRICT-mTLS PeerAuthentication), `k8s/code-quality/`, and the loose root files (`coredns-custom.yaml` = load-bearing LAN DNS, `coredns-lan.yaml`, `rbac-default-sa-noautomount`, headlamp trio, `rag-index-{neo4j,pgvector}.yaml`) — currently in 0 Applications.

### Wave 2 — secrets management (the big rock) — ✅ DONE 2026-07-17
- **[secrets] SealedSecrets adopted.** Bitnami controller (chart 2.19.1 / v0.37.0) in kube-system via the `sealed-secrets` Argo app; controller private key escrowed off-cluster. **53 imperative secrets sealed** into git (`k8s/sealed-secrets/sealed/<ns>__<name>.yaml`) via the explicit allow-list in `scripts/seal-secrets.sh`, applied by the `sealed-secrets-manifests` Argo app — each live secret adopted in place (ownerRef=SealedSecret, no disruption). Runbook `docs/runbooks/secrets.md` (mechanism: seal/restore/rotate/escrow); `data-mesh-secrets.md` re-pointed to it. Chart/operator-generated secrets (datahub-chart/superset/lightdash/jupyterhub-hub/kafka-prereq/prometheus-operator/webhook certs) deliberately NOT sealed (charts recreate them). Bricking values raw-escrowed: lakeFS `AUTH_ENCRYPT_SECRET_KEY`, n8n `N8N_ENCRYPTION_KEY`, glitchtip `SECRET_KEY`.
  - **Deferred (not blocking):** TLS/CA (`weyland-wildcard-tls` 45 ingresses + mkcert CA) left unsealed — mkcert-regenerable, replicated across ns, and they expire; revisit if a cert-manager is introduced.

### Wave 3 — reproducibility (images off `:local`) — ✅ DONE 2026-07-17
- **[gitops] `:local` / `imagePullPolicy: Never` images migrated.** 8 buildable images built+pushed to `registry.weyland.lab:v1` (`scripts/build-push-images.sh`, reusable, TAG-parameterized): weyland-tool-server · weyland-rag-index (×5 manifests) · weyland-dagster-base (×2) · weyland-dagster-user-code (×2) · weyland-flink (×3) · weyland-flink-py · feast-server (×2) · store-scaler. All 17 manifests repointed to `registry.weyland.lab/<name>:v1` + `Never`→`IfNotPresent`; `ranger` `Never`→`IfNotPresent` (real image, pullable). Verified: only musicbrainz on `:local`, no pull/crash errors. k3s nodes pull via node-level containerd auth (no imagePullSecret). Several deploys were already drifted to `:v1` live with git stale at `:local` (e.g. tool-server) — now reconciled.
  - **ROOT CAUSE found + fixed (the real work):** pushing multi-GB layers to `registry.weyland.lab` failed at exactly 60s (HTTP 499, registry never saw the blob). k3s **Traefik v3 default `readTimeout=60s`** bounds the full request-body read → large pushes guillotined. Fix: `k8s/traefik/traefik-config.yaml` (HelmChartConfig, `readTimeout: 0s`), Argo-managed (`traefik-config` app). See [[traefik-readtimeout-registry-push]].
  - **EXCEPTION (deliberate):** `musicbrainz-mb-import:local` left as-is — built from the external musicbrainz-docker repo (no in-repo Dockerfile), a completed one-off restore Job (only re-pulls on a manual re-run). Documented in the manifest.
  - **Deferred:** wire a Woodpecker/B57 auto-build pipeline (currently manual `build-push-images.sh` on rebuild).
- Note: the failing **`weyland` MCP** (`:30080/mcp`) is NOT an image problem — the tool-server pod is healthy on `:v1`. If the MCP still misbehaves in Claude Code it's the **client config** → moved to Wave 5 (MCP revisit).

### Wave 4 — monitoring / probes / triggers — PARTIALLY DONE (verified 2026-07-20)
- ✅ **MOSTLY DONE** — Slice-1 probes + a blackbox exporter covering **19** endpoints give synthetic coverage even where no ServiceMonitor exists (cube/jupyterhub/valkey/keycloak still have none). ❌ **STILL OPEN: LGTM self-monitoring** — no `LokiDown`/`TempoDown`/`AlloyDown` rules anywhere. **[monitoring] SPOFs unmonitored** — Keycloak + traefik-forward-auth (single replica, no probes, gate ~18 UIs) → liveness/readiness + down-alerts + Kuma synthetic. Cube/JupyterHub/Ranger/Valkey no ServiceMonitor/alert. Gatekeeper/Flink/Ray scrape-but-no-down-alert. LGTM doesn't monitor itself (no loki/tempo/alloy SM + Down rules).
- ⏸ **GATED ON B66 — not open.** Hermes is currently **shut off**; the agent lane is consolidated into **B66** (Operator Agent Platform), where the base-agent decision (Hermes vs OpenClaw) is made. Monitoring a deliberately-stopped service would page forever, so the heartbeat units are **staged in git, not installed**: `nodes/weyland/hermes/hermes-heartbeat.{service,timer}` (push-based — CT 104 is outside k3s so Prometheus has no scrape path; gated on `systemctl is-active` so a dead gateway can't report healthy). Install alongside a Kuma Push monitor when B66 brings an agent back up. **[monitoring] Hermes gateway** (CT 104) no failure monitoring → systemd heartbeat gated on `systemctl is-active` → Kuma push.
- ⚠️ **PARTIAL** — ✅ code-quality scans done (`code-scan-suite` Sun 13:00 + `sonar-scan` Sun 12:00, both live). ✅ roadmap-sync `.timer` authored 2026-07-20 (`nodes/weyland/hermes/roadmap-sync.{service,timer}`, daily 06:30, Persistent — staged with the Hermes units). ✅ docs-site rebuild codified 2026-07-20 (`k8s/docs-site/docs-site-rebuild.yaml` — daily 05:30 NY `rollout restart`, least-privilege SA pinned to that one Deployment via `resourceNames`). ✅ eval harness/leaderboard scheduled 2026-07-20 (`weyland_eval_schedule` Sat 03:00 + `weyland_eval_score_schedule` Sat 05:00, both `STOPPED` pending a green manual run — Ollama moved to rogueone in B79). ✅ ai_session producer codified 2026-07-20 (`nodes/rogueone/systemd/ai-session-producer.{service,timer}` — user unit, needs `loginctl enable-linger`). **Wave 4 triggers COMPLETE.** (7 CronJobs live, none of these). **[trigger] manual-only → schedule + freshness** — docs-site rebuild (CronJob), code-quality scans (weekly CronJob + Argo), eval harness/leaderboard (weekly or freshness), roadmap-sync (`.timer`), ai_session producer (commit the rogueone crontab).
- **[gitops] reproducibility misc** — Hermes runtime bootstrap, Ollama perf/Modelfile config, LiteLLM mutable `main-stable`→digest, headlamp Helm→Argo Application, n8n workflows→git, DataHub recipes UI→reconciled.

### Wave 5 — docs-drift
- Argo app count 28→**48** (backlog); strike Backstage/Jaeger/OpenClaw from the backlog BODY (retired/dropped, still referenced as live); reconcile DataHub dataset counts (3255 vs 3282 vs 3256); MinIO console SSO sweep.
- **Refresh `docs/platform-map.html`** — the hand-authored visual map has drifted from the live component set (openclaw card removed 2026-07-17; likely more ghosts/omissions — e.g. the full B1 data-mesh, LikeC4). Audit it card-by-card against `hosts.md` + the LikeC4 model and reconcile. (Now a standing DoD item — see [[completion-criteria]] pillar 1.)
- **Audit the Port.io catalog for drift** — reconcile what Port CLAIMS is integrated vs live reality (a standing DoD item now, pillar 1). Live evidence: the backlog/arch present the **K8s exporter (`weyland-cluster`) as a live integration**, but no in-cluster exporter is deployed — the `k8s_workload` links are MCP-maintained. Resolve it: either deploy the exporter (outbound, LAN-OK) or correct the claim + own the MCP-maintained model. Also **revisit the failing `port` MCP here** (`npx mcp-remote https://mcp.port.io/v1` re-prompts OAuth every session and currently fails to connect — remove it from the Claude Code config, or fix token persistence).

**Biggest live risks:** unloaded data-mesh alerts (believed-working, dead) · no dead-man's-switch · irreplaceable stores unbacked (core Postgres, mlflow models, tofu-state) · ~45 unmanaged secrets (one node loss = unrecoverable). Wave 1 removes most of the *immediate* danger cheaply.

---

## DATA-MESH — SOLVE NOW (bucket = data-mesh-now) — ✅ RESOLVED 2026-06-26

All 14 closed inline with B1: iceberg trigger wired (`weyland_eval_score_job`); all schedules
`default_status=RUNNING`; `iceberg_publish` env hardened; Dagster→Iceberg lineage edge emitted
(verified end-to-end); recipes codified (`k8s/data-mesh/datahub-ingestion/`); MinIO + Postgres
backups to NVMe (CronJobs, tested green); ServiceMonitors/PodMonitor + down-alerts; Loki rule
broadened to `data-mesh`; Dagster freshness watchdog (`k8s/dagster/freshness.yaml`, external —
the run_status_sensor is dead on 1.13); secrets runbook + lakeFS encrypt-key escrow
(`docs/runbooks/data-mesh-secrets.md`); storage→DataHub assessed (s3 for aidlc-kb only, rest
redundant/no-connector); docs corrected. **Deferred to B69 (cross-cutting):** the full
SealedSecrets/External-Secrets mechanism for all imperative secrets.



### High
- **[trigger] `iceberg_eval_scores` orphaned from every job & schedule** — `assets/iceberg_export.py` (group "eval") + `schedules/__init__.py` (eval jobs select named assets only; ingestion subtracts group "eval") — Fix: add `iceberg_eval_scores` to `weyland_eval_score_job`'s selection (`AssetSelection.assets("eval_scores","iceberg_eval_scores")`).
- **[lineage] Dagster→Iceberg→DataHub hop broken; tables never cataloged** — `datahub_emit.py` (PLATFORM="dagster" only), `iceberg_publish.py`, `k8s/data-mesh/datahub-values.yaml` (no Iceberg/Nessie source) — Fix: add a git-tracked DataHub Iceberg ingestion recipe → `nessie.data-mesh.svc:19120/iceberg`, and emit a cross-platform `UpstreamLineage` edge from each `iceberg_*` dagster URN to its `platform=iceberg` dataset URN.
- **[gitops] All Dagster schedules default to STOPPED** — `schedules/__init__.py`, `definitions.py` (no `default_status`) — Fix: `default_status=DefaultScheduleStatus.RUNNING` on every `ScheduleDefinition` (also fixes `datahub_catalog_emit_schedule` + B62 `ai_session_schedule`).
- **[gitops] Grafana DataHub source is UI-only with an imperatively-minted SA token** — no recipe/secret in git (`backlog.md:835/838`) — Fix: codify as a managed-ingestion recipe under `k8s/data-mesh/` + store the Grafana SA token via SealedSecrets/External Secrets.
- **[gitops] Data-mesh & catalog secrets are imperative one-offs; lakeFS encrypt-key un-escrowed** — `k8s/dagster/user-code.yaml` (`datahub-token`, `iceberg-s3-secret`), `datahub-values.yaml` (`datahub-auth-secrets`, `datahub-oidc`), `minio-creds` — Fix: SealedSecrets/SOPS for all; **escrow lakeFS `AUTH_ENCRYPT_SECRET_KEY`** (losing it bricks all stored creds); `iceberg_publish.py` `os.environ[...]` hard-index → KeyError on rebuild.
- **[other] MinIO data products on a single un-backed-up USB disk** — `k8s/minio/pv.yaml` (static local PV, no RAID); `storage-minio.md` declines backup but none exists — Fix: scheduled `mc mirror` CronJob of warehouse+lakefs (+aidlc-kb, mlflow) to a second target; correct the "reproducible" runbook claim.
- **[other] Nessie & lakeFS Postgres metadata (commit history / branch refs) have no backup** — `nessie.yaml`, `lakefs.yaml` — Fix: scheduled `pg_dump` CronJob (meshed for STRICT Postgres) → MinIO backup bucket, with rotation.
- **[monitoring] No Prometheus/Alertmanager for Nessie or lakeFS; MinIO ServiceMonitor not in git** — zero ServiceMonitor/PrometheusRule in `k8s/data-mesh/` — Fix: ServiceMonitors (Nessie :9000 `/q/metrics`, lakeFS :8000 `/metrics`) + pod-down/health alerts, commit the MinIO ServiceMonitor, Kuma checks on in-cluster health endpoints.

### Medium
- **[lineage] Storage tier (lakeFS repos, MinIO buckets) not ingested into DataHub** — Fix: add s3 source for warehouse/lakefs buckets + a lakeFS source via the meshed executor.
- **[lineage] No column schema on the tabular Iceberg data products** — `datahub_emit.py:10-11` stale "not tabular" comment — Fix: emit `SchemaMetadata` for `iceberg_*` datasets from the Arrow/Iceberg schema; fix the comment.
- **[monitoring] No failure/freshness monitoring on catalog-emit, Iceberg export, or DataHub executor** — Fix: Dagster run-failure sensor → GlitchTip/Telegram, Kuma heartbeat on the hourly emit, freshness check on `iceberg_*`; MinIO/Nessie/lakeFS down alerts.
- **[monitoring] Loki log-spike alert scoped to `namespace="weyland"` only** — `k8s/loki/loki-rules-configmap.yaml` — Fix: broaden the LogQL selector to cover `data-mesh`.

### Low
- **[docs] Backlog marks the Grafana catalog source ✅ DONE though non-reproducible** — `backlog.md:835` — Fix: downgrade to "configured (UI-only, not yet GitOps)".
- **[docs] DataHub emitter dataset count stale (15 vs 17)** — `backlog.md:849-851` — Fix: update to 17.

---

## PLATFORM-WIDE — clear right after B1 (bucket = platform-later, → B69)

### High
- **[gitops] No secrets-management mechanism; ~25 cluster secrets are imperative-only** — `neo4j-secret`, `tool-server-sentry`, `weyland-alerts-telegram`, grafana-admin/oauth, all SSO client secrets — Fix: adopt External Secrets/SealedSecrets/SOPS, or minimally commit a `*-secret.example.yaml` per secret + `docs/runbooks/secrets.md` index (name→keys→regen).
- **[monitoring] Ollama (sole generation backend) has no Prometheus/Alertmanager coverage** **(RESOLVED B79 — moved to rogueone GPU)** — CT 102 `192.168.1.244:11434` — Fix: Kuma HTTP monitor on `/api/tags` (Telegram) + blackbox probe + PrometheusRule.
- **[monitoring] Hermes gateway has zero failure monitoring** — `uptime-kuma.md:27` — Fix: Kuma push heartbeat from a CT 104 systemd timer gated on `systemctl is-active hermes-gateway`.
- **[gitops] Hermes agent runtime not reproducible from git** — `hermes.tf` is CT shell only — Fix: versioned bootstrap script under `nodes/weyland/hermes/` (config.yaml + mcp_servers + pinned `python-telegram-bot[webhooks]==22.6` + kanban init + templated `.env`).
- **[gitops] tool-server MCP image (`weyland-tool-server:local`) not reconstructible** — `imagePullPolicy: Never`, hand-built → ErrImageNeverPull on rebuild → `/mcp`+`/mcp-act` never start — Fix: push to `registry.weyland.lab` (**now exists, B-RT** — the local-registry fix is unblocked) / Woodpecker pipeline / committed bootstrap. (Still open: the tool-server image itself hasn't been migrated off `:local`/`Never` yet.)
- **[gitops] Always-firing `telegram-test` alert committed & Argo-synced** — `k8s/monitoring/telegram-test-rule.yaml` (`expr: vector(1)`) → pages every 4h forever — Fix: delete from git or add to `monitoring-extras` exclude.
- **[gitops] Uptime Kuma monitor definitions live only in SQLite on a PVC** — 23 monitors built in UI — Fix: export Kuma Backup JSON into the repo, or migrate critical checks to git-managed blackbox Probe CRDs.
- **[monitoring] No dead-man's-switch — Watchdog routed to `null`** — `kube-prometheus-stack-values.yaml` — Fix: route Watchdog to an external heartbeat (healthchecks.io / Kuma push).
- **[gitops] Entire `k8s/istio/` set (incl. STRICT mTLS PeerAuthentication) not onboarded to Argo** — 8 manifests in 0 Applications — Fix: add an Argo Application for `k8s/istio/` (ServerSideApply for CRD-bearing objects).

### Medium
- **[gitops] Ollama runtime perf/OOM config not reproducible** — systemd drop-in + `num_thread 8` Modelfiles (~160x) only in the runbook — Fix: Proxmox hook_script/cloud-init bootstrap from `ollama.tf`.
- **[trigger] Eval harness on-demand only; leaderboard frozen at run 3 (2026-06-13)** — Fix: low-frequency (weekly) schedule or freshness check on `eval_runs.created_at`.
- **[trigger] `roadmap-sync` cron is an un-codified manual crontab** — `agent-hermes.md:391` — Fix: ship `hermes-roadmap-sync.service`+`.timer` in `nodes/weyland/hermes/`.
- **[gitops] ai_session producer runs from an uncommitted rogueone crontab** — `scripts/ai_session_feeder.py` — Fix: committed k8s CronJob or systemd timer + freshness alert.
- **[gitops] `ai_session` blueprint (B62) not codified in tofu** — Fix: `tofu import port_blueprint.ai_session`, strip phantom fields, update `opentofu.md` to 13.
- **[gitops] Port ingestion integrations + webhooks are imperative MCP/UI one-offs, unmonitored** — Fix: document exact recreate steps per integration + freshness alert per key blueprint.
- **[trigger] `docs.weyland.lab` rebuilds only on manual pod restart** — Fix: CronJob `rollout restart deploy/docs-site` + surface built commit/date.
- **[trigger] code-quality scans (semgrep, trivy) are one-shot Jobs, not scheduled/Argo** — Fix: weekly CronJobs, onboard the dir as an Argo Application, last-scan freshness signal.
- **✅ RESOLVED 2026-08-18 (B57a) — weyland-image CI→registry→git pipeline landed.** The weyland-lab `.woodpecker.yml`
  now builds the weyland-built images (via a persistent `buildkitd` Deployment) → pushes `git-<sha>` to
  `registry.weyland.lab` → opens a tag-bump PR → merge → Argo deploys, on a **nightly 01:00 NY cron** + manual
  (the LAN-webhook wall means cron/manual, not push — accepted). Validated live (store-scaler → `git-ec59b430`).
  Residual: build-status → Port (`ci_pipeline`) — **✅ RESOLVED 2026-08-19 (B63):** a `notify-port` step feeds the
  `weyland_ci_reliability` dashboard (both farms, both outcomes proven). See `runbooks/woodpecker.md`.
- **[gitops] Loose `k8s/` root files not reconciled by Argo** — `coredns-custom.yaml` (load-bearing), `coredns-lan.yaml`, `rbac-default-sa-noautomount.yaml`, headlamp trio in 0 Applications — Fix: add Applications or widen `loose-apps` globs.
- **[monitoring] LGTM stack does not monitor itself** — no ServiceMonitor on loki/tempo/alloy — Fix: enable `monitoring.serviceMonitor` + `LokiDown`/`AlloyDaemonSetNotReady` rules.
- **[monitoring] traefik-forward-auth is a single-replica SPOF with no probes** — gates ~18 UIs — Fix: liveness+readiness on :4181 + synthetic monitor on `auth.weyland.lab/_oauth` + Keycloak `/health/ready`.
- **[docs] Live `dashboard.weyland.lab` absent from hosts.md/api.md/arch** — Fix: add host + UI-table rows + runbook section.
- **[gitops] OpenClaw degraded/unreproducible but listed ✅ healthy** **(OBSOLETE B28 — OpenClaw dropped 2026-07-17)** — `hosts.md:13` — Fix: flag degraded/deprioritized (or retire + tear down vm-100); codify compose if kept.

### Low
- **[gitops] LiteLLM pinned to mutable `main-stable` under selfHeal** — Fix: pin to immutable tag/digest.
- **[gitops] `k8s_workload` relation target not codified; bare apply to empty org fails** — `tofu/port/catalog.tf:393-399` — Fix: stub a minimal blueprint or document exporter-first ordering.
- **[docs] Backlog B59 overclaims component→k8s_workload entity links "codified in tofu"** — Fix: correct to "intentionally NOT codified".
- **[docs] Backlog B58 claims 28 Argo apps; actual 37** — Fix: update count.
- **[docs] MinIO console (`minio.weyland.lab`) left out of the forward-auth SSO sweep** — `k8s/minio/ingress.yaml` — Fix: add the forward-auth middleware or delete the dead console ingress.

---

## 2026-09-11 — Full completeness + correctness audit (whole repo)

Method: the 20 CI guards run directly (deterministic layer) + three parallel judgment agents (DoD-artifact
completeness · docs-vs-repo correctness · cross-refs + contradictions). Every agent finding was
verified against ground truth before action — which caught false positives (below).

### Deterministic guards — 17/20 clean; the 3 non-passes are NOT doc/DoD defects
Green: doc-counts (81) · app-registry · onboarding-completeness (61) · cron-budgets (18) · image-provenance
(126) · quality-tools · sa-automount · odcs-contracts (10) · verdict-sync · port-iac · secret-placeholders
(67) · pip-audit-ignores · api-lifecycle (12) · linear-sync (170) · mermaid (180 blocks / 345 docs) ·
dashboard-coverage (38) · alert-coverage (38).
Non-passes (environment/ops, not documentation): `servicemonitor-coverage` → **`weyland/ray-head` down**
(intended 1/actual 0) = live-ops; `datahub-coverage` → Trino unreachable from this host (re-run from
mother); `check-rego-policies` → `opa` not installed locally (CI validates; sibling Python provenance guard
passed).

### Correctness defects — FIXED 2026-09-11
- **scan-suite tool count stale (9/10/19 → actual 21, guard-confirmed)** — README.md, hosts.md, api.md (×2),
  arch.md:145, schedules.md:65. Fixed to 21 (arch.md:1178 already correct).
- **"ten k8s CronJobs" → 18** (cron-freshness rule covers 18) — schedules.md:53.
- **arch.md:113 `/mcp` said `fastapi-mcp`** — migrated to **FastMCP** 2026-08-01 (per api.md:52). Fixed.
- **Uptime Kuma monitor count contradiction (37/25/16)** — authoritative 37 (uptime-kuma.md). Fixed api.md
  (25→37) + README.md (16→37, and the stale "→ Port.io webhook", now retired).
- **Dead manifest paths** — code-quality.md `sonar-scan-job.yaml`→`sonar-scan.yaml`, `trivy-scan-job.yaml`→
  `scan-suite.yaml`; secrets.md `b69-onboarding.yaml`→ the sealed-secrets Helm app in `helm-apps.yaml`.
- **`register_bifrost_routing.py` documented as live-built** (bifrost-provider-loadout.md:52) but removed —
  marked removed (aligns with mcp-gateway.md:162; file absent).
- **`dagster-freshness-check` CronJob missing `timeZone`** (Design Rule #1) — added `America/New_York` to
  `k8s/dagster/freshness.yaml` (a `*/30` cron; no firing shift).
- **Undocumented user-facing hosts** — added `datahub.weyland.lab` + `opensearch.weyland.lab` + the lakeFS
  `mother:30800` NodePort to api.md's Web-UIs table.
- **Phantom `data-mesh-scaledown` 02:00 CronJob** (schedules.md:29,109) — no manifest exists + Argo selfHeal
  reverts `replicas:0`; corrected to PARKED / manual store-scaler.

### Verified FALSE POSITIVES (agent flagged, ground truth cleared — no change)
- `scripts/*.sql` "moved to sql/" — the `.sql` files exist under `services/weyland-dagster/scripts/`; the
  base-relative doc paths resolve.
- `flink-rta-sessionjob.yaml` "dead" — the job was deliberately DELETED and both flink.md ("it *was*…") and
  backlog.md document it as retired.
- `register_bifrost_*.py` / `feast_setup.py` "wrong path" — base-relative to the platform dir; resolvable.

### Correctness — Bifrost fleet tool count: RESOLVED by live validation (2026-09-11)
- **91 vs 95 contradiction** (arch.md internally inconsistent; api.md/design/gpu-inference/mcp-gateway said 91).
  Resolved by **querying the live compositor** (`weyland-mcp-compositor.weyland.svc:8000` MCP `tools/list`) =
  **95** (context 4 + grafana 52 + trino 6 + k8s 14 + postgres 9 + neo4j 2 + datahub 8). **95 is correct;
  the "91"s were stale** — fixed all (`91 fleet` / `91/91` / `~91` / `full 91` → 95) across the 5 docs.
  Lesson: a doc-vs-doc contradiction is resolved against the *running system*, not by picking the
  "more authoritative" doc.

### Live-ops finding — ray-head "down" ROOT-CAUSED + FIXED (2026-09-11)
`servicemonitor-coverage` flagged `weyland/ray-head` down (0/1). Diagnosis: the Ray **cluster is fully
healthy** (`ray status` = 2 nodes / 28 CPU / 1 GPU, no failures), but the readiness probe hit
`/api/version`, which **500s in Ray 2.56 through a dashboard subprocess-proxy bug**
(`AttributeError: 'NoneType' has no attribute 'request'`) — so the probe failed for 2.5 days while the
cluster worked. **Fix:** repoint the probe to `/api/gcs_healthz` (verified 200; reflects real GCS health)
in `k8s/ray/ray-head.yaml`. A redeploy brings ray-head to 1/1 and clears the guard.

### FLAGGED items — dispositions (2026-09-11)
- **B157/B158 pillar-2/3 N/A** — FIXED: added explicit diagram/demo-N/A rationale to both entries (as B156).
- **B72 no DONE date** — FIXED: marked "date unrecorded (predates the DoD)".
- **`coredns-lan.yaml` stale `dashboard.weyland.lab`→.247** — FIXED: removed the dead Hermes CT-104 zone.
- **13 orphan-doc candidates** — ACCEPTED as intentional archives (`units/` work-docs + superseded `design/`
  docs; `design/README.md` is deliberately sparse). No change.
- **KEDA / Hermes-Kanban in a couple arch.md paragraphs** — ACCEPTED as historical changelog context (KEDA's
  retirement is stated elsewhere; the lines are "what was added" narrative). No change.

### Remaining historical (NOT auto-fixed — accepted)
- **13 DONE items cite no doc artifacts** — the mid-July security batch (B89–B101) + 3 pre-DoD items, closed
  inline in backlog prose; accepted as historical (DoD is retroactive from 2026-07-14).
- **KEDA / Hermes-Kanban** appear in a couple of arch.md *changelog* paragraphs (their retirements are stated
  elsewhere) — historical narrative, left as-is.

### Highlights (completeness)
- **Zero broken internal doc links** (0 of 1,384) and **zero DONE items linking a missing artifact file** —
  the two highest-value completeness checks are clean.
