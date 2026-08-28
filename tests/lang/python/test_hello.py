"""Hello-world fixture for the Python lane (B88).

Its only job is to prove the lane can run at all — image, toolchain, discovery, runner. A failure
here means the LANE is broken (exit 2); nothing can be concluded about real code.
"""


def hello() -> str:
    return "hello, weyland"


def test_hello_returns_greeting():
    assert hello() == "hello, weyland"
