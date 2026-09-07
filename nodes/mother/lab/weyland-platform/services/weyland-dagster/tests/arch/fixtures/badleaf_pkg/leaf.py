"""Deliberately-violating fixture leaf (B152 architecture test).

A pure leaf that imports dagster — the exact boundary the real contract forbids. tests/test_architecture.py
runs import-linter against importlinter-violation.ini and asserts the contract BREAKS on this file, proving
the rule catches a real violation rather than merely loading. Never imported by production code.
"""
import dagster  # noqa: F401  — the planted violation


def shape():
    return "this fixture exists only to be caught by the architecture contract"
