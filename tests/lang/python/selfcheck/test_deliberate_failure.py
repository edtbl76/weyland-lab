"""Run ONLY by `run-lang-tests.sh python --self-check`.

A lane never seen failing is not a lane — the same argument the B148 guard makes about itself. This
test must FAIL, and --self-check asserts the runner propagates that failure instead of swallowing it.
Normal runs exclude this directory (`pytest --ignore=selfcheck`).
"""


def test_deliberate_failure():
    assert False, "deliberate: this failure is the point"
