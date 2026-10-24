"""Notebook 22's store_up() (B225, 2026-10-20) — the guard that turns a PARKED store into a printed up/down
instruction (B232; it was wake/wait/park) instead of a failed cell.

The function lives only in the notebook JSON, so it was never tested (the B225 DoD re-audit, 2026-10-21). These tests
load the REAL source out of the notebook — no copy to drift — and pin its two outcomes. Note what it cannot tell apart:
a parked store and a store that is down look the same ("PARKED (or down)"), so a headless PASS on notebook 22 does not
mean the parked stores answered (runbooks/jupyterhub.md, demos/jupyter-notebook-library.md).
"""
import json
import os

import pytest

NB = os.path.join(os.path.dirname(__file__), "..", "..", "nodes", "mother", "lab", "weyland-platform", "k8s",
                  "jupyterhub", "singleuser", "notebooks", "22_query_tier2_native.ipynb")


def load_store_up():
    """Exec only the STORE_PARK constant and the store_up() definition from the notebook's code cells."""
    for cell in json.load(open(NB, encoding="utf-8"))["cells"]:
        src = "".join(cell["source"])
        if cell["cell_type"] == "code" and "def store_up" in src:
            start = src.index("STORE_PARK = ")
            body = src[start:]
            lines, out = body.split("\n"), []
            for i, line in enumerate(lines):
                # stop at the first top-level statement after the function body
                if i > 0 and out and line and not line[0].isspace() and not line.startswith(("def store_up", "STORE_PARK")) \
                        and any(l.startswith("def store_up") for l in out):
                    break
                out.append(line)
            ns = {}
            exec("\n".join(out), ns)  # noqa: S102 — the repo's own notebook source, not external input
            return ns["store_up"]
    raise AssertionError("no cell in notebook 22 defines store_up() — the guard moved or was removed")


def test_a_store_that_answers_is_up_and_prints_nothing(capsys):
    store_up = load_store_up()
    assert store_up("cassandra", lambda: None) is True
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("exc", [ConnectionRefusedError("refused"), TimeoutError("timed out"), OSError("no route")])
def test_a_store_that_does_not_answer_is_skipped_with_the_up_and_down_commands(capsys, exc):
    store_up = load_store_up()

    def probe():
        raise exc

    assert store_up("mongodb", probe) is False
    out = capsys.readouterr().out
    assert "PARKED (or down): mongodb" in out and type(exc).__name__ in out
    # B232: one command each way (commit + push + wait), not the old wake / push / wait / park / push / wait
    for verb in ("up", "down"):
        assert f"store-park.sh {verb} mongodb" in out, f"the {verb} command for mongodb is missing:\n{out}"
    for old in ("wake", "wait", "park"):
        assert f"store-park.sh {old} mongodb" not in out, f"the old multi-step '{old}' is still printed:\n{out}"


def test_the_commands_use_the_absolute_store_park_path():
    store_up = load_store_up()
    assert store_up.__globals__["STORE_PARK"] == \
        "bash /home/edwardmangini/IdeaProjects/weyland/scripts/store-park.sh"
