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
#   REPOS_YAML, PR_STALENESS_FILE, PORT_INTEGRATIONS_FILE, TOFU_GITHUB_DIR, SCAN_PY_FILE, BACKUP_CONF_FILE
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_YAML="${REPOS_YAML:-$ROOT/repos.yaml}"
PR_STALENESS_FILE="${PR_STALENESS_FILE:-$ROOT/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/pr-staleness.yaml}"
PORT_INTEGRATIONS_FILE="${PORT_INTEGRATIONS_FILE:-$ROOT/nodes/mother/lab/weyland-platform/tofu/port/b137_integrations.tf}"
TOFU_GITHUB_DIR="${TOFU_GITHUB_DIR:-$ROOT/nodes/mother/lab/weyland-platform/tofu/github}"
SCAN_PY_FILE="${SCAN_PY_FILE:-$ROOT/nodes/mother/lab/weyland-platform/services/scan-suite/scan.py}"
BACKUP_CONF_FILE="${BACKUP_CONF_FILE:-$ROOT/nodes/rogueone/backup/backup-repos.conf}"

[ -r "$REPOS_YAML" ] || { echo "❌ guard broken: cannot read SoT $REPOS_YAML" >&2; exit 2; }

REPOS_YAML="$REPOS_YAML" \
PR_STALENESS_FILE="$PR_STALENESS_FILE" \
PORT_INTEGRATIONS_FILE="$PORT_INTEGRATIONS_FILE" \
TOFU_GITHUB_DIR="$TOFU_GITHUB_DIR" \
SCAN_PY_FILE="$SCAN_PY_FILE" \
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

# scan — the central orchestrator target (scan.py TARGET). Single-repo today by design.
txt = read(os.environ["SCAN_PY_FILE"], required=False)
m = re.search(r'^TARGET\s*=\s*"([^"]+)"', txt, re.M)
actual["scan"] = {m.group(1)} if m else set()

# backup — local checkout paths in backup-repos.conf; match basenames case-insensitively to repo names
conf = read(os.environ["BACKUP_CONF_FILE"], required=False)
basenames = [ln.strip().rstrip("/").split("/")[-1].lower()
             for ln in conf.splitlines() if ln.strip() and not ln.strip().startswith("#")]
bk = set()
for n in names:
    key = n.lower()
    if key in basenames or (key == "weyland-lab" and "weyland" in basenames):
        bk.add(n)
actual["backup"] = bk

# ci — configured by a .woodpecker.yml inside each repo (+ Woodpecker server activation); not centrally visible.
actual["ci"] = None  # reported as checklist, never guard-compared

# --- compare ------------------------------------------------------------------------------
fail = 0
print(f"repo-coverage: {len(names)} canonical repos, enforcing lanes {sorted(enforce) or '[]'}")
for lane in ALL_LANES:
    exp = expected[lane]
    act = actual[lane]
    enforced = lane in enforce
    tag = "ENFORCED" if enforced else "pending "
    if act is None:
        print(f"  [{tag}] {lane:8} — per-repo (.woodpecker.yml in each repo); verify via onboard-repo checklist")
        continue
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

if fail:
    print("\n❌ an ENFORCED lane drifted from repos.yaml — reconcile it or fix the SoT.", file=sys.stderr)
    sys.exit(1)
print("\n✓ all enforced lanes in parity with repos.yaml (pending lanes reported above).")
PY
