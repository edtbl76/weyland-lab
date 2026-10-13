#!/usr/bin/env python3
"""Live API drift check (B155) — the runtime half of API lifecycle governance.

For every catalogued API that has both a captured contract snapshot (`spec`) and a way to fetch its
live contract (`spec_source`), this fetches the LIVE spec and diffs it against the committed snapshot
with the breaking-change engine (api_spec_diff). It catches a deployed API that DRIFTED from its
governed contract — a route removed, a field dropped, a new required field — without the catalog +
snapshot being updated and the version bumped.

Runs in-cluster as the `api-drift` CronJob (the .svc / *.weyland.lab spec_sources resolve there). Also
runnable on-demand wherever the sources are reachable.

FAIL-CLOSED, but honest about reachability: a source that cannot be fetched (a scaled-to-zero service,
a down pod) is SKIPPED and reported as unreachable — that is not drift, and firing nightly on every
asleep service would be noise. A breaking DIFF between a reachable live spec and its snapshot is a real
defect → exit 1. Cannot read the catalog/snapshots at all → exit 2.

Every API is reported IDENTICAL (parsed JSON equal), ADDITIVE drift (differs, nothing breaking — named, and posted as
a `warning` ApiContractStale alert to Alertmanager at $ALERTMANAGER_URL so the snapshot gets refreshed and re-locked)
or BREAKING drift. Until B208 (2026-10-13) any non-breaking difference passed as "match": the tool-server served an
optional field for two weeks that its snapshot lacked. `ALERTMANAGER_URL=file://<path>` writes the alert JSON to a
file instead (the test seam).

  usage: api_drift.py <apis.yaml> <specs_dir>
  exit:  0 = no breaking drift (unreachable sources skipped + listed); any additive drift was alerted
         1 = breaking drift on a reachable API (named)
         2 = could not run (catalog/specs unreadable), or additive drift found but its alert could not be sent

  A spec_source of http(s):// is fetched over HTTP; anything else is treated as a local file path
  (used by the tests to feed a 'live' spec without a network).
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api_spec_diff  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


def _load_catalog(path):
    text = open(path).read()
    if yaml is not None:
        return (yaml.safe_load(text) or {}).get("apis") or []
    # Minimal fallback if pyyaml is absent (the cron image installs it; this keeps the runner honest).
    raise RuntimeError("pyyaml required to read the API catalog")


def _fetch(source, timeout=8):
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"Accept": "application/json"})
        # nosec B310 — `source` is a spec_source from the trusted apis.yaml catalog (in-cluster http(s)
        # hosts the cron reaches); the file: branch below is a deliberate test seam, not user input.
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
            return json.loads(r.read().decode())
    with open(source) as fh:  # local path — test fixture
        return json.load(fh)


def _contract(spec):
    """The part of a spec that IS the contract. An A2A card's `url` / `provider.url` / `additionalInterfaces[].url` are
    built from the request's host (realm-of-agents, observed 2026-10-13): the drift job fetches via the .svc name and
    sees an internal URL, while the snapshot was captured via the public one. They locate the agent; they are not the
    contract (skills, capabilities, protocol are), so they are left out of the comparison."""
    if not (isinstance(spec, dict) and "skills" in spec and "protocolVersion" in spec):
        return spec
    card = json.loads(json.dumps(spec))
    card.pop("url", None)
    if isinstance(card.get("provider"), dict):
        card["provider"].pop("url", None)
    for iface in card.get("additionalInterfaces") or []:
        if isinstance(iface, dict):
            iface.pop("url", None)
    return card


def _structural(old, new):
    """What differs, by operation and component schema: the engine names breaking changes and SOME compatible ones; an
    added optional request field or a newly documented response it does not report, so name every difference here."""
    out = []

    def ops(spec):
        return {(m.upper(), p): op for p, item in (spec.get("paths") or {}).items()
                for m, op in (item or {}).items() if isinstance(op, dict)}
    a, b = ops(old), ops(new)
    out += [f"operation added: {m} {p}" for m, p in sorted(set(b) - set(a))]
    out += [f"operation changed: {m} {p}" for m, p in sorted(set(a) & set(b)) if a[(m, p)] != b[(m, p)]]
    sa_ = (old.get("components") or {}).get("schemas") or {}
    sb_ = (new.get("components") or {}).get("schemas") or {}
    out += [f"schema added: {k}" for k in sorted(set(sb_) - set(sa_))]
    out += [f"schema changed: {k}" for k in sorted(set(sa_) & set(sb_)) if sa_[k] != sb_[k]]
    rest = {k: v for k, v in old.items() if k not in ("paths", "components")}
    if rest != {k: v for k, v in new.items() if k not in ("paths", "components")}:
        out.append("top-level fields changed (info / servers / ...)")
    return out or ["the spec differs (unclassified)"]


def _send_alerts(additive):
    """POST one warning per stale API to Alertmanager v2 (no endsAt: it auto-resolves after resolve_timeout, so each
    nightly run that still finds the drift fires it again; the pattern of k8s/pr-lifecycle/pr-staleness.yaml).
    Returns None on success, else why it could not be sent."""
    url = os.environ.get("ALERTMANAGER_URL", "")
    if not url:
        return "ALERTMANAGER_URL is unset"
    alerts = [{"labels": {"alertname": "ApiContractStale", "severity": "warning", "namespace": "monitoring",
                          "api": api_id, "source": "api-drift"},
               "annotations": {"summary": f"API {api_id} (v{ver}) drifted from its committed contract (additive)",
                               "description": "Live spec differs from docs/api/specs: " + "; ".join(changes[:6])
                               + ". Nothing breaking. Refresh the snapshot from the deployed app and re-lock"
                               " (scripts/gen-api-contract-lock.sh); runbook docs/runbooks/api-lifecycle.md."}}
              for api_id, ver, changes in additive]
    body = json.dumps(alerts).encode()
    try:
        if url.startswith("file://"):
            with open(url[len("file://"):], "wb") as fh:
                fh.write(body)
        else:
            req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
            # nosec B310 — the in-cluster Alertmanager URL from the CronJob's env
            with urllib.request.urlopen(req, timeout=10) as r:  # nosec B310
                r.read()
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:120]}"
    return None


class _CannotRun(Exception):
    pass


def _classify_one(a, specs_dir):
    """('skip', why) | ('breaking', changes) | ('identical', None) | ('additive', changes) for one catalogued API,
    or None when it has no snapshot-backed contract. Raises _CannotRun when its snapshot is missing."""
    spec, source = a.get("spec"), a.get("spec_source")
    if not spec or not source:
        return None  # not a snapshot-backed API (mcp/openai-compat without a captured contract)
    snap_path = os.path.join(specs_dir, os.path.basename(spec))
    if not os.path.isfile(snap_path):
        raise _CannotRun(f"snapshot missing for {a.get('id')}: {snap_path}")
    try:
        live = _fetch(source)
    except Exception as e:
        return "skip", f"unreachable: {str(e)[:60]}"
    snapshot = json.load(open(snap_path))
    changes = api_spec_diff.diff(snapshot, live)
    if changes is None:
        return "skip", "cannot compare (kind changed?)"
    bad = [c for c in changes if c[0] == "BREAKING"]
    if bad:
        return "breaking", bad
    if _contract(snapshot) == _contract(live):
        return "identical", None
    named = [d for _, d in changes] + _structural(_contract(snapshot), _contract(live))
    return "additive", list(dict.fromkeys(named))


def _report(found):
    """Print the verdict and return the exit code; additive drift is alerted first."""
    for i, _, why in found["skip"]:
        print(f"  SKIP {i}: {why}")
    for i, ver, changes in found["additive"]:
        print(f"  ADDITIVE DRIFT {i} (v{ver}): " + "; ".join(changes))
    alert_error = _send_alerts(found["additive"]) if found["additive"] else None
    if found["breaking"]:
        print(f"BREAKING DRIFT — {len(found['breaking'])} API(s) diverged from their governed contract:", file=sys.stderr)
        for i, ver, bad in found["breaking"]:
            print(f"  - {i} (v{ver}):", file=sys.stderr)
            for _, detail in bad:
                print(f"      {detail}", file=sys.stderr)
        print("Fix: re-capture the snapshot into docs/api/specs/, bump the MAJOR version in apis.yaml, "
              "and migrate consumers (or revert the API change).", file=sys.stderr)
        return 1
    if alert_error:
        print(f"CANNOT REPORT — {len(found['additive'])} API(s) drifted (additive), but could not send the alert: "
              f"{alert_error}", file=sys.stderr)
        return 2
    n = {k: len(v) for k, v in found.items()}
    print(f"OK — no breaking drift: {n['identical']} identical, {n['additive']} additive drift, "
          f"{n['skip']} skipped (unreachable)" + (" — additive drift alerted (ApiContractStale)" if n["additive"] else "."))
    return 0


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-6], file=sys.stderr)
        return 2
    apis_f, specs_dir = argv
    try:
        apis = _load_catalog(apis_f)
    except Exception as e:
        print(f"CANNOT RUN — catalog unreadable ({apis_f}): {str(e)[:120]}", file=sys.stderr)
        return 2
    if not apis:
        print(f"CANNOT RUN — no apis in {apis_f}", file=sys.stderr)
        return 2
    found = {"identical": [], "skip": [], "breaking": [], "additive": []}
    try:
        for a in apis:
            result = _classify_one(a, specs_dir)
            if result is not None:
                kind, detail = result
                found[kind].append((a.get("id"), a.get("version"), detail))
    except _CannotRun as e:
        print(f"CANNOT RUN — {e}", file=sys.stderr)
        return 2
    return _report(found)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
