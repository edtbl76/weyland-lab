"""Deliberately-failing test — proves the lane PROPAGATES failure (B88 --self-check).

A lane never seen failing is not a lane. `run-lang-tests.sh python --self-check` runs ONLY this and
asserts it fails; the normal run ignores the `selfcheck/` dir. It fails on a real, specific assertion
(not a bare `assert False`) so the failure has a checkable reason, per the estate's fail-closed posture.
"""


def test_the_lane_reports_failure():
    expected = "hello, weyland"
    actual = "this fixture is meant to fail"
    assert actual == expected, "selfcheck: the golden-path lane must surface this failure (exit non-zero)"
