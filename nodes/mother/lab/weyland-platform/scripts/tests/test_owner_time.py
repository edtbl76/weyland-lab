"""Tests for owner_time.py — B185 lane 2: the owner's own time per Linear issue, from ActivityWatch and Clockify.

Shapes OBSERVED 2026-10-15 on rogueone, not assumed:
- ActivityWatch events: {id, timestamp, duration (s, float), data}. The Chrome web bucket's data is
  {audible, incognito, tabCount, title, url}; a Linear tab's title carries BOTH ids ("EMA-243 B185 — …") and its url
  carries one ("/emangini/issue/EMA-243/b185-…"). The window bucket's data is {app, title}; Chrome is app
  "Google-chrome", and it sees the same tab title the web bucket does (so counting both double-counts).
- Clockify time entries: description "[EMA-243] B185 — …" (the extension's Linear button), timeInterval
  {start, end, duration: "PT25S"}; a running timer has end and duration null.
- systemctl --user show -p CPUUsageNSec -p MemoryCurrent -p ActiveEnterTimestampMonotonic -p ActiveState: KEY=VALUE lines.
"""
import json
import urllib.error

import pytest

import owner_time as o

LINEAR_URL = "https://linear.app/emangini/issue/EMA-243/b185-time-per-linear-issue-agent-session-time-"


# --- which issue an event belongs to ------------------------------------------------------------------------------

def test_a_linear_tab_is_attributed_by_its_url_not_its_title():
    # the title names EMA-243 AND B185; counting both would double the minutes
    assert o.issue_for_web(LINEAR_URL, "EMA-243 B185 — Time per Linear issue") == "EMA-243"


def test_a_linear_tab_whose_title_has_not_loaded_still_counts():
    assert o.issue_for_web("https://linear.app/emangini/issue/EMA-243", "Linear") == "EMA-243"


def test_a_non_linear_tab_falls_back_to_the_title():
    assert o.issue_for_web("https://github.com/edtbl76/weyland-lab/pull/9", "B185 notes · GitHub") == "B185"


@pytest.mark.parametrize("title, want", [
    ("EMA-243 B185 — Time per Linear issue", "EMA-243"),   # an EMA id outranks the backlog number beside it
    ("weyland – B185 issue_time_report.py", "B185"),
    ("EMA-12 and EMA-13 compared", None),                  # ambiguous: never guess
    ("B185 vs B206", None),
    ("Terminal", None),
    ("B2B onboarding", None),                              # not a backlog number
])
def test_a_window_title_names_at_most_one_issue(title, want):
    assert o.issue_for_title(title) == want


# --- ActivityWatch minutes ----------------------------------------------------------------------------------------

def _ev(duration, **data):
    return {"id": 1, "timestamp": "2026-10-15T20:20:00Z", "duration": duration, "data": data}


def test_aw_minutes_sums_web_and_non_browser_windows_per_issue():
    result = {"web": [_ev(120.0, url=LINEAR_URL, title="EMA-243 B185 — x"),
                      _ev(60.0, url="https://linear.app/emangini/issue/EMA-243", title="Linear"),
                      _ev(30.0, url="https://mail.google.com/", title="Inbox")],
              "other": [_ev(90.0, app="jetbrains-idea", title="weyland – B185 owner_time.py"),
                        _ev(45.0, app="gnome-terminal", title="Terminal")]}
    minutes, unattributed = o.aw_minutes(result)
    assert minutes == {"EMA-243": 3.0, "B185": 1.5}
    assert unattributed == pytest.approx(75 / 60)


def test_aw_minutes_refuses_a_result_without_the_expected_keys():
    with pytest.raises(o.SourceError, match="web"):
        o.aw_minutes({"other": []})


def test_the_aw_query_keeps_browser_time_only_while_chrome_is_active_and_drops_afk():
    q = "\n".join(o.aw_query("rogueone"))
    assert 'query_bucket("aw-watcher-afk_rogueone")' in q
    assert 'filter_keyvals(afk, "status", ["not-afk"])' in q
    assert 'filter_period_intersect(web, chrome)' in q
    assert 'exclude_keyvals(win, "app", ["Google-chrome"])' in q


# --- Clockify minutes ---------------------------------------------------------------------------------------------

def _entry(desc, start="2026-10-15T20:20:24Z", end="2026-10-15T20:20:49Z", duration="PT25S"):
    return {"description": desc, "timeInterval": {"start": start, "end": end, "duration": duration}}


@pytest.mark.parametrize("iso, seconds", [("PT25S", 25), ("PT1H2M3S", 3723), ("PT45M", 2700), ("P1DT1H", 90000)])
def test_iso_durations(iso, seconds):
    assert o.iso_seconds(iso) == seconds


@pytest.mark.parametrize("bad", ["PT25X", "P", "PT", "", "25S", "PT1S1M", "PT1H1H", "P1H", "PT1D"])
def test_an_unparseable_duration_fails_closed(bad):
    # empty, no P, out of order, a repeated unit, H on the date side, D on the time side — never read as 0
    with pytest.raises(o.SourceError, match="unparseable"):
        o.iso_seconds(bad)


def test_clockify_minutes_takes_the_id_from_the_linear_button_prefix():
    entries = [_entry("[EMA-243] B185 — Time per Linear issue"),
               _entry("[EMA-243] B185 — again", duration="PT1M35S"),
               _entry("reading email", duration="PT10M"),
               _entry("[EMA-300] stud.io", end=None, duration=None)]      # a running timer: not counted yet
    minutes, unattributed, running = o.clockify_minutes(entries)
    assert minutes == {"EMA-243": 2.0}
    assert unattributed == 10.0
    assert running == 1


def test_a_hand_typed_entry_naming_a_backlog_number_counts():
    minutes, _, _ = o.clockify_minutes([_entry("B185 review", duration="PT6M")])
    assert minutes == {"B185": 6.0}


# --- the trial's resource budget ----------------------------------------------------------------------------------

def test_resources_report_cpu_against_one_core_and_the_machine():
    # ActiveEnterTimestampMonotonic is in MICROSECONDS (observed: 2137163260016 µs beside a 2138461 s uptime);
    # 1000000 µs = started 1 s after boot.
    show = {"aw-server": "MemoryCurrent=7000000\nCPUUsageNSec=1000000000\nActiveState=active\n"
                         "ActiveEnterTimestampMonotonic=1000000",
            "aw-watcher-afk": "MemoryCurrent=35000000\nCPUUsageNSec=3000000000\nActiveState=active\n"
                              "ActiveEnterTimestampMonotonic=1000000"}
    r = o.resources(show, uptime_s=401.0, ncpu=4)          # active for 400 s
    assert r["cpu_pct_of_one_core"] == 1.0                 # 4 s of CPU in 400 s
    assert r["cpu_pct_of_machine"] == 0.25
    assert r["rss_mb"] == 42.0
    assert r["over_budget"] == []


def test_resources_name_each_broken_criterion_and_an_inactive_unit():
    show = {"aw-server": "MemoryCurrent=200000000\nCPUUsageNSec=10000000000\nActiveState=active\n"
                         "ActiveEnterTimestampMonotonic=1000000",
            "aw-watcher-window": "MemoryCurrent=[not set]\nCPUUsageNSec=[not set]\nActiveState=failed\n"
                                 "ActiveEnterTimestampMonotonic=0"}
    r = o.resources(show, uptime_s=101.0, ncpu=12)
    assert set(r["over_budget"]) == {"cpu > 1% of one core", "rss > 150 MB"}
    assert r["inactive"] == ["aw-watcher-window"]


# --- main: fail closed, never a silent zero -----------------------------------------------------------------------

def test_activitywatch_unreachable_is_exit_2(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")
    monkeypatch.setattr(o, "_http_json", boom)
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    assert o.main(["--out", str(tmp_path)]) == 2
    assert "ActivityWatch" in capsys.readouterr().err


def test_clockify_not_configured_is_recorded_not_counted_as_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(o, "_aw_result", lambda host, day: {"web": [_ev(60.0, url=LINEAR_URL, title="x")], "other": []})
    monkeypatch.setattr(o, "_systemctl_show", lambda unit: "ActiveState=active\nCPUUsageNSec=0\nMemoryCurrent=0\n"
                                                           "ActiveEnterTimestampMonotonic=0")
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    assert o.main(["--out", str(tmp_path), "--days", "1"]) == 0
    out = json.loads((tmp_path / "owner_time.json").read_text())
    assert out["sources"]["clockify"]["status"] == "not-configured"
    assert out["issues"]["EMA-243"] == {"aw_minutes": 1.0, "clockify_minutes": None}


def test_a_clockify_api_failure_is_exit_2_not_a_partial_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(o, "_aw_result", lambda host, day: {"web": [], "other": []})
    monkeypatch.setattr(o, "_systemctl_show", lambda unit: "ActiveState=active")
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")

    def http_401(*a, **k):
        raise o.SourceError("Clockify GET /user -> HTTP 401")
    monkeypatch.setattr(o, "_clockify_entries", http_401)
    assert o.main(["--out", str(tmp_path), "--days", "1"]) == 2
    assert "401" in capsys.readouterr().err
    assert not (tmp_path / "owner_time.json").exists()


def test_env_file_supplies_only_the_clockify_key(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER_SECRET=nope\nexport CLOCKIFY_API_KEY='abc123'\n# CLOCKIFY_API_KEY=commented\n")
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_SECRET", raising=False)
    assert o.clockify_key(str(env)) == "abc123"
    import os
    assert "OTHER_SECRET" not in os.environ


def test_env_file_without_the_key_is_not_configured(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    assert o.clockify_key(str(env)) == ""


def test_a_missing_env_file_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    with pytest.raises(o.SourceError, match="env file"):
        o.clockify_key(str(tmp_path / "absent.env"))
