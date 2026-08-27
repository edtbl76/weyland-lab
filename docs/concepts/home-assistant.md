# Home Assistant — design notes (B20, parked → Maturity)

**Status: PARKED (Maturity).** Design captured; not built yet. **Decoupled from B66/agents** — HA delivers value on
its own (a unified control layer over the consumer/physical environment). The guarded *agent act-tool* is a separate,
optional follow-on layer, NOT a dependency.

> **Moved into `docs/` on 2026-08-27.** This lived at `aidlc-docs/home-assistant.md`, which is **gitignored**
> (`.gitignore:102` → `/aidlc-docs/`) and therefore untracked — the specs, integration map and sequence below existed
> on exactly one disk while B20's backlog entry cited them as its source of truth. Same class of risk as the live-only
> Port config that [B137] existed to fix, just smaller. `docs/concepts/` is the committed home.

## Goal
Home Assistant as the lab's home-automation hub — one pane over the existing consumer ecosystems (**Nest**, **Google
Home / Cast**, **Amazon Alexa / Echo**, **Smart TVs**) to control lights, sensors, thermostats, speakers, and TVs.

## Deployment decision — Proxmox **HAOS VM** (not a k8s container)
The target devices are **cloud (Nest) + local-network (Cast / TVs / Echo)** — **no zigbee/zwave USB dongle** anywhere,
so USB passthrough (the usual VM driver) doesn't apply. BUT the local integrations rely on **mDNS/SSDP discovery on the
LAN**, which a network-isolated k8s pod can't see (discovery silently fails → hand-entered IPs, some integrations won't
accept that). HA's own docs push host networking for this. So: a **HAOS VM bridged to the LAN** discovers everything
natively and is the officially-supported topology. (A k8s container *can* work with `hostNetwork: true` + manual IPs,
but fights the mesh and HA's recommendations.)

### VM specs (on the weyland Proxmox host — Ryzen 9 9955HX / 96 GB, ample headroom)
| Resource | Spec | Why |
|---|---|---|
| vCPU | 2, type `host` | HAOS min 2; `cpu=host` avoids the AVX/SIGILL trap the lab VMs hit (see the `proxmox-vm-cpu-host-avx` note) |
| RAM | 4 GB | 2 GB floor; 4 GB gives headroom for HACS + Alexa Media Player + the recorder DB |
| Disk | 32 GB | HAOS default; ample (no camera NVR planned — bump only if Frigate is added later) |
| Firmware / machine | **UEFI (OVMF)** + **q35** | HAOS *requires* UEFI boot — the #1 gotcha |
| NIC | **bridged `vmbr0`** (LAN) | needs a real LAN IP so mDNS/SSDP discovery works |

HAOS is a **prebuilt appliance** — no OS install; the Supervisor manages the OS + add-ons + updates. Create via the
community Proxmox helper script (automates VM + qcow2 import + UEFI) or manually (`qm importdisk` the latest
`haos_ova-*.qcow2` into a q35/OVMF VM). Hostname: `ha.weyland.lab` (+ /etc/hosts + LAN DNS).

**Note on host choice:** this lands on **weyland** (the bare-metal Proxmox box), not mother — so it costs nothing on
the capacity-contended k8s node, and it is unaffected by the rogueone hardware situation ([B150]).

## Integration map (what connects, and the catch)
- **Nest** — Google **Nest** integration (SDM API). Cloud; needs a Google Cloud project/OAuth + a one-time **$5 Device
  Access fee**. Thermostats + sensors solid; Nest *cameras* have streaming limits.
- **Google Home / Nest speakers / Chromecast / Cast TVs** — local **Cast** integration (mDNS): cast media + TTS +
  playback control ("announce on the kitchen speaker").
- **Amazon Alexa / Echo** — **Alexa Media Player** (HACS, unofficial API via your Amazon login): Echos as media players
  + TTS "announce." WARNING: the *inbound* "Alexa, turn on X → HA" Smart Home Skill needs a **public endpoint or Nabu
  Casa** — this lab is LAN-only, so it is **out of scope** (and unneeded: the operator drives HA, not Alexa).
- **Smart TVs** — local, brand-specific: LG (webOS), Samsung (SmartThings/samsungtv), Roku, Apple TV (pyatv),
  Android/Google TV. Power / volume / app / input over the LAN.

## Cost
$0 except the **optional one-time $5** Nest Device Access. **No Nabu Casa** subscription needed for this scope.

## Sequence (when un-parked)
1. Create the HAOS VM (specs above) → LAN IP → `http://<ip>:8123` onboarding.
2. Add integrations (Nest cloud OAuth; Cast/TVs/Echo local discovery).
3. Mint a **long-lived access token**.
4. **(Optional, later — the agent layer):** a guarded operator act-tool — `operator → HA REST API (token) → call a
   service`, riding the B14/B17 guard/act confirm rails + enforcing `policy.gate` (physical side effects → not
   read-only). This is the ONLY agent-dependent piece, and it's a follow-on, not part of the core standalone HA.
