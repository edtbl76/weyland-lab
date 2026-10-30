#!/usr/bin/env python3
"""check-private-lanes.py — the B234 private-lane guarantee, checked against LiteLLM's config (2026-10-29).

A `wl-private-*` alias promises that a prompt never leaves the lab's own hardware: it is served by self-hosted Ollama on
an allowlisted LAN host, and when that host is down the call FAILS rather than falling back to a hosted provider. LiteLLM
has several ways to send a request for an alias somewhere else, and each one is checked here:

  1. target            — every deployment of a private alias is `ollama_chat/` or `ollama/` on an allowlisted host
                         (a missing api_base is LiteLLM's localhost default: inside the pod, so not allowlisted).
  2. fallbacks         — `fallbacks`, `context_window_fallbacks`, `content_policy_fallbacks` (router_settings or
                         litellm_settings) may take a private alias only to another private alias.
  3. default_fallbacks — applies to EVERY alias, private ones included, so any non-private target leaks.
  4. wildcards         — a wildcard model_name (`wl-*`, `*`) that matches a private name would serve it elsewhere.
  5. model_group_alias — a private name aliased to another model group is not the private deployment.

  usage: check-private-lanes.py <litellm configmap.yaml>
  EXIT: 0 every private lane holds · 1 a violation (each named) · 2 cannot check (unreadable, or no private alias).

The allowlist lives in scripts/ci/private-lane-hosts.yaml. Adding a host (e.g. the new GPU box): add it there, then run
the valve-off test in docs/runbooks/model-gateway.md § Private lane.
"""
import fnmatch
import os
import sys
from urllib.parse import urlparse

import yaml

PRIVATE_PREFIX = "wl-private-"
HOSTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ci", "private-lane-hosts.yaml")
OLLAMA_PREFIXES = ("ollama_chat/", "ollama/")
FALLBACK_KEYS = ("fallbacks", "context_window_fallbacks", "content_policy_fallbacks")


def is_private(name):
    return isinstance(name, str) and name.startswith(PRIVATE_PREFIX)


def check_targets(private_entries, allowed_hosts):
    bad = []
    for entry in private_entries:
        name = entry["model_name"]
        params = entry.get("litellm_params") or {}
        model = str(params.get("model", ""))
        if not model.startswith(OLLAMA_PREFIXES):
            bad.append(f"{name}: target {model!r} is not self-hosted Ollama")
            continue
        host = urlparse(str(params.get("api_base", ""))).hostname
        if host not in allowed_hosts:
            bad.append(f"{name}: api_base host {host!r} is not on the LAN allowlist {sorted(allowed_hosts)}")
    return bad


def check_wildcards(model_list):
    probe = PRIVATE_PREFIX + "x"
    return [f"wildcard {e['model_name']!r} captures private names" for e in model_list
            if any(c in str(e.get("model_name", "")) for c in "*?[") and fnmatch.fnmatch(probe, e["model_name"])]


def fallback_pairs(block, key):
    """Every (source, target) pair in one fallback list: [{"src": ["t1", "t2"]}, ...]."""
    return [(src, t) for rule in block.get(key) or [] for src, targets in (rule or {}).items() for t in targets or []]


def check_section_fallbacks(section, block):
    bad = [f"{section}.{key}: {src} -> {t}" for key in FALLBACK_KEYS for src, t in fallback_pairs(block, key)
           if is_private(src) and not is_private(t)]
    bad += [f"{section}.default_fallbacks applies to every alias, private ones included: {t}"
            for t in block.get("default_fallbacks") or [] if not is_private(t)]
    return bad


def check_group_aliases(router_settings):
    aliases = router_settings.get("model_group_alias") or {}
    return [f"router_settings.model_group_alias: {src} -> {dst.get('model') if isinstance(dst, dict) else dst}"
            for src, dst in aliases.items() if is_private(src)]


def check_fallbacks(settings):
    bad = []
    for section in ("router_settings", "litellm_settings"):
        bad += check_section_fallbacks(section, settings.get(section) or {})
    return bad + check_group_aliases(settings.get("router_settings") or {})


def main(argv):
    if len(argv) != 2:
        print("usage: check-private-lanes.py <litellm configmap.yaml>")
        return 2
    try:
        with open(HOSTS_FILE) as fh:
            allowed_hosts = {str(k): v for k, v in yaml.safe_load(fh)["hosts"].items()}
        if not allowed_hosts:
            raise ValueError(f"{HOSTS_FILE} lists no hosts")
    except Exception as exc:
        print(f"cannot read the private-lane host allowlist: {exc}")
        return 2
    try:
        with open(argv[1]) as fh:
            settings = yaml.safe_load(yaml.safe_load(fh)["data"]["config.yaml"])
        model_list = settings["model_list"]
        if not isinstance(model_list, list):
            raise TypeError("model_list is not a list")
    except Exception as exc:
        print(f"cannot read the LiteLLM config {argv[1]}: {exc}")
        return 2
    private = [e for e in model_list if is_private(e.get("model_name"))]
    if not private:
        print("no wl-private-* alias found — the guard is checking nothing")
        return 2
    bad = check_targets(private, allowed_hosts) + check_wildcards(model_list) + check_fallbacks(settings)
    if bad:
        print("private lane violation(s):")
        print("\n".join(f"  {b}" for b in bad))
        return 1
    names = sorted({e["model_name"] for e in private})
    hosts = sorted({allowed_hosts[urlparse(e["litellm_params"]["api_base"]).hostname] for e in private})
    print(f"OK — {len(names)} private alias(es) {names}, {len(private)} deployment(s), all self-hosted Ollama on "
          f"{hosts}, no route or fallback to a hosted provider")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
