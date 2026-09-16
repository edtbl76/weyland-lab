"""Tests for the fail-safe MLflow prompt cache (B100 Phase 2).

The contract is *a registry outage never takes a request offline*: with no MLflow reachable, ``load_prompt`` returns
the last-cached template, else the baked fallback; ``render_prompt`` formats whichever it got and, if a fetched
template has a bad placeholder, formats the baked fallback instead. Exercised with the registry deliberately absent
(MLFLOW_TRACKING_URI empty), driving the cache directly — no MLflow round-trip.
"""
import pytest

import prompts


@pytest.fixture(autouse=True)
def _isolate_cache():
    """Each test gets a clean cache and the fail-safe (no-registry) path."""
    prompts._cache.clear()
    saved = prompts.MLFLOW_TRACKING_URI
    prompts.MLFLOW_TRACKING_URI = ""      # force the fail-safe branch, never a live fetch
    yield
    prompts.MLFLOW_TRACKING_URI = saved
    prompts._cache.clear()


def test_load_prompt_returns_baked_fallback_when_uncached_and_no_registry():
    assert prompts.load_prompt("greeting", "hi there") == "hi there"


def test_load_prompt_returns_cached_within_ttl():
    import time
    prompts._cache["greeting"] = ("cached template", "3", time.monotonic())
    assert prompts.load_prompt("greeting", "IGNORED FALLBACK") == "cached template"


def test_load_prompt_returns_stale_cache_over_fallback_when_registry_down():
    # cache older than the TTL, but the registry is unreachable → last-known value beats the baked fallback
    prompts._cache["greeting"] = ("stale template", "2", 0.0)
    assert prompts.load_prompt("greeting", "baked") == "stale template"


def test_loaded_version_reports_cached_version_else_none():
    assert prompts.loaded_version("greeting") is None
    import time
    prompts._cache["greeting"] = ("t", "7", time.monotonic())
    assert prompts.loaded_version("greeting") == "7"


def test_render_prompt_formats_the_fallback_when_no_registry():
    out = prompts.render_prompt("welcome", "Hello {who}", who="Ed")
    assert out == "Hello Ed"


def test_render_prompt_recovers_from_a_bad_fetched_template():
    # a cached template with a placeholder the caller can't satisfy must not break the request:
    # render falls back to formatting the baked template.
    prompts._cache["welcome"] = ("Hi {missing}", "1", __import__("time").monotonic())
    out = prompts.render_prompt("welcome", "Hello {who}", who="Ed")
    assert out == "Hello Ed"
