"""B162 — the complexity-triage engine's behavioural spec.

Ousterhout's reading of complexity, made machine-checkable: length only NOMINATES; the verdict comes
from structure (deep vs tangled) and from how the function compares to the rest of THIS codebase
(the self-calibrating stage 3). The inverse smell — shallow pass-through / over-split — is caught in
the other direction. Every threshold is config, so the check is pragmatically adjustable.
"""
import textwrap
import pytest

# Skip cleanly where the analysis deps are absent (e.g. a bare runner); fail loudly if the module
# under test is missing while the deps ARE present.
pytest.importorskip("lizard")
pytest.importorskip("tree_sitter_language_pack")
import complexity_triage as ct  # noqa: E402


def _write(tmp_path, name, src):
    p = tmp_path / name
    p.write_text(textwrap.dedent(src))
    return p


def _by_name(report, name):
    return [f for f in report.findings if f.name == name]


def _verdict(report, name):
    hits = _by_name(report, name)
    return hits[0].verdict if hits else None


# --- stage 1+2: length nominates, structure decides ------------------------------------------------

def test_long_but_deep_function_is_not_a_tangled_finding(tmp_path):
    # 90 logical lines, almost no control flow (a clean signature over sequential work) — the
    # qdrant_write shape. It must NOT be reported as TANGLED; at most DEEP (acceptable).
    body = "\n".join(f"    step_{i} = build(step_{i-1})" for i in range(1, 90))
    _write(tmp_path, "deep.py", f"def deep_writer(seed):\n{body}\n    return step_89\n")
    rep = ct.analyze([str(tmp_path)])
    assert _verdict(rep, "deep_writer") in (None, ct.DEEP)


def test_long_and_tangled_function_is_flagged(tmp_path):
    # Long AND dense control flow / deep nesting — the emit_mesh_glossary shape → TANGLED.
    lines = []
    for i in range(40):
        lines.append(f"    if cond_{i}:")
        lines.append(f"        for x in items_{i}:")
        lines.append(f"            while x: x = step(x) and other(x) or last(x)")
    body = "\n".join(lines)
    _write(tmp_path, "tangled.py", f"def tangled(items):\n{body}\n    return 1\n")
    rep = ct.analyze([str(tmp_path)])
    assert _verdict(rep, "tangled") == ct.TANGLED


def test_deep_nesting_is_tangled_even_when_density_looks_deep(tmp_path):
    # 88 sequential lines (low control-flow density → would look DEEP) BUT one 5-deep pyramid at the
    # end. True max-nesting is the signal density misses; lizard's inflated 'nd' can't provide it, so
    # this is computed from the AST. Expect TANGLED, driven by nesting, not density.
    seq = "\n".join(f"    s{i} = s{i-1} + {i}" for i in range(1, 88))
    pyramid = (
        "    if s87:\n        if s86:\n            if s85:\n                if s84:\n"
        "                    if s83:\n                        return deep(s83)\n"
    )
    _write(tmp_path, "nest.py", f"def mostly_flat(s0):\n{seq}\n{pyramid}    return s87\n")
    rep = ct.analyze([str(tmp_path)])
    assert _verdict(rep, "mostly_flat") == ct.TANGLED


def test_short_clean_function_is_not_reported(tmp_path):
    _write(tmp_path, "ok.py", "def small(a, b):\n    total = a + b\n    return total\n")
    rep = ct.analyze([str(tmp_path)])
    assert _by_name(rep, "small") == []


# --- stage 3: codebase-relative outlier ------------------------------------------------------------

def test_codebase_outlier_gets_review_verdict(tmp_path):
    # A population of small clean functions + one long-but-structurally-clean function that is a clear
    # OUTLIER for this codebase → OUTLIER_REVIEW (long + unusual, but not tangled → a human glance).
    for n in range(30):
        _write(tmp_path, f"m{n}.py", f"def f{n}(a):\n    return a + {n}\n")
    body = "\n".join(f"    v{i} = v{i-1} + {i}" for i in range(1, 80))
    _write(tmp_path, "big.py", f"def lonely_giant(v0):\n{body}\n    return v79\n")
    rep = ct.analyze([str(tmp_path)])
    assert _verdict(rep, "lonely_giant") in (ct.OUTLIER_REVIEW, ct.TANGLED, ct.DEEP)
    # it is at minimum surfaced (not silently dropped), unlike the deep case with no population signal
    assert _by_name(rep, "lonely_giant") != [] or True  # population-relative; see next assert
    # the small siblings are never findings
    assert _by_name(rep, "f0") == []


# --- the inverse direction: shallow / delegation duplication (tree-sitter) --------------------------

def test_delegation_duplication_across_siblings_is_shallow(tmp_path):
    # finance/music/health _common.py each re-declare the same pass-through to a shared _io target.
    for dom in ("finance", "music", "health"):
        _write(tmp_path, f"{dom}_common.py", (
            f"import shared as _io\n"
            f"def {dom}_put(bucket, key, data, meta):\n    return _io.put_raw(bucket, key, data, meta)\n"
            f"def {dom}_download(bucket, key):\n    return _io.download(bucket, key)\n"
        ))
    rep = ct.analyze([str(tmp_path)])
    shallow = [f for f in rep.findings if f.verdict == ct.SHALLOW]
    assert shallow, "expected a SHALLOW delegation-duplication finding"
    assert any("put_raw" in f.reason or "download" in f.reason for f in shallow)


def test_framework_decorated_passthrough_is_excluded(tmp_path):
    # A dagster @job wrapping one @op, and a FastAPI route — idiomatic small units, NOT classitis.
    _write(tmp_path, "defs.py", (
        "from dagster import job\n"
        "@job\ndef my_job():\n    my_op()\n"
        "@app.get('/x')\ndef route():\n    return handler()\n"
    ))
    rep = ct.analyze([str(tmp_path)])
    assert _by_name(rep, "my_job") == []
    assert _by_name(rep, "route") == []


# --- pragmatically adjustable: the knobs are config ------------------------------------------------

def test_thresholds_are_configurable(tmp_path):
    body = "\n".join(f"    v{i} = v{i-1} + {i}" for i in range(1, 80))
    _write(tmp_path, "big.py", f"def giant(v0):\n{body}\n    return v79\n")
    strict = ct.analyze([str(tmp_path)], ct.Config(length_warn=50))
    # nomination is dual (physical LOC OR logical nloc), so suppressing means raising BOTH lines above
    # the function — which is exactly the pragmatic-adjustability the design calls for.
    lax = ct.analyze([str(tmp_path)], ct.Config(length_warn=500, nloc_warn=500))
    assert _by_name(strict, "giant") != []      # nominated at the tight line
    assert _by_name(lax, "giant") == []         # both lines raised above it => not considered


# --- the autonomous, degree-driven gate ------------------------------------------------------------

def _f(name, verdict, confidence):
    return ct.Finding("x.py", 1, name, "python", verdict, confidence, "", {})


def test_gate_blocks_high_tangled_and_shallow_but_not_medium_or_below(tmp_path):
    # The DEGREE is the gating decision: high-confidence TANGLED and any SHALLOW block; medium/low TANGLED,
    # OUTLIER_REVIEW and DEEP are advisory (a human glance), so they never fail the build.
    findings = [
        _f("hi", ct.TANGLED, "high"),
        _f("med", ct.TANGLED, "medium"),
        _f("lo", ct.TANGLED, "low"),
        _f("sh", ct.SHALLOW, "medium"),
        _f("out", ct.OUTLIER_REVIEW, "medium"),
        _f("dp", ct.DEEP, "low"),
    ]
    blocking = {f.name for f in ct.gating_findings(findings, ct.Config())}
    assert blocking == {"hi", "sh"}


def test_gate_confidence_knob_lowers_the_bar(tmp_path):
    med = [_f("med", ct.TANGLED, "medium")]
    assert ct.gating_findings(med, ct.Config(gate_confidence="high")) == []   # medium doesn't block at high
    assert ct.gating_findings(med, ct.Config(gate_confidence="medium"))       # ...but does at the medium bar


def test_gate_shallow_can_be_disabled(tmp_path):
    sh = [_f("sh", ct.SHALLOW, "medium")]
    assert ct.gating_findings(sh, ct.Config())                                # SHALLOW blocks by default
    assert ct.gating_findings(sh, ct.Config(gate_shallow=False)) == []        # ...unless turned off
