"""Soda Core's usage telemetry is off (B233 follow-through, 2026-10-23, owner: "turn it off").

Soda Core posts anonymous usage stats to collect.soda.io unless its USER config says otherwise. It reads the first of
~/.soda/config.yml, .soda/config.yml, /tmp/.soda/config.yml that exists (soda/common/config_helper.py, 3.5.6), and on
first run it creates ~/.soda/config.yml with `send_anonymous_usage_stats: True` — the pod already had one. So the opt-out
has to overwrite that file, not add a lower-priority one. The key in the data-source configuration.yml is ignored
(observed: still posting).
"""
import importlib.util
import os

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location("soda_telemetry_under_test",
                                                  os.path.join(_ROOT, "weyland_pipeline", "soda_telemetry.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_writes_the_opt_out_where_soda_looks_first(tmp_path):
    path = _load().disable_soda_telemetry(home=str(tmp_path))
    assert path == str(tmp_path / ".soda" / "config.yml")
    assert yaml.safe_load(open(path))["send_anonymous_usage_stats"] is False


def test_overwrites_the_default_soda_created(tmp_path):
    (tmp_path / ".soda").mkdir()
    (tmp_path / ".soda" / "config.yml").write_text("send_anonymous_usage_stats: true\nuser_cookie_id: abc\n")
    _load().disable_soda_telemetry(home=str(tmp_path))
    cfg = yaml.safe_load(open(tmp_path / ".soda" / "config.yml"))
    assert cfg["send_anonymous_usage_stats"] is False
    assert cfg["user_cookie_id"] == "abc"   # the rest of the file is kept


def test_defaults_to_the_process_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _load().disable_soda_telemetry()
    assert (tmp_path / ".soda" / "config.yml").exists()
