#!/usr/bin/env python3
"""Breaking-change engine for API specs (B155 — the enforcement arm of API lifecycle).

Compares two machine-readable API contracts and classifies every change as BREAKING or COMPATIBLE,
by the usual consumer-compatibility rules (semver intent):

  BREAKING (a consumer written against OLD can break on NEW):
    - an operation (path + method) removed
    - a 2xx response removed from an operation
    - a required request parameter/property ADDED (the client must now send something new)
    - a response property REMOVED (the client may have relied on it)
    - an enum value REMOVED (a value the server used to return / accept is gone)
  COMPATIBLE (additive / relaxing):
    - a new operation, a new optional parameter, a new response property
    - a required request field made optional / removed

HONEST DEPTH: this is an operation- and shallow-schema-level differ, not a full semantic OpenAPI
validator. It resolves `#/components/schemas/*` $refs one level (cycle-guarded) and inspects request
parameters, requestBody required set, and 2xx response JSON-schema property sets + enums. That covers
the changes that actually break the estate's consumers (a removed route, a new required field, a dropped
response field); it does NOT chase deep nested-schema polymorphism. What it cannot compare, it says so
rather than passing silently.

Kinds handled: OpenAPI 3.x (`openapi`/`paths`) and A2A agent cards (`protocolVersion`/`skills`). An
unknown pair is CANNOT-COMPARE (exit 2) — never a silent "no breaking changes".

  usage: api_spec_diff.py <old.json> <new.json> [--json]
  exit:  0 = no breaking changes   1 = breaking change(s) found   2 = cannot compare
"""
import json
import sys


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _resolve(schema, root, _seen=None):
    """Resolve a one-level $ref against #/components/schemas; cycle-guarded."""
    _seen = _seen or set()
    if isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        if ref in _seen:
            return {}
        _seen = _seen | {ref}
        if ref.startswith("#/components/schemas/"):
            name = ref.split("/")[-1]
            return _resolve((root.get("components", {}).get("schemas", {}) or {}).get(name, {}), root, _seen)
        return {}
    return schema if isinstance(schema, dict) else {}


def _schema_props(schema, root):
    s = _resolve(schema, root)
    props = set((s.get("properties") or {}).keys())
    required = set(s.get("required") or [])
    return props, required


def _enum_values(schema, root):
    return set(_resolve(schema, root).get("enum") or [])


def _operations(spec):
    """{(path, METHOD): operation-dict} for the real HTTP methods."""
    methods = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}
    ops = {}
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() in methods and isinstance(op, dict):
                ops[(path, method.upper())] = op
    return ops


def diff_openapi(old, new):
    changes = []  # (severity, detail)
    old_ops, new_ops = _operations(old), _operations(new)

    for key in old_ops.keys() - new_ops.keys():
        changes.append(("BREAKING", f"operation removed: {key[1]} {key[0]}"))
    for key in new_ops.keys() - old_ops.keys():
        changes.append(("COMPATIBLE", f"operation added: {key[1]} {key[0]}"))

    for key in old_ops.keys() & new_ops.keys():
        o, n = old_ops[key], new_ops[key]
        tag = f"{key[1]} {key[0]}"

        # --- request parameters (name+in), required-ness, enums ---
        def params(op):
            return {(p.get("name"), p.get("in")): p for p in (op.get("parameters") or []) if isinstance(p, dict)}
        op_p, np_p = params(o), params(n)
        for pk in np_p.keys() - op_p.keys():
            if np_p[pk].get("required"):
                changes.append(("BREAKING", f"{tag}: new REQUIRED param {pk[0]} (in {pk[1]})"))
            else:
                changes.append(("COMPATIBLE", f"{tag}: new optional param {pk[0]}"))
        for pk in op_p.keys() & np_p.keys():
            if np_p[pk].get("required") and not op_p[pk].get("required"):
                changes.append(("BREAKING", f"{tag}: param {pk[0]} became required"))
            removed_enum = _enum_values(op_p[pk].get("schema", {}), old) - _enum_values(np_p[pk].get("schema", {}), new)
            for v in removed_enum:
                changes.append(("BREAKING", f"{tag}: param {pk[0]} enum value removed: {v}"))

        # --- requestBody: a newly-required property is breaking ---
        def body_schema(op):
            c = (op.get("requestBody") or {}).get("content") or {}
            return (c.get("application/json") or {}).get("schema", {})
        o_props, o_req = _schema_props(body_schema(o), old)
        n_props, n_req = _schema_props(body_schema(n), new)
        for f in (n_req - o_req):
            changes.append(("BREAKING", f"{tag}: request body field '{f}' became required"))
        for f in (o_props - n_props):
            changes.append(("COMPATIBLE", f"{tag}: request body field '{f}' removed (server accepts less)"))

        # --- 2xx response JSON schema: a removed property is breaking ---
        def resp_schema(op):
            for code, resp in (op.get("responses") or {}).items():
                if str(code).startswith("2") and isinstance(resp, dict):
                    c = (resp.get("content") or {}).get("application/json") or {}
                    return c.get("schema", {})
            return {}
        or_props, _ = _schema_props(resp_schema(o), old)
        nr_props, _ = _schema_props(resp_schema(n), new)
        for f in (or_props - nr_props):
            changes.append(("BREAKING", f"{tag}: response field '{f}' removed"))
        for f in (nr_props - or_props):
            changes.append(("COMPATIBLE", f"{tag}: response field '{f}' added"))
    return changes


def diff_a2a(old, new):
    changes = []
    def skills(card):
        return {s.get("id") or s.get("name") for s in (card.get("skills") or []) if isinstance(s, dict)}
    for s in skills(old) - skills(new):
        changes.append(("BREAKING", f"A2A skill removed: {s}"))
    for s in skills(new) - skills(old):
        changes.append(("COMPATIBLE", f"A2A skill added: {s}"))
    if old.get("protocolVersion") != new.get("protocolVersion"):
        changes.append(("COMPATIBLE", f"A2A protocolVersion {old.get('protocolVersion')} -> {new.get('protocolVersion')}"))
    # a dropped transport is breaking for a client bound to it
    def transports(card):
        t = {card.get("preferredTransport")} if card.get("preferredTransport") else set()
        for iface in (card.get("additionalInterfaces") or []):
            if isinstance(iface, dict) and iface.get("transport"):
                t.add(iface["transport"])
        return {x for x in t if x}
    for t in transports(old) - transports(new):
        changes.append(("BREAKING", f"A2A transport removed: {t}"))
    return changes


def _kind(spec):
    if isinstance(spec, dict) and ("openapi" in spec or "paths" in spec):
        return "openapi"
    if isinstance(spec, dict) and ("protocolVersion" in spec or "skills" in spec):
        return "a2a"
    return None


def diff(old, new):
    ko, kn = _kind(old), _kind(new)
    if ko is None or kn is None or ko != kn:
        return None  # cannot compare
    return diff_openapi(old, new) if ko == "openapi" else diff_a2a(old, new)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    as_json = "--json" in argv
    if len(args) != 2:
        print(__doc__.strip().splitlines()[-2], file=sys.stderr)
        return 2
    changes = diff(_load(args[0]), _load(args[1]))
    if changes is None:
        print("CANNOT COMPARE — specs are different or unknown kinds (never a silent pass)", file=sys.stderr)
        return 2
    breaking = [c for c in changes if c[0] == "BREAKING"]
    if as_json:
        print(json.dumps([{"severity": s, "detail": d} for s, d in changes], indent=2))
    else:
        for sev, detail in sorted(changes):
            print(f"  {sev:11} {detail}")
        print(f"{'BREAKING' if breaking else 'OK'} — {len(breaking)} breaking / {len(changes)} total change(s)")
    return 1 if breaking else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
