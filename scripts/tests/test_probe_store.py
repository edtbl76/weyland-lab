"""scripts/probe-store.py (B211): the store probe must tell an answer from a refusal.

Its job is to make a NetworkPolicy refusal visible from a meshed pod, where envoy accepts every TCP handshake. So the
verdicts it can't get wrong are: a real answer is DATA, a connection that closes without a byte is CLOSED-NO-DATA (not
an answer), and a connection that can't be made is REFUSED. Each runs against a throwaway local socket server.
"""
import importlib.util
import socket
import struct
import threading
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "probe_store", Path(__file__).resolve().parents[1] / "probe-store.py")
probe_store = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe_store)


def _serve_once(reply):
    """A one-connection server that reads the client's first message, then sends `reply` (or nothing) and closes."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = {}

    def run():
        conn, _ = srv.accept()
        with conn:
            got["msg"] = conn.recv(200)
            if reply:
                conn.sendall(reply)
        srv.close()

    threading.Thread(target=run, daemon=True).start()
    return srv.getsockname()[1], got


def test_an_answer_is_data_and_names_the_bytes():
    port, got = _serve_once(b"+PONG\r\n")
    out = probe_store.probe(f"127.0.0.1:{port}")
    assert " DATA b'+PONG" in out
    assert got["msg"].startswith(b"GET / HTTP/1.1")   # not 6379/9092, so an HTTP GET


def test_a_silent_close_is_not_an_answer():
    port, _ = _serve_once(b"")
    assert " CLOSED-NO-DATA " in probe_store.probe(f"127.0.0.1:{port}")


def test_nothing_listening_is_refused():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()   # the port is now free and nothing listens on it
    assert " REFUSED ConnectionRefusedError " in probe_store.probe(f"127.0.0.1:{port}")


def test_the_first_message_matches_the_protocol():
    assert probe_store.first_message("valkey", "6379") == b"PING\r\n"
    msg = probe_store.first_message("redpanda", "9092")
    (length,) = struct.unpack(">i", msg[:4])
    assert length == len(msg) - 4                                # a correctly framed Kafka request
    assert struct.unpack(">hh", msg[4:8]) == (18, 0)              # ApiVersions v0
