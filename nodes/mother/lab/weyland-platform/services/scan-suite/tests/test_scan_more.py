"""More scan.py parser coverage — the tool-output → severity-count mapping for the remaining scanners, and the
pure worst-first sort key. Each feeds fixture tool output (subprocess stubbed) and asserts the real counts posted;
no tool actually runs. Separate file from test_scan.py to avoid touching shared fixtures.
"""
import json

import pytest


class _CP:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def _runner(by_tool, default=""):
    """A fake subprocess.run that returns fixture output keyed on the command's tool (cmd[0])."""
    def run(cmd, **k):
        tool = cmd[0] if isinstance(cmd, (list, tuple)) else cmd
        v = by_tool.get(tool, default)
        return v if isinstance(v, _CP) else _CP(stdout=v)
    return run


def _counts(captured_posts, tool):
    return dict(next(c for t, c in captured_posts if t == tool))


# ── pure sort key ────────────────────────────────────────────────────────────────────────────────────
def test_sev_weight_orders_worst_first(scan):
    crit = {"tool": "a", "critical": 1, "high": 0, "medium": 0, "low": 99}
    highs = {"tool": "b", "critical": 0, "high": 5, "medium": 0, "low": 0}
    assert scan._sev_weight(crit) < scan._sev_weight(highs)          # one critical beats any highs/lows
    t1 = {"tool": "aaa", "critical": 0, "high": 0, "medium": 0, "low": 0}
    t2 = {"tool": "bbb", "critical": 0, "high": 0, "medium": 0, "low": 0}
    assert scan._sev_weight(t1) < scan._sev_weight(t2)               # tie → alphabetical by tool


# ── subprocess parsers ─────────────────────────────────────────────────────────────────────────────
def test_shellcheck_maps_levels(scan, captured_posts, monkeypatch):
    findings = json.dumps([{"level": "error"}, {"level": "warning"}, {"level": "info"},
                           {"level": "style"}, {"level": "???"}])
    monkeypatch.setattr(scan.subprocess, "run",
                        _runner({"find": "a.sh\nb.sh", "shellcheck": findings}))
    scan.shellcheck()
    assert _counts(captured_posts, "shellcheck") == {"critical": 0, "high": 1, "medium": 1, "low": 3}  # info+style+unknown→low


def test_shfmt_counts_one_finding_per_diffed_file(scan, captured_posts, monkeypatch):
    diff = "--- a.sh.orig\n+++ a.sh\n@@\n-x\n+ x\n--- b.sh.orig\n+++ b.sh\n@@\n-y\n+ y"
    monkeypatch.setattr(scan.subprocess, "run",
                        _runner({"find": "a.sh\nb.sh", "shfmt": _CP(stdout=diff, returncode=1)}))
    scan.shfmt()
    assert _counts(captured_posts, "shfmt") == {"critical": 0, "high": 0, "medium": 0, "low": 2}  # 2 "--- " headers


def test_ruff_buckets_by_code_family(scan, captured_posts, monkeypatch):
    out = json.dumps([{"code": "S101"}, {"code": "S307"}, {"code": "F401"}, {"code": "E902"}, {"code": "W291"}])
    monkeypatch.setattr(scan.subprocess, "run", _runner({"ruff": out}))
    scan.ruff()
    assert _counts(captured_posts, "ruff") == {"critical": 0, "high": 2, "medium": 2, "low": 1}  # S*→high, F/E9→medium, W→low


def test_detect_secrets_counts_all_result_entries_as_medium(scan, captured_posts, monkeypatch):
    out = json.dumps({"results": {"a.py": [{"x": 1}, {"x": 2}], "b.py": [{"x": 3}]}})
    monkeypatch.setattr(scan.subprocess, "run", _runner({"detect-secrets": out}))
    scan.detect_secrets()
    assert _counts(captured_posts, "detect-secrets") == {"critical": 0, "high": 0, "medium": 3, "low": 0}


# ── Go scanners: clean no-op on a 0-Go tree, and severity mapping when modules exist ─────────────────
def test_gosec_is_empty_on_no_go_modules(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "_go_modules", lambda: [])
    scan.gosec()
    assert _counts(captured_posts, "gosec") == {"critical": 0, "high": 0, "medium": 0, "low": 0}


def test_gosec_maps_issue_severity(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "_go_modules", lambda: ["/mod"])
    out = json.dumps({"Issues": [{"severity": "HIGH"}, {"severity": "MEDIUM"}, {"severity": "LOW"}, {"severity": "?"}]})
    monkeypatch.setattr(scan.subprocess, "run", _runner({"gosec": out}))
    scan.gosec()
    assert _counts(captured_posts, "gosec") == {"critical": 0, "high": 1, "medium": 1, "low": 2}  # unknown→low


def test_govulncheck_dedups_osv_ids(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "_go_modules", lambda: ["/mod"])
    lines = "\n".join(json.dumps({"finding": {"trace": [{}], "osv": o}}) for o in ("GO-1", "GO-1", "GO-2"))
    monkeypatch.setattr(scan.subprocess, "run", _runner({"govulncheck": lines}))
    scan.govulncheck()
    assert _counts(captured_posts, "govulncheck") == {"critical": 0, "high": 2, "medium": 0, "low": 0}  # GO-1 deduped


def test_staticcheck_maps_severity(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "_go_modules", lambda: ["/mod"])
    lines = "\n".join(json.dumps({"severity": s}) for s in ("error", "warning", "ignored"))
    monkeypatch.setattr(scan.subprocess, "run", _runner({"staticcheck": lines}))
    scan.staticcheck()
    assert _counts(captured_posts, "staticcheck") == {"critical": 0, "high": 0, "medium": 2, "low": 1}


def test_go_vet_counts_go_error_lines(scan, captured_posts, monkeypatch):
    monkeypatch.setattr(scan, "_go_modules", lambda: ["/mod"])
    monkeypatch.setattr(scan.subprocess, "run",
                        _runner({"go": _CP(stderr="a.go:3: bad\nb.go:7: also bad\nnot a location")}))
    scan.go_vet()
    assert _counts(captured_posts, "go-vet") == {"critical": 0, "high": 0, "medium": 2, "low": 0}
