"""Tests for scan.py's parse/severity-map/payload logic — the code-quality scanner that feeds Port.

Every tool runner does: run the tool → load its JSON → map its severities into {critical,high,medium,low} → post.
If the severity map is wrong (or a missing severity defaults to the wrong band, or the wrong kubescape counter is
read — a real past bug), Port shows silently-wrong posture numbers. These tests feed each parser fixture tool-output
and assert the REAL counts, plus the payload builder — no tool executed, no network.
"""
import json


# ── payload builder + primitives ──────────────────────────────────────────────────────────────────
def test_z_is_all_zero(scan):
    assert scan.z() == {"critical": 0, "high": 0, "medium": 0, "low": 0}


def test_post_records_result_with_total_and_skips_network_when_no_url(scan, monkeypatch):
    monkeypatch.setattr(scan, "PORT_URL", None)
    scan.post("bandit", {"critical": 1, "high": 2, "medium": 0, "low": 3})
    assert scan.RESULTS[-1] == {"tool": "bandit", "critical": 1, "high": 2, "medium": 0, "low": 3, "total": 6}


def test_post_builds_the_port_payload_when_url_set(scan, monkeypatch):
    sent = {}

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _urlopen(req, timeout=None):
        sent["url"] = req.full_url
        sent["body"] = json.loads(req.data.decode())
        return _Resp()

    monkeypatch.setattr(scan, "PORT_URL", "http://port.example/ingest")
    monkeypatch.setattr(scan.urllib.request, "urlopen", _urlopen)
    scan.post("trivy", {"critical": 2, "high": 1, "medium": 0, "low": 0})
    assert sent["url"] == "http://port.example/ingest"
    b = sent["body"]
    assert b["tool"] == "trivy" and b["target"] == "test-repo"
    assert b["critical"] == 2 and b["high"] == 1 and b["total"] == 3
    assert "scannedAt" in b


# ── per-tool severity mapping (fixture JSON via stubbed load) ────────────────────────────────────────
def test_checkov_maps_severities_and_defaults_missing_to_medium(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: {"results": {"failed_checks": [
        {"severity": "CRITICAL"}, {"severity": "HIGH"}, {"severity": "LOW"}, {"severity": None}]}})
    scan.checkov()
    assert captured_posts[-1] == ("checkov", {"critical": 1, "high": 1, "medium": 1, "low": 1})  # None → medium


def test_kubescape_reads_resources_severity_counters(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: {"summaryDetails": {"resourcesSeverityCounters": {
        "criticalSeverity": 2, "highSeverity": 5, "mediumSeverity": 9, "lowSeverity": 1}}})
    scan.kubescape()
    assert captured_posts[-1] == ("kubescape", {"critical": 2, "high": 5, "medium": 9, "low": 1})


def test_bandit_maps_issue_severity_and_defaults_low(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: {"results": [
        {"issue_severity": "HIGH"}, {"issue_severity": "MEDIUM"}, {"issue_severity": "???"}]})
    scan.bandit()
    assert captured_posts[-1] == ("bandit", {"critical": 0, "high": 1, "medium": 1, "low": 1})  # unknown → low


def test_osv_buckets_by_leading_cvss_number(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: {"results": [{"packages": [{"vulnerabilities": [
        {"severity": [{"score": "9.8"}]},   # >=9 → critical
        {"severity": [{"score": "7.5"}]},   # >=7 → high
        {"severity": [{"score": "5.0"}]},   # >=4 → medium
        {"severity": [{"score": "2.0"}]},   # <4  → low
        {"severity": []},                   # no score → default high
    ]}]}]})
    scan.osv()
    assert captured_posts[-1] == ("osv-scanner", {"critical": 1, "high": 2, "medium": 1, "low": 1})


def test_semgrep_maps_extra_severity_no_critical(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: {"results": [
        {"extra": {"severity": "ERROR"}}, {"extra": {"severity": "WARNING"}},
        {"extra": {"severity": "INFO"}}, {"extra": {"severity": "UNKNOWN"}}]})  # unknown → dropped
    scan.semgrep()
    assert captured_posts[-1] == ("semgrep", {"critical": 0, "high": 1, "medium": 1, "low": 1})


def test_trivy_counts_across_vuln_misconfig_secret_keys(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: {"Results": [{
        "Vulnerabilities": [{"Severity": "CRITICAL"}, {"Severity": "HIGH"}],
        "Misconfigurations": [{"Severity": "MEDIUM"}],
        "Secrets": [{"Severity": "LOW"}, {"Severity": "UNKNOWN"}]}]})  # UNKNOWN → not in map → dropped
    scan.trivy()
    assert captured_posts[-1] == ("trivy", {"critical": 1, "high": 1, "medium": 1, "low": 1})


def test_gitleaks_counts_every_secret_as_critical(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "load", lambda p: [{"RuleID": "aws"}, {"RuleID": "gcp"}, {"RuleID": "pk"}])
    scan.gitleaks()
    assert captured_posts[-1] == ("gitleaks", {"critical": 3, "high": 0, "medium": 0, "low": 0})


# ── subprocess-driven runners (stub subprocess.run by command) ────────────────────────────────────────
def _fake_run_factory(by_cmd):
    class _R:
        def __init__(self, stdout): self.stdout = stdout
    def _run(cmd, **kw):
        for key, out in by_cmd.items():
            if key in cmd or any(key in str(a) for a in cmd):
                return _R(out)
        return _R("")
    return _run


def test_secret_files_flags_tracked_but_gitignored_as_critical(scan, captured_posts, monkeypatch):
    # git ls-files → tracked list; check-ignore → the intersection (tracked AND gitignored) = committed-secret risk
    monkeypatch.setattr(scan.subprocess, "run", _fake_run_factory({
        "ls-files": "a.py\nsecrets.env\nb.py\n",
        "check-ignore": "secrets.env\n"}))
    scan.secret_files()
    assert captured_posts[-1] == ("secret-files", {"critical": 1, "high": 0, "medium": 0, "low": 0})


def test_hadolint_maps_levels(scan, captured_posts, monkeypatch):
    findings = json.dumps([{"level": "error"}, {"level": "warning"}, {"level": "info"}, {"level": "style"}])
    monkeypatch.setattr(scan.subprocess, "run", _fake_run_factory({
        "find": "Dockerfile\n", "hadolint": findings}))
    scan.hadolint()
    # error→high, warning→medium, info→low, style→low
    assert captured_posts[-1] == ("hadolint", {"critical": 0, "high": 1, "medium": 1, "low": 2})
