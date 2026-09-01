"""Unit tests for the registry -> Port component mapping (B78 follow-up, EMA-69).

These cover the DECISIONS the reconciler makes — the identifier fallback, the is_data_application
derivation, capability passthrough, and which registry components Port is missing. The thin HTTP
wrapper (token/list/upsert) is validated by hand against live Port and at runtime, not here.
"""


def test_component_entity_identifier_prefers_port_component(port_components):
    e = port_components.component_entity({"key": "k", "name": "N", "port_component": "pc"})
    assert e["identifier"] == "pc"


def test_component_entity_identifier_falls_back_to_key(port_components):
    e = port_components.component_entity({"key": "k", "name": "N"})
    assert e["identifier"] == "k"


def test_component_entity_is_data_application_mirrors_datahub_flag(port_components):
    assert port_components.component_entity(
        {"key": "k", "datahub_application": True})["properties"]["is_data_application"] is True
    assert port_components.component_entity(
        {"key": "k", "datahub_application": False})["properties"]["is_data_application"] is False
    # absent flag = pure-compute, not a data application
    assert port_components.component_entity(
        {"key": "k"})["properties"]["is_data_application"] is False


def test_component_entity_capabilities_passthrough_and_omitted_when_empty(port_components):
    props = port_components.component_entity(
        {"key": "k", "capabilities": ["observability"]})["properties"]
    assert props["capabilities"] == ["observability"]
    # an empty/absent list contributes no key rather than an empty array
    assert "capabilities" not in port_components.component_entity({"key": "k"})["properties"]
    assert "capabilities" not in port_components.component_entity(
        {"key": "k", "capabilities": []})["properties"]


def test_component_entity_title_description_and_blueprint(port_components):
    e = port_components.component_entity({"key": "k", "name": "Name", "description": "D"})
    assert e["title"] == "Name"
    assert e["properties"]["description"] == "D"
    assert e["blueprint"] == "component"
    # title falls back to the identifier when the registry omits a name
    assert port_components.component_entity({"key": "k"})["title"] == "k"


def test_reconcile_plan_flags_only_the_missing_components(port_components):
    apps = [{"key": "a"}, {"key": "b", "port_component": "bb"}, {"key": "c"}]
    entities, missing = port_components.reconcile_plan(apps, {"a", "bb"})
    assert len(entities) == 3          # every app becomes an idempotent upsert
    assert missing == ["c"]           # a present, bb present (by port_component), c is drift


def test_reconcile_plan_no_drift_when_every_component_present(port_components):
    _, missing = port_components.reconcile_plan([{"key": "a"}, {"key": "b"}], {"a", "b"})
    assert missing == []


def test_reconcile_plan_uses_port_component_id_not_key_for_membership(port_components):
    # operator's Port id is its port_component, NOT "operator" — the exact false-alarm from the live
    # 2026-08-31 reconciliation, guarded so a future change cannot reintroduce it.
    apps = [{"key": "operator", "port_component": "weyland-operator"}]
    _, missing = port_components.reconcile_plan(apps, {"weyland-operator"})
    assert missing == []
