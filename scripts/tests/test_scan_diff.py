"""scripts/scan-diff.py: only NEW critical/high findings count, keyed so a moved line isn't "new", and an unreadable
report is never "nothing new". The report shapes are trimmed from the real archived JSON (2026-10-15)."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("scan_diff", Path(__file__).resolve().parents[1] / "scan-diff.py")
scan_diff = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scan_diff)


def _empty():
    return {"trivy.json": {"Results": []}, "osv.json": {"results": []}, "bandit.json": {"results": []},
            "semgrep.json": {"results": []}, "hadolint.json": [], "gitleaks.json": [],
            "kubescape.json": {"results": [], "summaryDetails": {"controls": {}}},
            "trivy-images.json": {"images": {}, "broken": [], "missing": []}}


def test_a_new_high_cve_is_reported_and_a_medium_is_not():
    old, new = _empty(), _empty()
    new["trivy.json"] = {"Results": [{"Target": "requirements.txt", "Vulnerabilities": [
        {"Severity": "HIGH", "PkgName": "urllib3", "VulnerabilityID": "CVE-2026-1"},
        {"Severity": "MEDIUM", "PkgName": "idna", "VulnerabilityID": "CVE-2026-2"}]}]}
    added, removed = scan_diff.diff(old, new)["trivy.json"]
    assert added == [("HIGH", "requirements.txt", "urllib3", "CVE-2026-1")]
    assert removed == 0


def test_a_finding_whose_line_moved_is_not_new():
    old, new = _empty(), _empty()
    old["gitleaks.json"] = [{"File": "a.bats", "RuleID": "private-key", "StartLine": 114}]
    new["gitleaks.json"] = [{"File": "a.bats", "RuleID": "private-key", "StartLine": 120}]
    assert scan_diff.diff(old, new)["gitleaks.json"] == ([], 0)


def test_kubescape_counts_only_high_score_controls():
    old, new = _empty(), _empty()
    new["kubescape.json"] = {
        "summaryDetails": {"controls": {"C-0017": {"scoreFactor": 7}, "C-0030": {"scoreFactor": 4}}},
        "results": [{"resourceID": "apps/v1/weyland/Deployment/x", "controls": [
            {"controlID": "C-0017", "status": {"status": "failed"}},
            {"controlID": "C-0030", "status": {"status": "failed"}}]}]}
    added, _ = scan_diff.diff(old, new)["kubescape.json"]
    assert added == [("apps/v1/weyland/Deployment/x", "C-0017")]


def test_an_unreadable_report_cannot_compare(monkeypatch):
    def boom(run, name):
        raise OSError("404 Not Found")
    monkeypatch.setattr(scan_diff, "fetch", boom)
    assert scan_diff.main(["scan-diff.py", "old", "new"]) == 2


# --- standing production findings (2026-10-26) ----------------------------------------------------------------------
# A diff only sees what is NEW, so a finding present in both runs never surfaced again: weyland-dagster's PyJWT and
# soupsieve sat in osv.json from 2026-09-04 to 2026-10-26 while every DoD scan read "0 new". osv applies
# osv-scanner.toml before writing osv.json, so anything still in it is UNACCEPTED; outside golden-paths/ (the B88
# sample apps, triaged on their own) that must be zero. Paths as the suite writes them (a clone under /src).

def _osv(*findings):
    return {"results": [{"source": {"path": path, "type": "lockfile"}, "packages": [
        {"package": {"name": pkg, "version": "1"}, "vulnerabilities": [{"id": vid}]}]} for path, pkg, vid in findings]}


def test_standing_lists_unaccepted_production_lockfile_findings_and_skips_golden_paths():
    rep = _osv(("/src/nodes/mother/lab/weyland-platform/services/weyland-dagster/requirements.txt", "soupsieve",
                "GHSA-836r-79rf-4m37"),
               ("/src/golden-paths/frontend/vue/package-lock.json", "vite", "GHSA-xxxx-1111-2222"))
    assert scan_diff.standing_production(rep) == [
        ("/src/nodes/mother/lab/weyland-platform/services/weyland-dagster/requirements.txt", "soupsieve",
         "GHSA-836r-79rf-4m37")]


def test_a_standing_production_finding_fails_even_when_it_is_not_new(monkeypatch, capsys):
    prod = ("/src/nodes/mother/lab/weyland-platform/services/weyland-dagster/requirements.txt", "PyJWT",
            "GHSA-x33g-cr3x-6449")
    runs = {"old": _empty(), "new": _empty()}
    runs["old"]["osv.json"] = _osv(prod)
    runs["new"]["osv.json"] = _osv(prod)
    monkeypatch.setattr(scan_diff, "fetch", lambda run, name: runs[run][name])
    assert scan_diff.main(["scan-diff.py", "old", "new"]) == 1
    out = capsys.readouterr().out
    assert "osv: 0 new" in out                                   # the diff alone would have passed
    assert "standing in production lockfiles: 1" in out and "PyJWT" in out


def test_standing_golden_path_findings_alone_do_not_fail(monkeypatch, capsys):
    gp = ("/src/golden-paths/frontend/vue/package-lock.json", "vite", "GHSA-xxxx-1111-2222")
    runs = {"old": _empty(), "new": _empty()}
    runs["old"]["osv.json"] = _osv(gp)
    runs["new"]["osv.json"] = _osv(gp)
    monkeypatch.setattr(scan_diff, "fetch", lambda run, name: runs[run][name])
    assert scan_diff.main(["scan-diff.py", "old", "new"]) == 0
    assert "standing in production lockfiles: 0" in capsys.readouterr().out


def test_new_findings_exit_1_and_none_exit_0(monkeypatch):
    runs = {"old": _empty(), "same": _empty(), "worse": _empty()}
    runs["worse"]["bandit.json"] = {"results": [{"filename": "x.py", "test_id": "B602", "issue_severity": "HIGH"}]}
    monkeypatch.setattr(scan_diff, "fetch", lambda run, name: runs[run][name])
    assert scan_diff.main(["scan-diff.py", "old", "same"]) == 0
    assert scan_diff.main(["scan-diff.py", "old", "worse"]) == 1


# --- trivy-images.json (2026-10-16): the deployed images, scanned by the suite's trivy_images() -------------------
# Shape: {"images": {ref: <trivy report>}, "broken": [refs], "missing": [names]}. Keyed by image NAME (tags change on
# every ship), package and vulnerability id. MEDIUM counts here: trivy rated the mcp advisory (CVE-2026-59951,
# OBSERVED in weyland-tool-server:git-a68d3d90) MEDIUM, so a critical/high filter would have dropped the very case.

def _img(ref, *vulns):
    return {ref: {"SchemaVersion": 2, "ArtifactName": ref, "Results": [{"Target": "Python", "Vulnerabilities": [
        {"VulnerabilityID": vid, "PkgName": pkg, "Severity": sev} for vid, pkg, sev in vulns]}]}}


def test_trivy_images_keys_by_image_name_not_tag_and_counts_medium():
    old = {"images": _img("registry.weyland.lab/weyland-tool-server:git-a68d3d90", ("CVE-1", "httpx", "HIGH")),
           "broken": [], "missing": []}
    new = {"images": _img("registry.weyland.lab/weyland-tool-server:git-af3ae0c8", ("CVE-1", "httpx", "HIGH"),
                          ("CVE-2026-59951", "mcp", "MEDIUM"), ("CVE-9", "zlib", "LOW")), "broken": [], "missing": []}
    assert sorted(scan_diff.trivy_images(new) - scan_diff.trivy_images(old)) == [
        ("MEDIUM", "weyland-tool-server", "mcp", "CVE-2026-59951")]


def test_a_broken_image_scan_cannot_be_compared(monkeypatch):
    runs = {"old": _empty(), "new": _empty()}
    runs["old"]["trivy-images.json"] = {"images": {}, "broken": [], "missing": []}
    runs["new"]["trivy-images.json"] = {"images": {}, "broken": ["registry.weyland.lab/x:git-1"], "missing": []}
    monkeypatch.setattr(scan_diff, "fetch", lambda run, name: runs[run][name])
    assert scan_diff.main(["scan-diff.py", "old", "new"]) == 2


def test_the_first_image_scan_is_a_baseline_not_a_failure(monkeypatch, capsys):
    runs = {"old": _empty(), "new": _empty()}
    runs["new"]["trivy-images.json"] = {"images": _img("registry.weyland.lab/x:git-1", ("CVE-1", "a", "HIGH")),
                                        "broken": [], "missing": []}

    def fetch(run, name):
        if run == "old" and name == "trivy-images.json":
            raise OSError("404 Not Found")          # the old run predates the image scan
        return runs[run][name]
    monkeypatch.setattr(scan_diff, "fetch", fetch)
    assert scan_diff.main(["scan-diff.py", "old", "new"]) == 0
    assert "trivy-images: baseline" in capsys.readouterr().out


def test_an_unreadable_new_image_scan_still_fails_closed(monkeypatch):
    def fetch(run, name):
        if run == "new" and name == "trivy-images.json":
            raise OSError("404 Not Found")
        return _empty()[name]
    monkeypatch.setattr(scan_diff, "fetch", fetch)
    assert scan_diff.main(["scan-diff.py", "old", "new"]) == 2
