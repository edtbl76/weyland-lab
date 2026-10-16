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
`tests/test_scan_diff.py` covers that case.

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
