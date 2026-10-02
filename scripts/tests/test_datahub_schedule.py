"""Tests for datahub_schedule.py — pause / resume a DataHub ingestion source's schedule (B199 store parking).

What these pin down: the source is found by its EXACT name (never a fuzzy match); the update resends every field it
read so only the schedule changes; and the change is verified by reading the source back — a mutation that returned
OK but did not land is a failure, not a success. GraphQL shapes follow DataHub v1.6.0's ingestion.graphql.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import datahub_schedule as ds

URN = "urn:li:dataHubIngestionSource:abc"
SRC = {"urn": URN, "name": "CockroachDB - Weyland", "type": "cockroachdb",
       "schedule": {"interval": "30 3 * * *", "timezone": "America/New_York"},
       "config": {"recipe": "source: {type: cockroachdb}", "version": "1.2.3", "executorId": "default",
                  "debugMode": False, "extraArgs": [{"key": "k", "value": "v"}]},
       "source": {"type": "SYSTEM"}}


class FakeGms:
    """Answers the three operations the helper uses; `lands=False` simulates a mutation that does not stick."""

    def __init__(self, sources, lands=True):
        self.sources = {s["urn"]: dict(s) for s in sources}
        self.lands = lands
        self.updates = []

    def __call__(self, query, variables):
        if "listIngestionSources" in query:
            hits = [s for s in self.sources.values() if variables["q"].lower() in s["name"].lower()]
            return {"data": {"listIngestionSources": {"total": len(hits), "ingestionSources": hits}}}
        if "updateIngestionSource" in query:
            self.updates.append(variables)
            if self.lands:
                s = self.sources[variables["urn"]]
                s["schedule"] = variables["input"].get("schedule")
            return {"data": {"updateIngestionSource": variables["urn"]}}
        if "ingestionSource(" in query:
            return {"data": {"ingestionSource": self.sources.get(variables["urn"])}}
        raise AssertionError(query)


def test_find_matches_the_exact_name_only():
    gms = FakeGms([SRC, dict(SRC, urn="urn:x", name="CockroachDB - Weyland (old)")])
    assert ds.find_source(gms, "CockroachDB - Weyland")["urn"] == URN


def test_find_refuses_a_name_that_is_not_there():
    with pytest.raises(ds.CannotRead):
        ds.find_source(FakeGms([SRC]), "MongoDB - Weyland")


def test_pause_removes_only_the_schedule_and_resends_everything_else():
    gms = FakeGms([SRC])
    ds.set_schedule(gms, "CockroachDB - Weyland", None)
    sent = gms.updates[0]["input"]
    assert sent.get("schedule") is None
    assert sent["name"] == SRC["name"] and sent["type"] == SRC["type"]
    assert sent["config"] == SRC["config"]          # recipe, version, executor, debug, extraArgs untouched
    assert sent["source"] == SRC["source"]
    assert gms.sources[URN]["schedule"] is None


def test_resume_sets_the_given_schedule():
    gms = FakeGms([dict(SRC, schedule=None)])
    ds.set_schedule(gms, "CockroachDB - Weyland", {"interval": "30 3 * * *", "timezone": "America/New_York"})
    assert gms.sources[URN]["schedule"] == {"interval": "30 3 * * *", "timezone": "America/New_York"}


def test_a_mutation_that_does_not_land_is_a_failure():
    with pytest.raises(ds.CannotRead, match="did not land"):
        ds.set_schedule(FakeGms([SRC], lands=False), "CockroachDB - Weyland", None)


def test_already_in_the_wanted_state_is_a_no_op():
    gms = FakeGms([dict(SRC, schedule=None)])
    assert ds.set_schedule(gms, "CockroachDB - Weyland", None) == "unchanged"
    assert gms.updates == []


def test_graphql_errors_refuse_even_on_http_200():
    with pytest.raises(ds.CannotRead):
        ds.find_source(lambda q, v: {"errors": [{"message": "Unauthorized"}]}, "x")


def test_describe_reads_the_schedule_or_paused():
    assert ds.describe(SRC) == "30 3 * * * America/New_York"
    assert ds.describe(dict(SRC, schedule=None)) == "paused"


def test_fingerprint_changes_with_the_recipe_and_nothing_else():
    a = ds.fingerprint(SRC)
    assert a == ds.fingerprint(dict(SRC, schedule=None))            # schedule is not part of it
    assert a != ds.fingerprint(dict(SRC, config=dict(SRC["config"], recipe="source: {type: other}")))
    assert len(a) == 12
