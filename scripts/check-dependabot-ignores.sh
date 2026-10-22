#!/usr/bin/env bash
# check-dependabot-ignores.sh (B214 leftover, 2026-10-22) — every `ignore` in .github/dependabot.yml is backed by a live
# acceptance in osv-scanner.toml, and the directory still pins a version below the ignored range.
#
# WHY THIS EXISTS: B214 added per-directory `ignore` rules so Dependabot stops re-proposing versions that break a build
# (apache-beam's caps under Flink 1.20, transformers 5 in the ONNX export stages, semgrep's protobuf/setuptools). An
# ignore silences SECURITY updates for that package in that directory, and nothing expires it. osv-scanner.toml's accepts
# carry the reason and an `effectiveUntil`; an ignore carries a comment. The day a cap lifts and the pin moves on, the
# osv accept stops matching (it is scoped to one version) but the ignore keeps blocking the next real fix, silently.
#
# BACKED means one of: a [[PackageOverrides]] entry with the same name AT THE PINNED VERSION (version-scoped, so it dies
# with the pin), or an [[IgnoredVulns]] entry (an advisory-id accept) whose reason names the package AND the directory's
# last path segment. Compatibility caps with no advisory need no ignore: Dependabot here opens security updates only.
# DEAD means the pinned version already satisfies the ignored range: the cap has been lifted and the ignore outlived it.
#
# EXIT: 0 = every ignore backed and live · 1 = a defect, named (UNBACKED / DEAD / NOT PINNED) · 2 = cannot check (a
# config missing or unparseable, no ignore at all, a version range it cannot read). Checking nothing is never a pass.
# SEAMS: DEPENDABOT_ROOT (the tree), DEPENDABOT_CONFIG, OSV_CONFIG. Tests: scripts/tests/dependabot-ignores.bats.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPENDABOT_ROOT="${DEPENDABOT_ROOT:-$ROOT}"
DEPENDABOT_CONFIG="${DEPENDABOT_CONFIG:-$DEPENDABOT_ROOT/.github/dependabot.yml}"
OSV_CONFIG="${OSV_CONFIG:-$DEPENDABOT_ROOT/osv-scanner.toml}"

command -v python3 >/dev/null 2>&1 || { echo "CANNOT CHECK: python3 not found on PATH" >&2; exit 2; }

rc=0
DEPENDABOT_ROOT="$DEPENDABOT_ROOT" DEPENDABOT_CONFIG="$DEPENDABOT_CONFIG" OSV_CONFIG="$OSV_CONFIG" python3 - <<'PY' || rc=$?
import glob, os, re, sys

root, cfg, osv = os.environ["DEPENDABOT_ROOT"], os.environ["DEPENDABOT_CONFIG"], os.environ["OSV_CONFIG"]


def cannot(msg):
    print(f"CANNOT CHECK: {msg}")
    sys.exit(2)


def norm(name):  # PEP 503
    return re.sub(r"[-_.]+", "-", name).lower()


def vtuple(v):
    if not re.fullmatch(r"\d+(\.\d+)*", v):
        return None
    return tuple(int(p) for p in v.split("."))


OPS = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b, "<=": lambda a, b: a <= b, "<": lambda a, b: a < b,
       "==": lambda a, b: a == b}


def in_range(version, spec):
    """True when `version` satisfies every clause of a Dependabot range like ">=5.0.0" or ">=1, <2". None = unreadable."""
    v = vtuple(version)
    if v is None:
        return None
    for clause in spec.split(","):
        m = re.fullmatch(r"\s*(>=|<=|==|>|<)\s*([\d.]+)\s*", clause)
        if not m or vtuple(m.group(2)) is None:
            return None
        width = max(len(v), len(vtuple(m.group(2))))
        a = v + (0,) * (width - len(v))
        b = vtuple(m.group(2)) + (0,) * (width - len(vtuple(m.group(2))))
        if not OPS[m.group(1)](a, b):
            return False
    return True


try:
    import yaml
except ImportError:
    cannot("pyyaml is not installed")
try:
    import tomllib
except ImportError:
    cannot("tomllib needs Python 3.11+")
try:
    doc = yaml.safe_load(open(cfg, encoding="utf-8"))
except FileNotFoundError:
    cannot(f"{cfg} does not exist")
except Exception as exc:
    cannot(f"{cfg} does not parse: {exc}")
try:
    accepts = tomllib.load(open(osv, "rb"))
except FileNotFoundError:
    cannot(f"{osv} (osv-scanner.toml) does not exist")
except Exception as exc:
    cannot(f"{osv} (osv-scanner.toml) does not parse: {exc}")
if not isinstance(doc, dict) or not isinstance(doc.get("updates"), list):
    cannot(f"{cfg} has no `updates:` list")

overrides = {(norm(o.get("name", "")), str(o.get("version", ""))) for o in accepts.get("PackageOverrides") or []}
id_reasons = [str(i.get("reason", "")).lower() for i in accepts.get("IgnoredVulns") or []]


def pins(directory):
    found = {}
    for path in glob.glob(os.path.join(root, directory, "requirements*.txt")):
        for line in open(path, encoding="utf-8"):
            m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;#]+)", line)
            if m:
                found.setdefault(norm(m.group(1)), set()).add(m.group(2))
    return found


defects, checked = [], 0
for u in doc["updates"]:
    if not isinstance(u, dict) or u.get("package-ecosystem") != "pip":
        continue
    for d in [u.get("directory")] + list(u.get("directories") or []):
        if not d:
            continue
        d = d.strip("/")
        here = pins(d)
        for ig in u.get("ignore") or []:
            pkg, ranges = ig.get("dependency-name", ""), ig.get("versions") or []
            checked += 1
            versions = here.get(norm(pkg))
            if not versions:
                defects.append(f"NOT PINNED: {d} ignores {pkg}, but no requirements*.txt there pins it — delete the ignore")
                continue
            for v in sorted(versions):
                for spec in ranges:
                    hit = in_range(v, spec)
                    if hit is None:
                        cannot(f"{d}: cannot read version {v!r} or range {spec!r} for {pkg}")
                    if hit:
                        defects.append(f"DEAD: {d} ignores {pkg} {spec} but pins {v} — the cap is lifted, delete the ignore")
                leaf = os.path.basename(d).lower()
                named = [r for r in id_reasons if re.search(rf"\b{re.escape(norm(pkg))}\b", norm(r))
                         and re.search(rf"\b{re.escape(leaf)}\b", r)]
                if (norm(pkg), v) not in overrides and not named:
                    defects.append(f"UNBACKED: {d} ignores {pkg} (pinned {v}) with no osv-scanner.toml accept — add a "
                                   f"[[PackageOverrides]] for {pkg} {v} with the reason, or delete the ignore")

if checked == 0:
    cannot(f"no ignore in {cfg} — nothing to check")
for line in defects:
    print(line)
if defects:
    print(f"{len(defects)} defect(s) in {checked} Dependabot ignore(s): an ignore with no live reason blocks security "
          "updates silently.")
    sys.exit(1)
print(f"OK — {checked} Dependabot ignore(s), each backed by a live osv-scanner.toml accept at the pinned version.")
PY
case "$rc" in 0|1|2) exit "$rc" ;; *) exit 2 ;; esac
