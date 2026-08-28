"""Hello-world fixture for the Python lane (B88).

This file's ONLY job is to prove the lane can run: image, toolchain, discovery and runner. If it
fails, the LANE is broken (exit 2) and nothing can be concluded about real code.
"""


def hello() -> str:
    return "hello, weyland"


def test_hello_returns_greeting():
    assert hello() == "hello, weyland"


def test_deliberate_failure():
    """Run ONLY by --self-check. Proves the runner propagates a failure rather than swallowing it.

    A lane never seen failing is not a lane — the same argument the B148 guard makes about itself.
    """
    assert False, "deliberate: this failure is the point"
