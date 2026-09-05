"""Asset-registration guard (B158 follow-up F).

The B158 audit's Plane-2 footgun: `assets/__init__.py` hand-imports every asset AND hand-lists it in
`all_assets` — miss one and the product SILENTLY does not load (it happened once at B113: `edgar_land`
was briefly unregistered). Full autodiscovery (dropping the manual lists) is the elegant fix but changes
the dagster load path and can only be validated by materialization; this closes the *silent* half safely
and now: a static check (stdlib ast, no dagster) that FAILS when a land asset defined via
`build_land_asset(...)` is not BOTH imported and present in `all_assets`. It runs in the light pytest lane,
so the footgun is loud at CI instead of at a missing-asset-in-production moment.

Scoped to the `build_land_asset` land modules — the concrete class of bug the audit cited; the same shape
extends to the transform/store factories when they need it.
"""
import ast
import pathlib

_ASSETS_DIR = pathlib.Path(__file__).resolve().parent.parent / "weyland_pipeline" / "assets"


def _land_asset_symbols(assets_dir):
    """{symbol: module_filename} for every top-level `NAME = build_land_asset(...)` in a datasets_*_land.py."""
    out = {}
    for py in sorted(pathlib.Path(assets_dir).glob("datasets_*_land.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                fn = node.value.func
                if isinstance(fn, ast.Name) and fn.id == "build_land_asset":
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            out[t.id] = py.name
    return out


def _imported_names(init_py):
    tree = ast.parse(pathlib.Path(init_py).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
    return names


def unregistered_land_assets(assets_dir):
    """Land-asset symbols defined via build_land_asset but not IMPORTED in __init__.py. Empty = clean.

    Since B158-F, all_assets is DERIVED from the imports (autodiscovery reads every imported AssetsDefinition
    from globals), so the import IS the registration — a symbol that is imported cannot fail to register, and
    one that is not imported will silently never load. This guards exactly that: every build_land_asset must
    be imported here.
    """
    init_py = pathlib.Path(assets_dir) / "__init__.py"
    imported = _imported_names(init_py)
    missing = {}
    for sym, mod in _land_asset_symbols(assets_dir).items():
        if sym not in imported:
            missing[sym] = f"{mod}: not imported (autodiscovery will never register it)"
    return missing


def test_every_build_land_asset_is_registered_in_init():
    # the real guard: no land asset may be defined without being imported + listed in all_assets
    missing = unregistered_land_assets(_ASSETS_DIR)
    assert not missing, f"land assets defined but not registered in assets/__init__.py: {missing}"


def test_the_finance_landers_are_actually_covered():
    # a positive control: the check is really SEEING the finance land assets (not vacuously passing on an
    # empty set) — the four B113 finance landers must be among the symbols it found.
    found = set(_land_asset_symbols(_ASSETS_DIR))
    assert {
        "datasets_finance_fred_land",
        "datasets_finance_edgar_land",
        "datasets_finance_edgar_text_land",
        "datasets_finance_market_land",
    } <= found


def test_detects_an_unregistered_land_asset(tmp_path):
    # the negative case: a land module whose build_land_asset symbol is not imported in __init__ is flagged.
    (tmp_path / "datasets_x_land.py").write_text(
        "from .datasets_lib.landers import build_land_asset\n"
        "foo_land = build_land_asset('foo_land', 'x', None, group='g')\n",
        encoding="utf-8",
    )
    (tmp_path / "__init__.py").write_text("# foo_land not imported here\n", encoding="utf-8")
    missing = unregistered_land_assets(tmp_path)
    assert "foo_land" in missing
    assert "not imported" in missing["foo_land"]


def test_a_registered_land_asset_is_not_flagged(tmp_path):
    (tmp_path / "datasets_y_land.py").write_text(
        "from .datasets_lib.landers import build_land_asset\n"
        "bar_land = build_land_asset('bar_land', 'y', None, group='g')\n",
        encoding="utf-8",
    )
    # importing it is the registration (autodiscovery collects it) — nothing else needed
    (tmp_path / "__init__.py").write_text("from .datasets_y_land import bar_land\n", encoding="utf-8")
    assert unregistered_land_assets(tmp_path) == {}
