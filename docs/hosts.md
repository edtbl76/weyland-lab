# Weyland — Host Inventory

Every machine/container in the lab. Keep updated as hosts change (see
[[feedback-keep-api-hosts-updated]]). Endpoints: [api.md](api.md).

> **IP confidence:** ✅ = confirmed this session (2026-06). ⚠ = from `weyland.md` (RE note, may be
> stale) — **verify and correct in place.**

| Host | Type | IP | Access | Role |
|---|---|---|---|---|
| **weyland** | Minisforum **MS-A2** — bare-metal Proxmox host (Ryzen 9 9955HX, 96 GB) | `192.168.1.232` ✅ | `root@weyland` | Proxmox infra: hosts the VMs + LXCs below. NOT a VM. |
| **mother** | VM (`vm-101`) on weyland | `192.168.1.243` ✅ | `emangini@mother` | k3s AI platform (tool-server, Postgres/pgvector, Qdrant, Weaviate, Neo4j, Dagster, n8n, Grafana, MinIO, CoreDNS, Traefik) |
| **openclaw** | VM (`vm-100`) on weyland | `192.168.1.169` ✅ | `emangini@openclaw` | Agent control plane — Docker OpenClaw + Telegram bot; calls tool-server + models |
| **rogueone** | Lenovo ThinkPad P16 laptop (external; RTX 5000 Ada 16 GB) | `192.168.1.230` ✅ | `edwardmangini@rogueone` | GPU inference (vLLM) + primary dev workstation; Obsidian source notes |
| **ollama** | LXC **CT 102** on weyland (unprivileged) | `192.168.1.244` ✅ (DHCP-reserved) | `pct enter 102` (from weyland host) | Ollama CPU LLM serving — `/v1` @ :11434. [b7-ollama-runbook.md](b7-ollama-runbook.md) |
| **whisper** | LXC **CT 103** on weyland (unprivileged) | `192.168.1.246` ✅ (DHCP-reserved) | `pct enter 103` (from weyland host) | whisper.cpp CPU STT — shim `/v1` @ :9000, native `/inference` @ :8080. [b11-whisper-runbook.md](b11-whisper-runbook.md) |
| **hermes** | LXC **CT 104** on weyland (unprivileged) | `192.168.1.247` ✅ (DHCP-reserved) | `pct enter 104` (from weyland host) | Hermes agent platform (B2) — primary system-view/ops agent; brain → Ollama `/v1`, system view → tool-server MCP. [b2-agent-platform-design.md](b2-agent-platform-design.md) |

## Access notes
- **Per-host SSH users differ:** `root@weyland`, `emangini@mother`, `emangini@openclaw`,
  `edwardmangini@rogueone`. Always use **hostnames**, not IPs, in commands (except standalone CTs,
  which aren't in DNS — use their reserved IPs or the new `*.weyland.lab` names).
- **LXC containers have no direct login** — reach them through the weyland host: `ssh root@weyland`
  → `pct enter <ctid>`. Push files in with `pct push <ctid> <host-file> <ct-path>`.
- **DNS:** `*.weyland.lab` resolves via CoreDNS on `mother:53` (k3s/Traefik UIs → mother;
  `ollama`/`whisper` → their CT IPs). rogueone also has `/etc/hosts` entries.

## Container/VM map on weyland (Proxmox)
```text
weyland (MS-A2, Proxmox)
├── vm-100  openclaw   (agent control plane)
├── vm-101  mother     (k3s platform)
├── ct-102  ollama     (LLM serving)
├── ct-103  whisper    (STT serving)
└── ct-104  hermes     (agent platform — B2)
```
