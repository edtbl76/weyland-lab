"""Deprecated-model guard (B223) — fail when any config names an Anthropic model that is deprecated or retired.

WHY THIS EXISTS: on 2026-10-18 an Anthropic email said Claude Haiku 3.5 was being retired and named one of our keys.
Checking took four manual steps (git history, the MLflow gateway, Bifrost, the key rotation log) and found nothing in
the lab used it, but nothing TOLD us that, and the next retirement could hit a live config. A retired model fails every
request, so a stale ID is an outage waiting for its date.

TWO MODES, ONE SET OF DECISIONS (the manifest scripts/anthropic-models.json, copied from Anthropic's deprecations page):
  scan [ROOT]  the repo guard (CI repo-guards, via scripts/check-model-deprecations.sh): every Anthropic model ID in
               config and code — not docs, history, tests or the vendored agent framework, and only the CODE cells of
               a notebook (an output that lists models is not a use).
  live         the anthropic-model-watch CronJob (03:55 NY): the IDs the running gateways hold — the MLflow gateway's
               Anthropic model definitions and Bifrost's key / virtual-key model lists — checked against the manifest
               and against Anthropic's free GET /v1/models (an ID the API no longer offers counts as retired).

VERDICTS: retired, or deprecated with the retirement date inside `fail_within_days` (30) -> FAIL. Deprecated with more
time (or no date yet), or an ID the manifest does not know -> WARN. Every spelling of one model is one model: aliases
(`claude-haiku-4-5`) resolve to their dated entry, and the LiteLLM/Bifrost word order (`claude-4.5-haiku`), provider
prefixes (`anthropic/`, `openai/anthropic/`) and `-latest` / `-v1:0` suffixes are normalised away.

EXIT: 0 clean · 1 a retired / retiring model is in use (named: file:line, or gateway + entry) · 2 COULD NOT CHECK —
no or malformed manifest, nothing scanned, a live source unreadable, or the API listing no models. Never a silent pass.
Secrets: the Bifrost setup token and the Anthropic key are read from the environment and never printed.
Stdlib only, so the CronJob runs it on python:3.12-alpine as nobody. Runbook: docs/runbooks/model-deprecations.md.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple

FAMILIES = ("haiku", "sonnet", "opus", "fable", "mythos", "instant")
STATES = ("active", "deprecated", "retired")
STALE_MANIFEST_DAYS = 90
# A model-looking token: `claude-` and what follows, linear-time (no overlapping quantifiers). find_ids() then walks
# back over any provider prefix attached to it (anthropic/, openai/anthropic/, global.anthropic.).
CORE_RE = re.compile(r"claude-[a-z0-9.-]+")
PREFIX_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-")

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".build", "site-techdocs",
             "docs", "aidlc", "aidlc-docs", "knowledge-repos", ".claude", "tests"}
SKIP_FILES = {"scripts/anthropic-models.json", "scripts/model_lifecycle.py",
              "nodes/mother/lab/weyland-platform/k8s/bifrost/anthropic-model-watch.yaml"}
SCAN_EXTS = {".py", ".yaml", ".yml", ".json", ".toml", ".sh", ".bash", ".ts", ".js", ".mjs", ".tf", ".ini", ".cfg",
             ".env", ".example", ".ipynb"}
MAX_BYTES = 2_000_000

Verdict = namedtuple("Verdict", "level status entry detail")         # level: ok | warn | fail
Finding = namedtuple("Finding", "path line model_id verdict")
Report = namedtuple("Report", "exit_code lines offered_count")


class ManifestError(Exception):
    pass


class LiveError(Exception):
    pass


# ── model IDs ────────────────────────────────────────────────────────────────────────────────────────────────────

def parse_model_id(text):
    """(family, version, date) for an Anthropic model ID in any spelling, or None when it is not one.

    `claude-haiku-4-5-20251001`, `claude-3-5-haiku-20241022`, `claude-4.5-haiku`, `anthropic/claude-opus-4-0`,
    `claude-2.1`, `claude-mythos-preview`. Product names (`claude-code`, `claude-cli`) and a family with no version
    (`claude-opus`) are not models. A trailing zero minor is its major alias (`claude-opus-4-0` = `claude-opus-4`)."""
    s = text.strip().lower()
    i = s.rfind("claude-")
    if i < 0:
        return None
    rest = re.sub(r"-v\d+(:\d+)?$", "", s[i + len("claude-"):])           # Bedrock's -v1:0
    tokens = [t for t in rest.split("-") if t]
    family, date, version, extra = _sort_tokens(tokens)
    if family is None:                                   # legacy claude-2.1 / claude-1.3: nothing but the number
        if extra or date or len(tokens) != 1 or not version:
            return None
        family = "claude"
    if not version:
        return None
    while len(version) > 1 and version[-1] == 0:
        version.pop()
    return family, tuple(version), date


def _sort_tokens(tokens):
    """Split an ID's dash-separated tokens into (family, date, version parts, everything else)."""
    family, date, version, extra = None, None, [], []
    for t in tokens:
        if re.fullmatch(r"\d{8}", t):
            date = t
        elif t in FAMILIES and family is None:
            family = t
        elif re.fullmatch(r"\d+(\.\d+)*", t):
            version.extend(int(x) for x in t.split("."))
        elif t == "preview":
            version.append("preview")
        else:
            extra.append(t)
    return family, date, version, extra


def find_ids(text):
    """[(line_number, token)] for every token in `text` that parses as an Anthropic model ID."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in CORE_RE.finditer(line):
            start = m.start()
            while start > 0 and line[start - 1] in PREFIX_CHARS:
                start -= 1
            token = line[start:m.end()].rstrip(".-")
            if parse_model_id(token):
                out.append((n, token))
    return out


# ── the manifest ─────────────────────────────────────────────────────────────────────────────────────────────────

def _date(value, field, mid):
    if value is None:
        return None
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ManifestError(f"{mid}: {field} {value!r} is not a YYYY-MM-DD date") from None


def _manifest_entry(m, path):
    """(parsed key, entry with real dates) for one manifest row; anything malformed -> ManifestError."""
    mid = m.get("id") if isinstance(m, dict) else None
    key = parse_model_id(mid) if isinstance(mid, str) else None
    if key is None:
        raise ManifestError(f"{path}: {mid!r} is not an Anthropic model ID")
    if m.get("state") not in STATES:
        raise ManifestError(f"{mid}: state {m.get('state')!r} is not one of {', '.join(STATES)}")
    entry = dict(m, date=key[2], retires=_date(m.get("retires"), "retires", mid),
                 deprecated=_date(m.get("deprecated"), "deprecated", mid),
                 not_before=_date(m.get("not_before"), "not_before", mid))
    if entry["state"] == "retired" and entry["retires"] is None:
        raise ManifestError(f"{mid}: a retired model needs its `retires` date")
    return key, entry


def load_manifest(path):
    """The manifest, validated and indexed by (family, version). Missing, unreadable or malformed -> ManifestError."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise ManifestError(f"cannot read the model manifest {path}: {e}") from None
    models = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(models, list) or not models:
        raise ManifestError(f"{path}: no `models` list")
    index = {}
    for m in models:
        key, entry = _manifest_entry(m, path)
        index.setdefault(key[:2], []).append(entry)
    return {"index": index, "count": len(models), "source": raw.get("source", "?"),
            "checked": _date(raw.get("checked"), "checked", "manifest"),
            "fail_within_days": int(raw.get("fail_within_days", 30))}


def classify(model_id, manifest, today):
    """The verdict for one ID on `today`. An undated alias resolves to the newest dated entry of its model."""
    key = parse_model_id(model_id)
    if key is None:
        return Verdict("warn", "unknown", None, "not an Anthropic model ID")
    cands = manifest["index"].get(key[:2], [])
    if key[2]:
        cands = [c for c in cands if c["date"] == key[2]]
    if not cands:
        return Verdict("warn", "unknown", None,
                       f"not in the manifest (checked {manifest['checked']}): a new model, or a typo")
    e = max(cands, key=lambda c: c["date"] or "")
    repl = f"; replacement {e['replacement']}" if e.get("replacement") else ""
    retires = e["retires"]
    if e["state"] == "retired" or (retires and retires <= today):
        return Verdict("fail", "retired", e, f"{e['id']} retired {retires}{repl}")
    if e["state"] == "deprecated":
        if retires and (retires - today).days <= manifest["fail_within_days"]:
            return Verdict("fail", "retiring", e,
                           f"{e['id']} retires {retires} — {(retires - today).days} day(s) left{repl}")
        return Verdict("warn", "deprecated", e,
                       f"{e['id']} deprecated {e['deprecated']}, retires {retires or 'TBA'}{repl}")
    nb = f" (not before {e['not_before']})" if e.get("not_before") else ""
    return Verdict("ok", "active", e, f"{e['id']} active{nb}")


# ── scan: the repo guard ─────────────────────────────────────────────────────────────────────────────────────────

def _scan_text(path, raw):
    if not path.endswith(".ipynb"):
        return raw
    try:                                                  # code cells only: outputs and prose are not uses
        cells = json.loads(raw).get("cells", [])
    except (ValueError, AttributeError):
        return raw
    return "\n".join("".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code")


def _wanted(rel, name):
    if rel in SKIP_FILES or name.endswith((".md", ".bats")) or name.startswith("test_") or name.endswith("_test.py"):
        return False
    return os.path.splitext(name)[1] in SCAN_EXTS or name == "Dockerfile"


def scan(root, manifest, today):
    """([Finding], files_scanned) over every config/code file under `root`."""
    findings, scanned = [], 0
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(d, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if not _wanted(rel, name):
                continue
            try:
                if os.path.getsize(full) > MAX_BYTES:
                    continue
                with open(full, encoding="utf-8", errors="replace") as f:
                    text = _scan_text(name, f.read())
            except OSError:
                continue
            scanned += 1
            findings.extend(Finding(rel, n, mid, classify(mid, manifest, today)) for n, mid in find_ids(text))
    return findings, scanned


# ── live: the gateways' running config ───────────────────────────────────────────────────────────────────────────

def _list_of(data, field, source):
    v = data.get(field) if isinstance(data, dict) else None
    if not isinstance(v, list):
        raise LiveError(f"{source}: unexpected response shape (no `{field}` list)")
    return v


def collect_live_refs(fetch):
    """[(where, entry name, model id)] for every Anthropic model ID the gateways name. A `*` allows every model and
    names none, so there is nothing to retire."""
    refs = []
    for d in _list_of(fetch("mlflow"), "model_definitions", "mlflow"):
        if d.get("provider") == "anthropic" and d.get("model_name"):
            refs.append(("mlflow", d.get("name"), d["model_name"]))
    for k in _list_of(fetch("bifrost_keys"), "keys", "bifrost_keys"):
        refs.extend(("bifrost key", k.get("name"), m) for m in k.get("models") or [] if m != "*")
    for vk in _list_of(fetch("bifrost_vks"), "virtual_keys", "bifrost_vks"):
        for pc in vk.get("provider_configs") or []:
            if pc.get("provider") == "anthropic":
                refs.extend(("bifrost vk", vk.get("name"), m) for m in pc.get("allowed_models") or [] if m != "*")
    return refs


def list_anthropic_models(get_json, base, api_key):
    """Every model ID `api_key` can call (GET /v1/models, free), following has_more pages."""
    ids, after = [], None
    for _ in range(20):
        url = f"{base.rstrip('/')}/v1/models?limit=1000" + (f"&after_id={urllib.parse.quote(after)}" if after else "")
        page = get_json(url, {"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        batch = [m["id"] for m in _list_of(page, "data", "anthropic") if isinstance(m, dict) and m.get("id")]
        ids.extend(batch)
        if not page.get("has_more") or not batch:
            return ids
        after = page.get("last_id") or batch[-1]
    raise LiveError("anthropic: /v1/models kept paging past 20 pages")


def live_check(fetch, manifest, today):
    lines = []
    try:
        refs = collect_live_refs(fetch)
        offered_ids = [m["id"] for m in _list_of(fetch("anthropic"), "data", "anthropic") if isinstance(m, dict)]
    except LiveError as e:
        return Report(2, [f"CANNOT CHECK: {e}"], 0)
    if not offered_ids:
        return Report(2, ["CANNOT CHECK: anthropic: GET /v1/models listed no models — an empty answer is not "
                          "'nothing retired'"], 0)
    offered = {k for k in map(parse_model_id, offered_ids) if k}
    failed = False
    for where, name, mid in refs:
        v, key = classify(mid, manifest, today), parse_model_id(mid)
        is_offered = bool(key) and any(o[:2] == key[:2] and (key[2] is None or o[2] == key[2]) for o in offered)
        if not is_offered:
            v = Verdict("fail", "not offered", v.entry, f"not offered by GET /v1/models (retired or never valid); {v.detail}")
        failed |= v.level == "fail"
        lines.append(f"{v.level.upper():4} {where} {name}: {mid} -> {v.detail}")
    lines.append(f"{len(refs)} Anthropic model reference(s) in the running gateways (MLflow + Bifrost; `*` names none); "
                 f"{len(offered_ids)} model(s) offered by the API")
    return Report(1 if failed else 0, lines, len(offered_ids))


def _http_json(url, headers, source, attempts=4):
    """GET JSON. Retries a refused connection: k3s admits a new pod's IP to a NetworkPolicy a few seconds late."""
    for n in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise LiveError(f"{source}: HTTP {e.code}") from None
        except OSError as e:                              # URLError is an OSError: refused, DNS, timeout
            if n == attempts:
                raise LiveError(f"{source}: unreachable ({getattr(e, 'reason', e)})") from None
            time.sleep(3)
        except ValueError:
            raise LiveError(f"{source}: the response is not JSON") from None


def _live_fetcher(env):
    """fetch(source) over the real sources. Every URL comes from the environment (the CronJob sets the in-cluster
    ones); one that is missing is a source that cannot be read, never a default."""
    mlflow, bifrost = env.get("MLFLOW_URL", "").rstrip("/"), env.get("BIFROST_URL", "").rstrip("/")
    token, key = env.get("BIFROST_SETUP_TOKEN", ""), env.get("ANTHROPIC_API_KEY", "")

    def need(source, **values):
        missing = [name for name, v in values.items() if not v]
        if missing:
            raise LiveError(f"{source}: no {' / '.join(missing)} (cannot read this source without it)")

    def from_mlflow():
        need("mlflow", MLFLOW_URL=mlflow)
        return _http_json(f"{mlflow}/api/3.0/mlflow/gateway/model-definitions/list", {}, "mlflow")

    def from_bifrost(source, path):
        need(source, BIFROST_URL=bifrost, BIFROST_SETUP_TOKEN=token)
        return _http_json(bifrost + path, {"X-Bifrost-Setup-Token": token}, source)

    def from_anthropic():
        need("anthropic", ANTHROPIC_API_KEY=key)
        base = env.get("ANTHROPIC_BASE", "https://api.anthropic.com")
        ids = list_anthropic_models(lambda url, h: _http_json(url, h, "anthropic"), base, key)
        return {"data": [{"id": i} for i in ids], "has_more": False}

    sources = {"mlflow": from_mlflow, "anthropic": from_anthropic,
               "bifrost_keys": lambda: from_bifrost("bifrost_keys", "/api/providers/anthropic/keys"),
               "bifrost_vks": lambda: from_bifrost("bifrost_vks", "/api/governance/virtual-keys")}
    return lambda source: sources[source]()


# ── entry point ──────────────────────────────────────────────────────────────────────────────────────────────────

def _today(env):
    return dt.date.fromisoformat(env["MODEL_GUARD_TODAY"]) if env.get("MODEL_GUARD_TODAY") else dt.date.today()


def _stale_note(manifest, today):
    c = manifest["checked"]
    if c is None or (today - c).days > STALE_MANIFEST_DAYS:
        return [f"WARN the manifest was last checked {c} (over {STALE_MANIFEST_DAYS} days) — re-read {manifest['source']}"]
    return []


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    env = os.environ if env is None else env
    here = os.path.dirname(os.path.abspath(__file__))
    if not argv or argv[0] not in ("scan", "live"):
        print("usage: model_lifecycle.py scan [ROOT] | live", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(env.get("MODEL_MANIFEST") or os.path.join(here, "anthropic-models.json"))
    except ManifestError as e:
        print(f"model-deprecations: CANNOT CHECK — {e}")
        return 2
    today = _today(env)
    notes = _stale_note(manifest, today)
    if argv[0] == "live":
        report = live_check(_live_fetcher(env), manifest, today)
        for line in notes + report.lines:
            print(line)
        return report.exit_code
    root = argv[1] if len(argv) > 1 else env.get("SCAN_ROOT") or os.path.dirname(here)
    return _run_scan(root, manifest, today, notes)


def _run_scan(root, manifest, today, notes):
    findings, scanned = scan(root, manifest, today)
    if scanned == 0:
        print(f"model-deprecations: CANNOT CHECK — no config or code files under {root} (scanning nothing is not clean)")
        return 2
    for line in notes:
        print(line)
    for f in findings:
        if f.verdict.level != "ok":
            print(f"{f.verdict.level.upper():4} {f.path}:{f.line}  {f.model_id} -> {f.verdict.detail}")
    fails = sum(f.verdict.level == "fail" for f in findings)
    warns = sum(f.verdict.level == "warn" for f in findings)
    if fails:
        print(f"model-deprecations: FAIL — {fails} reference(s) to a retired model, or one retiring within "
              f"{manifest['fail_within_days']} days. Move each to its replacement (docs/runbooks/model-deprecations.md).")
        return 1
    print(f"model-deprecations: OK — {len(findings)} Anthropic model reference(s) in {scanned} file(s); none retired or "
          f"retiring within {manifest['fail_within_days']} days ({warns} warning(s); manifest checked {manifest['checked']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
