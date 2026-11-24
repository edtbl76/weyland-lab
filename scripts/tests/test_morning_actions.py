"""B243 (2026-11-24): the morning runner may only take actions from the owner-approved allowlist.

Owner, 2026-11-24, on the four actions below: "yes, approve all four". The allowlist lives in git
(scripts/morning/allowlist.yaml); scripts/lib/morning_actions.py is the ONLY code that acts, and these tests are the
acceptance criterion "a test fails if the runner can execute anything not on it": an unknown action, a parameter that
does not match its pattern (shell injection included), a missing or extra parameter, a second attempt at the same item
in one night, and a user timer that is not one of the lab's own units are all refused, and no command runs through a
shell.
"""
import importlib.util
import inspect
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("morning_actions", ROOT / "scripts" / "lib" / "morning_actions.py")
ma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ma)

DATE = "2026-11-24"
RUN = "0f8e7d6c-1234-4abc-9def-0123456789ab"


@pytest.fixture
def allow():
    return ma.load_allowlist()


@pytest.fixture
def ledger(tmp_path):
    return ma.Ledger(tmp_path / f"ledger-{DATE}.json")


def test_the_allowlist_is_exactly_the_four_the_owner_approved(allow):
    assert set(allow["actions"]) == {"ci-retrigger-nightly", "dagster-reexecute-run", "cronjob-rerun",
                                     "user-timer-rerun"}
    assert allow["approval"] == "yes, approve all four" and allow["approved_on"] == "2026-11-24"


def test_each_approved_action_renders_its_exact_command(allow, ledger):
    assert ma.plan(allow, "ci-retrigger-nightly", {}, date=DATE, ledger=ledger).argv == [
        "woodpecker-cli", "pipeline", "create", "edtbl76/weyland-lab", "--branch", "main"]
    p = ma.plan(allow, "dagster-reexecute-run", {"run_id": RUN}, date=DATE, ledger=ledger)
    assert p.argv[-2:] == ["--run", RUN] and p.stdin.endswith("scripts/lib/dagster_reexecute.py")
    assert ma.plan(allow, "cronjob-rerun", {"namespace": "weyland", "cronjob": "pr-staleness-check"},
                   date=DATE, ledger=ledger).argv == ["kubectl", "-n", "weyland", "create", "job",
                                                      "--from=cronjob/pr-staleness-check",
                                                      "pr-staleness-check-retry-20261124"]
    assert ma.plan(allow, "user-timer-rerun", {"unit": "restic-backup.service"}, date=DATE,
                   ledger=ledger).argv == ["systemctl", "--user", "start", "restic-backup.service"]


def test_an_action_not_on_the_allowlist_is_refused(allow, ledger):
    for action in ("argocd-sync", "kubectl-delete", "git-push", "scale-down", ""):
        with pytest.raises(ma.Refused, match="not on the allowlist"):
            ma.plan(allow, action, {}, date=DATE, ledger=ledger)


def test_a_parameter_that_does_not_match_its_pattern_is_refused(allow, ledger):
    bad = [("dagster-reexecute-run", {"run_id": "not-a-run"}),
           ("dagster-reexecute-run", {"run_id": RUN + "; rm -rf /"}),
           ("cronjob-rerun", {"namespace": "weyland", "cronjob": "x --overrides={}"}),
           ("cronjob-rerun", {"namespace": "kube-system", "cronjob": "anything"}),
           ("user-timer-rerun", {"unit": "restic-backup.service; reboot"})]
    for action, params in bad:
        with pytest.raises(ma.Refused):
            ma.plan(allow, action, params, date=DATE, ledger=ledger)


def test_missing_or_extra_parameters_are_refused(allow, ledger):
    with pytest.raises(ma.Refused, match="missing"):
        ma.plan(allow, "dagster-reexecute-run", {}, date=DATE, ledger=ledger)
    with pytest.raises(ma.Refused, match="unexpected"):
        ma.plan(allow, "ci-retrigger-nightly", {"branch": "evil"}, date=DATE, ledger=ledger)


def test_a_user_timer_must_be_one_of_the_labs_own_units(allow, ledger):
    with pytest.raises(ma.Refused, match="placement"):
        ma.plan(allow, "user-timer-rerun", {"unit": "gnome-shell.service"}, date=DATE, ledger=ledger)


def test_each_item_is_attempted_at_most_once_a_night(allow, ledger, tmp_path):
    p = ma.plan(allow, "dagster-reexecute-run", {"run_id": RUN}, date=DATE, ledger=ledger)
    ledger.record(p, ok=True, detail="relaunched")
    with pytest.raises(ma.Refused, match="already attempted"):
        ma.plan(allow, "dagster-reexecute-run", {"run_id": RUN}, date=DATE, ledger=ledger)
    again = ma.Ledger(tmp_path / f"ledger-{DATE}.json")   # survives a restart of the runner
    with pytest.raises(ma.Refused, match="already attempted"):
        ma.plan(allow, "dagster-reexecute-run", {"run_id": RUN}, date=DATE, ledger=again)
    assert json.loads((tmp_path / f"ledger-{DATE}.json").read_text())[0]["action"] == "dagster-reexecute-run"


def test_the_nightly_ci_retrigger_counts_as_one_item_per_night(allow, ledger):
    ledger.record(ma.plan(allow, "ci-retrigger-nightly", {}, date=DATE, ledger=ledger), ok=True, detail="#900")
    with pytest.raises(ma.Refused, match="already attempted"):
        ma.plan(allow, "ci-retrigger-nightly", {}, date=DATE, ledger=ledger)


def test_execute_runs_the_planned_argv_without_a_shell_and_records_it(allow, ledger, monkeypatch):
    seen = {}

    def fake_run(argv, **kw):
        seen["argv"], seen["kw"] = argv, kw

        class R:
            returncode, stdout, stderr = 0, "pipeline 901 created", ""
        return R()
    monkeypatch.setattr(ma.subprocess, "run", fake_run)
    out = ma.execute(allow, "ci-retrigger-nightly", {}, date=DATE, ledger=ledger, env={})
    assert out.ok and seen["argv"][0] == "woodpecker-cli" and seen["kw"].get("shell", False) is False
    assert ledger.attempted("ci-retrigger-nightly", {}) is True


def test_no_command_anywhere_in_the_executor_goes_through_a_shell():
    src = inspect.getsource(ma)
    assert "shell=True" not in src and "os.system" not in src and "Popen(" not in src
