"""B255 (2026-11-21): two context-engineering trials on the Realm's single agent, run as evaluation arms (evalrun.py).

Tool retrieval (arm single-rt). B253's single agent carried every Realm tool (99, ~26k tokens of schemas) on every call
in a 32K window, and called no tool at all in 35 of 93 runs. Industry practice (langgraph-bigtool; RAG-MCP, arXiv
2505.03275) is to retrieve a few tools per request. This ranks the tools against the task with BM25 over each tool's
name, description and its family's roster text (the `what`/`role` of every agent holding that prefix), because some
tool descriptions say almost nothing (context_search: "Search."). Stopwords are dropped and each description is cut to
its first 400 characters (the datahub tools carry 2-6k characters of examples that matched unrelated tasks). Lexical,
in-process, no new dependency: the Realm has no embedding model, and the tasks name their systems (Trino, Grafana,
Neo4j, the docs). Checked offline on B253's tasks against the live 99 tools (2026-11-21): the top 8 hold a tool family
a correct agent would use for 18 of the 19 tasks that need one.

Per-step retrieval (arm single-rs, 2026-11-22). A fixed top 8 starved multi-realm tasks (−0.09 against the control):
tasks spanning several tool families lost the tools they needed. langgraph-bigtool's answer is to let the agent ask for
more tools mid-run: ToolPicker holds the selection, `find(query)` adds the best new matches, and the agent sees them on
its next step (agents.run_solo_retrieving binds the growing set before each model call).

Context editing (arm single-ce). Before each model call, once the messages pass a token trigger, every tool result but
the newest `keep` is replaced with a placeholder, in the model's view only (the graph state keeps the history). This
follows LangChain's ClearToolUsesEdit (trigger, keep, "[cleared]"), scaled down: its 100k default trigger can never fire
in a 32K window that tool schemas already fill to ~26k.

Pure logic only, so it is tested without the runtime (tests/test_context_trials.py)."""
import math
import re
from collections import Counter

PLACEHOLDER = "[cleared]"   # LangChain's DEFAULT_TOOL_PLACEHOLDER
_TERM = re.compile(r"[a-z0-9]+")
_K1, _B = 1.5, 0.75          # the usual BM25 constants
_DESC_CHARS = 400


_STOP = frozenset("a an and are as at be by can do does for from has have how i in is it its me my of on or our "
                  "should that the their them then there these this to us was we what when where which who why will "
                  "with would you your".split())


def _terms(text: str) -> list:
    return [w for w in _TERM.findall((text or "").lower()) if w not in _STOP]


def family_blurbs(roster) -> dict:
    """prefix -> the roster text of every agent that holds it (what the tool family is for, in the lab's words)."""
    out: dict = {}
    for spec in roster:
        for p in spec.tool_prefixes:
            out[p] = f"{out.get(p, '')} {spec.role} {spec.what}".strip()
    return out


def _document(tool, blurbs: dict) -> list:
    name = tool.name.lower()
    extra = " ".join(text for p, text in blurbs.items() if p.lower() in name)   # the same substring rule as fleet.py
    return _terms(f"{tool.name} {(tool.description or '')[:_DESC_CHARS]} {extra}")


def rank_tools(task: str, tools: list, k: int, blurbs: dict | None = None) -> list:
    """The `k` tools that best match `task` by BM25, best first; ties keep the input order. Tools that share no term
    with the task are never returned, so a pure-reasoning task can get no tools at all."""
    docs = [_document(t, blurbs or {}) for t in tools]
    if not docs:
        return []
    avg = sum(len(d) for d in docs) / len(docs) or 1.0
    df = Counter(term for d in docs for term in set(d))
    n = len(docs)
    query = set(_terms(task))
    scored = []
    for i, d in enumerate(docs):
        tf = Counter(d)
        s = 0.0
        for term in query:
            if tf[term]:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                s += idf * tf[term] * (_K1 + 1) / (tf[term] + _K1 * (1 - _B + _B * len(d) / avg))
        if s > 0:
            scored.append((-s, i))
    return [tools[i] for _, i in sorted(scored)[:k]]


FIND_N = 5   # tools one find_tools call may add


def _first_sentence(text: str) -> str:
    first = (text or "").strip().split(". ")[0].split("\n")[0]
    return first.rstrip(".")[:200]


class ToolPicker:
    """The tools an agent holds during one run: starts with the best `k` for the task, grows on request."""

    def __init__(self, tools: list, blurbs: dict | None = None):
        self.tools, self.blurbs = list(tools), blurbs or {}
        self.selected: list = []
        self.found: list = []   # names added by find(), in order

    def pick(self, task: str, k: int) -> list:
        self.selected = rank_tools(task, self.tools, k, self.blurbs)
        return self.selected

    def find(self, query: str, n: int = FIND_N) -> str:
        """Add up to `n` tools matching `query` that the agent does not hold yet; the reply names them for the model."""
        held = {t.name for t in self.selected}
        new = rank_tools(query, [t for t in self.tools if t.name not in held], n, self.blurbs)
        self.selected += new
        self.found += [t.name for t in new]
        if not new:
            return (f"No other tools match {query!r}. Answer with the tools you have, or describe the need in other "
                    "words.")
        return "Now available on your next step:\n" + "\n".join(
            f"- {t.name}: {_first_sentence(t.description)}" for t in new)


def _approx_tokens(messages) -> int:
    return sum(len(str(getattr(m, "content", "") or "")) for m in messages) // 4   # ~4 chars a token, as LangChain's


def clear_stale_tool_results(messages: list, *, trigger_tokens: int, keep: int) -> tuple:
    """(edited copy, how many results were cleared). Below the trigger, or with no more than `keep` tool results,
    the copy is unchanged. The input list and its messages are never mutated."""
    out = list(messages)
    if _approx_tokens(out) <= trigger_tokens:
        return out, 0
    idx = [i for i, m in enumerate(out) if getattr(m, "type", None) == "tool"]
    stale = idx[:-keep] if keep else idx
    cleared = 0
    for i in stale:
        if out[i].content != PLACEHOLDER:
            out[i] = out[i].model_copy(update={"content": PLACEHOLDER})
            cleared += 1
    return out, cleared


def clearing_hook(*, trigger_tokens: int, keep: int, on_clear=None):
    """A LangGraph `pre_model_hook`: the model sees the edited messages (llm_input_messages), the state keeps them all.
    `on_clear(n)` hears how many results this call's view had cleared (for the evaluation's counters)."""
    def hook(state: dict) -> dict:
        edited, n = clear_stale_tool_results(state["messages"], trigger_tokens=trigger_tokens, keep=keep)
        if on_clear and n:
            on_clear(n)
        return {"llm_input_messages": edited}
    return hook
