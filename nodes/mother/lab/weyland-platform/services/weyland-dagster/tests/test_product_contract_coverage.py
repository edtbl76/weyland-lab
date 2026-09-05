"""Product ↔ contract coverage (B157 / B158 follow-up A-tail 5).

Governance-by-CI, extended to contracts: every DATA-domain DataHub data product (Music / Health /
Finance) must have an ODCS contract. Without this, a new product can ship uncontracted and nothing says
so — the same no-positive-signal shape the catalog-coverage guard closes for datasets. Static: ast-reads
the emit's `_PRODUCTS` (the product source of truth) + the `dataProduct` of every `*.odcs.yaml`; no
dagster. Operational domains (Platform & Ops, Docs & RAG, ML & Modeling, AIDLC Knowledge) are out of
scope — they carry no domain data to contract.
"""
import ast
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent.parent
_EMIT = _HERE / "weyland_pipeline" / "datahub_emit.py"
_CONTRACTS = _HERE / "contracts"
_DATA_DOMAINS = {"Music", "Health", "Finance"}


def _products_by_domain():
    """{product_name: domain} from the emit's `_PRODUCTS = [(name, domain, desc, pats), ...]`."""
    tree = ast.parse(_EMIT.read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_PRODUCTS" for t in node.targets
        ) and isinstance(node.value, ast.List):
            for el in node.value.elts:
                if isinstance(el, ast.Tuple) and len(el.elts) >= 2:
                    name, domain = el.elts[0], el.elts[1]
                    if isinstance(name, ast.Constant) and isinstance(domain, ast.Constant):
                        out[name.value] = domain.value
    return out


def _contract_products():
    """The set of `dataProduct` values across every *.odcs.yaml (stdlib-only; a tiny hand parser avoids
    a yaml dependency for one scalar field)."""
    import re
    products = set()
    for f in _CONTRACTS.rglob("*.odcs.yaml"):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^dataProduct:\s*(.+?)\s*$", line)
            if m:
                products.add(m.group(1).strip().strip('"').strip("'"))
                break
    return products


def test_every_data_domain_product_has_a_contract():
    by_domain = _products_by_domain()
    assert by_domain, "could not parse _PRODUCTS from datahub_emit.py"
    data_products = {n for n, d in by_domain.items() if d in _DATA_DOMAINS}
    assert data_products, "no Music/Health/Finance products found — extraction likely broke"
    contracted = _contract_products()
    missing = sorted(data_products - contracted)
    assert not missing, f"data products with no ODCS contract in contracts/: {missing}"
