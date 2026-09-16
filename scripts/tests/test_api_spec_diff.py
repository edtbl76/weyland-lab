"""Tests for scripts/lib/api_spec_diff.py — the API/A2A contract-diff classifier (B155).

This decides whether a spec change is BREAKING or COMPATIBLE — the call a CI gate acts on. A misclassification
is silent and expensive: a breaking change waved through, or a safe change blocked. All pure (stdlib json only),
so every case is a real input→output assertion.
"""
import api_spec_diff as d


def test_operations_extracts_http_methods_only():
    spec = {"paths": {"/x": {"get": {}, "post": {}, "parameters": [], "summary": "s"}}}
    assert set(d._operations(spec)) == {("/x", "GET"), ("/x", "POST")}


def test_removed_operation_is_breaking_added_is_compatible():
    assert ("BREAKING", "operation removed: GET /x") in d.diff_openapi({"paths": {"/x": {"get": {}}}}, {"paths": {}})
    assert ("COMPATIBLE", "operation added: GET /x") in d.diff_openapi({"paths": {}}, {"paths": {"/x": {"get": {}}}})


def test_new_required_param_breaking_optional_compatible():
    base = lambda params: {"paths": {"/x": {"get": {"parameters": params}}}}
    br = d.diff_openapi(base([]), base([{"name": "q", "in": "query", "required": True}]))
    assert any(s == "BREAKING" and "new REQUIRED param q" in t for s, t in br)
    co = d.diff_openapi(base([]), base([{"name": "q", "in": "query", "required": False}]))
    assert any(s == "COMPATIBLE" and "new optional param q" in t for s, t in co)


def test_param_became_required_is_breaking():
    old = {"paths": {"/x": {"get": {"parameters": [{"name": "q", "in": "query", "required": False}]}}}}
    new = {"paths": {"/x": {"get": {"parameters": [{"name": "q", "in": "query", "required": True}]}}}}
    assert any(s == "BREAKING" and "param q became required" in t for s, t in d.diff_openapi(old, new))


def test_removed_response_field_breaking_added_compatible():
    spec = lambda props: {"paths": {"/x": {"get": {"responses": {
        "200": {"content": {"application/json": {"schema": {"properties": props}}}}}}}}}
    old, new = spec({"a": {}, "b": {}}), spec({"a": {}})
    assert any(s == "BREAKING" and "response field 'b' removed" in t for s, t in d.diff_openapi(old, new))
    assert any(s == "COMPATIBLE" and "response field 'b' added" in t for s, t in d.diff_openapi(new, old))


def test_request_body_newly_required_field_is_breaking():
    spec = lambda req: {"paths": {"/x": {"post": {"requestBody": {"content": {"application/json": {
        "schema": {"properties": {"a": {}}, "required": req}}}}}}}}
    assert any(s == "BREAKING" and "request body field 'a' became required" in t
               for s, t in d.diff_openapi(spec([]), spec(["a"])))


def test_ref_is_resolved_when_reading_schema_props():
    root = {"components": {"schemas": {"Foo": {"properties": {"a": {}, "b": {}}, "required": ["a"]}}}}
    props, req = d._schema_props({"$ref": "#/components/schemas/Foo"}, root)
    assert props == {"a", "b"} and req == {"a"}


def test_removed_enum_value_on_param_is_breaking():
    p = lambda vals: {"paths": {"/x": {"get": {"parameters": [{"name": "q", "in": "query", "schema": {"enum": vals}}]}}}}
    assert any(s == "BREAKING" and "enum value removed: b" in t for s, t in d.diff_openapi(p(["a", "b"]), p(["a"])))


def test_a2a_skill_protocol_and_transport_diffs():
    old = {"protocolVersion": "1", "skills": [{"id": "s1"}, {"id": "s2"}], "preferredTransport": "JSONRPC"}
    new = {"protocolVersion": "2", "skills": [{"id": "s1"}], "preferredTransport": "GRPC"}
    ch = d.diff_a2a(old, new)
    assert ("BREAKING", "A2A skill removed: s2") in ch
    assert ("BREAKING", "A2A transport removed: JSONRPC") in ch
    assert any("protocolVersion 1 -> 2" in t for _, t in ch)


def test_kind_detection_and_diff_refuses_mismatched_kinds():
    assert d._kind({"openapi": "3.0", "paths": {}}) == "openapi"
    assert d._kind({"protocolVersion": "1"}) == "a2a"
    assert d._kind({"x": 1}) is None
    assert d.diff({"openapi": "3.0", "paths": {}}, {"protocolVersion": "1"}) is None   # cannot compare
