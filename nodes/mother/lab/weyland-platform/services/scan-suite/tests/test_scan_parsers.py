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


# ── helpers: load / sh / post_hotspot / _prior_summary / the HTML report ─────────────────────────────
def test_load_parses_json_and_fails_soft(scan, tmp_path):
    good = tmp_path / "g.json"; good.write_text('{"a": 1}')
    assert scan.load(str(good)) == {"a": 1}
    bad = tmp_path / "b.json"; bad.write_text("not json")
    assert scan.load(str(bad)) is None                       # parse error → None, never raises
    assert scan.load(str(tmp_path / "missing.json")) is None  # missing → None


def test_sh_never_raises_on_failure(scan, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(scan.subprocess, "run", boom)
    scan.sh(["echo", "hi"])                                   # best-effort: must swallow the exception


def test_post_hotspot_noop_without_url(scan, monkeypatch):
    monkeypatch.setattr(scan, "PORT_URL", None)
    scan.post_hotspot({"file": "x", "kind": "hotspot"})       # no URL → silent no-op, no raise


def test_post_hotspot_posts_when_url_set(scan, monkeypatch):
    monkeypatch.setattr(scan, "PORT_URL", "http://port/ingest")
    calls = []
    monkeypatch.setattr(scan.urllib.request, "urlopen", lambda req, **k: calls.append(req))
    scan.post_hotspot({"file": "a.py", "kind": "hotspot"})
    assert len(calls) == 1


def test_prior_summary_returns_latest_prior_run(scan):
    import io as _io

    class _S3:
        def list_objects_v2(self, **k):
            return {"CommonPrefixes": [{"Prefix": "2026-01-01/"}, {"Prefix": "2026-02-01/"}, {"Prefix": "2026-03-01/"}]}

        def get_object(self, Bucket, Key):
            assert Key == "2026-02-01/summary.json"           # the latest prefix strictly BEFORE this run
            return {"Body": _io.BytesIO(json.dumps({"stamp": "2026-02-01"}).encode())}

    assert scan._prior_summary(_S3(), "bucket", "2026-03-01/") == {"stamp": "2026-02-01"}


def test_prior_summary_none_when_no_earlier_run(scan):
    class _S3:
        def list_objects_v2(self, **k):
            return {"CommonPrefixes": [{"Prefix": "2026-05-01/"}]}   # only a LATER run

    assert scan._prior_summary(_S3(), "bucket", "2026-03-01/") is None


def test_html_renders_rows_totals_and_deltas(scan, monkeypatch):
    monkeypatch.setattr(scan, "RESULTS", [
        {"tool": "bandit", "critical": 1, "high": 0, "medium": 2, "low": 3, "total": 6},
        {"tool": "ruff", "critical": 0, "high": 0, "medium": 0, "low": 5, "total": 5},
    ])
    prior = {"stamp": "2026-01-01", "results": [{"tool": "bandit", "total": 4}, {"tool": "ruff", "total": 9}]}
    html = scan._html("2026-02-01", {"bandit.json": "http://x/b"}, prior)
    assert "bandit" in html and "ruff" in html
    assert 'href="http://x/b"' in html                        # tool name links to its raw JSON
    assert "+2" in html                                        # bandit 6 vs prior 4 → +2
    assert "-4" in html                                        # ruff 5 vs prior 9 → -4
    assert "code-scan-suite" in html


def test_html_marks_new_tool_when_no_prior(scan, monkeypatch):
    monkeypatch.setattr(scan, "RESULTS", [{"tool": "osv", "critical": 0, "high": 1, "medium": 0, "low": 0, "total": 1}])
    html = scan._html("2026-02-01", {}, None)
    assert "new" in html and "osv" in html


def test_pip_audit_counts_each_vuln_as_high(scan, captured_posts, monkeypatch):
    out = json.dumps({"dependencies": [{"vulns": [{"id": "A"}, {"id": "B"}]}, {"vulns": []}]})
    monkeypatch.setattr(scan.subprocess, "run",
                        _runner({"find": "/src/requirements.txt", "pip-audit": out}))
    scan.pip_audit()
    assert _counts(captured_posts, "pip-audit") == {"critical": 0, "high": 2, "medium": 0, "low": 0}


def test_headers_is_empty_when_no_hosts_file(scan, captured_posts):
    # SRC (a tmp dir from conftest) has no docs/hosts.md → no hosts → all-zero, no network
    scan.headers()
    assert _counts(captured_posts, "headers") == {"critical": 0, "high": 0, "medium": 0, "low": 0}


def test_headers_counts_missing_security_headers(scan, captured_posts, monkeypatch):
    import os
    docs = os.path.join(scan.SRC, "docs")
    os.makedirs(docs, exist_ok=True)
    open(os.path.join(docs, "hosts.md"), "w").write("- realm.weyland.lab is an ingress\n")

    class _Resp:
        # HSTS present; the other 4 wanted headers (CSP, x-frame-options, x-content-type-options,
        # referrer-policy) are absent → 4 medium findings for the one reachable HTML host.
        headers = {"Content-Type": "text/html; charset=utf-8", "strict-transport-security": "max-age=1"}

    monkeypatch.setattr(scan.urllib.request, "urlopen", lambda url, **k: _Resp())
    scan.headers()
    assert _counts(captured_posts, "headers") == {"critical": 0, "high": 0, "medium": 4, "low": 0}


def test_go_modules_maps_gomod_paths_to_dirs(scan, monkeypatch):
    monkeypatch.setattr(scan.subprocess, "run", _runner({"find": "/src/a/go.mod\n/src/b/go.mod"}))
    assert scan._go_modules() == ["/src/a", "/src/b"]
