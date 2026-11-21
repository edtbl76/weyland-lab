"""B255 (2026-11-20): the agent's `rag-generate` generation carries the bare question and the exact context text as
metadata, so the Langfuse online evaluators read only what they need (langfuse_evaluators.py maps them to metadata).
Without it, the re-mapped evaluators would judge the agent's answers against an empty question and context."""
import contextlib

import graph


class _Gen:
    def update(self, **k):
        pass


def test_generate_records_question_and_context_as_metadata(monkeypatch):
    seen = {}

    @contextlib.contextmanager
    def fake_lf(name, model, input_data, prompt_name, session_id=None, user_id=None, metadata=None):
        seen.update(name=name, input=input_data, metadata=metadata)
        yield _Gen()
    monkeypatch.setattr(graph, "_lf_generation", fake_lf)
    chunks = [{"content": "nightly pg_dumpall", "source": "docs/dr.md", "chunk_index": 0}]
    out = graph.generate({"original_query": "how are backups taken?", "chunks": chunks, "session_id": "s1"})
    assert out == {"answer": "an answer"} and seen["name"] == "rag-generate"
    assert seen["metadata"] == {"query": "how are backups taken?", "context": graph._fmt_context(chunks)}
    assert seen["metadata"]["context"] in seen["input"][1][1]   # the text the model saw
