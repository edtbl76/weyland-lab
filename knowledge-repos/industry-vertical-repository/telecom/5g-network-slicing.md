---
id: 5g-network-slicing
vertical: telecom
tags: [telecom, 5g, network-slicing, nfv, sdn, edge-computing, private-network]
surfaces-at: [application-design, functional-design]
related: [telecom-overview, network-inventory, billing-charging]
---

# 5G & Network Slicing

## What It Is
5G is the fifth generation of mobile network technology, introducing new radio capabilities (sub-6GHz and mmWave), a cloud-native core network architecture (5G Core / 5GC), and network slicing — the ability to create logically isolated virtual networks on shared physical infrastructure with differentiated characteristics (latency, bandwidth, reliability, security). Network slicing enables operators to offer private networks, IoT connectivity, and ultra-low-latency services to enterprises as distinct, SLA-bound products.

## Why It Matters in Telecom
5G is the primary infrastructure investment cycle for mobile operators globally. Beyond consumer mobile broadband, 5G's enterprise opportunity (private networks, IoT, edge computing, URLLC for industrial automation) is the growth thesis justifying the capital expenditure. The software that manages 5G network slices, orchestrates network functions, and enables enterprise self-service for private networks is a new and expanding software domain. For system integrators, 5G enterprise deployments are a high-growth engagement type.

## Key Concepts
- **5G Core (5GC)**: The cloud-native, service-based architecture that replaces the 4G EPC (Evolved Packet Core). Key network functions: AMF (Access and Mobility), SMF (Session Management), UPF (User Plane Function), PCF (Policy Control), UDM (Unified Data Management). Each is a microservice, deployable on Kubernetes. Vendors: Ericsson, Nokia, Samsung, Mavenir.
- **Network Slicing**: The division of a physical 5G network into multiple logically independent virtual networks, each with its own resource allocation, QoS parameters, and isolation level. Each slice has an S-NSSAI (Single Network Slice Selection Assistance Information) identifier.
- **eMBB / URLLC / mMTC**: The three 5G service categories:
  - **eMBB** (Enhanced Mobile Broadband): High throughput for consumer mobile and fixed wireless
  - **URLLC** (Ultra-Reliable Low-Latency Communications): <1ms latency for industrial automation, autonomous vehicles, remote surgery
  - **mMTC** (Massive Machine-Type Communications): Massive IoT device density at low power
- **Network Slice Management (NSSMF/NSMF)**: The software layer that creates, configures, monitors, and manages network slices. The Network Slice Management Function (NSMF) orchestrates across RAN, transport, and core subnet slice managers (NSSMFs).
- **Private 5G Network**: A dedicated 5G network deployed for a specific enterprise or campus — manufacturing plant, port, airport, stadium. May use licensed spectrum (CBRS in US), shared spectrum, or operator-leased spectrum. Provides guaranteed SLAs and security isolation.
- **MEC (Multi-Access Edge Computing)**: Computing infrastructure deployed at or near the 5G RAN, enabling ultra-low-latency applications by processing data close to the device. Critical for URLLC use cases. Applications run on MEC hosts managed by the MEC platform.
- **CBRS (Citizens Broadband Radio Service)**: A shared spectrum band (3.5GHz) in the US used for private LTE and 5G networks without requiring a traditional spectrum license. Widely used for enterprise private networks. Requires a Spectrum Access System (SAS) for interference coordination.
- **O-RAN (Open RAN)**: An industry initiative to disaggregate and open the RAN (Radio Access Network) — separating radio unit (RU), distributed unit (DU), and centralized unit (CU) from different vendors. Enables multi-vendor RAN deployments and software-driven network optimization.

## Common Patterns / Gotchas
- **Network slicing management is still maturing.** End-to-end slice orchestration (RAN + transport + core) is technically complex and the vendor tooling is less mature than the standards suggest. Implementations that span multiple vendors' equipment face interoperability challenges not resolved by standards alone.
- **Private 5G deployment requires domain knowledge.** A private network for a manufacturing plant requires understanding of the plant's operational requirements, RF planning for the facility, integration with OT systems, and 5G core configuration. It is not a standard IT project.
- **URLLC latency guarantees are hard to achieve end-to-end.** <1ms latency is achievable at the radio layer but requires MEC deployment, optimized application placement, and careful network configuration end-to-end. Applications claiming URLLC benefits without MEC are overstating 5G capabilities.
- **Billing for network slices is a BSS gap.** Traditional telecom billing is not designed for slice-based charging — SLA-bound, enterprise-contracted, usage-measured slices. 5G monetization requires BSS evolution alongside network evolution.
- **Security isolation between slices requires validation.** Network slicing is logically isolated, not physically isolated. Security validation of slice isolation — ensuring one slice cannot observe or interfere with another — is a requirement for enterprise customers in sensitive industries.

## Industry Insight
📡 **Industry Insight — 5G & Network Slicing**: You're working on 5G or private network deployments. End-to-end slice orchestration across RAN, transport, and core is the hardest technical problem in 5G — multi-vendor interoperability gaps are real and not fully resolved by standards. Private 5G for enterprise (manufacturing, logistics, ports) requires OT integration expertise alongside network expertise; treat it as a cross-domain engagement. URLLC latency guarantees require MEC deployment and application co-location — validate the full latency budget before committing to URLLC SLAs. → `industry-vertical-repository/telecom/5g-network-slicing.md`

## Solutions Context
**Typical engagement patterns**: Private 5G network deployment (manufacturing, campus, port), network slice management platform, 5G core implementation, MEC application platform, O-RAN integration, 5G enterprise use case enablement (IoT, URLLC).

**Common scope anchors**: 5G core network functions (5GC), network slice lifecycle management (NSMF/NSSMF), private network deployment and integration, MEC platform, CBRS SAS integration, BSS evolution for slice-based charging.

**Risk factors**: Multi-vendor interoperability gaps in slice orchestration are the primary technical risk. RF planning for private network coverage is a specialized workstream. OT integration for industrial private networks requires domain expertise beyond standard telecom engineering.

## Related Entries
- [Telecom Overview](_overview.md)
- [Network Inventory](network-inventory.md)
- [Billing & Charging](billing-charging.md)
