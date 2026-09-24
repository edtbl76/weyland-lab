#!/usr/bin/env bash
# onboard-repo.sh — B138 repo-onboarding capability.
#
# Given a repo declared in repos.yaml, print the EXACT, ordered steps to bring it to the coverage its SoT entry
# declares — the central edits, the per-repo files that live inside the target repo, and the manual grants
# (private-repo access, Woodpecker activation). It reads the same SoT the guard enforces, so "onboarded" and
# "passes check-repo-coverage.sh" mean the same thing. It is a GUIDE (prints steps), not an auto-editor — the
# central files are tofu/k8s config whose edits belong in a reviewed commit, not a sed run. This is the repo
# slice of B154's paved-path onboarding; keep them consistent.
#
# Usage: scripts/onboard-repo.sh <repo-name>   (the name must already exist in repos.yaml)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_YAML="${REPOS_YAML:-$ROOT/repos.yaml}"

repo="${1:-}"
[ -n "$repo" ] || { echo "usage: onboard-repo.sh <repo-name>  (must exist in repos.yaml)" >&2; exit 2; }
[ -r "$REPOS_YAML" ] || { echo "cannot read SoT $REPOS_YAML" >&2; exit 2; }

REPO="$repo" REPOS_YAML="$REPOS_YAML" python3 - <<'PY'
import os, sys
try:
    import yaml
except Exception as e:
    print(f"pyyaml unavailable: {e}", file=sys.stderr); sys.exit(2)

sot = yaml.safe_load(open(os.environ["REPOS_YAML"], encoding="utf-8")) or {}
name = os.environ["REPO"]
entry = next((r for r in sot.get("repos", []) if r["name"] == name), None)
if entry is None:
    have = ", ".join(r["name"] for r in sot.get("repos", []))
    print(f"'{name}' is NOT in repos.yaml. Add it there FIRST (the SoT is the source of truth), then re-run.\n"
          f"  known repos: {have}", file=sys.stderr)
    sys.exit(1)

owner = entry.get("owner", sot.get("owner_default", "edtbl76"))
vis = entry.get("visibility", "public")
lanes = entry.get("lanes", {})
enforce = set(sot.get("enforce", []))

# per-lane onboarding instructions (kind: central | in-repo | manual)
STEPS = {
    "catalog": ("central", "Add \"{n}\" to BOTH `.name | IN(...)` and `.base.repo.name | IN(...)` queries in "
                            "nodes/mother/lab/weyland-platform/tofu/port/b137_integrations.tf, then `tofu apply`."),
    "pr":      ("central", "Add `{owner}/{n}` to the REPOS default in "
                           "nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/pr-staleness.yaml (and its bats test)."),
    "backup":  ("central", "Add the repo's LOCAL checkout path on rogueone to nodes/rogueone/backup/backup-repos.conf "
                           "(one path per line, ~ expands to $HOME)."),
    "iac":     ("central", "`tofu import github_repository.{slug} {n}` into nodes/.../tofu/github/, then codify the "
                           "imported state as a github_repository resource (NEVER hand-guess settings — import first)."),
    "scan":    ("in-repo", "Add .deepsource.toml + .coderabbit.yaml + .sourcery.yaml to the {n} repo, AND generalize "
                           "the central scan orchestrators (scan-suite.yaml / sonar-scan.yaml / scan.py) to iterate repos.yaml."),
    "ci":      ("in-repo", "Add a .woodpecker.yml to the {n} repo AND activate it in Woodpecker "
                           "(woodpecker-cli repo add {owner}/{n}); server-side, not in this tree."),
}
ORDER = ["catalog", "pr", "backup", "iac", "scan", "ci"]

print(f"Onboarding {owner}/{name}  (visibility: {vis}, status: {entry.get('status','active')})\n")
if vis == "private":
    print("⚠ PRIVATE REPO — before the catalog/pr lanes will see it you MUST grant access:")
    print("   • the Port github-ocean integration's GitHub token → read on this repo")
    print("   • the pr-lifecycle PAT (sealed secret pr-lifecycle-github/token) → `Pull requests: read` on this repo")
    print("   • any scan/CI tokens that will touch it\n")

# Linear project (check G of check-linear-sync.sh): every ACTIVE repo maps 1:1 to a Linear Project.
# repos ⊆ projects — a repo without one fails Pillar 5. `stale` repos need none until reactivated.
if entry.get("status", "active") == "active":
    lp = entry.get("linear_project")
    print("Linear project (every active repo maps 1:1 — ENFORCED by check-linear-sync.sh check G):")
    if lp:
        print(f"   • already mapped → \"{lp}\". Confirm it resolves: `bash scripts/check-linear-sync.sh --list`.\n")
    else:
        print("   • CREATE a Linear Project (team EMA, lead you) for this repo — add a GitHub link resource —")
        print("     then add `linear_project: \"<Project Name>\"` to this repo's entry in repos.yaml.")
        print("     Linear MCP: save_project(name=\"<Project Name>\", addTeams=[\"EMA\"], lead=\"me\","
              " links=[{url, title}]).\n")
    # Initiative (check H): initiatives drive scope, so the project must sit in EXACTLY one initiative.
    print("Linear initiative (every live project in EXACTLY one — ENFORCED by check-linear-sync.sh check H):")
    print("   • attach the project to its initiative (Lab & Systems ONLY if docs/backlog.md governs its work —")
    print("     that membership is what puts its issues in the weyland B-number checks; otherwise Music Studio /")
    print("     Helper Tools / Learning / My Work / Health and Fitness, or a new initiative).")
    print("     Linear MCP: save_project(id=\"<project>\", addInitiatives=[\"<Initiative>\"]).\n")

want = [l for l in ORDER if lanes.get(l) is True]
skip = [l for l in ORDER if lanes.get(l) is not True]
print("Lanes this repo should join (from repos.yaml):")
for l in want:
    kind, tmpl = STEPS[l]
    enf = "ENFORCED by check-repo-coverage.sh" if l in enforce else "pending (guard reports, does not block)"
    print(f"\n  [{l}] ({kind}; {enf})")
    print("    " + tmpl.format(n=name, owner=owner, slug=name.replace('-', '_').replace('.', '_')))
if skip:
    print("\nLanes intentionally skipped (lanes.<x> not true — keep a reasoned `except` note in repos.yaml): "
          + ", ".join(skip))
print("\nWhen done: `bash scripts/check-repo-coverage.sh` — enforced lanes must show ✓ parity;")
print("           `bash scripts/check-linear-sync.sh` — check G must map this repo to a live project,")
print("           and check H must find that project in exactly one initiative.")
PY
