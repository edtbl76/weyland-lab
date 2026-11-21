"""ollama_truncation_watch.py (B255, 2026-11-20): Ollama cuts an over-long prompt without an error, and the only reliable
trace is its WARN line `truncating input prompt limit=N prompt=M ...` (the request's closing `truncated = 0` is not
reliable: it said 0 on a request that had just lost 2,593 of 4,643 tokens). The watch reads Ollama's journal for the
last window and pushes the verdict to an Uptime Kuma push monitor. Rules under test: any truncation is DOWN with the
count and the worst cut named; a clean window is UP; an unreadable journal is DOWN, never UP (fail closed).
"""
import importlib.util
import pathlib

_PATH = pathlib.Path(__file__).resolve().parents[1] / "ollama_truncation_watch.py"
_spec = importlib.util.spec_from_file_location("ollama_truncation_watch", _PATH)
w = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w)

CUT = ('time=2026-11-20T21:59:28.581-05:00 level=WARN source=llama_server.go:314 msg="truncating input prompt" '
       'limit=2050 prompt=4643 keep=4 new=2050')
CUT2 = ('time=2026-11-20T22:02:59.475-05:00 level=WARN source=llama_server.go:314 msg="truncating input prompt" '
        'limit=4098 prompt=10596 keep=4 new=4098')
NOISE = "slot   release: id  0 | task 0 | stop processing: n_tokens = 3375, truncated = 0"


def test_parse_finds_every_truncation_with_its_numbers():
    cuts = w.parse("\n".join([NOISE, CUT, NOISE, CUT2]))
    assert cuts == [{"prompt": 4643, "kept": 2050}, {"prompt": 10596, "kept": 4098}]


def test_the_closing_truncated_flag_is_not_counted():
    assert w.parse(NOISE + "\n" + NOISE.replace("truncated = 0", "truncated = 1")) == []


def test_a_clean_window_is_up():
    status, msg = w.verdict([], window_min=16)
    assert status == "up" and "no prompt truncated" in msg


def test_any_truncation_is_down_naming_count_and_worst_cut():
    status, msg = w.verdict(w.parse(CUT + "\n" + CUT2), window_min=16)
    assert status == "down"
    assert "2 prompt(s) truncated" in msg and "10596" in msg and "4098" in msg


def test_an_unreadable_journal_is_down_not_up(monkeypatch):
    def boom(*a, **k):
        raise OSError("journal not readable")
    monkeypatch.setattr(w, "read_journal", boom)
    status, msg = w.check(window_min=16)
    assert status == "down" and "could not read" in msg


def test_check_reads_the_window_and_decides(monkeypatch):
    seen = {}

    def fake(window_min):
        seen["w"] = window_min
        return CUT
    monkeypatch.setattr(w, "read_journal", fake)
    assert w.check(window_min=16)[0] == "down" and seen["w"] == 16
