#!/usr/bin/env python3
"""Check or restore the APISIX gateway's routes in etcd (B239; replaces the broken routes-init.sh path).

  usage: apisix-routes.py check     compare etcd with the routes defined in scripts/lib/apisix_routes.py (read-only)
         apisix-routes.py restore   write back only what is missing or different, then check again

Talks to etcd through `kubectl exec sts/weyland-apisix-etcd -- etcdctl` (the etcd image has no shell; the gateway's
admin API listens on its pod's localhost only). Exit 0 in sync, 1 drift found (check) or still drifting after
restore, 2 could not reach etcd. Runbook: docs/runbooks/apisix.md.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import apisix_routes as ar  # noqa: E402

ETCD = ["kubectl", "exec", "-n", "weyland", "sts/weyland-apisix-etcd", "--", "etcdctl"]


class EtcdError(Exception):
    pass


def get(key: str) -> str | None:
    r = subprocess.run(ETCD + ["get", key, "--print-value-only"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise EtcdError(f"etcdctl get {key} failed: {r.stderr.strip()[:200]}")
    return r.stdout.strip() or None


def put(key: str, value: str) -> None:
    r = subprocess.run(ETCD + ["put", key, value], capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or "OK" not in r.stdout:
        raise EtcdError(f"etcdctl put {key} failed: {(r.stderr or r.stdout).strip()[:200]}")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"check", "restore"}:
        print("usage: apisix-routes.py check | restore", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "restore":
            written = ar.restore(get, put, int(time.time()))
            print(f"restored {len(written)} record(s): {', '.join(written) or 'none needed'}")
        problems = ar.drift(get)
    except (EtcdError, OSError, subprocess.TimeoutExpired) as e:
        print(f"apisix-routes: could not reach etcd: {e}", file=sys.stderr)
        return 2
    if problems:
        print("apisix-routes: DRIFT")
        print("\n".join(f"  {k}: {p}" for k, p in problems))
        return 1
    print(f"apisix-routes: in sync ({len(ar.desired_records(0))} records: 1 upstream, {len(ar.ROUTES)} routes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
