---
id: manufacturing-overview
vertical: manufacturing
tags: [manufacturing, industry4, iiot, mes, plm, ot-it, isa95, overview]
surfaces-at: [requirements-analysis, application-design]
related: [mes, iiot-predictive-maintenance, plm, digital-twin]
---

# Manufacturing — Industry Overview

## What It Is
Manufacturing technology spans discrete manufacturing (automotive, electronics, aerospace, industrial equipment) and process manufacturing (chemicals, food and beverage, pharmaceuticals). Engagements may sit inside an OEM, a contract manufacturer, a Tier 1 or Tier 2 supplier, or a manufacturing technology vendor. The domain is defined by the convergence of operational technology (shop floor systems, PLCs, sensors) with enterprise IT — commonly called Industry 4.0 or smart manufacturing.

## Why It Matters
Manufacturing is where physical and digital worlds meet most directly. The software that manages production scheduling, quality, equipment health, and supply chain directly determines output throughput, product quality, and cost. The Industry 4.0 transformation — connecting shop floor machines to enterprise analytics and AI — is the dominant technology investment theme. For Hitachi-affiliated engagements, manufacturing is a core domain with deep existing technology and customer relationships.

## Key Concepts
- **ISA-95 (IEC 62264)**: The international standard for integrating enterprise and control systems in manufacturing. Defines the functional hierarchy (Levels 0–4), the data models for production operations, and the integration interfaces between MES and ERP. ISA-95 is the architectural blueprint for most manufacturing IT programs.
- **ISA-95 Levels**:
  - Level 0–1: Physical process and sensing (sensors, actuators)
  - Level 2: Control (PLCs, DCS, SCADA)
  - Level 3: Manufacturing operations (MES, LIMS, quality)
  - Level 4: Business planning (ERP, SCM, PLM)
- **OT (Operational Technology)**: Shop floor systems — PLCs (Programmable Logic Controllers), DCS (Distributed Control Systems), SCADA, HMIs (Human-Machine Interfaces). OT prioritizes uptime and determinism over IT agility.
- **MES (Manufacturing Execution System)**: The Level 3 system that manages production operations in real-time — scheduling, dispatching, tracking, quality, and performance reporting. SAP ME, Rockwell FactoryTalk, Siemens Opcenter, and Honeywell are major platforms.
- **PLM (Product Lifecycle Management)**: Manages the product data through its lifecycle — CAD models, BOMs, engineering changes, specifications. Siemens Teamcenter, PTC Windchill, Dassault Systèmes ENOVIA are dominant platforms.
- **IIoT (Industrial Internet of Things)**: The network of sensors, machines, and connected devices on the shop floor generating operational data. Platforms: PTC ThingWorx, GE Predix, Siemens MindSphere, Azure IoT Hub, AWS IoT.
- **OPC-UA**: The modern OT communication standard for machine data exchange. Machine-agnostic, secure, and the de facto standard for new IIoT integrations. Replaces legacy OPC Classic and proprietary protocols.
- **Digital Twin**: A virtual model of a physical asset (machine, production line, product) synchronized with real-time operational data. Used for simulation, optimization, predictive maintenance, and virtual commissioning.
- **ERP Integration**: SAP S/4HANA and Oracle dominate manufacturing ERP. MES-to-ERP integration (production orders, confirmations, inventory movements, quality results) is ubiquitous and typically complex.

## Common System Archetypes
- **MES**: Real-time production management and execution
- **Quality Management System (QMS/LIMS)**: Manages quality plans, inspections, non-conformances, and lab results
- **Asset Performance Management (APM)**: Monitors equipment health, predicts failures, and optimizes maintenance
- **Supply Chain Visibility Platform**: Real-time visibility across multi-tier supplier networks
- **Digital Twin Platform**: Virtual replicas of assets or production lines for simulation and optimization

## Common Integration Points
- **PLC/DCS via OPC-UA**: Machine data from shop floor controllers — production counts, machine states, process parameters
- **SCADA Historians (OSIsoft PI, Aveva PI)**: Time-series operational data store; the bridge between OT and IT analytics
- **ERP (SAP, Oracle)**: Production orders, material movements, quality notifications, maintenance work orders
- **PLM (Teamcenter, Windchill)**: Engineering BOMs, specifications, engineering change orders
- **Barcode / RFID**: Work-in-process tracking, inventory management, traceability

## Industry Insight
🏭 **Industry Insight — Manufacturing**: You're working in manufacturing. ISA-95 is the architectural framework — align your data model and integration design to its hierarchy before designing APIs or schemas. The OT/IT integration layer (typically via OPC-UA and a SCADA historian like OSIsoft PI) is the foundation for any IIoT or analytics capability; validate what data is actually available from shop floor systems before designing analytics use cases. ERP integration (SAP in particular) will be on the critical path. → `industry-vertical-repository/manufacturing/_overview.md`

## Solutions Context
**Typical engagement patterns**: MES implementation or modernization, IIoT platform and analytics, digital twin, predictive maintenance, quality management system, supply chain visibility, Industry 4.0 transformation programs.

**Common scope anchors**: ISA-95 architecture alignment, OPC-UA / historian integration, MES-ERP integration, production tracking and genealogy, quality management, OEE (Overall Equipment Effectiveness) analytics.

**Risk factors**: Shop floor data availability is almost always more limited than expected — many machines expose limited or proprietary data. ERP integration scope expands with every new business requirement. OT change control extends timelines significantly.

## Related Entries
- [MES](mes.md)
- [IIoT & Predictive Maintenance](iiot-predictive-maintenance.md)
- [PLM](plm.md)
- [Digital Twin](digital-twin.md)
