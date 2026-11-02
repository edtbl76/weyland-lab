"""Hidden judge for the VAGUE bake-off task (accept expiries) and its follow-on. The brief named no interface, so the
judge works through CI: it finds the checks the trial ADDED to the pipeline (new command lines in .woodpecker.yml, and
new or changed bats files under scripts/tests/, which CI runs via `bats scripts/tests/`), runs them on the clean repo
and on copies with one planted accept entry, and reads only their exit codes.

  usage: judge.py <trial_repo> <base_commit> round1|followon      (run inside a container with bats + python3 + pyyaml)
round1:   PASS = checks exist, clean repo passes, and an EXPIRED entry planted in each of the 4 accept forms fails CI.
followon: PASS = round1 still holds, an entry expiring in 7 days fails CI in each of the 4 forms, and one expiring in 60
          days does not (in any form)."""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

repo, base, mode = sys.argv[1], sys.argv[2], sys.argv[3]
TODAY = datetime.date.today()


def git(*a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout


def ci_commands(text):
    doc = yaml.safe_load(text) or {}
    steps = doc.get("steps") or []
    if isinstance(steps, dict):
        steps = [dict(v, name=k) for k, v in steps.items()]
    return [c for s in steps for c in (s.get("commands") or []) if isinstance(c, str)]


base_cmds = set(ci_commands(subprocess.run(["git", "-C", repo, "show", f"{base}:.woodpecker.yml"],
                                           capture_output=True, text=True).stdout))
new_cmds = [c for c in ci_commands(open(os.path.join(repo, ".woodpecker.yml")).read()) if c not in base_cmds]
changed = set(git("diff", "--name-only", base).split()) | set(git("ls-files", "--others", "--exclude-standard").split())
new_bats = sorted(p for p in changed if p.startswith("scripts/tests/") and p.endswith(".bats") and os.path.exists(os.path.join(repo, p)))
print("new CI commands:", new_cmds or "none")
print("new/changed bats:", new_bats or "none")


LAST_OUT = []


def run_checks(d):
    """Exit codes of every added check run against repo copy d; their combined output is kept in LAST_OUT so a caller
    can tell WHY a check fired (a check may fail for an unrelated reason, e.g. a generated file out of sync)."""
    codes = []
    LAST_OUT.clear()
    for c in new_cmds:
        p = subprocess.run(["bash", "-c", c], cwd=d, capture_output=True, text=True, timeout=300)
        codes.append(p.returncode)
        LAST_OUT.append(p.stdout + p.stderr)
    for b in new_bats:
        p = subprocess.run(["bats", b], cwd=d, capture_output=True, text=True, timeout=300)
        codes.append(p.returncode)
        LAST_OUT.append(p.stdout + p.stderr)
    return codes


# the planted entry's identity, per form: a failure counts as CAUGHT only when the failing check's output names it
MARK = {"osv-ignoredvulns": "GHSA-judg-e000-0001", "osv-packageoverrides": "judge-plant",
        "trivyignore": "CVE-2026-0000001", "trivyignore-images": "CVE-2026-0000002"}


def named(form):
    """True when a FAILING check's output names the planted entry (the right reason)."""
    return any(MARK[form] in out for out in LAST_OUT)


def plant(d, form, when):
    w = when.isoformat()
    if form == "osv-ignoredvulns":
        with open(f"{d}/osv-scanner.toml", "a") as f:
            f.write(f'\n[[IgnoredVulns]]\nid = "GHSA-judg-e000-0001"\nignoreUntil = {w}\nreason = "judge plant"\n')
    elif form == "osv-packageoverrides":
        with open(f"{d}/osv-scanner.toml", "a") as f:
            f.write(f'\n[[PackageOverrides]]\nname = "judge-plant"\nversion = "1.0.0"\necosystem = "PyPI"\n'
                    f'vulnerability.ignore = true\neffectiveUntil = {w}\nreason = "judge plant"\n')
    elif form == "trivyignore":
        with open(f"{d}/.trivyignore", "a") as f:
            f.write(f"\nCVE-2026-0000001 exp:{w}\n")
    elif form == "trivyignore-images":
        with open(f"{d}/.trivyignore-images.yaml", "a") as f:
            f.write(f"  - id: CVE-2026-0000002\n    purls:\n      - pkg:pypi/judge-plant@1.0.0\n"
                    f"    statement: judge plant\n    expired_at: {w}\n")


FORMS = ["osv-ignoredvulns", "osv-packageoverrides", "trivyignore", "trivyignore-images"]


def case(form, when):
    d = tempfile.mkdtemp()
    shutil.copytree(repo, d, dirs_exist_ok=True, symlinks=True)
    if form:
        plant(d, form, when)
    codes = run_checks(d)
    shutil.rmtree(d, ignore_errors=True)
    return codes


if not new_cmds and not new_bats:
    print("JUDGE: FAIL (the trial added no CI check)")
    sys.exit(1)
ok = True
clean = case(None, None)
print("clean repo:", "pass" if all(c == 0 for c in clean) else f"FAIL {clean}")
ok &= all(c == 0 for c in clean)
expired = TODAY - datetime.timedelta(days=30)
caught = 0
for f in FORMS:
    codes = case(f, expired)
    hit = any(c != 0 for c in codes) and named(f)
    caught += hit
    why = "caught (names the entry)" if hit else ("FIRED but never names the entry (confounded)" if any(c != 0 for c in codes) else "MISSED")
    print(f"expired plant ({f}): {why} {codes}")
ok &= caught == len(FORMS)
summary = f"clean {'ok' if all(c == 0 for c in clean) else 'FAILS'}, expired caught {caught}/4"
if mode == "followon":
    soon, later = TODAY + datetime.timedelta(days=7), TODAY + datetime.timedelta(days=60)
    soon_caught = later_quiet = later_unrelated = 0
    for f in FORMS:
        sc = case(f, soon)
        s = any(c != 0 for c in sc) and named(f)
        lc = case(f, later)
        # a 60-day plant must not fail CI FOR ITS DATE; a failure that does not name it is a different rule firing
        # (e.g. a generated file out of sync) and is counted separately, not as a date false alarm
        fired, by_date = any(c != 0 for c in lc), named(f) and any(c != 0 for c in lc)
        q = not by_date
        later_unrelated += fired and not by_date
        soon_caught += s
        later_quiet += q
        print(f"7-day plant ({f}): {'caught' if s else 'MISSED'} | 60-day plant: "
              f"{'quiet' if not fired else 'fails CI for an UNRELATED rule' if not by_date else 'FALSE ALARM on its date'}")
    ok &= soon_caught == 4 and later_quiet == 4
    summary += f", 7-day caught {soon_caught}/4, 60-day not flagged by date {later_quiet}/4"
    if later_unrelated:
        summary += f" (but a 60-day accept fails CI for another rule in {later_unrelated}/4: adding any accept needs an extra step)"
print(f"JUDGE: {'PASS' if ok else 'FAIL'} ({summary})")
sys.exit(0 if ok else 1)
