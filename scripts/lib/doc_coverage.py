"""Every deployed app has a runbook and a place on a map (B239 batch C). Stdlib only.

Reads the B82 application registry entries. For each app with `deployed: true`:
  - `runbook:` names a file in docs/runbooks/ (an `#anchor` suffix is allowed), or is null with a `runbook_gap:`
    reason. A null with a reason is a KNOWN gap: reported, not an error. A missing field or a missing file is an error.
  - the app's `map_label:` (else its name, else its key) appears, case-insensitive and as a whole word, in at least
    one docs/*-map.html.
No maps at all is an error (fail closed: nothing checked is not a pass).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    checked: int = 0


def _labels(app: dict) -> list[str]:
    if app.get("map_label"):
        return [app["map_label"]]
    return [x for x in (app.get("name"), app.get("key")) if x]


def _on_a_map(app: dict, maps: dict[str, str]) -> bool:
    for label in _labels(app):
        pat = re.compile(r"(?<![\w-])" + re.escape(label) + r"(?![\w-])", re.IGNORECASE)
        if any(pat.search(text) for text in maps.values()):
            return True
    return False


def _runbook_error(app: dict, runbook_dir: Path) -> tuple[str | None, str | None]:
    """(error, gap) for one app's runbook field."""
    key = app["key"]
    if "runbook" not in app:
        return f"{key}: no runbook: field (name its runbook, or null with a runbook_gap: reason)", None
    rb = app["runbook"]
    if rb is None:
        reason = (app.get("runbook_gap") or "").strip()
        if not reason:
            return f"{key}: runbook is null but has no runbook_gap: reason", None
        return None, f"{key}: {reason}"
    name = str(rb).split("#", 1)[0]
    if not (runbook_dir / name).is_file():
        return f"{key}: runbook {name} does not exist in docs/runbooks/", None
    return None, None


def check(apps: list[dict], root: Path) -> Result:
    res = Result()
    runbook_dir = root / "docs" / "runbooks"
    maps = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in sorted((root / "docs").glob("*-map.html"))}
    if not maps:
        res.errors.append("no maps found (docs/*-map.html): nothing to check presence against")
    for app in apps:
        if not app.get("deployed"):
            continue
        res.checked += 1
        err, gap = _runbook_error(app, runbook_dir)
        if err:
            res.errors.append(err)
        if gap:
            res.gaps.append(gap)
        if maps and not _on_a_map(app, maps):
            res.errors.append(f"{app['key']}: on no map (add it to a docs/*-map.html, or set map_label: to the map's name for it)")
    return res
