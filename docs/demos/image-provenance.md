# Demo — declared-image provenance invariant (B88)

The Gatekeeper `require-signed-images` constraint AUDITS running pods in dryrun; "0 violations" is a
transient observation. Two guards make it a durable invariant — *every declared image is from a
reviewed source* — with one decision core (`scripts/check-image-provenance.sh`) fed by a CI git scan
and a nightly in-cluster enumerator. Audit context:
[supply-chain.md § the provenance invariant](../runbooks/supply-chain.md#the-provenance-invariant--what-makes-0-violations-trustworthy);
flow: [flow-image-provenance.md](../diagrams/flow-image-provenance.md).

This is repo tooling — no UI. The **CLI walkthrough IS the demo**, run in the CI's exact images, and it
includes the **negative cases** (each guard shown failing with its exit code — a guard nobody has
watched fail is not a guard).

## CLI walkthrough (RUN 2026-09-07)

**1. CI guard — the whole declared estate is from a reviewed source (git mode):**

```
bash scripts/check-image-provenance.sh
# OK — all 120 declared image(s) are from a reviewed source (allowlist / exempt publisher / official).  → exit 0
```

It applies the same three-way rule as the constraint's Rego — allowlist (`registry.weyland.lab/`),
exempt publisher prefix (by full path), or implicit single-segment Docker Hub official — reading the
allow/exempt lists straight from `k8s/gatekeeper/image-signatures.yaml` (no drifting copy).

Negative case — an unreviewed image MUST be named and fail (proved against the real policy):

```
IMAGE_LIST=$'data-mesh\tregistry.weyland.lab/weyland-guard:v10\ndefault\tsketchyvendor/miner:latest' \
  bash scripts/check-image-provenance.sh
# UNREVIEWED IMAGES — 1 declared image(s) are from no reviewed source:
#   - default/sketchyvendor/miner:latest
# Fix: build it into registry.weyland.lab, or ... add its FULL-PATH prefix to exemptImages ...  → exit 1
```

Fail-closed — a read that could not run must NEVER read as a clean estate:

```
IMAGE_LIST="" ... bash scripts/check-image-provenance.sh          # no images  → exit 2
POLICY_FILE=/nonexistent ... bash scripts/check-image-provenance.sh  # no policy → exit 2
```

**2. In-cluster enumerator — every declared workload live, running or not (the deny-flip evidence):**

The `image-provenance` CronJob dumps the live constraint + every deployment/statefulset/daemonset/
cronjob/job/pod via kubectl and judges each image. Run end-to-end by hand against the live cluster:

```
# (mimics the CronJob: kubectl init-dump -> derive IMAGE_LIST + POLICY_* -> run the guard)
excluded-ns: kube-system gatekeeper-system istio-system cert-manager
live image refs enumerated: 599
# OK — all 569 declared image(s) are from a reviewed source ...  → exit 0
```

599 image refs across ALL declared workloads (599 → 569 after excluding the 4 infra namespaces the
constraint excludes) — including non-running CronJobs, scaled-to-zero stores, and chart-rendered images
the CI git scan and the Gatekeeper *running-pods* audit both miss. All reviewed: the estate provably
conforms to the prefix rule, which is the precondition the eventual dryrun→deny flip rests on.

**3. Tests + wiring, green in CI images:**

```
bats scripts/tests/image-provenance.bats   # 10 passed (incl. the byte-identity drift case)
shellcheck --severity=warning scripts/check-image-provenance.sh scripts/embed-image-provenance.sh  # 0
promtool check rules <cron-freshness-rules>  # SUCCESS: 7 rules found
kubectl apply --dry-run=client -f k8s/monitoring/image-provenance.yaml  # 5 resources OK
```

The CI guard runs in the `repo-guards` step (secret-free — pure file analysis); the enumerator runs as
the nightly `image-provenance` CronJob (03:10, `monitoring` ns, read-only cluster RBAC).

## UI walkthrough

N/A — repo tooling, no UI surface. A failed enumerator Job surfaces on the existing pattern:
`kube_job_status_failed` → the `ScheduledJobFailed` rule (`cron-freshness-rules.yaml`) → Telegram, like
the other coverage CronJobs.

## Teardown

Read-only. The CI guard reads repo files. The CronJob reads the cluster (kubectl) and writes only to a
per-run `emptyDir` (the two JSON dumps), gone when the Job pod exits. Nothing is deployed or persisted.
