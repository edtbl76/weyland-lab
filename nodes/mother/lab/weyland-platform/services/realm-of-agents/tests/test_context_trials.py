"""B255 (2026-11-21): two context-engineering trials on the single agent, run as evaluation arms.

  single-rt  tool retrieval: rank the 99 tools against the task (BM25 over each tool's name, description and its
             family's roster text) and give the agent only the top k. B253's single agent carried ~26k tokens of tool
             schemas on every call and called no tool at all in 35 of 93 runs.
  single-ce  context editing: before each model call, replace all but the newest tool results with a placeholder once
             the messages pass a token trigger (LangChain's ClearToolUsesEdit semantics, scaled to a 32K window).
context_trials.py is pure logic, so these tests need no runtime deps."""
import types

import context_trials as ct


def _tool(name, description=""):
    return types.SimpleNamespace(name=name, description=description)


def _spec(prefixes, what, role="r"):
    return types.SimpleNamespace(tool_prefixes=prefixes, what=what, role=role)


TOOLS = [
    _tool("weyland_fleet-grafana_search_dashboards", "Search for Grafana dashboards by a query string."),
    _tool("weyland_fleet-grafana_query_prometheus", "Query Prometheus using a PromQL expression."),
    _tool("weyland_fleet-trino_list_catalogs", "List all available catalogs."),
    _tool("weyland_fleet-neo4j_read_neo4j_cypher", "Execute a read Cypher query."),
    _tool("weyland_fleet-context_context_search", "Search."),
]


def test_the_tool_named_by_the_task_ranks_first():
    top = ct.rank_tools("Which Trino catalogs can I query?", TOOLS, k=2)
    assert top[0].name == "weyland_fleet-trino_list_catalogs"


def test_k_caps_the_result_and_keeps_rank_order():
    top = ct.rank_tools("find the grafana dashboards for prometheus", TOOLS, k=2)
    assert [t.name for t in top] == ["weyland_fleet-grafana_search_dashboards", "weyland_fleet-grafana_query_prometheus"]


def test_a_family_blurb_finds_a_tool_whose_own_description_says_nothing():
    # context_search's own description is one word; the roster says what the family is for.
    blurbs = ct.family_blurbs([_spec(("context",), "Answers from the lab's own documentation and runbooks.")])
    top = ct.rank_tools("According to the lab's documentation, which model answers?", TOOLS, k=1, blurbs=blurbs)
    assert top[0].name == "weyland_fleet-context_context_search"


def test_blurbs_join_every_agent_sharing_a_prefix():
    blurbs = ct.family_blurbs([_spec(("trino",), "SQL analyst"), _spec(("trino", "postgres"), "data seer")])
    assert "SQL analyst" in blurbs["trino"] and "data seer" in blurbs["trino"] and blurbs["postgres"].strip()


def test_a_task_with_no_matching_terms_gets_no_tools():
    assert ct.rank_tools("zzz qqq", TOOLS, k=3) == []


def test_ranking_is_deterministic_on_ties():
    a = ct.rank_tools("query", TOOLS, k=5)
    assert [t.name for t in a] == [t.name for t in ct.rank_tools("query", TOOLS, k=5)]


# --- context editing ---------------------------------------------------------------------------------------------
class _Msg:
    def __init__(self, type_, content):
        self.type, self.content = type_, content

    def model_copy(self, update):
        m = _Msg(self.type, self.content)
        for k, v in update.items():
            setattr(m, k, v)
        return m


def _conv(n_tools, size=400):
    msgs = [_Msg("system", "role"), _Msg("human", "task")]
    for i in range(n_tools):
        msgs += [_Msg("ai", f"call {i}"), _Msg("tool", f"r{i}:" + "x" * size)]
    return msgs


def test_below_the_trigger_nothing_is_cleared():
    msgs = _conv(4, size=10)
    out, cleared = ct.clear_stale_tool_results(msgs, trigger_tokens=10_000, keep=2)
    assert cleared == 0 and [m.content for m in out] == [m.content for m in msgs]


def test_past_the_trigger_all_but_the_newest_keep_results_are_cleared():
    msgs = _conv(4)
    out, cleared = ct.clear_stale_tool_results(msgs, trigger_tokens=100, keep=2)
    tools = [m.content for m in out if m.type == "tool"]
    assert cleared == 2 and tools[:2] == [ct.PLACEHOLDER] * 2 and tools[2].startswith("r2:") and tools[3].startswith("r3:")


def test_the_input_list_is_not_mutated():
    # The graph state keeps the full history; only the model's view is edited (llm_input_messages).
    msgs = _conv(4)
    ct.clear_stale_tool_results(msgs, trigger_tokens=100, keep=1)
    assert all(m.content != ct.PLACEHOLDER for m in msgs)


def test_fewer_results_than_keep_clears_nothing():
    out, cleared = ct.clear_stale_tool_results(_conv(2), trigger_tokens=1, keep=2)
    assert cleared == 0


def test_the_hook_returns_the_edited_view_and_reports_what_it_cleared():
    seen = []
    hook = ct.clearing_hook(trigger_tokens=100, keep=1, on_clear=seen.append)
    out = hook({"messages": _conv(3)})
    assert set(out) == {"llm_input_messages"} and seen == [2]
    assert [m.content for m in out["llm_input_messages"] if m.type == "tool"][-1].startswith("r2:")


def test_stopwords_alone_never_match():
    assert ct.rank_tools("what is the one for this", [_tool("x_thing", "What is the thing for this.")], k=3) == []


def test_only_the_start_of_a_long_description_counts():
    long_doc = _tool("weyland_fleet-datahub_search", "Search the catalog. " + "filler " * 100 + "neo4j")
    assert ct.rank_tools("neo4j", [long_doc], k=1) == []


# --- per-step retrieval (arm single-rs, 2026-11-22) ----------------------------------------------------------------
# A fixed top 8 starved multi-realm tasks (−0.09). langgraph-bigtool's pattern: the agent can ask for more tools mid-run.
def test_the_picker_starts_with_the_top_k():
    p = ct.ToolPicker(TOOLS)
    assert [t.name for t in p.pick("Which Trino catalogs?", 1)] == ["weyland_fleet-trino_list_catalogs"]


def test_find_adds_new_matching_tools_and_says_which():
    p = ct.ToolPicker(TOOLS)
    p.pick("Which Trino catalogs?", 1)
    text = p.find("grafana dashboards", n=1)
    assert [t.name for t in p.selected] == ["weyland_fleet-trino_list_catalogs", "weyland_fleet-grafana_search_dashboards"]
    assert "weyland_fleet-grafana_search_dashboards" in text and p.found == ["weyland_fleet-grafana_search_dashboards"]


def test_find_never_returns_a_tool_already_held():
    p = ct.ToolPicker(TOOLS)
    p.pick("trino catalogs", 5)
    held = len(p.selected)
    assert "No other tools" in p.find("trino catalogs") and len(p.selected) == held


def test_find_shows_only_the_first_sentence_of_a_description():
    p = ct.ToolPicker([_tool("weyland_fleet-trino_list_catalogs", "List all catalogs. Then much more text here.")])
    assert "Then much more" not in p.find("trino")
