---
id: automotive-overview
vertical: automotive
tags: [automotive, oem, tier1, autosar, iso26262, connected-vehicle, ev, adas, overview]
surfaces-at: [requirements-analysis, application-design]
related: [connected-vehicle, adas-autonomous, ev-charging, automotive-software-development]
---

# Automotive — Industry Overview

## What It Is
Automotive technology spans vehicle software (embedded, ADAS, infotainment), connected vehicle platforms (telematics, OTA, V2X), EV powertrain and charging infrastructure, and manufacturing execution for vehicle production. The industry is structured around OEMs (Original Equipment Manufacturers — Ford, GM, Toyota, BMW, Stellantis), Tier 1 suppliers (Bosch, Continental, Aptiv, Magna — who deliver major systems to OEMs), and Tier 2/3 suppliers (component and technology vendors). GlobalLogic has deep presence across all three tiers.

## Why It Matters
Automotive is undergoing its most significant transformation since the introduction of mass production — the convergence of electrification (EV), autonomy (ADAS/AV), and connectivity (software-defined vehicle). Software is displacing hardware as the primary source of vehicle differentiation and revenue. The industry's safety culture (ISO 26262 functional safety, ASPICE process standards) creates engineering constraints that differ fundamentally from consumer software. A software defect in a vehicle can cause injury or death — this changes how software is developed, validated, and released.

## Key Concepts
- **Software-Defined Vehicle (SDV)**: The shift toward vehicles where functionality, features, and performance are primarily determined by software rather than hardware — and can be updated over-the-air post-delivery. The strategic direction of every major OEM.
- **AUTOSAR (Automotive Open System Architecture)**: The standard software architecture for automotive ECUs (Electronic Control Units). Classic AUTOSAR governs embedded ECU software structure; Adaptive AUTOSAR governs high-performance compute platforms (ADAS, infotainment). Understanding AUTOSAR is essential for any embedded automotive software engagement.
- **ISO 26262**: The international functional safety standard for road vehicles. Defines Automotive Safety Integrity Levels (ASIL A–D) based on severity, exposure, and controllability of hazards. ASIL D is the highest safety level — powertrain, steering, braking. Any software in the safety path must be developed to the appropriate ASIL level.
- **ECU (Electronic Control Unit)**: The embedded computers that control vehicle functions — engine, transmission, brakes, steering, HVAC, doors, lights. Modern vehicles have 50–150+ ECUs. Consolidation onto fewer, more powerful compute platforms is a major architectural trend.
- **HPC (High-Performance Compute Platform)**: The next-generation centralized compute architecture replacing distributed ECUs — Nvidia DRIVE, Qualcomm Snapdragon Ride, Mobileye EyeQ. Central to ADAS and SDV architectures.
- **V2X (Vehicle-to-Everything)**: Communication between vehicles and infrastructure (V2I), other vehicles (V2V), pedestrians (V2P), and networks (V2N). Enables cooperative driving, intersection management, and safety warnings. DSRC and C-V2X are the competing standards.
- **ASPICE (Automotive SPICE)**: The process assessment model for automotive software development. OEMs require Tier 1 suppliers to achieve specific ASPICE capability levels as a contract requirement. Not the same as ISO 26262 (functional safety) — ASPICE is about development process rigor.
- **OTA (Over-the-Air Update)**: Remote software update of vehicle ECUs and systems without requiring a dealer visit. Foundational to the SDV model. Requires secure delivery, rollback capability, and update campaign management.

## Common System Archetypes
- **Telematics Platform**: Cloud-side platform for connected vehicle data ingestion, processing, and services
- **OTA Update Platform**: Campaign management, update delivery, and ECU flash management
- **Infotainment / Head Unit**: In-vehicle multimedia and connectivity (Android Automotive, QNX, Linux-based)
- **ADAS Stack**: Software stack for driver assistance — perception, fusion, planning, control
- **Charging Network Management**: Cloud platform for EV charging station management (OCPP, smart charging)
- **Vehicle Data Platform**: Ingestion and processing of vehicle telemetry for analytics, engineering, and services

## Common Integration Points
- **Vehicle Telematics / OBD-II**: CAN bus and OBD-II port for vehicle data; proprietary OEM protocols for deeper integration
- **Backend Cloud Platforms**: OEM vehicle cloud platforms (Ford SYNC Connect, GM OnStar, BMW Connected Drive) for telematics, OTA, and services
- **AUTOSAR BSW (Basic Software)**: Standard software components (communication, memory, diagnostics) for ECU software development
- **AUTOSAR Adaptive Platform**: POSIX-based runtime for high-performance ECUs — service-oriented architecture, SOME/IP
- **Charging Protocols**: OCPP (Open Charge Point Protocol) for EVSE management; ISO 15118 for vehicle-to-charger communication

## Industry Insight
🚗 **Industry Insight — Automotive**: You're working in automotive. Functional safety (ISO 26262) requirements apply to any software that could affect vehicle control — establish ASIL level requirements before designing, as they govern development, testing, and documentation obligations that cannot be retrofitted. The OEM/Tier 1/Tier 2 supply chain means your integration interfaces are typically defined by the OEM or Tier 1's architecture — validate interface specifications early. OTA update capability requires security and rollback to be designed in from the start. → `industry-vertical-repository/automotive/_overview.md`

## Solutions Context
**Typical engagement patterns**: Connected vehicle platform development, OTA update infrastructure, telematics data platform, ADAS software development (perception, fusion, planning), EV charging network management, infotainment platform, automotive manufacturing execution.

**Common scope anchors**: ISO 26262 safety analysis and compliance, AUTOSAR architecture (Classic or Adaptive), V2X or telematics platform, OTA campaign management, CAN/Ethernet vehicle integration, EV charging (OCPP), vehicle data ingestion pipeline.

**Risk factors**: ISO 26262 compliance adds significant development and documentation overhead that must be scoped explicitly. OEM integration specifications are often incomplete at project start. Vehicle hardware availability for integration testing is frequently a schedule constraint.

## Related Entries
- [Connected Vehicle](connected-vehicle.md)
- [ADAS & Autonomous](adas-autonomous.md)
- [EV Charging](ev-charging.md)
- [Automotive Software Development](automotive-software-development.md)
