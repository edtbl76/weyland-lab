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
            "kubescape.json": {"results": [], "summaryDetails": {"controls": {}}}}


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


def test_new_findings_exit_1_and_none_exit_0(monkeypatch):
    runs = {"old": _empty(), "same": _empty(), "worse": _empty()}
    runs["worse"]["bandit.json"] = {"results": [{"filename": "x.py", "test_id": "B602", "issue_severity": "HIGH"}]}
    monkeypatch.setattr(scan_diff, "fetch", lambda run, name: runs[run][name])
    assert scan_diff.main(["scan-diff.py", "old", "same"]) == 0
    assert scan_diff.main(["scan-diff.py", "old", "worse"]) == 1
