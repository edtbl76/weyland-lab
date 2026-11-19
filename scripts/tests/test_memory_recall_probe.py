"""scripts/memory-recall-probe.py (B250, 2026-11-19) — does a natural question find the note that answers it?

Lab Recall answered "How does Weyland manage ADRs?" with "Actionable Design Reviews" because the shared-memory search
returned hardware-topology, weyland-guard-b70 and prompt-federation-b103, not adr-log-b248. The probe asks fixed
questions the way the gateway does (semantic search, as the compositor rewrites it) and fails when the expected note is
not in the top 3. The MCP call is stubbed here; the result text is the shape OBSERVED from Basic Memory on 2026-11-19
("### <note>" per hit). An empty, errored or unreachable search is exit 2, never a pass.
"""
import asyncio
import importlib.util
import pathlib

import pytest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "memory-recall-probe.py"
_spec = importlib.util.spec_from_file_location("memory_recall_probe", _PATH)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

OBSERVED_MISS = """# Search Results: How does Weyland manage ADRs
*project: weyland*

### hardware-topology
- permalink: None
- score: 0.7511
- match: **weyland** is the **physical machine**

### weyland-guard-b70
- permalink: None
- score: 0.7313

### prompt-federation-b103
- permalink: None
- score: 0.7258
"""


def _hits(*names):
    return "# Search Results: q\n*project: weyland*\n\n" + "".join(f"### {n}\n- score: 0.8\n\n" for n in names)


def _search(replies):
    """A stub search: query -> (is_error, text); a missing query raises like an unreachable store."""
    async def search(query):
        if query not in replies:
            raise probe.CannotReach("connection refused")
        return replies[query]
    return search


def test_titles_are_read_in_rank_order_from_the_observed_text():
    assert probe.titles(OBSERVED_MISS) == ["hardware-topology", "weyland-guard-b70", "prompt-federation-b103"]


def test_the_observed_miss_fails_and_names_what_came_back(capsys):
    cases = [("How does Weyland manage ADRs", "adr-log-b248")]
    rc = asyncio.run(probe.run(cases, _search({"How does Weyland manage ADRs": (False, OBSERVED_MISS)})))
    assert rc == 1
    out = capsys.readouterr().out
    assert "MISS" in out and "adr-log-b248" in out and "hardware-topology" in out


def test_expected_note_in_the_top_3_is_a_hit():
    cases = [("q1", "adr-log-b248"), ("q2", "adr-log-b248")]
    replies = {"q1": (False, _hits("adr-log-b248", "x", "y")), "q2": (False, _hits("x", "y", "adr-log-b248"))}
    assert asyncio.run(probe.run(cases, _search(replies))) == 0


def test_fourth_place_is_a_miss():
    replies = {"q": (False, _hits("a", "b", "c", "adr-log-b248"))}
    assert asyncio.run(probe.run([("q", "adr-log-b248")], _search(replies))) == 1


def test_an_empty_result_is_exit_2_not_a_pass(capsys):
    rc = asyncio.run(probe.run([("q", "adr-log-b248")], _search({"q": (False, "# Search Results: q\n\nNo results")})))
    assert rc == 2
    assert "no results" in capsys.readouterr().out.lower()


def test_an_errored_search_is_exit_2(capsys):
    rc = asyncio.run(probe.run([("q", "adr-log-b248")], _search({"q": (True, "Error: bad query")})))
    assert rc == 2


def test_an_unreachable_store_is_exit_2_even_after_hits(capsys):
    cases = [("q1", "adr-log-b248"), ("down", "adr-log-b248")]
    rc = asyncio.run(probe.run(cases, _search({"q1": (False, _hits("adr-log-b248"))})))
    assert rc == 2
    assert "UNREACHABLE" in capsys.readouterr().out


def test_cases_file_reads_tab_separated_lines_and_skips_comments(tmp_path):
    f = tmp_path / "cases.tsv"
    f.write_text("# question\texpected note\nHow does Weyland manage ADRs\tadr-log-b248\n\nwhat is our decision log\tadr-log-b248\n")
    assert probe.load_cases(f) == [("How does Weyland manage ADRs", "adr-log-b248"),
                                   ("what is our decision log", "adr-log-b248")]


def test_an_empty_or_malformed_cases_file_is_refused(tmp_path):
    empty = tmp_path / "empty.tsv"
    empty.write_text("# nothing\n")
    with pytest.raises(ValueError, match="no cases"):
        probe.load_cases(empty)
    bad = tmp_path / "bad.tsv"
    bad.write_text("a question with no expected note\n")
    with pytest.raises(ValueError, match="line 1"):
        probe.load_cases(bad)


def test_the_repo_cases_cover_the_b250_questions():
    cases = probe.load_cases(probe.DEFAULT_CASES)
    asked = {q for q, _ in cases}
    assert {"How does Weyland manage ADRs", "what is our decision log",
            "where are architecture decisions recorded"} <= asked
