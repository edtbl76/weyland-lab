# Task: fix `median()` for even-length lists

`stats.py` has a `median()` function. It is correct for odd-length lists but
wrong for even-length lists: it returns the lower of the two middle values
instead of the average of the two middle values.

Fix `median()` in `stats.py` so that all tests in `test_stats.py` pass. Do not
change the tests.

Verify with:

    python3 -m unittest -v test_stats
