# Change request: a second private host and a third private lane

**Repo:** this repository. **Area:** the LiteLLM gateway config
`nodes/mother/lab/weyland-platform/k8s/litellm/configmap.yaml`, the private-lane guard `scripts/check-private-lanes.py`,
and its tests.

**Background.** The private lanes (`wl-private-*`) are served only by self-hosted Ollama on an allowlisted LAN host
(today only rogueone, `192.168.1.230`), and the guard fails CI if a private alias could reach anything else. A new GPU
box joins the LAN at `192.168.1.231`, also running Ollama on port 11434.

**Required behaviour.**
1. `192.168.1.231` becomes an allowed private host; every other host stays disallowed.
2. Add a third private alias `wl-private-fast` (Ollama model `qwen2.5:7b-operator`) served by BOTH hosts (one
   deployment on each, `http://192.168.1.230:11434` and `http://192.168.1.231:11434`).
3. `wl-private-rag` falls back to `wl-private-fast` (a private-to-private fallback).
4. The guard keeps its contract: `python3 scripts/check-private-lanes.py <configmap.yaml>` exits 0 safe / 1 unsafe /
   2 cannot check, and still catches every unsafe case it caught before.
5. Update the guard's tests for the new host.

**Acceptance criteria.**
- [ ] The real configmap has `wl-private-fast` on both hosts and the `wl-private-rag` → `wl-private-fast` fallback, and
      the guard exits 0 on it.
- [ ] The guard accepts a private alias on `192.168.1.231` and still rejects any other host (e.g. `192.168.1.232`).
- [ ] Every unsafe case the guard caught before is still caught; its tests pass.

**Tools available on PATH:** `bats`, `python3` (with PyYAML).
