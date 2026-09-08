"""Deliberately-failing test — proves the lane PROPAGATES failure (B88 --self-check)."""


def test_the_lane_reports_failure():
    assert "this fixture is meant to fail" == "hello, weyland", \
        "selfcheck: the golden-path lane must surface this failure (exit non-zero)"
