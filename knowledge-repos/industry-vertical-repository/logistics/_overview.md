---
id: logistics-overview
vertical: logistics
tags: [logistics, supply-chain, tms, wms, tracking, overview]
surfaces-at: [requirements-analysis, application-design]
related: [eventual-consistency]
---

# Logistics — Industry Overview

## What It Is
Logistics technology covers the systems that plan, execute, and track the movement of goods — from supplier to warehouse to last-mile delivery. Engagements may sit inside a shipper (retailer, manufacturer), a carrier (trucking, parcel, freight), or a broker/platform connecting the two.

## Why It Matters
Logistics is operationally complex, data-intensive, and increasingly real-time. Supply chain disruptions have elevated the strategic importance of visibility and resilience. The domain is rich with legacy systems and integration complexity — EDI is still the dominant messaging standard despite being decades old.

## Key Concepts
- **TMS (Transportation Management System)**: Manages freight planning, carrier selection, load tendering, and shipment execution. The operational hub for shippers.
- **WMS (Warehouse Management System)**: Manages inbound/outbound freight, inventory, and labor within a facility.
- **Load / Shipment / Leg**: A load is a unit of freight. A shipment is a customer's order in transit. A leg is a single segment of movement (origin → destination). Multi-leg shipments are common in intermodal freight.
- **EDI (Electronic Data Interchange)**: The dominant B2B messaging standard in logistics. X12 204 (load tender), 214 (shipment status), 210 (freight invoice) are common transaction sets. New integrations increasingly use REST/JSON APIs, but EDI is unavoidable in established carrier relationships.
- **Track and Trace**: Real-time or near-real-time visibility into shipment location and status. Data comes from carrier APIs, ELD devices, GPS pings, and manual check calls.
- **Dwell / Transit Time**: How long freight sits or moves. Key operational KPIs for both shippers and carriers.
- **Last-Mile Delivery**: The final leg from distribution center to end customer. The most expensive per-mile segment and the most visible to consumers.

## Common System Archetypes
- **Freight Marketplace / Brokerage Platform**: Connects shippers with available carriers; includes load board, tendering, and tracking
- **Visibility Platform**: Aggregates shipment status across carriers and modes into a single view
- **Route Optimization Engine**: Computes optimal delivery routes for last-mile fleets
- **Carrier Integration Layer**: Normalizes connectivity across hundreds of carrier APIs and EDI connections

## Common Integration Points
- **Carrier APIs**: FedEx, UPS, USPS, LTL carriers — shipment creation, tracking, label generation
- **EDI X12**: Load tender (204), shipment status (214), freight invoice (210), advance ship notice (856)
- **ELD (Electronic Logging Device)**: Telematics data from truck cab devices — location, hours of service
- **ERP / OMS**: Source of order and inventory data driving shipment requirements

## Industry Insight
🚚 **Industry Insight — Logistics**: You're working in logistics. EDI is unavoidable — even greenfield platforms must connect to established carrier relationships that speak X12. Plan for a carrier integration layer that normalizes EDI and REST APIs behind a common interface; building point-to-point carrier integrations does not scale. Track-and-trace data is high-volume, low-latency, and often unreliable — design for eventual consistency and missing updates, not guaranteed real-time accuracy. → `industry-vertical-repository/logistics/_overview.md`

## Solutions Context
**Typical engagement patterns**: Freight visibility platform builds, TMS modernization, carrier integration layer, last-mile route optimization, supply chain analytics.

**Common scope anchors**: EDI integration infrastructure, carrier API normalization layer, shipment state machine, track-and-trace data pipeline, route optimization, ERP/OMS integration.

**Risk factors**: Carrier integration scope grows quickly — each carrier has its own API quirks and EDI dialects. EDI infrastructure (VANs, AS2, SFTP) adds operational overhead. Real-time visibility data is high-volume; data pipeline and storage costs should be estimated explicitly.

## Related Entries
- [Eventual Consistency](../../engineering-knowledge-repository/eventual-consistency.md) — track-and-trace data is high-volume and unreliable; design for eventual consistency and missing updates, not guaranteed real-time accuracy

**Estimation notes**: Carrier integration should be scoped per carrier, not as a single line item. EDI setup (VAN configuration, trading partner agreements) has lead times outside the team's control. Route optimization engines require historical delivery data and domain expertise; off-the-shelf solvers (Google OR-Tools, Vroom) can reduce build scope significantly.
