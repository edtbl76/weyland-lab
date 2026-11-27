# GENERATED from golden-paths-shared/python/integration/conftest.py by scripts/sync-golden-shared.sh: edit the source, not this copy.
"""The integration tier needs REAL backends: a missing one fails the run, it is never skipped (B260).

SOURCE: golden-paths-shared/python/integration/. Each path holds a synced copy (scripts/sync-golden-shared.sh).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REQUIRED = ["GOLDEN_DATABASE_URL", "GOLDEN_VALKEY_URL", "GOLDEN_KAFKA_BOOTSTRAP", "GOLDEN_S3_ENDPOINT",
            "GOLDEN_S3_ACCESS_KEY", "GOLDEN_S3_SECRET_KEY"]


def pytest_configure(config):
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        raise pytest.UsageError(f"integration tier: backend settings missing ({', '.join(missing)}); "
                                "refusing to run (an unchecked backend is never 'passed')")
