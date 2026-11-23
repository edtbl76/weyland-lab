# Flow: Ollama truncation watch (B255)

Ollama cuts a prompt longer than the model's window without an error: the request succeeds, the closing log line even
reads `truncated = 0`, and only a `WARN ... truncating input prompt limit=N prompt=M` line in its journal says what was
lost. The watch reads those lines every 15 minutes and pushes the result to Uptime Kuma, which alerts on `down` and on a
missed heartbeat (the watch itself dead). Runbook: [model-serving-ollama.md § Truncation watch](../runbooks/model-serving-ollama.md);
script `scripts/ollama_truncation_watch.py`; units `nodes/rogueone/systemd/ollama-truncation-watch.{service,timer}`.

```mermaid
sequenceDiagram
    participant Caller as Caller (tool-server, weyland-agent, LiteLLM judge, Open WebUI)
    participant OLL as Ollama (rogueone)
    participant J as journald (ollama unit)
    participant T as ollama-truncation-watch.timer (user, every 15 min)
    participant W as ollama_truncation_watch.py
    participant K as Uptime Kuma (push monitor ollama-truncation, heartbeat 1200 s)
    participant N as Telegram (Kuma notification)
    Caller->>OLL: chat request (prompt larger than the model's num_ctx)
    OLL->>J: WARN truncating input prompt limit=N prompt=M
    OLL-->>Caller: 200 answer, from the cut prompt (no error)
    T->>W: run
    W->>J: journalctl -u ollama --since 16 min ago
    J-->>W: WARN lines (or none)
    alt one or more truncations
        W->>K: push status=down, worst prompt sent and kept
        K->>N: alert
    else none
        W->>K: push status=up
    end
    Note over K: no push within 1200 s => down (the watch stopped)
```
