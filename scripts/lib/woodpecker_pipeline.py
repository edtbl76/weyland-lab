"""Read the weyland-lab Woodpecker pipeline: a directory of workflows (.woodpecker/*.yml, since B200 2026-11-18) or,
for a guard's test fixture, a single file. Every guard that inspects the pipeline's steps goes through here, so the
layout lives in one place.

Fails closed: a missing path, a directory with no workflow, an unparseable file or a workflow without a step list
raises PipelineError. A guard must never read "no steps" as "nothing to check, all clean".
Tests: scripts/tests/test_woodpecker_pipeline.py.
"""
import glob
import os

import yaml

PIPELINE_DIR = ".woodpecker"     # relative to the repo root


class PipelineError(Exception):
    """The pipeline could not be read; the caller must exit 2 (could not check), never pass."""


def files(path):
    """The workflow files at path, in name order (a single file is returned as itself)."""
    if os.path.isfile(path):
        return [path]
    if not os.path.isdir(path):
        raise PipelineError(f"{path} not found")
    found = sorted(glob.glob(os.path.join(path, "*.yml")) + glob.glob(os.path.join(path, "*.yaml")))
    if not found:
        raise PipelineError(f"no workflow (*.yml) in {path}")
    return found


def workflows(path):
    """[(workflow name, parsed document)], the name being the file name without its extension."""
    out = []
    for f in files(path):
        try:
            with open(f, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            raise PipelineError(f"cannot read {f}: {exc}") from exc
        if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
            raise PipelineError(f"{f} has no step list")
        out.append((os.path.splitext(os.path.basename(f))[0], doc))
    return out


def steps(path):
    """[(workflow name, step dict)] across every workflow, in file then step order."""
    return [(name, step) for name, doc in workflows(path) for step in doc["steps"] if isinstance(step, dict)]
