# Demo — CI/CD hardening: making the pipeline actually verify things (B88 Track B, gaps #1–#5)

## The point

A green pipeline meant almost nothing. Each "verification" existed in a shallow form that verified the
*shape* of success without the *substance*: coverage was computed and discarded, "integration" had no tier,
the image scan ran weekly (a CVE shipped Mon–Sat uncaught), "pod Ready" was taken for "works," and no flag
ever touched the deploy path. This bucket pushed each gate one layer deeper — a real number read, a real
request asserted, a per-change delta, a real transaction, a real toggle — and **proved every one against
live infra**. Each section below is RUN; the output shown is real.

Every gap surfaced defects that only a real run reveals (a SIGPIPE on an 8 GB report, an OOMKill, a selfHeal
race, a YAML map-vs-string compile error) — recorded per gap in `docs/backlog.md` B88 OUTSTANDING.

---

## #1 — Coverage ratchet · `scripts/coverage-ratchet.sh`

**Proves:** exactly one lane (Go) emitted coverage and nothing read it. The ratchet fails **only** on a drop
vs a committed baseline (`tests/lang/coverage-baseline.tsv`) — not an 80% floor (which would fail the
mostly-fixture lanes or force fake tests). A number that only has to not-decrease can't be gamed upward.

### CLI walkthrough (RUN)

```
[rogueone] bash scripts/coverage-ratchet.sh compare go:/demo 80.0 /tmp/base.tsv
baseline recorded: go:/demo = 80.0%                      # first sight → recorded, exit 0

[rogueone] bash scripts/coverage-ratchet.sh compare go:/demo 80.0 /tmp/base.tsv
coverage held: go:/demo = 80.0%                          # unchanged → exit 0

[rogueone] bash scripts/coverage-ratchet.sh compare go:/demo 71.5 /tmp/base.tsv
COVERAGE REGRESSED: go:/demo dropped 80.0% -> 71.5% (baseline held, not rewritten down)
# exit 1 — AND the baseline is NOT laundered down:
[rogueone] cat /tmp/base.tsv
go:/demo	80.0
```

**UAT:** a drop is exit 1 and the baseline file still reads `80.0`, never the regressed `71.5` — a regression
cannot quietly rewrite the bar it failed. Extractors fail **closed** (exit 2) if their tool is missing.

---

## #2 — Integration tier (black-box the live services) · `scripts/integration/*-blackbox.sh`

**Proves:** there was no test tier above unit — nothing asserted a request crosses into a running service and
comes back correct. Two black-boxes assert real responses against the **live deployed** services in-cluster.

### CLI walkthrough (RUN — the committed scripts, in throwaway in-cluster pods)

```
[mother|rogueone] kubectl run demo-guard -n weyland --rm -i --restart=Never --image=alpine:latest \
  --command -- sh -c 'apk add --no-cache bash curl >/dev/null; cat > /tmp/bb.sh; bash /tmp/bb.sh' \
  < scripts/integration/guard-blackbox.sh
OK — weyland-guard black-box: 5/5 assertions passed against http://weyland-guard.weyland.svc.cluster.local:8080

[mother|rogueone] kubectl run demo-dhrp -n data-mesh --rm -i --restart=Never \
  --image=docker.redpanda.com/redpandadata/redpanda:v24.2.7 \
  --command -- bash -c 'cat > /tmp/bb.sh; bash /tmp/bb.sh' \
  < scripts/integration/datahub-redpanda-blackbox.sh
OK — datahub<->redpanda: topic spine present and MAE/MCE consumers Stable on redpanda.data-mesh.svc.cluster.local:9092
```

**UAT:** the guard asserts real verdicts across all three hooks (an actorless act is **BLOCKED** by policy.gate;
the model hooks are contract-checked because they ship SHADOW — a fact the observation *corrected*, see B88
notes). DataHub asserts the MAE/MCE consumer groups are **Stable** on the Redpanda it was repointed onto — the
check the UI cannot make, since DataHub serves its catalog from Postgres+OpenSearch and a severed bus is
invisible there. In CI these run as `test-integration-guard` / `test-integration-datahub` (verified in
pipeline #41, green from real Woodpecker pods).

---

## #3 — Per-build image scan + delta · `scripts/supply-chain.sh vuln`

**Proves:** trivy ran only weekly, so a base-image CVE shipped and sat uncaught until Sunday. Now every pushed
image is scanned at build time — and, crucially, the scan reports the **delta vs the currently-deployed image**
(both scanned with the same DB, so CVE-disclosure drift is controlled out): the absolute count is dominated by
unchanged base-image CVEs and tells you nothing about safety; the delta tells you what *this change* adds.

### CLI walkthrough (RUN — real CI build, pipeline #47)

From the `build` step log of a real pipeline run:

```
OK — SBOM written for registry.weyland.lab/weyland-dagster-user-code:git-... (cyclonedx + spdx)
OK — no licence findings for registry.weyland.lab/weyland-dagster-user-code:git-...
OK — vuln scan registry.weyland.lab/weyland-dagster-user-code:git-...: 327 finding(s) [CRITICAL 12 · HIGH 73]
     — Δ vs deployed: no new CVEs introduced by this change — reported, non-blocking
...
[build] done — 5 image(s) pushed.       # feast 169 · flink 314 · flink-py 3088 · scan-suite 2082 — all Δ: no new CVEs
```

**UAT:** the `Δ vs deployed` phrasing (not "absolute count only", not "BROKEN") confirms each baseline image was
pulled, scanned, and diffed. "No new CVEs" is correct — this change touched only scripts/docs, not any
Dockerfile — so the delta is 0; a change that added a CVE flips this to a loud `⚠ VULN DELTA` naming it. The scan
is **non-fatal** (a base-image CVE count is a signal, not a merge blocker); only a scan that could not run is exit 2.

**Woodpecker UI** — <https://woodpecker.weyland.lab> → weyland-lab → the `build` step of a recent run shows the
per-image SBOM/vuln/delta lines above.

---

## #4 — Post-deploy verification (Ready ≠ works) · `scripts/ship-images.sh` `txn_ok`

**Proves:** the ship loop checked "pod Ready," but a `/ready` 200 is byte-identical whether the service works or
not. `txn_ok` runs a real transaction per shipped service, in-cluster. This bucket added the tool-server: the RAG
path must **retrieve**, not merely be live.

### CLI walkthrough (RUN — the committed txn against the live cluster)

```
[rogueone] SHIP_IMAGES_LIB=1 source scripts/ship-images.sh
[rogueone] POD="$(txn_pod)"; txn_tool_server "$POD"
TXN_OK
```

**UAT:** `txn_tool_server` POSTs a real `/context/search` and asserts the `results` array is **non-empty** — a
`/ready` 200 over an empty or unbuilt index would pass the probe but fail this, and it *also* verifies the
endpoint-less `rag-index` loader Job landed. `weyland-dagster-base` routes to `txn_dagster` (it deploys the
webserver that transaction hits). Services with no transaction (Jobs) are **named as unchecked**, never silently
passed.

---

## #5 — Feature-flag deploy gate · `scripts/ship-images.sh` `ship_flag_allows`

**Proves:** Unleash was app-runtime only; nothing in the deploy path consulted a flag. Now an operator can HOLD
the whole rollout with a toggle — the N=1 substitute for canary/progressive delivery. Gated **before the PR
merge**, because every Argo app is `selfHeal: true`: gating the sync is futile (Argo reconverges on git HEAD in
~3min), so the only selfHeal-proof hold is to keep the new tag out of git.

### CLI walkthrough (RUN — the committed check reading the live Unleash flag, toggled)

```
[rogueone] SHIP_IMAGES_LIB=1 source scripts/ship-images.sh
flag ON  -> ALLOW      # ship_flag_allows: deploy proceeds
flag OFF -> HELD       # toggled weyland-ship-enabled OFF in Unleash → deploy held before merge (exit 3)
flag ON  -> ALLOW      # toggled back ON → proceeds
```

**UAT — UI walkthrough:** <https://unleash.weyland.lab> → `weyland-ship-enabled` → toggle it **OFF** in the
`development` environment; the next `ship-images.sh` run stops with `⏸ deploy HELD by the Unleash flag …`, leaves
the PR **open**, and deploys nothing (exit 3). Toggle **ON** to release. **Fail-open:** an absent flag or an
unreachable Unleash proceeds — a flag service never blocks deploys. The flag is left **ON** (deploys proceed).

---

## #6 — CI toolchain caching · `k8s/woodpecker/ci-caches.yaml` + `.woodpecker.yml`

**Proves:** every lane reinstalled its toolchain per run — `cargo install` compiled cargo-llvm-cov/audit/deny from
source, maven re-downloaded plugins, and (since #3) the 109 MB trivy DB re-downloaded every build. Five persistent
cache PVCs (mounted per-lane at each toolchain's cache dir) fix it. Requires the repo's `trusted.volumes` in
Woodpecker (a server-side setting `woodpecker-cli lint` cannot see — the lint-vs-server gap again).

### CLI walkthrough (RUN — cold populate vs warm reuse, real CI)

Two consecutive real pipeline runs, cold (#49, empty caches) then warm (#50, populated):

```
lane          cold(#49)  warm(#50)
scan-rust        125s        6s      ~20x — cargo no longer recompiles cargo-audit/cargo-deny
test-rust         52s        8s      ~6x  — cargo-llvm-cov cached
test-java         68s       19s      ~3.6x — maven plugins cached
test-go           18s        8s      go modules + build cache
build            682s      370s      -312s — trivy vuln DB not re-downloaded
```

**UAT:** ~9 min saved on the warm run, both green. `kubectl get pvc -n woodpecker` shows `ci-cache-{cargo,maven,
trivy,go,npm}` **Bound**. The repo carries `trusted.volumes:true` in Woodpecker (the operator already had the
stronger `trusted.security:true`, so this is a consistent least-privilege increment; `trusted.network` stays false).

## UI walkthrough — the map

<https://edtbl76.github.io/weyland-lab/> is internal; open `docs/ci-architecture-map.html` (23 steps): the
**integration lanes** (1f), the **build → sign → vuln + Δ** step, and the CD **ship loop** card (the Unleash
kill-switch → 3-condition merge gate → per-service transaction). **UAT:** confirm it renders in both themes and
the step count reads 23.

## Teardown

Read-only against live infra except: #1 writes `/tmp/base.tsv` (`rm -f /tmp/base.tsv`); #2 uses `--rm` throwaway
pods (auto-removed); #5 toggles `weyland-ship-enabled` and **restores it ON** in the same run. No durable state
is created. The `weyland-ship-enabled` flag itself is intentionally durable (the deploy kill-switch) and left ON.
