---
id: iiot-predictive-maintenance
vertical: manufacturing
tags: [manufacturing, iiot, predictive-maintenance, sensors, ml, opc-ua, historian]
surfaces-at: [application-design, functional-design]
related: [manufacturing-overview, mes, digital-twin, time-series-databases]
---

# IIoT & Predictive Maintenance

## What It Is
Industrial IoT (IIoT) in manufacturing refers to the collection, transmission, and analysis of data from shop floor machines, sensors, and equipment. Predictive maintenance (PdM) is one of the primary use cases: using machine sensor data and ML models to predict equipment failures before they occur, enabling maintenance to be scheduled at the optimal time rather than reacting to breakdowns (reactive) or following fixed schedules (preventive).

## Why It Matters in Manufacturing
Unplanned downtime is one of the highest-cost events in manufacturing — a production line stoppage can cost tens of thousands of dollars per hour. Predictive maintenance directly attacks this cost by giving maintenance teams advance warning of failures. Beyond PdM, IIoT data enables process optimization, quality analytics, energy management, and digital twin synchronization. It is the foundational data layer for the Industry 4.0 vision.

## Key Concepts
- **OPC-UA (OPC Unified Architecture)**: The modern standard for machine data communication. Provides a machine-agnostic, secure, and structured data model for connecting PLCs, CNCs, robots, and other devices to higher-level systems. Every new IIoT integration should default to OPC-UA where supported.
- **SCADA Historian**: A time-series database optimized for high-frequency operational data — OSIsoft PI (now AVEVA PI), Ignition Historian, GE Proficy Historian. The historian is the standard "data lake" for OT data and the primary integration point between OT and IT analytics.
- **Edge Computing**: Processing data at or near the machine rather than transmitting raw data to a central cloud. Reduces latency, bandwidth, and cloud costs. Required for closed-loop control and near-real-time anomaly detection. Common edge platforms: AWS Greengrass, Azure IoT Edge, Siemens Industrial Edge.
- **Digital Signal Processing**: Vibration, current, temperature, and pressure signals from machines often require signal processing (FFT, filtering, feature extraction) before they are useful for ML models. This is typically done at the edge or in a feature pipeline.
- **Condition Monitoring**: Continuously monitoring the condition of equipment through sensor data — vibration, temperature, current, oil analysis, acoustic emission. The data foundation for predictive maintenance.
- **Remaining Useful Life (RUL)**: An ML model output that predicts how much operating life remains for a component before failure. More sophisticated than binary fault/no-fault classification.
- **Anomaly Detection**: Identifying deviations from normal operating patterns that may indicate incipient failure. Can be rule-based (threshold alerts) or ML-based (unsupervised anomaly models).
- **CMMS (Computerized Maintenance Management System)**: The system of record for maintenance work orders, asset history, and spare parts. PdM outputs must integrate with CMMS to trigger work orders. SAP PM, IBM Maximo, and Infor EAM are common.

## Common Patterns / Gotchas
- **Data availability is the first constraint, not the algorithm.** The most common IIoT project failure is discovering that the machines targeted for PdM don't have the sensors required for the use case. Sensor audit and retrofitting is frequently in scope and frequently underestimated.
- **OPC-UA availability varies.** Older machines may only support proprietary protocols (Fanuc FOCAS, Mitsubishi MC Protocol, Siemens S7) or have no data interface at all. Protocol translation gateways add cost and complexity.
- **Historian data quality degrades over time.** Missed samples, timestamp drift, and tag configuration changes create data quality issues that compound over years. Any ML pipeline must include data quality validation.
- **Failure data is scarce.** ML models for predictive maintenance require examples of failures to learn from. For low-frequency failure modes, there may be insufficient historical data for supervised learning. Anomaly detection or physics-based models may be more appropriate.
- **Alert fatigue is the adoption killer.** An alert system that fires too often is worse than no alert system — operators learn to ignore it. Precision matters more than recall in most PdM deployments.
- **Integration with CMMS closes the loop.** An alert without a work order is just noise. The integration between PdM alerts and CMMS work order creation determines whether PdM actually changes maintenance behavior.

## Industry Insight
🏭 **Industry Insight — IIoT & Predictive Maintenance**: You're building an IIoT or predictive maintenance platform. Before designing the ML pipeline or analytics architecture, conduct a sensor and connectivity audit — data availability from target machines is the most common reason IIoT projects fail to deliver. Design the OPC-UA / historian integration layer as the foundational step; analytics and ML are built on top of it, not in parallel. Integrate PdM alert output directly with the CMMS work order system — without this integration, adoption will be poor regardless of model accuracy. → `industry-vertical-repository/manufacturing/iiot-predictive-maintenance.md`

## Solutions Context
**Typical engagement patterns**: IIoT platform implementation, predictive maintenance program, OEE analytics, process optimization, energy monitoring, digital twin data integration.

**Common scope anchors**: Sensor and connectivity audit, OPC-UA / historian integration, edge computing architecture, time-series data pipeline, anomaly detection and PdM models, CMMS integration, operational dashboard.

**Risk factors**: Sensor availability and machine connectivity are the highest-risk assumptions — validate before scoping. Historian data quality audits consistently reveal more issues than expected. ML model development requires failure history data that may not exist for newer or rarely-failing equipment.

## Related Entries
- [Manufacturing Overview](_overview.md)
- [MES](mes.md)
- [Digital Twin](digital-twin.md)
- [Time Series Databases](../../engineering-knowledge-repository/time-series-databases.md) — SCADA historian data is time-series at high frequency; dedicated TSDBs handle the scale that relational DBs cannot
