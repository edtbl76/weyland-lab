---
id: quality-management
vertical: manufacturing
tags: [manufacturing, quality, qms, lims, non-conformance, capa, iso9001, spc]
surfaces-at: [application-design, functional-design]
related: [manufacturing-overview, mes, plm, iiot-predictive-maintenance]
---

# Quality Management

## What It Is
Quality management systems (QMS) in manufacturing encompass the software, processes, and data infrastructure for defining quality standards, executing inspections, managing non-conformances, driving corrective and preventive actions (CAPA), and providing the audit trail required by quality certifications (ISO 9001, IATF 16949, AS9100) and regulatory bodies (FDA for medical devices and pharma). In process manufacturing, Laboratory Information Management Systems (LIMS) handle the lab-side of quality management.

## Why It Matters in Manufacturing
Product quality failures are costly at every stage — defects caught in-process are far cheaper than defects caught by customers or regulators. In regulated industries (automotive IATF 16949, aerospace AS9100, medical devices 21 CFR Part 820, pharma 21 CFR Part 211), QMS compliance is a prerequisite for doing business. Customer quality agreements (PPM targets, PPAP requirements, 8D response obligations) create contractual quality obligations with financial consequences. Quality data generated in manufacturing is also a high-value analytics asset for continuous improvement.

## Key Concepts
- **PPAP (Production Part Approval Process)**: The automotive industry's formal process for approving new or changed parts before production. Requires documented evidence (dimensional data, material certs, process capability studies) at specified submission levels. Required by IATF 16949 and OEM customer requirements.
- **APQP (Advanced Product Quality Planning)**: A structured framework for planning quality into the product and process design phase — before production starts. Outputs include control plans, FMEA, measurement system analysis. Part of IATF 16949 and broadly used in automotive and aerospace.
- **FMEA (Failure Mode and Effects Analysis)**: A systematic analysis of potential failure modes in a product or process, their effects, and risk mitigation actions. Design FMEA (DFMEA) and Process FMEA (PFMEA) are distinct documents. FMEA data should be maintained in the QMS and updated based on field failures.
- **Control Plan**: A document specifying the measurement and control methods for each critical characteristic at each production step. Used by operators and inspectors to ensure consistent process control. Linked to FMEA and maintained in the QMS.
- **SPC (Statistical Process Control)**: Real-time monitoring of process measurements (dimensions, temperatures, pressures) using control charts to detect process drift before defects are produced. Cp/Cpk process capability indices measure whether a process is capable of meeting specification limits.
- **NCR (Non-Conformance Record)**: A formal record of a product or process that deviates from specification — captured at inspection, from production, or from customer complaints. NCRs trigger disposition (use-as-is, rework, scrap, return to supplier) and may trigger CAPA.
- **CAPA (Corrective and Preventive Action)**: The formal process for identifying the root cause of a non-conformance, implementing a corrective action (fix this occurrence), and implementing a preventive action (prevent recurrence). 8D (Eight Disciplines) is the most common CAPA methodology in automotive.
- **LIMS (Laboratory Information Management System)**: Manages lab sample tracking, test methods, results, and certificates of analysis (CoA). Critical in process manufacturing (chemicals, food, pharma) where lab testing is a primary quality control activity.
- **Audit Management**: QMS module for scheduling, conducting, and tracking internal and external quality audits — ISO 9001, IATF 16949, customer audits. Audit findings must be tracked through closure.

## Common Patterns / Gotchas
- **QMS is only as good as its data capture discipline.** A QMS that isn't used — NCRs not raised, inspections skipped — provides no value and a false sense of compliance. Change management and operator adoption are as important as the software.
- **CAPA closure rates are a leading indicator of quality culture.** Open CAPAs that are never closed indicate either an overloaded quality team or a system that makes closure difficult. Track CAPA cycle time and overdue rate as operational metrics, not just total open count.
- **SPC requires process stability before it adds value.** Running SPC on an unstable process generates constant alarms that operators learn to ignore. Establish process stability before implementing SPC charting; otherwise the alert fatigue problem defeats the purpose.
- **Regulated industries require validated QMS software.** FDA-regulated industries (med device, pharma) require 21 CFR Part 11 compliance (electronic records and signatures) and formal software validation (CSV — Computer System Validation) for any QMS used in regulated processes. This is a significant additional workstream.
- **Customer-specific requirements (CSRs) add complexity.** Major OEM customers (GM, Ford, Toyota, BMW) publish their own quality requirements on top of IATF 16949. These CSRs must be tracked and implemented in the QMS. The volume and specificity of CSRs across a large customer base is substantial.

## Industry Insight
🏭 **Industry Insight — Quality Management**: You're designing a quality management system. CAPA closure rate and cycle time are the operational health metrics that matter most — a QMS full of open, aging CAPAs indicates a system that creates work without driving improvement. In regulated industries (FDA, IATF 16949, AS9100), plan QMS software validation (CSV / IQ/OQ/PQ) as a dedicated workstream — it cannot be retrofitted after go-live. SPC alert thresholds must be tuned to the actual process capability; overly sensitive alerts create fatigue and get ignored regardless of the software quality. → `industry-vertical-repository/manufacturing/quality-management.md`

## Solutions Context
**Typical engagement patterns**: QMS implementation or modernization, PPAP/APQP management, SPC and process control platform, CAPA management, LIMS implementation, audit management, FDA 21 CFR Part 11 compliance.

**Common scope anchors**: NCR and CAPA workflow, inspection and measurement data capture, SPC charting and alerting, PPAP documentation management, control plan management, LIMS integration, audit scheduling and finding management, customer-specific requirements tracking.

**Risk factors**: Regulated industry QMS requires software validation (CSV) — scope this as a separate workstream. Customer-specific requirements vary by OEM and change with customer audits. Operator adoption (discipline to raise NCRs, complete inspections) is a change management risk that software alone cannot solve.

## Related Entries
- [Manufacturing Overview](_overview.md)
- [MES](mes.md)
- [PLM](plm.md)
