---
id: plm
vertical: manufacturing
tags: [manufacturing, plm, bom, cad, engineering-change, product-data]
surfaces-at: [application-design, functional-design]
related: [manufacturing-overview, mes, digital-twin]
---

# Product Lifecycle Management (PLM)

## What It Is
Product Lifecycle Management (PLM) is the discipline and the software that manages a product's data from concept through design, manufacturing, and end-of-life. At its core, PLM is a system of record for the product definition — the CAD models, bills of materials (BOMs), specifications, tolerances, and engineering changes that define what the product is and how it is made. Major platforms: Siemens Teamcenter, PTC Windchill, Dassault Systèmes ENOVIA/3DEXPERIENCE, SAP PLM.

## Why It Matters in Manufacturing
In complex manufactured products — automotive, aerospace, industrial equipment — a single product may have tens of thousands of part numbers, multiple BOM variants by region and configuration, and thousands of active engineering changes at any point in time. Without PLM, this data lives in CAD files, spreadsheets, and email threads, making it impossible to answer basic questions: "What is in production right now, and is it the right revision?" PLM is the foundation of product governance, quality, and manufacturing readiness.

## Key Concepts
- **BOM (Bill of Materials)**: The hierarchical list of all components, materials, and sub-assemblies that make up a product, with quantities and relationships. Multiple BOM types coexist:
  - **EBOM (Engineering BOM)**: How engineering defines the product. Organized around product function.
  - **MBOM (Manufacturing BOM)**: How manufacturing builds the product. Reorganized around production process steps and assembly sequences. Distinct from EBOM.
  - **SBOM (Service BOM)**: How the product is maintained and serviced. Used by aftermarket and field service.
- **Part / Item**: The atomic unit of PLM — a unique part number representing a component, material, or assembly at a specific revision.
- **Revision Control**: PLM maintains the full revision history of every part and document. Understanding which revision is "released" vs "in development" vs "obsolete" is fundamental to PLM data management.
- **ECO (Engineering Change Order)**: The formal process for changing a released product design. Includes impact analysis, approval workflow, effectivity dating (when the change takes effect in production), and communication to manufacturing and supply chain.
- **Product Configuration / Variant Management**: Managing the definition of product variants — different trims, options, regional variants — within a single product platform. Critical in automotive and consumer electronics. Rules-based configuration (150% BOM, AML/AVL) is complex.
- **EBOM to MBOM Transformation**: The process of translating engineering's product definition into a manufacturing-executable build plan. This transformation is one of the most complex and error-prone processes in manufacturing — it is often partially manual, poorly governed, and a source of production errors.
- **CAD Integration**: PLM stores CAD files (CATIA, NX, SOLIDWORKS, Creo) and maintains the association between CAD geometry and BOM items. CAD/PLM integration must handle large assemblies efficiently.
- **AML/AVL (Approved Manufacturer/Vendor List)**: The list of approved sources for each purchased part. Managed in PLM and consumed by procurement and MES.

## Common Patterns / Gotchas
- **EBOM ↔ MBOM alignment is always messy.** The transformation from EBOM to MBOM is never clean — manufacturing structures differ from engineering structures by design. Automated EBOM-to-MBOM transformation rules require significant configuration and business knowledge.
- **PLM data quality is a program, not a one-time effort.** Legacy product data migrated into PLM will have inconsistencies, missing attributes, and revision gaps. Data quality improvement requires sustained effort after go-live.
- **Engineering change management is politically complex.** ECO approval workflows involve engineering, manufacturing, procurement, quality, and often customers. The workflow must match the actual decision-making process, not an idealized one.
- **PLM platforms are deeply customized.** Teamcenter and Windchill installations are almost always heavily customized — custom attributes, workflows, integrations, and business rules. This significantly complicates upgrades and migrations.
- **PLM-ERP integration is critical and complex.** Transferring BOMs, parts, and engineering changes from PLM to ERP (SAP) for procurement and production planning is a high-frequency, business-critical integration. Mapping between PLM and ERP data models is non-trivial.
- **Multi-site and multi-instance PLM is an advanced problem.** Large manufacturers with global operations may have multiple PLM instances that need to share or synchronize product data. This is a complex data governance and integration challenge.

## Industry Insight
🏭 **Industry Insight — PLM**: You're working with PLM data or systems. The EBOM-to-MBOM transformation — translating engineering's product definition into a manufacturing-executable structure — is consistently the most underestimated complexity in PLM programs. Get explicit requirements for how this transformation is governed before designing any automated BOM management capability. PLM-ERP integration (BOM and engineering change transfer to SAP) is typically on the critical path and should be treated as a high-complexity, high-risk integration. → `industry-vertical-repository/manufacturing/plm.md`

## Solutions Context
**Typical engagement patterns**: PLM implementation or migration, EBOM/MBOM management, engineering change management, PLM-ERP integration, product configuration and variant management, PLM data quality program.

**Common scope anchors**: BOM structure and revision management, ECO workflow, EBOM-to-MBOM transformation, PLM-ERP (SAP) integration, CAD integration, variant and configuration management.

**Risk factors**: Legacy product data migration is the highest-risk workstream in any PLM implementation — data quality issues discovered late cause schedule overruns. PLM platform customization limits upgrade paths. PLM-ERP integration complexity is consistently underestimated.

## Related Entries
- [Manufacturing Overview](_overview.md)
- [MES](mes.md)
- [Digital Twin](digital-twin.md)
