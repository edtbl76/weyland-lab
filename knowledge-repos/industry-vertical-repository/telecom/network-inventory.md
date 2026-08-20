---
id: network-inventory
vertical: telecom
tags: [telecom, oss, network-inventory, topology, provisioning, service-catalog]
surfaces-at: [application-design, functional-design]
related: [telecom-overview, billing-charging, digital-channels]
---

# Network Inventory & OSS

## What It Is
Network inventory is the system of record for the physical and logical assets that make up a telecom network — cables, conduits, nodes, racks, ports, circuits, and the services provisioned on them. Operations Support Systems (OSS) build on this inventory foundation to provide network lifecycle management: activation of new services, fault detection and management, performance monitoring, and capacity planning. OSS is the operational layer that keeps the network running and enables new services to be delivered to customers.

## Why It Matters in Telecom
A telecom network is an enormous physical and logical asset — hundreds of thousands of network elements, millions of ports, and billions of service relationships. Without accurate inventory, provisioning is manual and error-prone, fault isolation takes longer, and capacity planning is guesswork. Network inventory inaccuracy is a pervasive problem in the industry — operators frequently discover significant discrepancies between their inventory records and the actual network, particularly after acquisitions or rapid build-outs.

## Key Concepts
- **Physical Network Inventory**: The catalog of physical assets — fiber cables, conduits, splice points, manholes, towers, racks, chassis, line cards, ports. Managed in a GIS-integrated inventory system with geographic representation of cable routes and node locations.
- **Logical Network Inventory**: The virtual/logical layer — circuits, VLANs, VPNs, IP addresses, wavelengths, service instances — configured on top of physical infrastructure. A single physical fiber may carry thousands of logical circuits.
- **Service Inventory**: The services activated for customers — a broadband connection, a VPN, a leased line — and their mapping to logical and physical network resources. Service inventory bridges OSS (network view) and BSS (customer view).
- **Network Topology**: The graph representation of how network elements are connected — nodes, links, and their relationships. Topology data is the foundation for path computation, fault impact analysis, and capacity planning.
- **Service Activation / Provisioning**: The automated workflow that configures network elements to deliver a new customer service. Provisioning triggers device configuration (via NETCONF, CLI, REST API), activates the logical service, and updates inventory. End-to-end provisioning automation is the goal; manual configuration is a source of errors and delays.
- **NETCONF / YANG**: The modern standards for network device configuration management. NETCONF is the protocol; YANG is the data modeling language. Replacing legacy CLI-based configuration in new network builds.
- **TMF 642 (Alarm Management) / TMF 724 (Network Activation)**: TM Forum Open API standards for OSS functions. Used for standardizing interfaces between OSS components and BSS systems.
- **Network Discovery / Reconciliation**: The process of automatically scanning the live network to discover actual device configurations and comparing against inventory records. Identifies discrepancies between what inventory says and what the network actually contains. Essential for maintaining inventory accuracy.
- **MTTR / MTTF**: Mean Time To Repair and Mean Time To Failure — key SLA metrics for network operations. OSS tools that accelerate fault isolation and restore actions directly reduce MTTR.

## Common Patterns / Gotchas
- **Network inventory is almost always inaccurate.** Disconnects between as-built records and as-deployed reality accumulate over years — particularly after network modifications, fiber cuts and repairs, and acquisitions. Any program that depends on inventory accuracy must include a reconciliation and remediation workstream.
- **Physical and logical inventory are often in separate systems.** Physical inventory may be in a GIS tool (Esri ArcGIS, Smallworld); logical inventory in a separate OSS (Netcracker, TEOCO, Nokia NSP). These systems are often poorly synchronized. Establishing a single source of truth across physical and logical is a core design challenge.
- **Provisioning automation requires network element API coverage.** Automating service activation depends on being able to configure every device in the service path programmatically. Legacy network elements with CLI-only interfaces or no API at all block automation. A device API audit is essential before scoping automation.
- **Service topology complexity grows with scale.** A single customer broadband service may involve 10–15 network elements across the access, aggregation, and core layers. Modeling the full service topology — and keeping it current as network changes occur — requires active topology management, not just a point-in-time snapshot.
- **Fault impact analysis requires accurate topology.** When a network element fails, operators need to know instantly which customer services are affected. This requires a live, accurate service topology graph and the ability to traverse it quickly. Stale or inaccurate topology data makes impact analysis unreliable.

## Industry Insight
📡 **Industry Insight — Network Inventory**: You're working on telecom OSS or network inventory. Assume inventory inaccuracy and scope a reconciliation workstream — operators consistently underestimate the gap between their inventory records and the actual network. Service activation automation is constrained by device API coverage; conduct a device API audit before scoping automation depth. Fault impact analysis requires a live, accurate service topology graph; if topology data quality is poor, impact analysis will be unreliable regardless of the tool. → `industry-vertical-repository/telecom/network-inventory.md`

## Solutions Context
**Typical engagement patterns**: Network inventory modernization, OSS consolidation, service activation automation, fault management, capacity planning platform, network topology visualization.

**Common scope anchors**: Physical/logical inventory data model, network discovery and reconciliation, service topology, NETCONF/YANG device integration, service activation workflow, TM Forum Open API alignment, fault impact analysis.

**Risk factors**: Network inventory data quality is almost always worse than expected — remediation scope is an unknown until reconciliation begins. Device API coverage gaps block automation — validate before scoping. OSS modernization programs frequently involve migrating away from deeply entrenched legacy platforms (Netcracker, Nokia NSP) with complex data models.

## Related Entries
- [Telecom Overview](_overview.md)
- [Billing & Charging](billing-charging.md)
- [Digital Channels](digital-channels.md)
