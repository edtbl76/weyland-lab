"""B243: scripts/lib/morning_run.py, the morning remediation's decisions (2026-11-24).

The model is injected (a `triage` callable), and so are the actions, verification, the fix attempt and history, so
every rule in the issue is tested here without calling a model or touching a system:
  * a quiet night says so, and a night with an unreadable source is NOT quiet (unreachable is never "nothing broke");
  * a transient item gets ONE allowlisted action, and is reported fixed only when verification passed (with evidence);
  * an action the allowlist refuses is reported, never retried another way;
  * a real code failure gets a fix attempt on a local auto-fix/<date>-<slug> branch, reported with its gate result;
  * a cause attempted on an earlier night is reported as recurring, with the earlier attempts, and not retried;
  * items the agent itself caused are reported separately;
  * a triage that fails or times out is reported, and the remaining items still run.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = _load("morning_collect_r", "scripts/lib/morning_collect.py")
mr = _load("morning_run", "scripts/lib/morning_run.py")
DATE = "2026-11-24"


class Deps:
    """Fakes for everything the run reaches out to; each records what it was asked."""

    def __init__(self, triage=None, act=None, verify=None, fix=None, history=None):
        self.calls = []
        self._triage = triage or (lambda item: {"classification": "unknown", "diagnosis": "?", "action": None,
                                                "fix": False})
        self._act = act or (lambda action, params: (True, "done"))
        self._verify = verify or (lambda item, action, detail: (True, "verified"))
        self._fix = fix or (lambda item, decision: {"branch": "auto-fix/x", "gates": "passed"})
        self.history = history or {}

    def triage(self, item):
        self.calls.append(("triage", item.key))
        return self._triage(item)

    def act(self, action, params):
        self.calls.append(("act", action, params))
        return self._act(action, params)

    def verify(self, item, action, detail):
        self.calls.append(("verify", item.key, action))
        return self._verify(item, action, detail)

    def fix(self, item, decision):
        self.calls.append(("fix", item.key))
        return self._fix(item, decision)


def _ci(nightly=True):
    return mc.Failure("ci", "ci:platform/test-ada", "CI #900 (cron): platform / test-ada failed", "404 Not Found",
                      extra={"pipeline": 900, "event": "cron" if nightly else "manual", "nightly": nightly})


ALL_CHECKED = {s: "checked" for s in ("ci", "alerts", "dagster", "glitchtip", "incidents", "dependabot")}


def test_a_quiet_night_says_so():
    report = mr.run([], ALL_CHECKED, Deps(), date=DATE)
    assert report.quiet and "Quiet night" in mr.render(report)


def test_a_night_with_an_unreadable_source_is_never_quiet():
    status = {**ALL_CHECKED, "glitchtip": "NOT CHECKED: kubectl exit 1"}
    report = mr.run([], status, Deps(), date=DATE)
    text = mr.render(report)
    assert not report.quiet and "NOT CHECKED" in text and "glitchtip" in text


def test_a_transient_failure_gets_one_allowlisted_retry_and_is_fixed_only_when_verified():
    deps = Deps(triage=lambda i: {"classification": "transient", "diagnosis": "upstream 404 while fetching gnat",
                                  "action": {"id": "ci-retrigger-nightly", "params": {}}, "fix": False},
                act=lambda a, p: (True, "pipeline 901 created"),
                verify=lambda i, a, d: (True, "CI #901 passed"))
    report = mr.run([_ci()], ALL_CHECKED, deps, date=DATE)
    (o,) = report.outcomes
    assert o.result == "fixed by an allowlisted retry" and "CI #901 passed" in o.detail
    assert [c[0] for c in deps.calls] == ["triage", "act", "verify"]


def test_a_retry_whose_verification_fails_is_not_fixed():
    deps = Deps(triage=lambda i: {"classification": "transient", "diagnosis": "d",
                                  "action": {"id": "ci-retrigger-nightly", "params": {}}, "fix": False},
                verify=lambda i, a, d: (False, "CI #901 failed again at test-ada"))
    (o,) = mr.run([_ci()], ALL_CHECKED, deps, date=DATE).outcomes
    assert o.result == "not fixed" and "failed again" in o.detail


def test_an_action_the_allowlist_refuses_is_reported_not_worked_around():
    def refuse(a, p):
        raise mr.ActionRefused("'argocd-sync' is not on the allowlist")
    deps = Deps(triage=lambda i: {"classification": "transient", "diagnosis": "d",
                                  "action": {"id": "argocd-sync", "params": {}}, "fix": False}, act=refuse)
    (o,) = mr.run([_ci()], ALL_CHECKED, deps, date=DATE).outcomes
    assert o.result == "not fixed" and "not on the allowlist" in o.detail
    assert not any(c[0] in ("verify", "fix") for c in deps.calls)


def test_a_real_code_failure_gets_a_fix_branch_with_its_gate_result():
    deps = Deps(triage=lambda i: {"classification": "real", "diagnosis": "SC1090 in scripts/x.sh", "action": None,
                                  "fix": True},
                fix=lambda i, d: {"branch": "auto-fix/2026-11-24-ci-platform-shellcheck", "gates": "passed"})
    item = mc.Failure("ci", "ci:platform/shellcheck", "CI #718: platform / shellcheck failed", "SC1090")
    (o,) = mr.run([item], ALL_CHECKED, deps, date=DATE).outcomes
    assert o.result == "fix branch ready" and "auto-fix/2026-11-24-ci-platform-shellcheck" in o.detail


def test_a_fix_whose_gates_fail_is_not_reported_ready():
    deps = Deps(triage=lambda i: {"classification": "real", "diagnosis": "d", "action": None, "fix": True},
                fix=lambda i, d: {"branch": "auto-fix/x", "gates": "failed: bats 3 not ok"})
    (o,) = mr.run([_ci()], ALL_CHECKED, deps, date=DATE).outcomes
    assert o.result == "not fixed" and "bats 3 not ok" in o.detail and "auto-fix/x" in o.detail


def test_a_cause_attempted_on_an_earlier_night_is_recurring_and_not_retried():
    history = {"ci:platform/test-ada": [{"date": "2026-11-23", "outcome": "fixed by an allowlisted retry"}]}
    deps = Deps(triage=lambda i: {"classification": "transient", "diagnosis": "d",
                                  "action": {"id": "ci-retrigger-nightly", "params": {}}, "fix": False},
                history=history)
    (o,) = mr.run([_ci()], ALL_CHECKED, deps, date=DATE).outcomes
    assert o.result == "recurring, not retried" and "2026-11-23" in o.detail
    assert not any(c[0] == "act" for c in deps.calls)


def test_items_the_agent_caused_are_reported_separately_and_not_acted_on():
    item = mc.Failure("dagster", "dagster:emit_job", "Dagster run r2 failed", "", agent_caused=True)
    deps = Deps()
    report = mr.run([item], ALL_CHECKED, deps, date=DATE)
    (o,) = report.outcomes
    assert o.result == "caused by an agent" and deps.calls == []
    assert "Caused by an agent" in mr.render(report)


def test_a_triage_that_fails_is_reported_and_the_rest_still_run():
    def triage(item):
        if item.key == "ci:platform/test-ada":
            raise TimeoutError("triage exceeded 900 s")
        return {"classification": "unknown", "diagnosis": "needs a person", "action": None, "fix": False}
    other = mc.Failure("alerts", "cronjob:weyland/x", "CronJob weyland/x failed", "")
    outcomes = mr.run([_ci(), other], ALL_CHECKED, Deps(triage=triage), date=DATE).outcomes
    assert outcomes[0].result == "not fixed" and "triage stopped" in outcomes[0].detail
    assert outcomes[1].result == "not fixed" and outcomes[1].diagnosis == "needs a person"
    assert "needs a person" not in outcomes[1].detail   # the report shows the diagnosis once, not twice


def test_the_report_names_evidence_diagnosis_action_and_outcome_per_item():
    deps = Deps(triage=lambda i: {"classification": "transient", "diagnosis": "upstream 404",
                                  "action": {"id": "ci-retrigger-nightly", "params": {}}, "fix": False},
                act=lambda a, p: (True, "pipeline 901 created"), verify=lambda i, a, d: (True, "CI #901 passed"))
    text = mr.render(mr.run([_ci()], ALL_CHECKED, deps, date=DATE))
    for part in ("CI #900", "404 Not Found", "upstream 404", "ci-retrigger-nightly", "fixed by an allowlisted retry",
                 "CI #901 passed"):
        assert part in text, part
