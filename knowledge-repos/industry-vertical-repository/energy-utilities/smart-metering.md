---
id: smart-metering
vertical: energy-utilities
tags: [energy, ami, smart-meter, mdm, head-end, billing]
surfaces-at: [application-design, functional-design]
related: [energy-utilities-overview, grid-management, renewable-integration, time-series-databases]
---

# Smart Metering (AMI)

## What It Is
Advanced Metering Infrastructure (AMI) is the system of smart meters, communication networks, head-end systems, and meter data management platforms that replace manual meter reading with automated, two-way communication between the utility and customer premises. AMI is the primary data source for granular customer energy consumption and the foundational platform for demand response, dynamic pricing, and grid edge visibility.

## Why It Matters in Energy & Utilities
AMI deployments are massive capital programs — millions of endpoints, complex communication networks, and deep integration with billing and grid operations. The data volumes are substantial: a utility with 1M smart meters collecting 15-minute interval data generates over 96M meter reads per day. Data quality, latency, and completeness directly affect billing accuracy, regulatory reporting, and grid analytics. Utilities have significant regulatory obligations around AMI data — both for billing accuracy and customer data privacy.

## Key Concepts
- **Smart Meter / AMI Endpoint**: The customer-premises device that measures consumption, communicates with the head-end, and may support two-way commands (disconnect/reconnect, demand response signals). Landis+Gyr, Itron, and Honeywell (Elster) dominate the meter market.
- **HES (Head-End System)**: The software platform that communicates with meters over the AMI network. Manages meter configuration, firmware updates, on-demand reads, and data collection. Typically vendor-proprietary.
- **MDM (Meter Data Management)**: Receives raw interval data from the HES, performs validation, estimation, and editing (VEE), stores the time-series data, and feeds downstream systems (billing, analytics, grid ops).
- **VEE (Validation, Estimation, and Editing)**: The data quality process that detects missing or anomalous meter reads, estimates replacements using statistical models, and flags exceptions for manual review. VEE quality directly determines billing accuracy.
- **Interval Data**: The time-series consumption readings from smart meters — typically 15-minute or hourly intervals. Distinct from the scalar monthly kWh used for legacy billing.
- **Demand Response (DR)**: Programs that incentivize or direct customers to reduce consumption during grid stress events. AMI enables direct load control (send a signal to the thermostat or water heater) and automated DR dispatch.
- **NAN / WAN (Neighborhood/Wide Area Network)**: The communication infrastructure connecting meters to the head-end. RF mesh (Itron OpenWay, Landis+Gyr Gridstream), cellular (4G/5G), or PLC (power line communication) — each with different coverage, latency, and cost profiles.
- **Green Button / ESPI**: The standard API for sharing customer energy usage data. Green Button Connect enables third-party apps to access a customer's interval data with consent.

## Common Patterns / Gotchas
- **Data volumes are much larger than expected.** 15-minute interval data for millions of meters is orders of magnitude more data than scalar monthly reads. Downstream systems (MDM, billing, analytics) must be designed for time-series data at scale — relational databases with naive schemas will not perform.
- **VEE is complex and business-critical.** The rules for detecting bad reads, estimating replacements, and routing exceptions are extensive and utility-specific. VEE logic is often embedded in legacy MDM vendors (Itron MV90, Oracle MDM) and is painful to migrate.
- **HES integration is constrained by vendor APIs.** Meter vendors do not publish open APIs. HES integration typically happens via vendor SDK, proprietary web services, or file exports. Validate API capabilities before scoping.
- **Communication network gaps mean not all meters communicate reliably.** Design for expected non-communication rates (typically 1–5% of endpoints on any given read cycle). Missing reads must be estimated, not assumed to be zero consumption.
- **Billing transformation is a separate workstream.** AMI enables new rate structures (time-of-use, demand charges) but moving a utility's billing system to consume interval data rather than scalar reads is a significant program in its own right.
- **Customer data privacy regulations apply.** Granular interval data reveals household behavioral patterns (when people are home, when they leave). California (CPUC Rule 25), and other state PUC rules govern how utilities store and share this data.

## Industry Insight
⚡ **Industry Insight — Smart Metering**: You're building or integrating with AMI/MDM systems. Design for time-series data at scale from the start — interval data volumes make naive relational schemas unworkable at utility scale. VEE rules are the heart of MDM logic and are always more complex than they first appear; treat VEE rule design as a dedicated workstream with business stakeholders, not a technical afterthought. Expect communication gaps in the AMI network and design for missing reads explicitly. → `industry-vertical-repository/energy-utilities/smart-metering.md`

## Solutions Context
**Typical engagement patterns**: MDM implementation or modernization, AMI data pipeline and analytics, demand response platform, Green Button / customer data access, billing transformation for interval-based rates.

**Common scope anchors**: HES integration, VEE rule design and implementation, interval data storage and pipeline, billing system integration, demand response dispatch, customer portal energy data access.

**Risk factors**: HES vendor API constraints are frequently more limiting than documented. VEE rule complexity is consistently underestimated. Billing system changes to support interval-based rates often expand scope significantly.

## Related Entries
- [Energy & Utilities Overview](_overview.md)
- [Grid Management](grid-management.md)
- [Time Series Databases](../../engineering-knowledge-repository/time-series-databases.md) — purpose-built storage for the interval data volumes AMI/MDM systems generate
