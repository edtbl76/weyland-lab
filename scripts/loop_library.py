"""B175 — the loop library's validator and bundler.

A loop is a reusable agent workflow: a prompt with checkpoints and an explicit TERMINAL CONDITION, a stopping rule
that keeps it from running away. The library lives in knowledge-repos/loop-library/ (one Markdown file per loop, YAML
frontmatter + a `## Prompt` section) and is published to Bifrost's Prompt Repository by the Dagster `registrations`
group (services/weyland-dagster/scripts/register_bifrost_loops.py), which reads the bundle this module writes.

    python3 scripts/loop_library.py validate [DIR]   # exit 0 valid · 1 an entry is invalid · 2 could not read
    python3 scripts/loop_library.py bundle [DIR]     # the JSON the publisher reads (stdout)

Runbook: knowledge-repos/loop-library/README.md.
"""
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
LIBRARY = REPO / "knowledge-repos" / "loop-library"
CATEGORIES = ("Engineering", "Operations", "Evaluation", "Content", "Design")   # the Forward Future loop-library set
REQUIRED = ("id", "title", "category", "description", "terminal_condition")
OPTIONAL = ("pacing", "source")
# A terminal condition is a checkable stopping rule. Short or stock phrases ("when done", "until it works") are not.
MIN_TERMINAL_CHARS = 25
PROMPT_HEADING = "## Prompt"


class InvalidLibrary(ValueError):
    pass


def parse(path: Path) -> dict:
    """One loop file -> its fields plus `prompt`. A file without frontmatter parses to {} (and then fails validation)."""
    text = path.read_text()
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return {}
    front, _, body = text[4:].partition("\n---")
    fields = yaml.safe_load(front) or {}
    if not isinstance(fields, dict):
        return {}
    loop = {k: (str(v).strip() if v is not None else "") for k, v in fields.items()}
    _, found, prompt = body.partition(PROMPT_HEADING)
    loop["prompt"] = prompt.strip() if found else ""
    return loop


def problems(loop: dict, stem: str) -> list[str]:
    """Every reason this entry is not acceptable; empty means valid."""
    if not loop:
        return ["no YAML frontmatter (the file must start with a --- block)"]
    out = [f"missing {field}" for field in REQUIRED if not loop.get(field)]
    if loop.get("id") and loop["id"] != stem:
        out.append(f"id '{loop['id']}' does not match the file name '{stem}'")
    if loop.get("category") and loop["category"] not in CATEGORIES:
        out.append(f"category '{loop['category']}' is not one of {', '.join(CATEGORIES)}")
    terminal = loop.get("terminal_condition", "")
    if terminal and len(terminal) < MIN_TERMINAL_CHARS:
        out.append(f"terminal_condition '{terminal}' is not a checkable stopping rule (under {MIN_TERMINAL_CHARS} chars)")
    if not loop.get("prompt"):
        out.append(f"empty prompt (a '{PROMPT_HEADING}' section with the full prompt is required)")
    unknown = set(loop) - set(REQUIRED) - set(OPTIONAL) - {"prompt"}
    if unknown:
        out.append(f"unknown field(s): {', '.join(sorted(unknown))}")
    return out


def _loop_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.glob("*.md") if p.name != "README.md")


def load(directory: Path) -> tuple[list[dict], dict[str, list[str]]]:
    if not directory.is_dir():
        raise FileNotFoundError(f"no loop library at {directory}")
    files = _loop_files(directory)
    if not files:
        raise FileNotFoundError(f"no loops in {directory} — an empty library is not a valid one")
    loops, bad = [], {}
    for path in files:
        loop = parse(path)
        found = problems(loop, path.stem)
        if found:
            bad[path.name] = found
        else:
            loops.append(loop)
    return loops, bad


def bundle(directory: Path = LIBRARY) -> str:
    """The publisher's input: every loop, sorted by id, as stable JSON. Refuses an invalid library."""
    loops, bad = load(directory)
    if bad:
        raise InvalidLibrary(f"{len(bad)} invalid loop(s): {', '.join(sorted(bad))}")
    keys = REQUIRED + OPTIONAL + ("prompt",)
    entries = [{k: loop[k] for k in keys if loop.get(k)} for loop in sorted(loops, key=lambda x: x["id"])]
    return json.dumps({"source": "knowledge-repos/loop-library", "loops": entries}, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("validate", "bundle"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    directory = Path(argv[1]) if len(argv) > 1 else LIBRARY
    try:
        loops, bad = load(directory)
    except (OSError, yaml.YAMLError) as exc:
        print(f"loop-library: cannot read — {exc}", file=sys.stderr)
        return 2
    if argv[0] == "bundle":
        if bad:
            print(f"loop-library: refusing to bundle — {len(bad)} invalid loop(s); run validate", file=sys.stderr)
            return 1
        sys.stdout.write(bundle(directory))
        return 0
    for name, found in sorted(bad.items()):
        for problem in found:
            print(f"INVALID {name}: {problem}")
    if bad:
        print(f"loop-library: {len(bad)} of {len(bad) + len(loops)} loop(s) invalid")
        return 1
    print(f"OK — {len(loops)} loop(s), each with a terminal condition.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
