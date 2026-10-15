"""Probe a data store at the protocol level, from inside a pod (B211, 2026-10-14).

WHY: a TCP connect proves nothing from a meshed pod. The local envoy accepts the handshake whether or not a
NetworkPolicy admits the caller, then answers 503 or drops the connection. So this sends each store a real first
message and reports what came back:
    6379 -> a Redis/Valkey PING (expect +PONG)
    9092 -> a Kafka ApiVersions request (expect a framed response)
    else -> an HTTP GET / (any status line means the server answered; envoy's 503 means the policy refused)

usage (stdlib only, so it runs in any pod with a python):
    kubectl -n <ns> exec -i deploy/<caller> -c <container> -- python - <host:port>... < scripts/probe-store.py

Each line: <host>:<port> DATA <first bytes> | CLOSED-NO-DATA | REFUSED <error>, and the time taken. Read the bytes:
an envoy `503 Service Unavailable` is a refusal even though it is DATA. Runbook: docs/runbooks/write-surfaces.md.
"""
import socket
import struct
import sys
import time

TIMEOUT_S = 5


def kafka_api_versions() -> bytes:
    # request header v1: api_key 18 (ApiVersions), version 0, correlation id 1, client id "probe"
    body = struct.pack(">hhih", 18, 0, 1, 5) + b"probe"
    return struct.pack(">i", len(body)) + body


def first_message(host: str, port: str) -> bytes:
    if port == "6379":
        return b"PING\r\n"
    if port == "9092":
        return kafka_api_versions()
    return f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode()


def probe(target: str) -> str:
    host, port = target.rsplit(":", 1)
    start = time.time()
    try:
        with socket.create_connection((host, int(port)), timeout=TIMEOUT_S) as s:
            s.sendall(first_message(host, port))
            s.settimeout(TIMEOUT_S)
            data = s.recv(200)
        verdict = f"DATA {data[:40]!r}" if data else "CLOSED-NO-DATA"
    except OSError as e:
        verdict = f"REFUSED {type(e).__name__}"
    return f"{host.split('.')[0]}:{port} {verdict} {time.time() - start:.2f}s"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python - <host:port>... < scripts/probe-store.py", file=sys.stderr)
        sys.exit(2)
    for t in sys.argv[1:]:
        print(probe(t))
