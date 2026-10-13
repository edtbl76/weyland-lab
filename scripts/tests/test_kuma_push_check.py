"""Tests for kuma_push_check.py — every Uptime-Kuma push monitor's heartbeat interval matches the runbook (2026-10-13).

Kuma's default heartbeat interval is 60 s, so a push monitor fed by a daily job goes red a minute after every good push.
It happened three times: `machine-inventory-drift` and `agent-memory` (found 2026-10-03), then `emdash-conveyor`
(2026-10-13, where 90000 was typed into the RETRY interval and the heartbeat stayed 60). The expected values live in ONE
place, the push-monitor table in docs/runbooks/uptime-kuma.md; Kuma's are read from its SQLite store. Row shape OBSERVED
2026-10-13 (`select id,name,active,interval,retry_interval,maxretries from monitor where type='push'`):
`56|emdash-conveyor|1|60|90000|0`.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import kuma_push_check as k

RUNBOOK = """# Uptime Kuma

## Push monitors — the heartbeat interval must outlast the job's cadence

| Push monitor | Pushed by | Cadence | Heartbeat interval | Env var (`scripts/.env`, no `?query`) |
|---|---|---|---|---|
| `rogueone-backup` | `restic-backup.timer` (rogueone) | daily 02:30 | **93600 s** (26 h) | `KUMA_BACKUP_PUSH_URL` |
| `agent-memory` | `agent-memory-watch.timer` (rogueone, B182) | every 15 min | **1200 s** (20 min) — fixed from 60 s 2026-10-03 | `KUMA_MEMORY_PUSH_URL` |
| `emdash-conveyor` | `emdash-conveyor-watch.timer` (rogueone, B179) | daily 06:00 | **90000 s** (25 h) | `KUMA_CONVEYOR_PUSH_URL` |

A **down** push is not the same as a missed one.

## Gotchas
| `not-a-push-row` | x | x | **5 s** | x |
"""


def _runbook(tmp_path, text=RUNBOOK):
    p = tmp_path / "uptime-kuma.md"
    p.write_text(text)
    return str(p)


def test_the_runbook_table_is_the_expected_set():
    assert k.expected_intervals(RUNBOOK) == {"rogueone-backup": 93600, "agent-memory": 1200, "emdash-conveyor": 90000}


def test_kuma_rows_parse_from_the_observed_shape():
    rows = k.parse_kuma("51|rogueone-backup|1|93600|93600|0\n56|emdash-conveyor|1|60|90000|0\n")
    assert rows == {"rogueone-backup": {"active": True, "interval": 93600},
                    "emdash-conveyor": {"active": True, "interval": 60}}


def test_all_matching_is_clean():
    exp = {"a": 93600, "b": 1200}
    assert k.compare(exp, {"a": {"active": True, "interval": 93600}, "b": {"active": True, "interval": 1200}}) == []


def test_the_retry_field_trap_is_named():
    findings = k.compare({"emdash-conveyor": 90000}, {"emdash-conveyor": {"active": True, "interval": 60}})
    assert findings == ["emdash-conveyor: heartbeat interval 60 s, runbook says 90000 s "
                        "(Kuma → Edit → Heartbeat Interval, not Retry)"]


def test_a_missing_paused_or_unlisted_monitor_is_a_finding():
    findings = k.compare({"a": 93600, "gone": 1200},
                         {"a": {"active": False, "interval": 93600}, "new-one": {"active": True, "interval": 60}})
    assert "gone: in the runbook but not a push monitor in Kuma" in findings
    assert "a: paused in Kuma" in findings
    assert "new-one: push monitor with no row in docs/runbooks/uptime-kuma.md" in findings


def test_main_exit_0_when_clean(tmp_path, monkeypatch, capsys):
    rows = "1|rogueone-backup|1|93600|93600|0\n2|agent-memory|1|1200|1200|0\n3|emdash-conveyor|1|90000|90000|0\n"
    monkeypatch.setattr(k, "read_kuma", lambda: rows)
    assert k.main(["--runbook", _runbook(tmp_path)]) == 0
    assert "OK — 3 push monitor(s) match" in capsys.readouterr().out


def test_main_exit_1_names_each_mismatch(tmp_path, monkeypatch, capsys):
    rows = "1|rogueone-backup|1|93600|93600|0\n2|agent-memory|1|1200|1200|0\n3|emdash-conveyor|1|60|90000|0\n"
    monkeypatch.setattr(k, "read_kuma", lambda: rows)
    assert k.main(["--runbook", _runbook(tmp_path)]) == 1
    assert "emdash-conveyor: heartbeat interval 60 s" in capsys.readouterr().out


def test_an_unreadable_kuma_is_exit_2(tmp_path, monkeypatch, capsys):
    def boom():
        raise k.CannotRead("ssh mother: Permission denied")
    monkeypatch.setattr(k, "read_kuma", boom)
    assert k.main(["--runbook", _runbook(tmp_path)]) == 2
    assert "Permission denied" in capsys.readouterr().err


def test_an_empty_kuma_answer_is_exit_2_not_clean(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(k, "read_kuma", lambda: "")
    assert k.main(["--runbook", _runbook(tmp_path)]) == 2
    assert "no push monitors" in capsys.readouterr().err


def test_a_runbook_without_the_table_is_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(k, "read_kuma", lambda: "1|a|1|60|60|0\n")
    assert k.main(["--runbook", _runbook(tmp_path, "# Uptime Kuma\n\nno table here\n")]) == 2
    assert "push-monitor table" in capsys.readouterr().err


def test_a_malformed_kuma_row_is_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(k, "read_kuma", lambda: "garbage without pipes\n")
    with pytest.raises(SystemExit) as e:
        k.main(["--runbook", _runbook(tmp_path)])
    assert e.value.code == 2 and "unexpected row" in capsys.readouterr().err


def test_the_real_runbook_parses_with_every_documented_monitor():
    real = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "docs", "runbooks", "uptime-kuma.md")
    exp = k.expected_intervals(open(real, encoding="utf-8").read())
    assert {"rogueone-backup", "machine-inventory-drift", "agent-memory", "emdash-conveyor"} <= set(exp)
    assert all(v > 60 for v in exp.values())                       # the 60 s default is never the right answer
