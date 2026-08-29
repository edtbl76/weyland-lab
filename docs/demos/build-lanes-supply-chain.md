# Demo — per-language build lanes + software supply chain (B88)

One hardcoded `pytest` step became **nine languages, three scan lanes, and a signed supply chain** —
and the interesting part is not the count, it is that every control had to *actually run* before it
was true. Each walkthrough below is a real command against the live repo or cluster; the numbers are
observed, not illustrative.

- **Flow:** [diagrams/flow-build-lanes.md](../diagrams/flow-build-lanes.md)
- **Runbook:** [runbooks/supply-chain.md](../runbooks/supply-chain.md) · **Registry:** repo-root `quality-tools.yaml`
- **Backlog:** B88 (Linear EMA-80)

## The point

The Python test lane named ONE service by path (`cd services/weyland-guard && pytest`), so a suite
added anywhere else was **never executed and sat green by absence**. The replacement discovers suites
by test file and reports three non-interchangeable outcomes — `0` fixture+projects passed, `1` a real
project failed, `2` the lane itself could not run. Every lane ships a hello-world fixture so a
language with no production code yet (Go, Rust) still executes a real test, and `--self-check` runs
each fixture's *deliberately failing* test to prove the runner propagates failure. A lane never seen
failing is not a lane.

## CLI walkthrough (RUN against the repo)

**1. Discovery keys on TESTS, not manifests.** The bug this replaced: keying on a manifest missed the
one suite CI runs (`weyland-guard` has `tests/` and no manifest) and matched five services that have a
manifest and no tests, where `pytest` exits 5.

```
bash scripts/run-lang-tests.sh python --list-roots
```

Expected: the fixture, then `project: .../services/weyland-guard` — the suite that was previously the
only thing running, now found by discovery rather than by a hardcoded path.

**2. Four archetypes, one runner.** TypeScript / JavaScript / React / Next.js are archetypes on one
node toolchain, not four toolchains:

```
for l in typescript javascript react nextjs; do echo "$l -> $(bash scripts/run-lang-tests.sh $l --print-runner)"; done
```

Expected: all four print `node`.

**3. Prove a lane can FAIL** (the most important step — a guard never seen failing is theatre):

```
WEYLAND_LANG_FIXTURE_DIR=/tmp/absent bash scripts/run-lang-tests.sh go ; echo "EXIT=$?"
```

Expected: `LANE BROKEN: no go fixture ...` and **`EXIT=2`** — the lane, not the estate. A missing
dependency (`pytest` exit 2/3/4) and a discovered-but-empty suite (exit 5) map to 2 as well; a real
test failure is 1. Conflating them makes a broken runner read exactly like broken code.

**4. The three registry runners agree with their implementations.** `quality-tools.yaml` is the
source of truth; this fails if any runner's script drifts from it:

```
bash scripts/check-quality-tools.sh
```

Expected: `OK — 21 scan-suite tools match scan.py, 13 lang-scan tools match run-lang-scan.sh, 5
supply-chain tools match supply-chain.sh.` Rust went from **0** registry entries to 4, Java from
SonarQube-only to 5, the JS/TS family from no linter to 5.

**5. A real SBOM** (needs `syft` — the runbook installs it):

```
WEYLAND_SBOM_DIR=/tmp/sb bash scripts/supply-chain.sh sbom alpine:3.19 && jq '.components|length' /tmp/sb/alpine_3.19.cyclonedx.json && jq '.packages|length' /tmp/sb/alpine_3.19.spdx.json
```

Expected: CycloneDX with **96** components and SPDX with **16** packages — both formats, because they
serve different consumers (CycloneDX → vuln tooling, SPDX → licence/compliance).

**6. The exit-code contract holds under real cosign.** No key must be `2` (could not run), an unsigned
image must be `1` (looked, it is unsigned) — never confused:

```
COSIGN_KEY= bash scripts/supply-chain.sh sign registry.weyland.lab/x:git-abc ; echo "no-key EXIT=$?"
```

Expected: `LANE BROKEN: COSIGN_KEY is unset ...` and **`EXIT=2`**. An unsigned image reported as
success is the whole failure mode signing exists to prevent.

**7. The Gatekeeper Rego is compiled AND exercised** — `kubeconform` skips Gatekeeper CRDs, so before
B88 no Rego in this repo had ever been validated. This compiles every ConstraintTemplate and runs the
signature constraint against real admission payloads:

```
docker run --rm -v "$PWD":/w -w /w python:3.12-slim sh -c 'pip install -q pyyaml >/dev/null; apt-get update -qq >/dev/null && apt-get install -y -qq curl >/dev/null; curl -sSfL -o /usr/local/bin/opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64_static >/dev/null; chmod +x /usr/local/bin/opa; sh scripts/ci/check-rego-policies.sh'
```

Expected: every policy compiles, then the behaviour cases — signed-registry admitted, foreign flagged,
istio sidecar admitted, **typosquat `docker.io/grafanaa/grafana` flagged**, **`attacker/evil` flagged**
(the bypass that a security review caught and that this repo's own tests had briefly blessed).

**8. The full shell suite** (the lanes' own tests + everything else):

```
docker run --rm --entrypoint sh -v "$PWD":/w -w /w bats/bats:latest -c 'apk add --no-cache python3 py3-yaml jq git >/dev/null 2>&1; cd /w/scripts/tests && bats .'
```

Expected: `310 tests, 0 failures`.

## UI walkthrough (eyes-on the live cluster)

**1. The signature policy is live in `dryrun`, and the audit reads zero.**

```
kubectl get k8simagesignature require-signed-images -o jsonpath='{.spec.enforcementAction}{" violations="}{.status.totalViolations}{"\n"}'
```

**UAT — confirm:**
- `enforcementAction` is **`dryrun`**. It must never be `deny` while any running image is unsigned —
  that would reject every workload on the next pod creation.
- `violations=0`. This is the *earned* zero: the first audit reported **270**, which surfaced two real
  gaps (istio sidecars, implicit Docker-Hub refs) and one bypass I had introduced. It reached zero
  only after 44 publishers were reviewed and allowlisted by prefix — so a future non-zero means an
  **unreviewed** image appeared, which is a signal worth having.

**2. The exemption list is a reviewed inventory, not a suppression list.**

```
kubectl get k8simagesignature require-signed-images -o jsonpath='{.spec.parameters.exemptImages}' | tr ',' '\n'
```

**UAT:** 49 entries, tiered VENDOR / COMMUNITY / SOLO in the source file. The `bitnamilegacy/` entry is
**absent** — it was removed not by trusting an unmaintained image but by eliminating it (DataHub moved
off the bundled broker onto Redpanda). The list shrinking is the proof.

**3. DataHub is healthy on Redpanda** (the migration that removed the unmaintained broker):

```
kubectl -n data-mesh exec redpanda-0 -c redpanda -- rpk group list | grep -E 'mae|mce|usage'
```

**UAT:** `generic-mae-consumer-job-client` and `generic-mce-consumer-job-client` read **Stable** — the
metadata-change consumers are live on Redpanda. Open `datahub.weyland.lab` and confirm the catalog
still answers (the source of truth is Postgres + OpenSearch, so it was never at risk; this confirms the
event path reconnected).

## Teardown

Steps 1–4 and 8 are read-only against the repo. Step 5 writes two SBOM files under `/tmp/sb`
(`rm -rf /tmp/sb`). Steps 6–7 create nothing that persists. The UI steps are read-only `kubectl` /
`rpk` queries. Nothing in this demo mutates the catalog, a secret, or the signing key.
