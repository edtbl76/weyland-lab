"""What did this scan find that the last one didn't? (2026-10-15)

The DoD Pillar 7 gate is "triage NEW critical/high", but a repo's standing totals (weyland-lab: hundreds of OSV and
kubescape highs) bury a new one. This diffs two archived runs of the code-scan-suite, per tool, on the critical/high
findings only, keyed on what identifies a finding (file, package, rule or CVE: never a line number, which moves).

usage:  python3 scripts/scan-diff.py <old-run> <new-run>
        a run is an archive prefix under s3://scan-reports/, e.g. 2026-10-14T19-18-00Z (one per repo per run;
        run-scan-suite.sh prints each repo's). Exit 0 nothing new · 1 new critical/high findings, listed · 2 could not
        compare (a report missing or unreadable in either run: an unreadable report is not "nothing new").
Runbook: docs/runbooks/code-quality.md.
"""
import json
import sys
import urllib.request

BASE = "https://s3.weyland.lab/scan-reports/"
HIGH = ("CRITICAL", "HIGH")


def trivy(d):
    out = set()
    for r in d.get("Results") or []:
        t = r.get("Target")
        out |= {(v["Severity"], t, v.get("PkgName"), v.get("VulnerabilityID"))
                for v in r.get("Vulnerabilities") or [] if v.get("Severity") in HIGH}
        out |= {(m["Severity"], t, m.get("ID")) for m in r.get("Misconfigurations") or [] if m.get("Severity") in HIGH}
        out |= {(s["Severity"], t, s.get("RuleID")) for s in r.get("Secrets") or [] if s.get("Severity") in HIGH}
    return out


def osv(d):
    return {(r["source"]["path"], p["package"]["name"], v["id"])
            for r in d.get("results") or [] for p in r.get("packages") or [] for v in p.get("vulnerabilities") or []}


def bandit(d):
    return {(x["filename"], x["test_id"]) for x in d.get("results") or [] if x.get("issue_severity") == "HIGH"}


def semgrep(d):
    return {(x["path"], x["check_id"]) for x in d.get("results") or [] if x["extra"].get("severity") == "ERROR"}


def hadolint(d):
    return {(x["file"], x["code"]) for x in d if x.get("level") == "error"} if isinstance(d, list) else set()


def gitleaks(d):
    return {(x["File"], x["RuleID"]) for x in d} if isinstance(d, list) else set()


def kubescape(d):
    controls = (d.get("summaryDetails") or {}).get("controls") or {}
    return {(r["resourceID"], c["controlID"]) for r in d.get("results") or [] for c in r.get("controls") or []
            if (c.get("status") or {}).get("status") == "failed"
            and (controls.get(c["controlID"]) or {}).get("scoreFactor", 0) >= 7}


TOOLS = {"trivy.json": trivy, "osv.json": osv, "bandit.json": bandit, "semgrep.json": semgrep,
         "hadolint.json": hadolint, "gitleaks.json": gitleaks, "kubescape.json": kubescape}


def fetch(run, name):
    # Verified TLS: rogueone trusts the lab CA (mkcert), so no verification bypass is needed.
    with urllib.request.urlopen(f"{BASE}{run.rstrip('/')}/{name}", timeout=120) as r:
        return json.load(r)


def diff(old, new):
    """{tool: (added, removed_count)} for every tool; raises if a report can't be read."""
    return {name: (sorted(fn(new[name]) - fn(old[name])), len(fn(old[name]) - fn(new[name])))
            for name, fn in TOOLS.items()}


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        old = {n: fetch(argv[1], n) for n in TOOLS}
        new = {n: fetch(argv[2], n) for n in TOOLS}
    except Exception as e:   # any unreadable report: we can't say "nothing new"
        print(f"CANNOT COMPARE: {e}", file=sys.stderr)
        return 2
    added_any = False
    for name, (added, removed) in diff(old, new).items():
        print(f"{name.removesuffix('.json')}: {len(added)} new, {removed} gone")
        for a in added:
            print("   +", " | ".join(str(x) for x in a))
        added_any |= bool(added)
    return 1 if added_any else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
