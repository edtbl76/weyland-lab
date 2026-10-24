"""Tests for owner_time.py — B185 lane 2: the owner's own time per Linear issue, from Clockify.

ActivityWatch was the automatic half of lane 2 and failed its week-long trial on memory (2026-10-23: 27 of 53 samples
over the 150 MB budget, peaking at 180 MB and growing with uptime), so the owner killed it. These tests pin that the
collector never contacts it again and records it as retired — the report then shows its column as unknown, never 0.

Shapes OBSERVED 2026-10-15 on rogueone, not assumed:
- Clockify time entries: description "[EMA-243] B185 — …" (the extension's Linear button), timeInterval
  {start, end, duration: "PT25S"}; a running timer has end and duration null.
"""
import json

import pytest

import owner_time as o


# --- which issue a hand-typed entry names -------------------------------------------------------------------------

@pytest.mark.parametrize("title, want", [
    ("EMA-243 B185 — Time per Linear issue", "EMA-243"),   # an EMA id outranks the backlog number beside it
    ("weyland – B185 issue_time_report.py", "B185"),
    ("EMA-12 and EMA-13 compared", None),                  # ambiguous: never guess
    ("B185 vs B206", None),
    ("Terminal", None),
    ("B2B onboarding", None),                              # not a backlog number
])
def test_a_description_names_at_most_one_issue(title, want):
    assert o.issue_for_title(title) == want


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


# --- main: Clockify only; ActivityWatch retired; fail closed, never a silent zero ---------------------------------

def _never_activitywatch(monkeypatch):
    def guard(req, *a, **k):
        url = getattr(req, "full_url", str(req))
        assert "5600" not in url, f"contacted ActivityWatch: {url}"
        raise AssertionError(f"unexpected HTTP call: {url}")
    monkeypatch.setattr(o, "_http_json", guard)


def test_activitywatch_is_never_contacted_and_is_recorded_retired(tmp_path, monkeypatch):
    _never_activitywatch(monkeypatch)
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")
    monkeypatch.setattr(o, "_clockify_entries", lambda key: [_entry("[EMA-243] B185 — x", duration="PT3M")])
    assert o.main(["--out", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "owner_time.json").read_text())
    assert out["sources"]["activitywatch"]["status"] == "retired"   # the report reads anything but "ok" as unknown
    assert out["issues"] == {"EMA-243": {"clockify_minutes": 3.0}}  # no aw_minutes at all, so no fake zero
    assert not (tmp_path / "resources.jsonl").exists()              # the trial's resource log has ended


def test_clockify_not_configured_is_recorded_not_counted_as_zero(tmp_path, monkeypatch):
    _never_activitywatch(monkeypatch)
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    assert o.main(["--out", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "owner_time.json").read_text())
    assert out["sources"]["clockify"]["status"] == "not-configured"
    assert out["issues"] == {}


def test_a_clockify_api_failure_is_exit_2_not_a_partial_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")

    def http_401(*a, **k):
        raise o.SourceError("Clockify GET /user -> HTTP 401")
    monkeypatch.setattr(o, "_clockify_entries", http_401)
    assert o.main(["--out", str(tmp_path)]) == 2
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
