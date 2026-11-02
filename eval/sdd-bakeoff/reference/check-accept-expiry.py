#!/usr/bin/env python3
"""REFERENCE solution for the bake-off vague task (judge validation only, not part of the lab repo): fail when any
scanner accept has expired, or expires within --days days. Reads the four expiry forms: osv-scanner.toml
IgnoredVulns.ignoreUntil and PackageOverrides.effectiveUntil, .trivyignore `exp:YYYY-MM-DD`, and
.trivyignore-images.yaml vulnerabilities[].expired_at.   usage: check-accept-expiry.py [--days N]   exit 0 ok / 1 due"""
import datetime
import re
import sys
import tomllib

import yaml

days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 0
limit = datetime.date.today() + datetime.timedelta(days=days)
due = []
osv = tomllib.load(open("osv-scanner.toml", "rb"))
for e in osv.get("IgnoredVulns", []):
    if "ignoreUntil" in e and e["ignoreUntil"] <= limit:
        due.append(f"osv-scanner.toml IgnoredVulns {e.get('id')} {e['ignoreUntil']}")
for e in osv.get("PackageOverrides", []):
    if "effectiveUntil" in e and e["effectiveUntil"] <= limit:
        due.append(f"osv-scanner.toml PackageOverrides {e.get('name')} {e['effectiveUntil']}")
for line in open(".trivyignore"):
    m = re.search(r"exp:(\d{4}-\d{2}-\d{2})", line)
    if m and not line.lstrip().startswith("#") and datetime.date.fromisoformat(m.group(1)) <= limit:
        due.append(f".trivyignore {line.split()[0]} {m.group(1)}")
for e in (yaml.safe_load(open(".trivyignore-images.yaml")) or {}).get("vulnerabilities", []):
    d = e.get("expired_at")
    if d is not None and (d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d))) <= limit:
        due.append(f".trivyignore-images.yaml {e.get('id')} {d}")
print("\n".join(due) or "no accept expired or due")
sys.exit(1 if due else 0)
