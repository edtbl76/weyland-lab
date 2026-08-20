---
id: tms
vertical: logistics
tags: [logistics, tms, transportation, freight, carrier, load-planning, routing]
surfaces-at: [application-design, functional-design]
related: [logistics-overview, last-mile, supply-chain-visibility-logistics]
---

# Transportation Management System (TMS)

## What It Is
A Transportation Management System (TMS) is the operational platform for planning, executing, and optimizing the movement of freight — from load tendering and carrier selection through shipment execution, tracking, and freight audit and payment. TMS serves shippers (manufacturers, retailers, distributors) who need to manage outbound and inbound freight, and 3PLs (third-party logistics providers) who manage freight on behalf of multiple shippers. Major platforms: Oracle TMS, SAP TM, MercuryGate, BluJay, project44.

## Why It Matters in Logistics
Freight transportation is one of the largest cost lines for any company that moves physical goods. Transportation costs typically represent 5–10% of revenue for manufacturers and retailers. A TMS that optimizes carrier selection, consolidates shipments, and reduces empty miles directly reduces this cost. In an environment of carrier capacity volatility (post-COVID spot market swings, driver shortages), automated carrier selection and multi-modal optimization provide resilience as well as cost savings.

## Key Concepts
- **Load Planning / Load Optimization**: Determining how to consolidate orders into shipments and assign them to transportation modes (truckload, LTL, parcel, intermodal) to minimize cost while meeting delivery commitments. Cube and weight optimization, multi-stop routing, and mode selection are core functions.
- **Carrier Selection / Rate Shopping**: Selecting the optimal carrier for each shipment based on contracted rates, service level, capacity availability, and lane performance history. Rate shopping across the carrier base requires current rate tables and real-time capacity signals.
- **Load Tendering**: The process of offering a load to a carrier and managing acceptance or rejection. Primary tender (to contracted carrier) → secondary tender (to backup carrier) → spot market (open auction) is the standard fallback sequence. EDI 204 is the standard tender transaction.
- **Freight Audit and Payment (FAP)**: Verifying carrier invoices against contracted rates and shipment records, disputing discrepancies, and processing payment. Freight audit is a significant cost recovery function — carrier overbilling is common and often catches 2–5% of freight spend.
- **Mode Selection**: Choosing between truckload (FTL), less-than-truckload (LTL), parcel (FedEx/UPS/USPS), intermodal (rail + truck), air freight, or ocean freight based on cost, transit time, and shipment characteristics. Multi-modal optimization is a core TMS capability for complex networks.
- **Continuous Move / Network Optimization**: Advanced TMS capability that chains loads across multiple shippers or legs to keep trucks moving and reduce empty miles. Network optimization considers all loads across the shipper's network simultaneously rather than optimizing each load independently.
- **Private Fleet Management**: For shippers that operate their own truck fleets, TMS includes driver dispatch, hours-of-service (HOS) compliance, and vehicle routing for their own assets alongside carrier-managed freight.
- **Inbound Transportation Management**: Coordinating freight from suppliers to the shipper's facilities — often under the shipper's control (Free On Board origin) to optimize carrier selection and reduce inbound freight costs.

## Common Patterns / Gotchas
- **Carrier rate tables go stale quickly.** Contracted rates change with annual negotiations, fuel surcharges update weekly, and accessorial charges change with carrier policy. A TMS with outdated rate tables produces incorrect cost estimates and wrong carrier selections. Rate table maintenance is an ongoing operational obligation.
- **Tender acceptance rates determine optimization value.** A TMS that tenders optimally but has low carrier acceptance rates (carriers reject loads) falls back to spot market, erasing optimization savings. Carrier relationship management and tender process design are operational complements to the technology.
- **Integration with WMS and ERP is critical.** TMS receives shipment requirements from the order management/WMS layer and returns shipment confirmations and costs to ERP for financial accrual. These integrations are on the critical path and must be designed for volume and latency requirements.
- **Freight audit requires current rate tables and contract terms.** Automated freight audit depends on having the current carrier contract terms in the system — rates, accessorials, fuel schedules, minimum charges. Keeping contract data current is an ongoing data governance function.
- **Exceptions dominate operational effort.** Load planning algorithms handle the standard case. Carrier rejections, shipment exceptions, late pickups, damaged freight, and appointment misses require exception management workflows that consume most of the operations team's time. Design exception management as a first-class capability.

## Industry Insight
🚚 **Industry Insight — TMS**: You're designing a transportation management system. Carrier rate table maintenance is an ongoing operational obligation that degrades TMS value if neglected — design rate update workflows (EDI 259/ANSI rate upload, API feeds) and a table freshness monitoring capability from the start. Exception management workflow (carrier rejections, late shipments, damage claims) consumes the majority of TMS users' time; design it as carefully as the load planning algorithm. Freight audit automation requires current contract terms in the system — establish a contract data governance process alongside the technical implementation. → `industry-vertical-repository/logistics/tms.md`

## Solutions Context
**Typical engagement patterns**: TMS implementation or modernization, carrier integration layer, freight audit automation, multi-modal optimization, 3PL platform, inbound transportation program.

**Common scope anchors**: Load planning and optimization, carrier rate management, tender workflow (EDI 204/214), shipment tracking integration, WMS/ERP integration, freight audit and payment, exception management workflow.

**Risk factors**: Carrier integration breadth (EDI, API, portal) is a significant scope driver. Rate table maintenance is an ongoing operational cost that must be designed into the operating model. WMS and ERP integration complexity is consistently underestimated.

## Related Entries
- [Logistics Overview](_overview.md)
- [Last-Mile Delivery](last-mile.md)
