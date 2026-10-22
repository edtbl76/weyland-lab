# Demo: seeing the packages a Dockerfile installs (B213)

**What it proves:** every Python package a weyland image carries is visible to a scanner, and stays pinned.
- The scan suite scans the images the manifests actually deploy.
- Every Dockerfile installs from a lockfile.
- A ratchet in `repo-guards` keeps the count of direct `pip install`s at zero.

**Why it exists:** tool-server's `mcp==1.28.1` sat on a Dockerfile `pip install` line through GHSA-84m7-p3x7-pcfv.
The source scanners read requirements files, so they flagged the same package in other services and missed it there.
At the first count, 14 Dockerfiles installed 103 packages this way, and 80 of them were unpinned.

Flow: [flow-code-quality.md](../diagrams/flow-code-quality.md), the `trivy-images` path. Runbook:
[code-quality.md](../runbooks/code-quality.md).

## CLI walkthrough (run 2026-10-16)

### 1. The ratchet: zero direct installs, and it fails when one appears

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dockerfile-installs.sh
```

Expected (exit 0):
```
OK — 0 direct pip install(s) across 0 Dockerfile(s), none above its ceiling.
```

**Negative case:** a scratch tree outside the repo with one Dockerfile that installs two packages directly, against an
empty baseline.

[rogueone]
```
T=$(mktemp -d) && mkdir -p $T/nodes/svc && printf 'FROM python:3.12-slim\nRUN pip install fastapi uvicorn==0.30.0\n' > $T/nodes/svc/Dockerfile && : > $T/baseline && DOCKERFILE_INSTALLS_ROOT=$T DOCKERFILE_INSTALLS_BASELINE=$T/baseline bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dockerfile-installs.sh; echo "exit $?"
```

Expected (exit 1, naming the file):
```
  FAIL nodes/svc/Dockerfile: 2 direct pip install(s), baseline 0 (not in the baseline)
DOCKERFILE INSTALLS ABOVE THE RATCHET: 1 file(s). Move them into a pinned requirements file.
exit 1
```

**It cannot check** a tree with no Dockerfile at all, and says so (exit 2, never a clean tree):

[rogueone]
```
E=$(mktemp -d) && mkdir -p $E/nodes && DOCKERFILE_INSTALLS_ROOT=$E bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dockerfile-installs.sh; echo "exit $?"
```

Expected:
```
CANNOT CHECK: no Dockerfile under /tmp/tmp.XXXXXXXXXX/nodes — refusing to report a clean tree
exit 2
```

### 2. The scan suite scans the deployed images

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/run-scan-suite.sh
```

The run took 55 minutes, about 31 of them on weyland-lab. Its weyland-lab section includes:
```
  edtbl76/weyland-lab  trivy-images: 158C / 3313H / 13958M / 4087L (total 21516)
  edtbl76/weyland-lab  archive: 16 file(s) → s3://scan-reports/2026-10-16T16-29-54Z/ (90d ILM)
```

Which images it scanned, read from that run's archive:

[rogueone]
```
cd /home/edwardmangini/IdeaProjects/weyland && python3 -c "import importlib.util as u; s=u.spec_from_file_location('sd','scripts/scan-diff.py'); m=u.module_from_spec(s); s.loader.exec_module(m); d=m.fetch('2026-10-16T16-29-54Z','trivy-images.json'); print('images', len(d['images']), 'broken', d['broken'], 'missing', d['missing'])"
```

Expected: `images 23 broken [] missing []`. The 23 are every `registry.weyland.lab` image a `k8s/` manifest deploys
at its live tag. They include the hand-tagged ones `images.tsv` never lists: `weyland-agent:v9`,
`mcp-server-datahub:0.4`, `ray-head:v8` and `weyland-jupyter:v1`.

### 3. Compare against the previous run

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/scan-diff.py 2026-10-16T04-20-53Z 2026-10-16T16-29-54Z
```

Expected (exit 1: new findings exist):
```
trivy-images: baseline (15156 finding(s)); the previous run predates this scan, so there is nothing to compare yet
trivy: 8 new, 0 gone
osv: 114 new, 0 gone
bandit: 0 new, 0 gone
semgrep: 0 new, 0 gone
hadolint: 2 new, 0 gone
gitleaks: 0 new, 0 gone
kubescape: 0 new, 0 gone
```

The trivy and osv "new" findings are the point of B213: package versions that were already deployed, now visible
because their lockfiles exist. Their remediation is B214. The 2 hadolint findings were a scanner bug: its
`-iname 'Dockerfile*'` target list linted `dockerfile_installs.py` and `dockerfile-installs.bats`. It now matches
real Dockerfile names only (`tests/test_hadolint_targets.py`).

A run whose image scan failed has `broken` images, and `scan-diff.py` then exits 2 instead of comparing.
`tests/test_scan_diff.py` covers that case. The run itself fails too: `scan.py` exits 3 with an `!! SCAN DEFECT` line
naming the image, the Job fails without a retry, and `run-scan-suite.sh` exits 2 at once
(`tests/test_suite_verdict.py`, `scripts/tests/scan-all-runner.bats`, `scripts/tests/run-scan-suite.bats`). That
case cannot be forced live without breaking a deployed image; the tests carry it.

### 4. B214: the newly visible findings fixed or accepted (run 2026-10-17)

The fixes shipped as `git-cecd52fc` (PR #197; scan-suite, pyflink, Dagster) plus `mcp-server-datahub:0.5` and
`ray-head:v10`. Compare the next scan against the B213 re-scan:

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/scan-diff.py 2026-10-16T20-12-15Z 2026-10-17T02-38-33Z
```

Expected (exit 0: nothing new):
```
trivy: 0 new, 8 gone
osv: 0 new, 114 gone
bandit: 0 new, 0 gone
semgrep: 0 new, 0 gone
hadolint: 0 new, 0 gone
gitleaks: 0 new, 0 gone
kubescape: 0 new, 0 gone
trivy-images: 0 new, 26 gone
```

All 122 findings B213 made visible are gone: bumped where a fixed version installs, or accepted in `osv-scanner.toml`
with a reason and an expiry, per exact package version where it has no installable fix.

**Every requirements directory is watched by Dependabot**, and the guard fails when one is not:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-coverage.sh
```
```
OK — 23 requirements directories watched by Dependabot (excluded: golden-paths/, tests/lang/).
```

Negative cases, in a `mktemp -d` scratch tree: a requirements directory with no entry, then no config at all.

[rogueone]
```
T=$(mktemp -d) && mkdir -p $T/.github $T/svc/a && : > $T/svc/a/requirements.txt && printf 'version: 2\nupdates: []\n' > $T/.github/dependabot.yml && DEPENDABOT_ROOT=$T bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-coverage.sh; echo "exit $?"; rm -f $T/.github/dependabot.yml; DEPENDABOT_ROOT=$T bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-coverage.sh; echo "exit $?"
```
```
UNWATCHED: svc/a has requirements files but no pip entry in .github/dependabot.yml
1 of 1 requirements directory unwatched: an advisory against their pins never reaches a security PR. Add a pip entry for each.
exit 1
CANNOT CHECK: /tmp/tmp.XXXXXXXXXX/.github/dependabot.yml does not exist
exit 2
```

**A new upstream advisory against unchanged pins, end to end (RUN 2026-10-22).** The 2026-10-21 scan named certifi
GHSA-6q48-6c7w-9gw2 (CRITICAL: compromised emSign intermediates; fixed 2026.10.19) and 28 pillow advisories (fixed 13.0.0).
Every lockfile moved except two that fastembed caps at `pillow<13` (accepted per version, with a matching Dependabot
ignore). The proof is the running pods, not the lockfiles:
```
for spec in "weyland realm-of-agents" "weyland weyland-operator" "weyland weyland-tool-server" "weyland weyland-agent" "weyland nemo-guardrails" "weyland dagster-user-code" "weyland weyland-guard" "data-mesh feast-server" "weyland datahub-mcp"; do set -- $spec; c=$(kubectl -n $1 get deploy $2 -o jsonpath='{.spec.template.spec.containers[0].name}'); echo "$1/$2: $(kubectl -n $1 exec deploy/$2 -c $c -- python3 -c "import importlib.metadata as m
def g(p):
  try: return m.version(p)
  except Exception: return '-'
print('certifi', g('certifi'), 'pillow', g('pillow'))" | tail -1)"; done
```
```
weyland/realm-of-agents: certifi 2026.10.19 pillow 13.0.0
weyland/weyland-operator: certifi 2026.10.19 pillow 13.0.0
weyland/weyland-tool-server: certifi 2026.10.19 pillow -
weyland/weyland-agent: certifi 2026.10.19 pillow 13.0.0
weyland/nemo-guardrails: certifi 2026.10.19 pillow 12.3.0
weyland/dagster-user-code: certifi 2026.10.19 pillow -
weyland/weyland-guard: certifi 2026.10.19 pillow -
data-mesh/feast-server: certifi 2026.10.19 pillow -
weyland/datahub-mcp: certifi 2026.10.19 pillow -
```
(nemo-guardrails' 12.3.0 is the accepted cap.) **Negative control:** osv-scanner on the operator's lockfile as it was
before the change reports `{'certifi': 2}`, and 0 on the bumped one, so the scanner was reading the file, not skipping it.
**What the lockfiles could not show:** `ray-head:v10` ran certifi **2025.1.31**, older than either pin, because its
`requirements-ray-head.txt` never named certifi and the base image `rayproject/ray:2.56.0` supplies its own. It now pins
`certifi==2026.10.19` (`ray-head:v11`). Read a long-running hand-tagged image's packages live; a lockfile only covers what
it names.

**Every Dependabot ignore has a live reason behind it** (2026-10-22). An ignore blocks security updates for one package
in one directory and never expires, so the guard checks each one against `osv-scanner.toml` and the directory's pin:

[rogueone]
```
bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-ignores.sh
```
```
OK — 11 Dependabot ignore(s), each backed by a live osv-scanner.toml accept at the pinned version.
```

Negative case (RUN 2026-10-22), in a scratch tree: an ignore whose pin already moved past the cap, with no accept behind it.

[rogueone]
```
T=$(mktemp -d) && mkdir -p $T/.github $T/svc/a && printf 'pillow==13.0.0\n' > $T/svc/a/requirements.txt && printf 'version: 2\nupdates:\n  - package-ecosystem: "pip"\n    directory: "/svc/a"\n    ignore:\n      - dependency-name: "pillow"\n        versions: [">=13.0.0"]\n' > $T/.github/dependabot.yml && : > $T/osv-scanner.toml && DEPENDABOT_ROOT=$T bash /home/edwardmangini/IdeaProjects/weyland/scripts/check-dependabot-ignores.sh; echo "exit $?"
```
```
DEAD: svc/a ignores pillow >=13.0.0 but pins 13.0.0 — the cap is lifted, delete the ignore
UNBACKED: svc/a ignores pillow (pinned 13.0.0) with no osv-scanner.toml accept — add a [[PackageOverrides]] for pillow 13.0.0 with the reason, or delete the ignore
2 defect(s) in 1 Dependabot ignore(s): an ignore with no live reason blocks security updates silently.
exit 1
```

**A version-scoped accept suppresses only that version.** Two directories, protobuf 4.25.9 (overridden) and 4.23.4 (not),
scanned with the suite's own osv-scanner 1.9.1: only 4.23.4 is reported, with its 4 advisories. That is why
`osv-scanner.toml` uses `[[PackageOverrides]]` with `name` + `version` for pins that have no installable fix, and
`[[IgnoredVulns]]` by id only for an advisory that cannot apply anywhere.

**Port shows the re-scan** (checked by API 2026-10-17): `osv-scanner-weyland-lab` 973 → 859 high,
`trivy-weyland-lab` 71 → 63 high, `pip-audit-weyland-lab` 57 → 35 high, `trivy-images-weyland-lab` 3313 → 3301 high,
each `scannedAt` 2026-10-17T02:25–02:37Z.

### 5. B220: the 216 base-image findings fixed or accepted (run 2026-10-19)

The B218 DoD scan (`2026-10-17T21-25-35Z`) showed 216 new `trivy-images` HIGH/CRITICAL — new advisories against
unchanged images. B220 rebuilt six images, then had to fix the scanners themselves: the image scan applied no ignore
file, and osv-scanner v2 invented transitive versions. The final scan against the one that found the 216:

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/scripts/scan-diff.py 2026-10-17T21-25-35Z 2026-10-18T21-10-54Z
```
```
trivy: 0 new, 2 gone
osv: 0 new, 618 gone
bandit: 0 new, 0 gone
semgrep: 0 new, 0 gone
hadolint: 0 new, 0 gone
gitleaks: 0 new, 0 gone
kubescape: 0 new, 0 gone
trivy-images: 888 new, 8000 gone
exit 1
```
The 888 are **all MEDIUM** (the scan-diff lines: `+ MEDIUM | weyland-flink-py | libc6 | …`; 876 in Jupyter's new
Ubuntu 26.04 base) — 0 HIGH/CRITICAL. Against the morning re-scan the same command
(`2026-10-18T04-06-06Z 2026-10-18T21-10-54Z`) prints **0 new in every scanner** (osv 186 gone, trivy-images 77 gone),
exit 0.

**How the accepts are scoped.** `.trivyignore-images.yaml` holds 47 entries, every one with an `expired_at`, matched
by package URL (and by path for the adbc wheel), so an accept never hides the same CVE in another package or image;
`scan.py` passes it with `--ignorefile` (lines 318, 403). osv runs with `--no-resolve` (line 250): it grades the pins a
requirements file declares, and `trivy-images` grades what is actually installed.

**The gitleaks allowlist still catches a real secret.** gitleaks 8.30 found 111 reviewed false positives on a clean
tree, so `.gitleaks.toml` allows those exact paths. Negative case: a random `ghp_…` token planted in a scratch copy,
scanned with the suite's own gitleaks (`registry.weyland.lab/scan-suite:git-5999a4d6`) and the repo's allowlist,
output redacted:

[rogueone]
```
S=$(mktemp -d) && cp /home/edwardmangini/IdeaProjects/weyland/.gitleaks.toml $S/ && python3 -c "import secrets,string;print('TOKEN = \"ghp_'+''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(36))+'\"')" > $S/config.py && docker run --rm --user "$(id -u):$(id -g)" -v $S:/scan:ro --entrypoint gitleaks registry.weyland.lab/scan-suite:git-5999a4d6 dir /scan --config /scan/.gitleaks.toml --redact --no-banner; echo "exit=$?"
```
```
WRN leaks found: 1
exit=1
```
With `config.py` removed: `INF no leaks found`, exit 0.

## UI walkthrough + UAT

1. Open <https://app.port.io> → **Catalog** → **Security scans** (`security_scan`), search `trivy-images`.
   **Confirm:** the entity `trivy-images-weyland-lab` exists, with tool `trivy-images`, target `weyland-lab`,
   critical 158 · high 3313 · medium 13958 · low 4087, and `scannedAt` 2026-10-16T16:29:10Z. Checked by API on
   2026-10-16; a `202` from the ingest URL alone would not prove it.
2. Open **Catalog** → **Code Health**. **Confirm:** the critical, high and medium cards rose by the trivy-images
   counts. They sum every `security_scan` entity, and this is the first run with image findings in them.

## Cleanup

Read-only against the estate. The negative cases write only to `mktemp -d` scratch directories, outside the repo
(`rm -rf` them afterwards, or leave them to the OS's tmp cleanup). The scan's own archive expires under the bucket's 90-day lifecycle rule.
