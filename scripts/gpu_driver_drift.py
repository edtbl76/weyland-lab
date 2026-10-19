#!/usr/bin/env python3
"""gpu_driver_drift.py — does rogueone's LOADED NVIDIA kernel module match the INSTALLED driver? (B226, 2026-10-19)

WHY THIS EXISTS: on 2026-10-09 unattended-upgrades moved rogueone's userspace driver to 595.99.02 while the running
kernel module stayed 595.91.07 (boot 2026-09-20). Nothing noticed for nine days; a stray `nvidia-smi` ("Driver/library
version mismatch") found it. Ollama kept working only because it had run since boot with the old libraries loaded —
its next restart would have loaded 595.99 against the 595.91 module, likely lost CUDA, and pushed every local model,
including the MLflow gateway's guardrail judge (fail-closed, in the critical path), to CPU. The NVIDIA packages are now
held back from unattended-upgrades (nodes/rogueone/apt/51weyland-hold-nvidia); this check catches what the hold does
not — a hand-run `apt upgrade` without the reboot, or a package name the hold's pattern misses.

WHAT IT CHECKS: the module version in /proc/driver/nvidia/version against the one installed `nvidia-driver-*` package
(dpkg status `ii` only — dpkg also lists names it knows but never installed, with an empty version). Run hourly by the
user timer nodes/rogueone/systemd/gpu-driver-drift.{service,timer}; the verdict goes to an Uptime-Kuma PUSH monitor
(KUMA_GPU_DRIFT_PUSH_URL in scripts/.env), a dead-man's switch, so a check that stops running alerts too.

EXIT: 0 module == installed driver · 1 they differ (reboot to load the installed driver) · 2 could not check (no
module loaded, no installed driver, two installed drivers, unreadable output). Fail closed: nothing read is never a
match. GPU_DRIFT_MODULE_FILE overrides the /proc path (the forced-mismatch test).

    usage: python3 scripts/gpu_driver_drift.py [--no-push]
"""
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

MODULE_FILE = "/proc/driver/nvidia/version"
MODULE_ENV = "GPU_DRIFT_MODULE_FILE"
PUSH_KEY = "KUMA_GPU_DRIFT_PUSH_URL"
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
# "...Open Kernel Module for x86_64  595.99.02  Release Build ..." or "...x86_64 Kernel Module  580.159.03  <date>"
_MODULE_RE = re.compile(r"^NVRM version:.*?Kernel Module\b.*?\s(\d+\.\d+(?:\.\d+)?)\s", re.MULTILINE)
_DRIVER_PKG = re.compile(r"^nvidia-driver-\d+")


class CannotRead(Exception):
    """A source the verdict depends on could not be read."""


def module_version(text):
    """The loaded module's version from /proc/driver/nvidia/version, or None if it does not parse."""
    m = _MODULE_RE.search(text or "")
    return m.group(1) if m else None


def installed_drivers(rows):
    """[(package, upstream version)] for fully installed (`ii`) nvidia-driver-<N>* packages."""
    out = []
    for line in rows.splitlines():
        pkg, _, rest = line.partition("|")
        version, _, status = rest.partition("|")
        if _DRIVER_PKG.match(pkg) and status.strip() == "ii" and version:
            out.append((pkg, version.split("-", 1)[0]))  # 595.99.02-0ubuntu0.24.04.1 -> 595.99.02
    return out


def evaluate(module_text, dpkg_rows):
    """(rc, message) — 0 match, 1 drift, 2 could not check."""
    if module_text is None:
        return 2, "no NVIDIA kernel module loaded (no /proc/driver/nvidia/version) — could not check"
    loaded = module_version(module_text)
    if loaded is None:
        return 2, "unparseable /proc/driver/nvidia/version — could not check"
    drivers = installed_drivers(dpkg_rows)
    if not drivers:
        return 2, f"no installed nvidia-driver-* package (module {loaded} loaded) — could not check"
    if len(drivers) > 1:
        names = ", ".join(f"{p} {v}" for p, v in drivers)
        return 2, f"two installed driver packages ({names}) — could not tell which one should be loaded"
    pkg, installed = drivers[0]
    if loaded == installed:
        return 0, f"gpu-driver-drift: OK — loaded module {loaded} == {pkg} {installed}"
    return 1, (f"DRIFT: loaded module {loaded} != installed {pkg} {installed} — reboot to load the installed driver "
               "(until then a restarted Ollama may lose the GPU)")


def _dpkg_rows():
    try:
        r = subprocess.run(["dpkg-query", "-W", "-f=${Package}|${Version}|${db:Status-Abbrev}\\n", "nvidia-driver-*"],
                           capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise CannotRead(f"dpkg-query: {e}") from e
    if r.returncode != 0:
        raise CannotRead(f"dpkg-query exited {r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def _module_text():
    try:
        with open(os.environ.get(MODULE_ENV) or MODULE_FILE, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return None


def push(url, rc, summary):
    """Report the verdict to the Kuma push monitor. A missed heartbeat is itself the alarm, so a failed push only logs."""
    if not url:
        print(f"{PUSH_KEY} unset — verdict NOT reported to Kuma (runbook model-serving-ollama.md § NVIDIA driver)",
              file=sys.stderr)
        return
    q = urllib.parse.urlencode({"status": "up" if rc == 0 else "down", "msg": summary[:250]})
    try:
        urllib.request.urlopen(f"{url}?{q}", timeout=15).read()  # nosec B310 — the operator's own Kuma push URL
    except OSError as e:   # URLError is an OSError
        print(f"could not reach Kuma ({e}) — the push monitor will alert on the missed heartbeat", file=sys.stderr)


def push_url(env_file=ENV_FILE):
    """KUMA_GPU_DRIFT_PUSH_URL from the environment, else that ONE key from scripts/.env — never the whole file."""
    if os.environ.get(PUSH_KEY) is not None:
        return os.environ[PUSH_KEY]
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                k, sep, v = line.strip().partition("=")
                if sep and k.strip() == PUSH_KEY:
                    return v.strip().strip("'\"")
    except OSError:
        pass
    return ""


def main(argv):
    try:
        rc, msg = evaluate(_module_text(), _dpkg_rows())
    except CannotRead as e:
        rc, msg = 2, f"could not read the installed driver: {e}"
    print(msg)
    if "--no-push" not in argv:
        push(push_url(), rc, msg)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
