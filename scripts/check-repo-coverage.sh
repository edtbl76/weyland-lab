#!/usr/bin/env bash
# check-repo-coverage.sh — B138 repo-coverage-parity drift guard.
#
# The lab's repo-watching lanes each grew their own repo list; they diverged silently (1..6 repos, a stale
# repo still cataloged, two active repos watched nowhere). This guard reconciles every lane against the ONE
# canonical source of truth, `repos.yaml`, and FAILS when an ENFORCED lane drifts from it. Same posture as
# check-app-registry.sh / check-port-iac-coverage.sh: the guard, not a periodic human sweep, is what catches
# this class.
#
# ENFORCE MODEL: `repos.yaml` `enforce:` lists the lanes that hard-fail CI. A lane not in that list is still
# checked and its gaps REPORTED (onboarding-pending), but does not fail — so the guard ships incrementally as
# each lane reaches parity. A lane is "covered" for a repo when the lane's central config lists that repo AND
# the repo's `lanes.<lane>` is true in the SoT; a repo present in a lane's config but NOT expected there (e.g.
# a stale/retired repo) is an over-coverage failure just as much as a missing one.
#
# FAIL-CLOSED: an unreadable repos.yaml, a missing lane config, or an unparseable input is exit 2 (guard broken),
# never a silent pass. Exit 0 = enforced lanes in parity; exit 1 = an enforced lane drifted; exit 2 = guard broken.
#
# Test seams (override any path for bats fixtures):
#   REPOS_YAML, PR_STALENESS_FILE, PR_RECONCILE_FILE, PORT_INTEGRATIONS_FILE, TOFU_GITHUB_DIR, SCAN_SUITE_FILE,
#   BACKUP_CONF_FILE, WOODPECKER_REPOS_JSON ({"<repo>": "active"|"inactive"|"unknown"}), WOODPECKER_URL
#
# The ci lane is the ONE lane read over the network (Woodpecker activation, anonymous — no secret); every other
# lane is pure file analysis. Unreachable Woodpecker = exit 2. See docs/runbooks/repo-coverage.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_YAML="${REPOS_YAML:-$ROOT/repos.yaml}"
PR_STALENESS_FILE="${PR_STALENESS_FILE:-$ROOT/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/pr-staleness.yaml}"
PR_RECONCILE_FILE="${PR_RECONCILE_FILE:-$ROOT/scripts/check-pr-lifecycle.sh}"
PORT_INTEGRATIONS_FILE="${PORT_INTEGRATIONS_FILE:-$ROOT/nodes/mother/lab/weyland-platform/tofu/port/b137_integrations.tf}"
TOFU_GITHUB_DIR="${TOFU_GITHUB_DIR:-$ROOT/nodes/mother/lab/weyland-platform/tofu/github}"
SCAN_SUITE_FILE="${SCAN_SUITE_FILE:-$ROOT/nodes/mother/lab/weyland-platform/k8s/code-quality/scan-suite.yaml}"
BACKUP_CONF_FILE="${BACKUP_CONF_FILE:-$ROOT/nodes/rogueone/backup/backup-repos.conf}"

[ -r "$REPOS_YAML" ] || { echo "❌ guard broken: cannot read SoT $REPOS_YAML" >&2; exit 2; }

REPOS_YAML="$REPOS_YAML" \
PR_STALENESS_FILE="$PR_STALENESS_FILE" \
PR_RECONCILE_FILE="$PR_RECONCILE_FILE" \
PORT_INTEGRATIONS_FILE="$PORT_INTEGRATIONS_FILE" \
TOFU_GITHUB_DIR="$TOFU_GITHUB_DIR" \
SCAN_SUITE_FILE="$SCAN_SUITE_FILE" \
BACKUP_CONF_FILE="$BACKUP_CONF_FILE" \
python3 - <<'PY'
import os, re, sys, glob

def die_broken(msg):
    print(f"❌ guard broken: {msg}", file=sys.stderr); sys.exit(2)

try:
    import yaml
except Exception as e:
    die_broken(f"pyyaml unavailable: {e}")

def read(path, required=True):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        if required: die_broken(f"cannot read {path}: {e}")
        return ""

sot_path = os.environ["REPOS_YAML"]
try:
    sot = yaml.safe_load(read(sot_path)) or {}
except Exception as e:
    die_broken(f"cannot parse {sot_path}: {e}")

repos = sot.get("repos")
if not repos:
    die_broken(f"{sot_path} declares no repos")
enforce = set(sot.get("enforce", []))

# canonical repo names + per-lane expected sets from the SoT
ALL_LANES = ["iac", "ci", "scan", "pr", "catalog", "backup"]
names = [r["name"] for r in repos]
expected = {lane: set() for lane in ALL_LANES}
status = {}
for r in repos:
    status[r["name"]] = r.get("status", "active")
    lanes = r.get("lanes", {})
    for lane in ALL_LANES:
        if lanes.get(lane) is True:
            expected[lane].add(r["name"])

def strip_owner(tok):
    return tok.split("/", 1)[1] if "/" in tok else tok

# --- actual sets per lane, from each lane's central config ---------------------------------
actual = {}

# pr — the REPOS="${PR_REPOS:-...}" default in pr-staleness.yaml
txt = read(os.environ["PR_STALENESS_FILE"])
m = re.search(r'REPOS="\$\{PR_REPOS:-([^}]*)\}"', txt)
if not m: die_broken("could not find REPOS=\"${PR_REPOS:-...}\" in pr-staleness config")
actual["pr"] = {strip_owner(t) for t in m.group(1).split()}

# catalog — the repository selector `.name | IN("a","b",...)` in the Port integration
txt = read(os.environ["PORT_INTEGRATIONS_FILE"])
m = re.search(r'\.name \| IN\(([^)]*)\)', txt)
if not m: die_broken("could not find `.name | IN(...)` repository selector in Port integration")
actual["catalog"] = set(re.findall(r'\\"([^"\\]+)\\"', m.group(1)))

# iac — github_repository resources in tofu/github/*.tf
iac = set()
for tf in glob.glob(os.path.join(os.environ["TOFU_GITHUB_DIR"], "*.tf")):
    body = read(tf, required=False)
    for block in re.findall(r'resource\s+"github_repository"\s+"[^"]+"\s*\{(.*?)\n\}', body, re.S):
        nm = re.search(r'\bname\s*=\s*"([^"]+)"', block)
        if nm: iac.add(nm.group(1))
actual["iac"] = iac

# scan — the code-scan suite's SCAN_REPOS env (the repos scan-all.sh loops over). B138 generalized the suite
# from weyland-lab-only to all scan:true repos; this list is what the guard reconciles against the SoT.
txt = read(os.environ["SCAN_SUITE_FILE"], required=False)
m = re.search(r'name:\s*SCAN_REPOS\s*\n\s*value:\s*"([^"]+)"', txt)
actual["scan"] = set(m.group(1).split()) if m else set()

# backup — the restic allow-list is CHECKOUT PATHS, not names; a repo is covered when its SoT `backup_path`
# is present as a line. Matched by PATH because a checkout folder can differ from the repo name (freejack
# lives under ~/Documents/Education), which name-matching would silently miss.
conf = read(os.environ["BACKUP_CONF_FILE"], required=False)
conf_paths = {ln.strip() for ln in conf.splitlines() if ln.strip() and not ln.strip().startswith("#")}
declared_bp = {r["name"]: r.get("backup_path") for r in repos}
bk = {n for n, bp in declared_bp.items() if bp and bp in conf_paths}
actual["backup"] = bk
orphan_bp = sorted(p for p in conf_paths if p not in set(filter(None, declared_bp.values())))

# ci — Woodpecker ACTIVATION per repo (2026-09-24). Until then `ci: true` was an unchecked claim: 7 of 9 repos
# said it and had no pipeline. Activation is read with an ANONYMOUS lookup (no secret — repo-guards stays
# secret-free): 200 + active:true = activated; 404, or 401 on a PUBLIC repo = not activated. A PRIVATE repo
# answers 401 whether activated or not, so it is "unknown" — acceptable only when the SoT says ci:false (nothing
# is being claimed); a ci:true claim that cannot be verified is exit 2. Fixture seam: WOODPECKER_REPOS_JSON =
# {"<repo>": "active"|"inactive"|"unknown"}, which must answer for EVERY SoT repo.
import json, urllib.request, urllib.error
owner_default = sot.get("owner_default", "edtbl76")

def wp_state_live(base, r):
    url = f"{base}/api/repos/lookup/{r.get('owner', owner_default)}/{r['name']}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            body = json.load(resp)
            return "active" if body.get("active") is True else "inactive"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "inactive"
        if e.code == 401:
            return "unknown" if r.get("visibility") == "private" else "inactive"
        die_broken(f"Woodpecker lookup of {r['name']} returned HTTP {e.code}")
    except Exception as e:
        die_broken(f"Woodpecker lookup of {r['name']} failed: {e}")

def wp_base():
    cands = [os.environ["WOODPECKER_URL"]] if os.environ.get("WOODPECKER_URL") else \
        ["http://woodpecker-server.woodpecker.svc.cluster.local", "http://mother:30980"]
    for c in cands:
        try:
            with urllib.request.urlopen(f"{c}/healthz", timeout=5) as resp:
                if resp.status in (200, 204):
                    return c
        except Exception:
            continue
    die_broken(f"Woodpecker unreachable at {', '.join(cands)} — cannot verify the ci lane")

fx = os.environ.get("WOODPECKER_REPOS_JSON")
if fx:
    try:
        wp = json.loads(read(fx))
    except Exception as e:
        die_broken(f"cannot parse WOODPECKER_REPOS_JSON: {e}")
    unanswered = [n for n in names if n not in wp]
    if unanswered:
        die_broken(f"WOODPECKER_REPOS_JSON does not answer for: {', '.join(unanswered)}")
else:
    base = wp_base()
    wp = {r["name"]: wp_state_live(base, r) for r in repos}
unverifiable = sorted(n for n in expected["ci"] if wp.get(n) == "unknown")
if unverifiable:
    die_broken(f"ci:true claimed but Woodpecker activation is unverifiable anonymously (private repo): "
               f"{', '.join(unverifiable)}")
actual["ci"] = {n for n, st in wp.items() if st == "active"}

# --- compare ------------------------------------------------------------------------------
fail = 0
print(f"repo-coverage: {len(names)} canonical repos, enforcing lanes {sorted(enforce) or '[]'}")
for lane in ALL_LANES:
    exp = expected[lane]
    act = actual[lane]
    enforced = lane in enforce
    tag = "ENFORCED" if enforced else "pending "
    missing = sorted(exp - act)      # expected here but absent
    extra   = sorted(act - exp)      # present here but NOT expected (stale/retired lingering, or off-SoT)
    if not missing and not extra:
        print(f"  [{tag}] {lane:8} — ✓ parity ({len(exp)} repos)")
        continue
    verb = "❌" if enforced else "•"
    if missing: print(f"  [{tag}] {lane:8} — {verb} missing: {', '.join(missing)}")
    if extra:   print(f"  [{tag}] {lane:8} — {verb} unexpected: {', '.join(extra)}")
    if enforced:
        fail = 1

# pr lane has TWO consumers — pr-staleness (surface) AND pr-lifecycle-reconcile (resolve, 2026-09-23). Both must
# carry the IDENTICAL repo set, or the two watchers silently disagree on what they cover. The loop above checked
# staleness's REPOS; this checks the reconcile script's REPOS default against the SoT pr-lane too.
rec_txt = read(os.environ["PR_RECONCILE_FILE"])
m = re.search(r'REPOS="\$\{PR_REPOS:-([^}]*)\}"', rec_txt)
if not m:
    die_broken("could not find REPOS=\"${PR_REPOS:-...}\" in the reconcile script")
actual_pr_recon = {strip_owner(t) for t in m.group(1).split()}
exp_pr = expected["pr"]
enf_pr = "pr" in enforce
tag = "ENFORCED" if enf_pr else "pending "
missing = sorted(exp_pr - actual_pr_recon)
extra   = sorted(actual_pr_recon - exp_pr)
if not missing and not extra:
    print(f"  [{tag}] pr(recon) — ✓ parity ({len(exp_pr)} repos)")
else:
    verb = "❌" if enf_pr else "•"
    if missing: print(f"  [{tag}] pr(recon) — {verb} missing: {', '.join(missing)}")
    if extra:   print(f"  [{tag}] pr(recon) — {verb} unexpected: {', '.join(extra)}")
    if enf_pr:
        fail = 1

# backup allow-list is repo-only: a checkout path no SoT repo claims is a backed-up repo that isn't tracked.
if orphan_bp:
    enf = "backup" in enforce
    mark = "❌" if enf else "•"
    print(f"  [{'ENFORCED' if enf else 'pending '}] backup   — {mark} orphan path(s) not claimed by any repos.yaml backup_path: {', '.join(orphan_bp)}")
    if enf:
        fail = 1

if fail:
    print("\n❌ an ENFORCED lane drifted from repos.yaml — reconcile it or fix the SoT.", file=sys.stderr)
    sys.exit(1)
print("\n✓ all enforced lanes in parity with repos.yaml (pending lanes reported above).")
PY
