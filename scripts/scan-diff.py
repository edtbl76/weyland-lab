"""What did this scan find that the last one didn't? (2026-10-15)

The DoD Pillar 7 gate is "triage NEW critical/high", but a repo's standing totals (weyland-lab: hundreds of OSV and
kubescape highs) bury a new one. This diffs two archived runs of the code-scan-suite, per tool, on the critical/high
findings only, keyed on what identifies a finding (file, package, rule or CVE: never a line number, which moves).

usage:  python3 scripts/scan-diff.py <old-run> <new-run>
        a run is an archive prefix under s3://scan-reports/, e.g. 2026-10-14T19-18-00Z (one per repo per run;
        run-scan-suite.sh prints each repo's). Exit 0 nothing new and nothing standing · 1 new critical/high findings,
        or a STANDING unaccepted OSV finding in a production lockfile, listed · 2 could not compare (a report missing
        or unreadable in either run: an unreadable report is not "nothing new").

A diff alone never re-raises a finding present in both runs, so it also lists every OSV finding left in a lockfile
outside golden-paths/ (2026-10-26: weyland-dagster's PyJWT and soupsieve sat there from 2026-09-04 behind "0 new").
osv applies osv-scanner.toml before writing osv.json, so whatever remains is unaccepted: fix it or accept it there.
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


def standing_production(d):
    """Every OSV finding (any severity) in a lockfile outside golden-paths/: unaccepted, since osv already applied
    osv-scanner.toml. The golden paths are the B88 sample apps, triaged on their own."""
    return sorted(f for f in osv(d) if "/golden-paths/" not in "/" + f[0].lstrip("/"))


def bandit(d):
    return {(x["filename"], x["test_id"]) for x in d.get("results") or [] if x.get("issue_severity") == "HIGH"}


def semgrep(d):
    return {(x["path"], x["check_id"]) for x in d.get("results") or [] if x["extra"].get("severity") == "ERROR"}


def hadolint(d):
    return {(x["file"], x["code"]) for x in d if x.get("level") == "error"} if isinstance(d, list) else set()


def gitleaks(d):
    return {(x["File"], x["RuleID"]) for x in d} if isinstance(d, list) else set()


def trivy_images(d):
    """The DEPLOYED images (the suite's trivy_images step). Keyed by image NAME, package, id — never the tag, which
    changes on every ship. MEDIUM counts here: trivy rated the mcp advisory MEDIUM (CVE-2026-59951, 2026-10-16)."""
    out = set()
    for ref, rep in (d.get("images") or {}).items():
        name = ref.rsplit("/", 1)[-1].split(":", 1)[0]
        for r in rep.get("Results") or []:
            out |= {(v["Severity"], name, v.get("PkgName"), v.get("VulnerabilityID"))
                    for v in r.get("Vulnerabilities") or [] if v.get("Severity") in HIGH + ("MEDIUM",)}
    return out


def kubescape(d):
    controls = (d.get("summaryDetails") or {}).get("controls") or {}
    return {(r["resourceID"], c["controlID"]) for r in d.get("results") or [] for c in r.get("controls") or []
            if (c.get("status") or {}).get("status") == "failed"
            and (controls.get(c["controlID"]) or {}).get("scoreFactor", 0) >= 7}


TOOLS = {"trivy.json": trivy, "osv.json": osv, "bandit.json": bandit, "semgrep.json": semgrep,
         "hadolint.json": hadolint, "gitleaks.json": gitleaks, "kubescape.json": kubescape,
         "trivy-images.json": trivy_images}
IMAGES_REPORT = "trivy-images.json"
# Added after scans were already being archived: an OLD run without it is a baseline, not an unreadable report.
LATER_TOOLS = {IMAGES_REPORT}


def fetch(run, name):
    # Verified TLS: rogueone trusts the lab CA (mkcert), so no verification bypass is needed.
    with urllib.request.urlopen(f"{BASE}{run.rstrip('/')}/{name}", timeout=120) as r:
        return json.load(r)


def diff(old, new):
    """{tool: (added, removed_count)} for every tool; raises if a report can't be read."""
    return {name: (sorted(fn(new[name]) - fn(old[name])), len(fn(old[name]) - fn(new[name])))
            for name, fn in TOOLS.items()}


def _fetch_new(run):
    new = {}
    for n in TOOLS:
        try:
            new[n] = fetch(run, n)
        except Exception as e:
            hint = (" — the run predates the image scan (ship the scan-suite image) or its trivy_images step failed"
                    if n in LATER_TOOLS else "")
            raise RuntimeError(f"{n} unreadable in {run}: {e}{hint}") from e
    return new


def _fetch_old(run):
    """(reports, the LATER_TOOLS the old run predates). Any other unreadable report raises."""
    old, baseline = {}, []
    for n in TOOLS:
        try:
            old[n] = fetch(run, n)
        except Exception:
            if n not in LATER_TOOLS:
                raise
            baseline.append(n)
    return old, baseline


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        new = _fetch_new(argv[2])
        old, baseline = _fetch_old(argv[1])
    except Exception as e:   # any unreadable report: we can't say "nothing new"
        print(f"CANNOT COMPARE: {e}", file=sys.stderr)
        return 2
    broken = (new.get(IMAGES_REPORT) or {}).get("broken") or []
    if broken:
        print(f"CANNOT COMPARE: trivy-images could not scan {broken} (an unscanned image is not a clean one)",
              file=sys.stderr)
        return 2
    for n in baseline:
        print(f"{n.removesuffix('.json')}: baseline ({len(TOOLS[n](new[n]))} finding(s)); the previous run predates "
              "this scan, so there is nothing to compare yet")
        old[n] = new[n]
    added_any = False
    for name, (added, removed) in diff(old, new).items():
        if name in baseline:
            continue
        print(f"{name.removesuffix('.json')}: {len(added)} new, {removed} gone")
        for a in added:
            print("   +", " | ".join(str(x) for x in a))
        added_any |= bool(added)
    standing = standing_production(new["osv.json"])
    print(f"osv standing in production lockfiles: {len(standing)} (unaccepted; fix or accept in osv-scanner.toml)")
    for s in standing:
        print("   !", " | ".join(str(x) for x in s))
    return 1 if added_any or standing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
