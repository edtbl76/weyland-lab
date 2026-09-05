#!/usr/bin/env python3
"""Generate an ODCS contract skeleton from the mesh's existing substance (B157 / B158 follow-up E).

"Generate ODCS from the substance": rather than hand-author every contract, this reads what the mesh
already knows — the Trino physical schema (columns + types), the Soda checks (data-quality rules), and the
dbt model/column descriptions — and emits a conformant ODCS v3 (lab-subset) contract. It is how the
music/health contracts were produced and how a new product's contract is bootstrapped; a human then adds
the prose (purpose/usage/limitations) that only a person knows. Re-running it keeps the schema + quality
sections in lockstep with the substance.

  usage: gen_odcs_contract.py --domain <d> --product "<Name>" --table <catalog.schema.table> \
                              --id <slug> [--layer gold|silver] [--source <system>] [--out <file>]

Reads Trino at $TRINO_HTTP (default the noauth gateway); the Soda file at
services/weyland-dagster/soda/checks/<domain>.yml (+ <domain>_silver.yml); the dbt schema at
services/weyland-dagster/dbt/models/marts/<domain>/schema.yml when the table is a mart.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.request

_HERE = pathlib.Path(__file__).resolve().parent.parent
_DAGSTER = _HERE / "nodes/mother/lab/weyland-platform/services/weyland-dagster"
_TRINO = os.environ.get("TRINO_HTTP", "http://trino-noauth.data-mesh.svc.cluster.local:8080")
_OWNER = "ed@timberbacklabs.com"

# Trino physical type -> ODCS logicalType.
_LOGICAL = {
    "varchar": "string", "char": "string",
    "bigint": "integer", "integer": "integer", "int": "integer", "smallint": "integer", "tinyint": "integer",
    "double": "number", "real": "number", "decimal": "number",
    "boolean": "boolean", "date": "date", "timestamp": "date",
}


def _logical(physical_type):
    base = re.split(r"[(\s]", physical_type.strip().lower(), maxsplit=1)[0]
    return _LOGICAL.get(base, "string")


def trino_columns(catalog, schema, table):
    """[(name, physical_type)] for a Trino table, in ordinal order — or raise (fail closed)."""
    # nosec B608 — catalog/schema/table come from a git-reviewed contract's physicalName (a dev-run CLI arg),
    # not from untrusted input, and Trino's REST /v1/statement has no bind-parameter API to use instead.
    sql = (f"SELECT column_name, data_type FROM {catalog}.information_schema.columns "  # nosec B608
           f"WHERE table_schema='{schema}' AND table_name='{table}' ORDER BY ordinal_position")
    body = _post(f"{_TRINO}/v1/statement", sql.encode())
    rows = []
    while True:
        rows.extend(body.get("data") or [])
        nxt = body.get("nextUri")
        if not nxt:
            break
        nxt = _TRINO + re.sub(r"^[a-zA-Z]+://[^/]+", "", nxt)
        body = _get(nxt)
        if (body.get("stats") or {}).get("state") == "FAILED":
            raise RuntimeError(f"Trino query FAILED for {catalog}.{schema}.{table}")
    if not rows:
        raise RuntimeError(f"no columns found for {catalog}.{schema}.{table} (wrong table?)")
    return [(r[0], r[1]) for r in rows]


def _post(url, data):
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"X-Trino-User": "odcs-generator", "Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 — fixed TRINO_HTTP gateway (env-configured in-cluster host), no user-controlled URL
        return json.load(r)


def _get(url):
    req = urllib.request.Request(url, headers={"X-Trino-User": "odcs-generator"})
    with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 — nextUri stays on TRINO_HTTP (host re-pointed by the caller); no user-controlled URL
        return json.load(r)


def soda_rules(domain, table):
    """Raw Soda checks under `checks for <table>:` across the domain's soda files → quality-rule strings."""
    rules = []
    for name in (f"{domain}.yml", f"{domain}_silver.yml"):
        path = _DAGSTER / "soda" / "checks" / name
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        grabbing = False
        for ln in lines:
            if re.match(rf"^checks for {re.escape(table)}:\s*$", ln):
                grabbing = True
                continue
            if grabbing:
                if re.match(r"^\S", ln):  # dedent to column 0 = next block
                    grabbing = False
                    continue
                m = re.match(r"^\s*-\s*(.+?)\s*$", ln)
                if m:
                    rules.append(re.sub(r"\s*#.*$", "", m.group(1)).strip())
    return rules


def dbt_descriptions(domain, table):
    """{column: description} + a model description for a mart, parsed loosely from dbt schema.yml."""
    path = _DAGSTER / "dbt" / "models" / "marts" / domain / "schema.yml"
    out, model_desc = {}, ""
    if not path.exists():
        return out, model_desc
    try:
        import yaml
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for model in doc.get("models", []):
            if model.get("name") == table:
                model_desc = (model.get("description") or "").strip()
                for col in model.get("columns", []):
                    if col.get("name"):
                        out[col["name"]] = (col.get("description") or "").strip()
    except Exception:
        pass
    return out, model_desc


def build_contract(domain, product, physical, cid, layer, source):
    catalog, schema, table = physical.split(".", 2)
    cols = trino_columns(catalog, schema, table)
    descs, model_desc = dbt_descriptions(domain, table)
    rules = soda_rules(domain, table)

    props = []
    for name, ptype in cols:
        p = {"name": name, "logicalType": _logical(ptype), "physicalType": ptype}
        if descs.get(name):
            p["description"] = descs[name]
        props.append(p)

    quality = [{"property": "table", "rule": r} for r in rules] or [
        {"property": "table", "rule": "row_count > 0"}]

    return {
        "apiVersion": "v3.0.0",
        "kind": "DataContract",
        "id": cid,
        "name": product,
        "version": "1.0.0",
        "status": "active",
        "domain": domain,
        "dataProduct": product,
        "tenant": "weyland",
        "description": {
            "purpose": model_desc or f"The {product} data product of the {domain} domain.",
            "usage": f"Query the {physical} table in Trino; see docs/demos/{domain}-domain.md for worked queries and the BI surfaces.",
        },
        "servers": [{"server": f"trino-{schema}", "type": "trino", "catalog": catalog,
                     "schema": schema, "physicalName": physical}],
        "schema": [{"name": table, "physicalName": physical, "properties": props}],
        "quality": quality,
        "slaProperties": [{"property": "frequency", "value": "on-demand"},
                          {"property": "retention", "value": "indefinite"}],
        "team": [{"role": "owner", "username": _OWNER}],
        "support": [{"channel": "runbook", "url": f"docs/demos/{domain}-domain.md"}],
        "customProperties": [{"property": "medallion_layer", "value": layer},
                             {"property": "source_system", "value": source}],
    }


def to_yaml(contract):
    import yaml
    return yaml.safe_dump(contract, sort_keys=False, default_flow_style=False, width=100, allow_unicode=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--product", required=True)
    ap.add_argument("--table", required=True, help="catalog.schema.table")
    ap.add_argument("--id", required=True)
    ap.add_argument("--layer", default="gold")
    ap.add_argument("--source", default="")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    contract = build_contract(a.domain, a.product, a.table, a.id, a.layer, a.source)
    text = ("# Generated by scripts/gen_odcs_contract.py from Trino + Soda + dbt substance (B157). "
            "Enrich the description prose by hand.\n" + to_yaml(contract))
    if a.out:
        out = pathlib.Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
