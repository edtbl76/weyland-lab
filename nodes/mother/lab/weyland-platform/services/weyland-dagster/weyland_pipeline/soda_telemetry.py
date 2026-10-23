"""Turn off Soda Core's anonymous usage telemetry (owner, 2026-10-23).

Soda Core posts usage stats to collect.soda.io unless its USER config says `send_anonymous_usage_stats: false`. It reads
the first of ~/.soda/config.yml, .soda/config.yml, /tmp/.soda/config.yml that exists, and creates ~/.soda/config.yml with
the stats ON at its first run, so the opt-out overwrites that file (keeping its other keys). The key is ignored in the
data-source configuration.yml. Called by soda_scan_op before every scan. Dagster-free on purpose (tested in isolation).
"""
import os

import yaml


def disable_soda_telemetry(home=None) -> str:
    """Write the opt-out into <home>/.soda/config.yml (default: this process's HOME) and return the path."""
    path = os.path.join(home or os.path.expanduser("~"), ".soda", "config.yml")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    config = {}
    if os.path.exists(path):
        with open(path) as f:
            config = yaml.safe_load(f) or {}
    config["send_anonymous_usage_stats"] = False
    with open(path, "w") as f:
        yaml.safe_dump(config, f)
    return path
