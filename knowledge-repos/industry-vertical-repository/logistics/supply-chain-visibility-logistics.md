---
id: supply-chain-visibility-logistics
vertical: logistics
tags: [logistics, visibility, tracking, control-tower, eta, exceptions]
surfaces-at: [application-design, functional-design]
related: [logistics-overview, tms, last-mile]
---

# Supply Chain Visibility (Logistics)

## What It Is
Supply chain visibility in logistics is real-time and near-real-time tracking of shipments across all modes (ocean, air, rail, truck, parcel) and all parties (carriers, forwarders, customs brokers, ports). Visibility platforms aggregate location, status, and event data from carriers, telematics devices, port systems, and customs feeds into a unified view — enabling proactive exception management, accurate ETA prediction, and customer delivery notifications.

## Why It Matters in Logistics
Blind spots in freight movement are operationally expensive. Late deliveries that are not detected early cannot be mitigated. Customs delays that are not surfaced immediately cause production or retail stockouts. Customer escalations about missing shipments are handled reactively rather than proactively. Visibility platforms shift freight management from reactive exception handling to proactive intervention — the difference between a missed delivery and a successful recovery.

## Key Concepts
- **Multimodal Tracking**: Aggregating shipment status across all transport modes — ocean (vessel AIS tracking, port events), air (flight tracking, customs scans), rail (intermodal container tracking), and road (carrier EDI, GPS telematics). Each mode has different data sources, update frequencies, and latency characteristics.
- **AIS (Automatic Identification System)**: The vessel tracking system used for ocean freight — real-time position of vessels broadcast on VHF radio. AIS data is aggregated by providers (MarineTraffic, exactEarth) and used to track ocean container shipments.
- **Milestone Events**: Discrete status updates in a shipment's journey — booking confirmed, departed origin port, transshipment, arrived destination port, cleared customs, out for delivery, delivered. Milestone tracking maps carrier-specific event codes to a standardized event taxonomy.
- **Predictive ETA**: Machine learning models that predict actual arrival times based on historical lane performance, current vessel position, port congestion, weather, and carrier patterns. More accurate than carrier-quoted ETAs, particularly for ocean and rail.
- **Port Congestion**: Delays at major ports (Los Angeles/Long Beach, Rotterdam, Shanghai) that add days or weeks to ocean transit times. Port congestion data feeds are a critical input to predictive ETA for ocean shipments.
- **Customs Visibility**: Tracking shipment status through customs clearance — CBP entry filing, examination holds, release. Customs delays are a major source of ETA variance for international shipments. Customs broker API integrations provide this data.
- **Exception Prioritization**: Ranking exceptions (late shipments, customs holds, carrier delays) by their impact on downstream operations — which exceptions will affect production schedules or customer deliveries, and which can be absorbed. Connecting visibility data to inventory and demand data enables impact-based prioritization.
- **Control Tower**: The operational hub that aggregates visibility data, surfaces exceptions, and supports response workflow. Effective control towers are exception-driven — surfacing the 5% of shipments that need attention, not the 95% that are on track.

## Common Patterns / Gotchas
- **Carrier data quality and latency vary widely.** Large carriers (FedEx, UPS, Maersk) provide real-time or near-real-time tracking via API. Regional carriers may provide only EDI milestone updates with 4–12 hour latency. Small carriers may have no digital tracking at all. Design for heterogeneous data quality from the start.
- **Event data normalization is harder than it looks.** Carrier A's "Departed" event means the truck left the terminal. Carrier B's "Departed" means the driver picked up the shipment. Normalizing carrier-specific event codes to a consistent taxonomy requires extensive mapping work that is never complete — carriers change their event codes.
- **Predictive ETA for ocean freight is particularly valuable.** Ocean transit times can vary by 5–15 days due to port congestion and vessel schedule changes. Predictive ETA that accurately forecasts arrival 2–3 weeks out enables meaningful supply chain response. Rule-based ETA (scheduled transit time) has too much error to be useful for planning.
- **Connecting visibility to business impact requires ERP/OMS integration.** A platform that shows shipment locations without context about which orders, which customers, or which production schedules they affect is a map, not a decision tool. ERP/OMS integration is what transforms tracking into actionable intelligence.
- **Real-time tracking for LTL and parcel is well-solved; ocean and rail are harder.** Parcel tracking (FedEx, UPS) is mature and reliable. LTL tracking via carrier EDI is adequate for most use cases. Ocean and rail tracking depend on port systems, vessel AIS, and intermodal container databases that have higher latency and lower coverage.

## Industry Insight
🚚 **Industry Insight — Supply Chain Visibility**: You're building a logistics visibility platform. Event data normalization across carriers is an ongoing data engineering challenge — invest in a carrier event mapping layer that can be updated without code changes as carriers modify their event codes. Connecting shipment visibility to downstream business impact (which orders, which production schedules are at risk) requires ERP/OMS integration; without it, the platform provides situational awareness without decision support. Predictive ETA is most valuable for ocean freight, where rule-based ETAs have the highest error rate — prioritize ocean lane modeling. → `industry-vertical-repository/logistics/supply-chain-visibility-logistics.md`

## Solutions Context
**Typical engagement patterns**: Multimodal visibility platform, ocean freight visibility, customs visibility, supply chain control tower, carrier performance analytics, proactive exception management.

**Common scope anchors**: Carrier and port data integration (EDI, API, AIS, customs), event normalization and milestone mapping, predictive ETA model, exception detection and prioritization, ERP/OMS integration for impact analysis, control tower UX.

**Risk factors**: Carrier integration breadth is a scope driver — each new carrier or mode adds integration work. Event normalization mapping requires domain expertise and ongoing maintenance. Predictive ETA model accuracy requires historical lane data; model quality improves over time as data accumulates.

## Related Entries
- [Logistics Overview](_overview.md)
- [TMS](tms.md)
- [Last-Mile Delivery](last-mile.md)
