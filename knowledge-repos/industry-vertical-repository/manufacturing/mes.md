---
id: mes
vertical: manufacturing
tags: [manufacturing, mes, production, scheduling, traceability, quality, isa95]
surfaces-at: [application-design, functional-design]
related: [manufacturing-overview, iiot-predictive-maintenance, plm]
---

# Manufacturing Execution System (MES)

## What It Is
A Manufacturing Execution System (MES) is the software layer that manages, monitors, and controls production operations on the shop floor in real-time. It bridges the gap between business planning (ERP) and physical production (OT/control systems), translating production orders into work instructions, tracking work-in-process, collecting production data, and confirming completions back to ERP. MES is the ISA-95 Level 3 system — the operational brain of a manufacturing facility.

## Why It Matters in Manufacturing
Without MES, the factory operates on paper, clipboards, and tribal knowledge. Product quality data is captured manually and late. Traceability — knowing which components went into which product — is reconstructed after the fact rather than tracked in real time. Equipment utilization is estimated, not measured. MES addresses all of these — but it also represents one of the most complex integration programs in manufacturing IT, touching shop floor OT, ERP, quality, and maintenance systems simultaneously.

## Key Concepts
- **Production Order / Work Order**: The instruction from ERP to produce a quantity of a product by a date. MES receives, schedules, and executes against production orders.
- **Work Instructions**: Step-by-step instructions for operators at each workstation. Electronic work instructions (EWI) replace paper and can be context-specific to the material being processed.
- **Dispatching / Sequencing**: The process of assigning production orders to machines and operators and sequencing them for optimal throughput. Advanced scheduling (APS) may be a separate system.
- **WIP (Work-in-Process) Tracking**: Real-time tracking of materials and assemblies as they move through production steps. Requires scan points (barcode, RFID) or automatic machine integration.
- **Genealogy / Traceability**: The full record of which components, materials, and process parameters were used to produce each unit. Critical for quality investigations, regulatory compliance (aerospace, automotive, pharma), and recalls.
- **OEE (Overall Equipment Effectiveness)**: The standard KPI for manufacturing productivity: Availability × Performance × Quality. MES collects the downtime, rate, and quality data needed to calculate OEE.
- **NCR (Non-Conformance Record)**: A formal record of a product or process that does not meet specification. MES captures defects at the point of detection and routes them through disposition workflows.
- **ERP Integration (GR/GI, Confirmations)**: MES must communicate production completions (confirmations), material consumption (goods issues), and quality results back to ERP. This is a bidirectional, near-real-time integration that is typically the most complex interface in MES programs.
- **Electronic Batch Record (EBR)**: In regulated industries (pharma, medical devices), MES must generate a complete electronic record of every production step, parameter, and signature for each batch. Regulatory requirement (FDA 21 CFR Part 11).

## Common Patterns / Gotchas
- **MES scope always grows.** The initial scope seems bounded — scheduling, dispatching, WIP tracking. But every downstream system (quality, maintenance, ERP) wants real-time production data. Define the integration scope explicitly and hold the boundary.
- **Data from the shop floor is messy.** Machine signals are noisy, unreliable, and ambiguous. A PLC "machine running" signal may mean different things on different machines. Data cleaning and normalization is a significant workstream.
- **Traceability requirements drive significant complexity.** One-up/one-down traceability (immediate parent/child) is straightforward. Full genealogy tracing every component through every process step is far harder and requires careful design at the data model level.
- **ERP integration is on the critical path.** MES without ERP integration is incomplete — production confirmations and material movements must flow both ways. SAP PP-PI integration in particular has significant complexity; plan accordingly.
- **Change management is as important as software delivery.** MES changes how operators work. Adoption requires operator training, change management, and floor-level champions. Projects that underinvest here suffer poor adoption regardless of software quality.
- **Validation is mandatory in regulated industries.** Pharma, med device, and aerospace MES implementations require formal IQ/OQ/PQ (Installation, Operational, Performance Qualification) validation. This is a significant effort that must be scoped explicitly.

## Industry Insight
🏭 **Industry Insight — MES**: You're designing or integrating a manufacturing execution system. Traceability requirements — specifically the granularity of genealogy (which components went into which units) — are the most consequential data model decision you will make; get these requirements explicitly before designing schemas. ERP integration (production order receipt, confirmation, goods movement) will dominate the integration architecture; validate the ERP integration API before finalizing the MES data model. Scope creep in MES is structural — set explicit integration boundaries early. → `industry-vertical-repository/manufacturing/mes.md`

## Solutions Context
**Typical engagement patterns**: MES greenfield implementation, MES platform migration, MES-ERP integration, electronic work instructions, traceability and genealogy platform, OEE analytics.

**Common scope anchors**: Production order management, WIP tracking and genealogy, electronic work instructions, ERP integration (SAP PP/PP-PI), OEE data collection, NCR workflow, shift reporting.

**Risk factors**: Scope creep from adjacent systems (quality, maintenance) is the primary delivery risk. SAP integration complexity is consistently underestimated. Regulatory validation (pharma/medical) is a significant additional workstream.

## Related Entries
- [Manufacturing Overview](_overview.md)
- [IIoT & Predictive Maintenance](iiot-predictive-maintenance.md)
- [PLM](plm.md)
