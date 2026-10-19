"""Tests for gpu_driver_drift.py — does rogueone's loaded NVIDIA kernel module match the installed driver (B226)?

The fixtures are the real outputs observed on rogueone: `/proc/driver/nvidia/version` before the 2026-10-19 reboot
(module 595.91.07 while the package was already 595.99.02 — nine days of silent drift) and after it, and the
`dpkg-query` rows, which include packages dpkg knows but has NOT installed (status `un`, empty version) — those must
never count as a driver. Anything the check cannot read is "could not check" (2), never "match".
"""
import os
import sys
import urllib.parse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import gpu_driver_drift as g

BEFORE = ("NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  595.91.07  Release Build  "
          "(dvs-builder@U22-I3-B08-02-2)  Wed Jul 29 03:01:16 UTC 2026\nGCC version:  gcc version 13.3.0\n")
AFTER = ("NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  595.99.02  Release Build  "
         "(dvs-builder@U22-I3-AF05-06-2)  Wed Aug 26 05:20:50 UTC 2026\n")
PROPRIETARY = "NVRM version: NVIDIA UNIX x86_64 Kernel Module  580.159.03  Thu Jun  5 00:00:00 UTC 2026\n"
DPKG = ("nvidia-driver-595||un \n"
        "nvidia-driver-595-open|595.99.02-0ubuntu0.24.04.1|ii \n"
        "nvidia-driver-binary||un \n")


def test_module_version_open_and_proprietary_lines():
    assert g.module_version(AFTER) == "595.99.02"
    assert g.module_version(BEFORE) == "595.91.07"
    assert g.module_version(PROPRIETARY) == "580.159.03"


@pytest.mark.parametrize("text", ["", "garbage\n", "NVRM version: NVIDIA UNIX Kernel Module  no-version-here\n"])
def test_module_version_unparseable_is_none(text):
    assert g.module_version(text) is None


def test_installed_drivers_ignores_not_installed_rows_and_strips_the_debian_revision():
    assert g.installed_drivers(DPKG) == [("nvidia-driver-595-open", "595.99.02")]


def test_installed_drivers_keeps_half_configured_out():
    # only fully installed (ii) rows count: rc = removed but config left, iU = unpacked not configured
    rows = "nvidia-driver-580|580.159.03-0ubuntu1|rc \nnvidia-driver-595-open|595.99.02-0ubuntu1|iU \n"
    assert g.installed_drivers(rows) == []


def test_match_is_zero():
    rc, msg = g.evaluate(AFTER, DPKG)
    assert rc == 0 and "595.99.02" in msg


def test_the_real_drift_is_one_and_names_both_versions():
    rc, msg = g.evaluate(BEFORE, DPKG)
    assert rc == 1
    assert "595.91.07" in msg and "595.99.02" in msg and "reboot" in msg


def test_no_module_is_two():
    rc, msg = g.evaluate(None, DPKG)
    assert rc == 2 and "module" in msg


def test_unparseable_module_is_two():
    rc, msg = g.evaluate("garbage\n", DPKG)
    assert rc == 2 and "unparseable" in msg


def test_no_installed_driver_is_two():
    rc, msg = g.evaluate(AFTER, "nvidia-driver-595||un \n")
    assert rc == 2 and "no installed" in msg


def test_two_installed_drivers_is_two_and_names_both():
    rows = DPKG + "nvidia-driver-600-open|600.10.01-0ubuntu1|ii \n"
    rc, msg = g.evaluate(AFTER, rows)
    assert rc == 2 and "nvidia-driver-595-open" in msg and "nvidia-driver-600-open" in msg


def test_main_reads_the_module_file_seam_and_dpkg(tmp_path, monkeypatch, capsys):
    mod = tmp_path / "version"
    mod.write_text(BEFORE)
    monkeypatch.setenv(g.MODULE_ENV, str(mod))
    monkeypatch.setattr(g, "_dpkg_rows", lambda: DPKG)
    assert g.main(["--no-push"]) == 1
    assert "595.91.07" in capsys.readouterr().out


def test_main_missing_module_file_is_two(tmp_path, monkeypatch):
    monkeypatch.setenv(g.MODULE_ENV, str(tmp_path / "absent"))
    monkeypatch.setattr(g, "_dpkg_rows", lambda: DPKG)
    assert g.main(["--no-push"]) == 2


def test_main_dpkg_failure_is_two(tmp_path, monkeypatch):
    mod = tmp_path / "version"
    mod.write_text(AFTER)
    monkeypatch.setenv(g.MODULE_ENV, str(mod))

    def boom():
        raise g.CannotRead("dpkg-query exited 2")
    monkeypatch.setattr(g, "_dpkg_rows", boom)
    assert g.main(["--no-push"]) == 2


@pytest.mark.parametrize("module,rc,status", [(AFTER, 0, "up"), (BEFORE, 1, "down")])
def test_main_pushes_the_verdict(tmp_path, monkeypatch, module, rc, status):
    mod = tmp_path / "version"
    mod.write_text(module)
    monkeypatch.setenv(g.MODULE_ENV, str(mod))
    monkeypatch.setenv(g.PUSH_KEY, "https://kuma.example/api/push/abc")
    monkeypatch.setattr(g, "_dpkg_rows", lambda: DPKG)
    sent = []

    class _R:
        def read(self):
            return b"ok"
    monkeypatch.setattr(g.urllib.request, "urlopen", lambda url, timeout: sent.append(url) or _R())
    assert g.main([]) == rc
    q = urllib.parse.parse_qs(urllib.parse.urlparse(sent[0]).query)
    assert q["status"] == [status]


def test_push_url_reads_only_its_own_key(tmp_path, monkeypatch):
    monkeypatch.delenv(g.PUSH_KEY, raising=False)
    env = tmp_path / ".env"
    env.write_text("KUMA_LAN_PUSH_URL=https://other\nKUMA_GPU_DRIFT_PUSH_URL='https://kuma.example/api/push/gpu'\n")
    assert g.push_url(str(env)) == "https://kuma.example/api/push/gpu"


def test_push_url_missing_is_empty(tmp_path, monkeypatch):
    monkeypatch.delenv(g.PUSH_KEY, raising=False)
    assert g.push_url(str(tmp_path / "absent.env")) == ""


def test_unset_push_url_does_not_push(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(g.urllib.request, "urlopen", lambda *a, **k: called.append(a))
    g.push("", 1, "drift")
    assert not called and "NOT reported" in capsys.readouterr().err
