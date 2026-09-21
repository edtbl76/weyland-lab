"""B162 complexity-triage engine — how the lab reads complexity, made machine-checkable.

Length only NOMINATES a function; the verdict comes from STRUCTURE (deep vs tangled) and from how the
function compares to the rest of THIS codebase (stage 3, self-calibrating). The inverse smell — shallow
pass-through / over-split delegation — is caught in the other direction. Every threshold is a `Config`
field, so the check is pragmatically adjustable rather than a hardcoded line count.

Ousterhout's own principle applied to the tool: a simple interface (`analyze`) over substantial
implementation. Numeric metrics come from `lizard` (uniform across ~20 languages, incl. the Flink Java);
the structural shapes that a metric can't see (delegation / shallow wrappers, decorator-awareness) come
from `tree-sitter` (Python first; Java/others extend the same two functions).
"""
from __future__ import annotations

import os
import statistics
from collections import namedtuple
from dataclasses import dataclass, field

import lizard
from tree_sitter_language_pack import get_parser

# --- verdicts -------------------------------------------------------------------------------------
DEEP = "DEEP"                     # long but a clean signature over sequential work — acceptable
TANGLED = "TANGLED"              # long AND dense/nested control flow — stop and fix
OUTLIER_REVIEW = "OUTLIER_REVIEW"  # long AND unusual for this codebase — a human glance
SHALLOW = "SHALLOW"             # pass-through / over-split delegation — the inverse smell

_EXT_LANG = {
    ".py": "python", ".java": "java", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".scala": "scala", ".swift": "swift", ".kt": "kotlin", ".lua": "lua",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp", ".cs": "csharp",
}
_SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}


@dataclass
class Config:
    # stage 1 — nomination (length only nominates; it is never a verdict on its own)
    length_warn: int = 70          # physical LOC that nominates a function for review
    nloc_warn: int = 60            # logical LOC that also nominates
    # stage 2 — structure (deep vs tangled), from cyclomatic density + nesting
    density_deep: float = 0.15     # ccn/nloc at or below this (+ shallow nesting) => DEEP
    density_tangled: float = 0.28  # ccn/nloc at or above this => TANGLED
    nesting_ok: int = 3
    nesting_bad: int = 5
    ccn_hard: int = 20             # absolute cyclomatic that is tangled regardless of length
    # stage 3 — codebase-relative outlier (self-calibrating: "unusual for how WE write")
    z_cut: float = 2.5
    min_population: int = 20       # need this many functions in a language before z-scores mean anything
    # inverse smell — shallow / delegation duplication
    shallow_max_loc: int = 5
    delegation_dup_min: int = 3    # N sibling modules delegating to the same target => a finding
    # gating (autonomous, degree-driven) — `--gate` blocks CI on the clearly-bad, high-degree findings; medium/
    # low TANGLED stay advisory (a human glance). The degree IS the gating decision, made per-finding, no human
    # in the loop. Raise/lower the bar here.
    gate_confidence: str = "high"  # TANGLED at or above this confidence blocks --gate (low | medium | high)
    gate_shallow: bool = True      # a SHALLOW over-split always blocks --gate (a clear defect)
    # framework decorators whose small functions are idiomatic, never classitis
    exclude_decorators: tuple = (
        "job", "op", "asset", "sensor", "schedule", "graph", "resource", "multi_asset",  # dagster
        "get", "post", "put", "delete", "patch", "route", "websocket",                   # fastapi/flask
        "fixture", "task", "test", "command", "callback",                                # pytest/celery/click
    )

    @classmethod
    def from_file(cls, path):
        """Load the adjustable knobs from a JSON file; unknown keys are ignored, absent keys keep defaults."""
        import json
        base = cls()
        data = json.load(open(path, encoding="utf-8"))
        for key, value in data.items():
            if hasattr(base, key) and key != "from_file":
                setattr(base, key, tuple(value) if key == "exclude_decorators" else value)
        return base


@dataclass
class Finding:
    path: str
    line: int
    name: str
    language: str
    verdict: str
    confidence: str        # low | medium | high
    reason: str
    metrics: dict = field(default_factory=dict)


@dataclass
class Report:
    findings: list
    stats: dict            # language -> {"functions": n, "nloc_mean": .., "ccn_mean": ..}

    def counts(self) -> dict:
        out = {}
        for f in self.findings:
            out[f.verdict] = out.get(f.verdict, 0) + 1
        return out


# --- public interface -----------------------------------------------------------------------------
def analyze(paths, config: Config = None) -> Report:
    """Triage every function under `paths`. The one entry point; everything else is implementation."""
    cfg = config or Config()
    files = list(_iter_code_files(paths))
    findings, stats = _numeric_findings(files, cfg)
    findings += _shallow_findings([f for f in files if f.endswith(".py")], cfg)
    return Report(findings=findings, stats=stats)


# --- file discovery -------------------------------------------------------------------------------
def _iter_code_files(paths):
    seen = set()
    for p in paths:
        if os.path.isfile(p):
            if os.path.splitext(p)[1] in _EXT_LANG and p not in seen:
                seen.add(p)
                yield p
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                if os.path.splitext(fn)[1] in _EXT_LANG:
                    full = os.path.join(dirpath, fn)
                    if full not in seen:
                        seen.add(full)
                        yield full


def _lang_of(path):
    return _EXT_LANG.get(os.path.splitext(path)[1], "other")


# --- stages 1-3: numeric metrics (lizard) ---------------------------------------------------------
def _gather_functions(files):
    """First pass: lizard metrics per function grouped by language (the stage-3 population), plus a true
    max-nesting map per Python file (lizard can't measure it honestly). Returns (per_lang, nesting_maps)."""
    per_lang, nesting_maps = {}, {}
    for path in files:
        try:
            info = lizard.analyze_file(path)
        except Exception:
            continue
        lang = _lang_of(path)
        per_lang.setdefault(lang, []).extend((path, fn) for fn in info.function_list)
        if lang == "python":
            try:
                nesting_maps[path] = _python_nesting_map(open(path, "rb").read())
            except OSError:
                nesting_maps[path] = {}
    return per_lang, nesting_maps


def _population_stats(rows):
    """(nloc_mean, ccn_mean, nloc_sd, ccn_sd, population) for one language's functions."""
    nlocs = [fn.nloc for _, fn in rows]
    ccns = [fn.cyclomatic_complexity for _, fn in rows]
    pop = len(rows)
    return (statistics.mean(nlocs) if nlocs else 0.0,
            statistics.mean(ccns) if ccns else 0.0,
            statistics.pstdev(nlocs) if pop > 1 else 0.0,
            statistics.pstdev(ccns) if pop > 1 else 0.0,
            pop)


def _zscores(fn, nloc_mean, ccn_mean, nloc_sd, ccn_sd, pop, cfg):
    """Stage-3 z-scores of a function against its language population, or (None, None) when the population is
    too small (< min_population) or has no spread — so a small codebase never manufactures an outlier."""
    usable = pop >= cfg.min_population
    zloc = (fn.nloc - nloc_mean) / nloc_sd if (nloc_sd and usable) else None
    zccn = (fn.cyclomatic_complexity - ccn_mean) / ccn_sd if (ccn_sd and usable) else None
    return zloc, zccn


def _finding_for(path, fn, lang, cfg, nesting, zloc, zccn):
    """Build a Finding for one function, or None when it isn't flagged."""
    verdict = _numeric_verdict(fn, cfg, zloc, zccn, nesting)
    if verdict is None:
        return None
    v, conf, reason = verdict
    return Finding(
        path=path, line=fn.start_line, name=fn.name, language=lang,
        verdict=v, confidence=conf, reason=reason,
        metrics={"nloc": fn.nloc, "loc": fn.length, "ccn": fn.cyclomatic_complexity, "nesting": nesting,
                 "z_loc": round(zloc, 1) if zloc is not None else None,
                 "z_ccn": round(zccn, 1) if zccn is not None else None},
    )


def _numeric_findings(files, cfg):
    per_lang, nesting_maps = _gather_functions(files)
    stats, findings = {}, []
    for lang, rows in per_lang.items():
        nloc_mean, ccn_mean, nloc_sd, ccn_sd, pop = _population_stats(rows)
        stats[lang] = {"functions": pop, "nloc_mean": round(nloc_mean, 1), "ccn_mean": round(ccn_mean, 1)}
        for path, fn in rows:
            zloc, zccn = _zscores(fn, nloc_mean, ccn_mean, nloc_sd, ccn_sd, pop, cfg)
            nesting = nesting_maps.get(path, {}).get(fn.start_line) if lang == "python" else None
            f = _finding_for(path, fn, lang, cfg, nesting, zloc, zccn)
            if f is not None:
                findings.append(f)
    return findings, stats


_Signals = namedtuple("_Signals", "nloc ccn density nominated outlier tangled deep deep_nesting")


def _signals(fn, cfg, zloc, zccn, nesting):
    """The derived stage-1/2/3 signals for one function — the inputs the verdict decides from."""
    nloc = fn.nloc or 1
    ccn = fn.cyclomatic_complexity
    density = ccn / nloc
    deep_nesting = nesting is not None and nesting >= cfg.nesting_bad
    return _Signals(
        nloc=nloc, ccn=ccn, density=density,
        nominated=fn.length > cfg.length_warn or nloc > cfg.nloc_warn,
        outlier=(zloc is not None and zloc >= cfg.z_cut) or (zccn is not None and zccn >= cfg.z_cut),
        tangled=density >= cfg.density_tangled or deep_nesting or ccn >= cfg.ccn_hard,
        deep=density <= cfg.density_deep and (nesting is None or nesting <= cfg.nesting_ok),
        deep_nesting=deep_nesting,
    )


def _tangled_confidence(s, cfg):
    """TANGLED confidence rises with the number of independent signals that agree."""
    agree = sum([s.density >= cfg.density_tangled, s.deep_nesting, s.ccn >= cfg.ccn_hard, bool(s.outlier)])
    return "high" if agree >= 3 else "medium" if agree == 2 else "low"


def _numeric_verdict(fn, cfg, zloc, zccn, nesting):
    s = _signals(fn, cfg, zloc, zccn, nesting)
    nz = nesting if nesting is not None else "n/a"
    # TANGLED regardless of nomination when the cyclomatic count is hard-high; otherwise length nominated it.
    if s.tangled and (s.nominated or s.ccn >= cfg.ccn_hard):
        tail = " + codebase outlier" if s.outlier else ""
        return TANGLED, _tangled_confidence(s, cfg), f"ccn={s.ccn}, nloc={s.nloc}, density={s.density:.2f}, nesting={nz}{tail}"
    if not s.nominated:
        return None
    # Stage 3 elevates a codebase-outlier to a human glance even when it looks locally clean.
    if s.outlier:
        z = ", ".join(x for x in (f"z_loc={zloc:.1f}" if zloc is not None else "",
                                  f"z_ccn={zccn:.1f}" if zccn is not None else "") if x)
        return OUTLIER_REVIEW, "medium", f"long and unusual for this codebase ({z}); nloc={s.nloc}, ccn={s.ccn}"
    if s.deep:
        return DEEP, "low", f"long but shallow control flow (ccn={s.ccn}/nloc={s.nloc}, nesting={nz}) — a deep function"
    return OUTLIER_REVIEW, "low", f"long (nloc={s.nloc}) with moderate structure (ccn={s.ccn}, nesting={nz})"


# --- inverse smell: shallow / delegation duplication (tree-sitter, Python first) -------------------
def _shallow_findings(py_files, cfg):
    parser = get_parser("python")
    # (dir, callee_base) -> list of (path, line, fn_name)
    delegations = {}
    for path in py_files:
        try:
            src = open(path, "rb").read()
        except OSError:
            continue
        root = parser.parse(src).root_node
        for fn in _iter_nodes(root, "function_definition"):
            base = _passthrough_target(fn, cfg)
            if base is None:
                continue
            key = (os.path.dirname(path), base)
            delegations.setdefault(key, []).append((path, fn.start_point[0] + 1,
                                                     fn.child_by_field_name("name").text.decode()))

    findings = []
    for (dirpath, base), sites in delegations.items():
        files = {p for p, _, _ in sites}
        if len(files) < cfg.delegation_dup_min:
            continue
        p0, line0, _ = sorted(sites)[0]
        names = ", ".join(sorted(os.path.basename(p) for p in files))
        findings.append(Finding(
            path=p0, line=line0, name=f"<delegation:{base}>", language="python",
            verdict=SHALLOW, confidence="medium",
            reason=f"{len(files)} sibling modules delegate to {base}() — shallow / over-split duplication ({names})",
            metrics={"siblings": len(files), "target": base},
        ))
    return findings


def _passthrough_target(fn, cfg):
    """Return the callee's base name if `fn` is an excludable-free pass-through, else None."""
    name = fn.child_by_field_name("name").text.decode()
    if name.startswith("_"):                      # private/dunder — not a public interface smell
        return None
    if (fn.end_point[0] - fn.start_point[0] + 1) > cfg.shallow_max_loc:
        return None
    if _has_excluded_decorator(fn, cfg):          # dagster @op/@job, FastAPI routes, etc. are idiomatic
        return None
    body = fn.child_by_field_name("body")
    stmts = [c for c in body.named_children]
    if len(stmts) != 1:
        return None
    stmt = stmts[0]
    if stmt.type not in ("return_statement", "expression_statement"):
        return None
    call = next((c for c in stmt.named_children if c.type == "call"), None)
    if call is None:
        return None
    callee = call.child_by_field_name("function")
    if callee is None:
        return None
    return callee.text.decode().split(".")[-1]


def _has_excluded_decorator(fn, cfg):
    parent = fn.parent
    if parent is None or parent.type != "decorated_definition":
        return False
    for c in parent.children:
        if c.type != "decorator":
            continue
        text = c.text.decode().lstrip("@")
        callable_part = text.split("(")[0]        # "app.get('/x')" -> "app.get"
        base = callable_part.split(".")[-1].strip()  # -> "get"
        if base in cfg.exclude_decorators:
            return True
    return False


def _iter_nodes(root, node_type):
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == node_type:
            yield n
        stack.extend(n.children)


# --- true max control-nesting (tree-sitter) -------------------------------------------------------
# lizard's 'nd' extension inflates on flat sibling control structures (10 flat `if`s report depth 10),
# so it double-counts what CCN already measures. We compute real max depth from the AST instead — the
# one structural signal density can miss: a long, low-density function hiding a deep pyramid.
_CONTROL_PY = {"if_statement", "for_statement", "while_statement", "with_statement",
               "try_statement", "match_statement"}


def _max_nesting_depth(node, depth):
    best = depth
    for c in node.children:
        d = depth + 1 if c.type in _CONTROL_PY else depth
        best = max(best, _max_nesting_depth(c, d))
    return best


def _python_nesting_map(src):
    """{def-line (1-based) -> max control-nesting depth} for every function in a Python source."""
    root = get_parser("python").parse(src).root_node
    out = {}
    for fn in _iter_nodes(root, "function_definition"):
        body = fn.child_by_field_name("body")
        out[fn.start_point[0] + 1] = _max_nesting_depth(body, 0) if body is not None else 0
    return out


_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def gating_findings(findings, cfg):
    """The findings that BLOCK `--gate`: any SHALLOW (a clear over-split) plus every TANGLED at or above the
    configured confidence bar. Medium/low TANGLED, OUTLIER_REVIEW and DEEP never block — the DEGREE is itself the
    autonomous gating decision, made per finding with no human in the loop."""
    floor = _CONF_RANK.get(cfg.gate_confidence, 2)
    out = []
    for f in findings:
        if f.verdict == SHALLOW and cfg.gate_shallow:
            out.append(f)
        elif f.verdict == TANGLED and _CONF_RANK.get(f.confidence, 0) >= floor:
            out.append(f)
    return out


# --- CLI (advisory report, or --gate for autonomous degree-driven gating; the shell lane calls this) ---------
def main(argv=None):
    import argparse
    import json
    import sys
    ap = argparse.ArgumentParser(description="B162 complexity triage — deep vs tangled vs shallow.")
    ap.add_argument("paths", nargs="+", help="files or directories to analyze")
    ap.add_argument("--config", help="JSON file of threshold overrides (the adjustable knobs)")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 on gating findings (high-confidence TANGLED + SHALLOW); the autonomous gate")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--show-deep", action="store_true", help="include DEEP (acceptable) findings")
    args = ap.parse_args(argv)

    cfg = Config.from_file(args.config) if args.config and os.path.exists(args.config) else Config()
    report = analyze(args.paths, cfg)
    findings = [f for f in report.findings if args.show_deep or f.verdict != DEEP]
    order = {TANGLED: 0, SHALLOW: 1, OUTLIER_REVIEW: 2, DEEP: 3}
    findings.sort(key=lambda f: (order.get(f.verdict, 9), -f.metrics.get("nloc", 0)))

    blocking = gating_findings(report.findings, cfg) if args.gate else []
    gate_rc = 1 if blocking else 0

    if args.json:
        print(json.dumps({"counts": report.counts(), "stats": report.stats,
                          "gate": {"blocking": len(blocking)} if args.gate else None,
                          "findings": [vars(f) for f in findings]}, indent=2))
        return gate_rc

    c = report.counts()
    mode = "gated" if args.gate else "advisory"
    print(f"complexity triage: {c.get(TANGLED,0)} TANGLED, {c.get(SHALLOW,0)} SHALLOW, "
          f"{c.get(OUTLIER_REVIEW,0)} OUTLIER-REVIEW, {c.get(DEEP,0)} DEEP ({mode})")
    for f in findings:
        print(f"  {f.verdict:14s} {f.confidence:6s} {f.path}:{f.line}  {f.name}")
        print(f"                        {f.reason}")
    if gate_rc:
        print(f"\nGATE FAILED: {len(blocking)} blocking finding(s) (TANGLED at confidence>={cfg.gate_confidence}, "
              f"or SHALLOW). Fix them, or adjust the bar in scripts/complexity-triage.json.", file=sys.stderr)
    return gate_rc


if __name__ == "__main__":
    raise SystemExit(main())
