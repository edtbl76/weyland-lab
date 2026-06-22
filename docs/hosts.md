# Weyland — Host Inventory

Every machine/container in the lab. Keep updated as hosts change (see
[[feedback-keep-api-hosts-updated]]). Endpoints: [api.md](api.md).

> **IP confidence:** ✅ = confirmed this session (2026-06). ⚠ = from `weyland.md` (RE note, may be
> stale) — **verify and correct in place.**

| Host | Type | IP | Access | Role |
|---|---|---|---|---|
| **weyland** | Minisforum **MS-A2** — bare-metal Proxmox host (Ryzen 9 9955HX, 96 GB; **Proxmox VE 9.2.3**) | `192.168.1.232` ✅ | `root@weyland` | Proxmox infra: hosts the VMs + LXCs below. NOT a VM. |
| **mother** | VM (`vm-101`) on weyland — **32 GB / 8 vCPU** (raised from 16/4 on 2026-06-20) | `192.168.1.243` ✅ | `emangini@mother` | k3s AI platform (tool-server, Postgres/pgvector, Qdrant, Weaviate, Neo4j (+APOC/GDS), **NeoDash** NodePort 30088, Dagster, n8n, **weyland IDP** (Backstage, idp.weyland.lab — ⚠️ decommission in progress → Port.io), **Port.io k8s-exporter** (in-cluster agent, ns `port-k8s-exporter`), **MLflow** (mlflow.weyland.lab, B10+B16), **Uptime Kuma** (kuma.weyland.lab, 24 monitors → Telegram paging; pod uses LAN CoreDNS + mounts mkcert CA), **Unleash** (unleash.weyland.lab — OSS feature flags, B43 feature-mgmt category; stateless, meshed to STRICT Postgres, → Port `feature_flag` webhook), **SonarQube** (sonarqube.weyland.lab — B43 code-quality; meshed Postgres, + on-demand Trivy/Semgrep scan Jobs → Port), **KEDA** (ns `keda`, core + HTTP add-on — autoscaling/run-mode engine for the data mesh), **prometheus-pve-exporter** (ns `monitoring` — Proxmox metrics → Grafana #10347), **Loki + Alloy** (logs, ns `monitoring` → MinIO) + **Tempo** (traces, ns `monitoring` → MinIO) — **full LGTM in Grafana** (B48), **GlitchTip** (glitchtip.weyland.lab — B51 error tracking: web+worker+Valkey, meshed Postgres; tool-server+Dagster wired via Sentry SDK → Port `glitchtip_issue`), **Loki ruler** (LogQL log alerts → Alertmanager→Telegram), **OpenCost** (opencost.weyland.lab, ns `opencost` — B55 k8s cost allocation, custom on-prem pricing → Port Cloud Cost; reads the in-cluster Prometheus), Grafana (+ Loki/Tempo/Alertmanager datasources), MinIO, CoreDNS, Traefik, **LiteLLM model gateway** NodePort 30400, **Istio service mesh** (B8 done — istiod + Kiali (traces→Tempo); tool-server + 4 backends + Dagster meshed, PERMISSIVE mTLS, Postgres STRICT; **Jaeger retired B48**)). Hosts the **AIDLC knowledge corpus** (B37, MinIO `aidlc-kb` → RAG + Neo4j `:Entry` graph). Host tuning: `fs.inotify.max_user_instances=512` + `vm.max_map_count=524288` (`/etc/sysctl.d/`; inotify exhausted by Istio sidecars, max_map_count for SonarQube ES). qemu-guest-agent installed (clean Proxmox shutdowns). |
| **openclaw** | VM (`vm-100`) on weyland | `192.168.1.169` ✅ | `emangini@openclaw` | Agent control plane — Docker OpenClaw + Telegram bot; calls tool-server + models |
| **rogueone** | Lenovo ThinkPad P16 laptop (external; RTX 5000 Ada 16 GB) | `192.168.1.230` ✅ | `edwardmangini@rogueone` | GPU inference (vLLM) + primary dev workstation; Obsidian source notes |
| **ollama** | LXC **CT 102** on weyland (unprivileged) | `192.168.1.244` ✅ (DHCP-reserved) | `pct enter 102` (from weyland host) | Ollama CPU LLM serving — `/v1` @ :11434. [runbooks/model-serving-ollama.md](runbooks/model-serving-ollama.md) |
| **whisper** | LXC **CT 103** on weyland (unprivileged) | `192.168.1.246` ✅ (DHCP-reserved) | `pct enter 103` (from weyland host) | whisper.cpp CPU STT — shim `/v1` @ :9000, native `/inference` @ :8080. [runbooks/transcription-whisper.md](runbooks/transcription-whisper.md) |
| **hermes** | LXC **CT 104** on weyland (unprivileged) | `192.168.1.247` ✅ (DHCP-reserved) | `pct enter 104` (from weyland host) | Hermes agent platform (B2) — primary system-view/ops agent; brain → Ollama `/v1`, system view → tool-server MCP; **Telegram gateway front door live** (allowlisted DM → agent). [concepts/agent-platform-design.md](concepts/agent-platform-design.md) |

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
