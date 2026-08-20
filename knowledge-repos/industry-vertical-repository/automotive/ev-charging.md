---
id: ev-charging
vertical: automotive
tags: [automotive, ev, charging, ocpp, iso15118, smart-charging, grid]
surfaces-at: [application-design, functional-design]
related: [automotive-overview, connected-vehicle, renewable-integration]
---

# EV Charging Infrastructure

## What It Is
EV charging infrastructure software spans the management of charging stations (EVSE — Electric Vehicle Supply Equipment), the cloud platforms that operate charging networks, smart charging optimization, and the integration between vehicles, chargers, and the electric grid. The market involves CPOs (Charge Point Operators who own/operate stations), eMSPs (e-Mobility Service Providers who offer charging services to drivers), and roaming networks that enable cross-network charging.

## Why It Matters in Automotive
EV adoption is the strategic direction of the automotive industry — every major OEM has committed to electrification timelines. Charging infrastructure is the critical enabler: range anxiety (fear of running out of charge) is the primary barrier to EV adoption, and software is the solution — smart charging that manages grid load, predictive charging recommendations, seamless payment, and reliable station operation. For Hitachi-adjacent engagements, EV charging sits at the intersection of automotive and energy, which is a natural GlobalLogic/Hitachi strength.

## Key Concepts
- **EVSE (Electric Vehicle Supply Equipment)**: The physical charging station. Level 1 (120V, slow), Level 2 (240V, 7–22 kW, standard home/workplace), DC Fast Charging (50–350 kW, highway corridors).
- **OCPP (Open Charge Point Protocol)**: The open standard protocol between EVSE hardware and the CSMS (Charge Station Management System). OCPP 1.6 (JSON/SOAP) is widely deployed; OCPP 2.0.1 adds smart charging, security, and ISO 15118 support. Every new charging network build should target OCPP 2.0.1.
- **CSMS (Charge Station Management System)**: The cloud backend that manages EVSE — remote start/stop, firmware updates, transaction records, diagnostics, and smart charging. The operational platform for a CPO.
- **ISO 15118**: The vehicle-to-charger communication standard for Plug & Charge (PnC). Enables a vehicle to automatically authenticate and authorize charging without a card or app — the vehicle's certificate identifies it to the charger. Requires PKI infrastructure. The direction mandated by major OEMs.
- **Smart Charging (OCPP Smart Charging Profile)**: Dynamic management of charging power based on grid capacity, local load, energy prices, and user preferences. Can be implemented at the station level (static limits) or network level (dynamic optimization across sites).
- **V2G (Vehicle-to-Grid)**: Bidirectional charging — the EV battery can discharge back to the grid or building (V2B). Requires bidirectional chargers (not all EVSE supports this), ISO 15118-20 for vehicle communication, and utility grid integration.
- **Roaming (OCPI)**: OCPI (Open Charge Point Interface) is the protocol for CPO-to-eMSP communication — enabling a driver from one network to charge on another. Required for charging network interoperability.
- **CPO / eMSP split**: The CPO operates the physical infrastructure; the eMSP manages the customer relationship and payment. A single operator may play both roles, or they may be separate businesses connected via OCPI roaming.

## Common Patterns / Gotchas
- **OCPP compliance varies significantly across hardware vendors.** Not all chargers that claim OCPP compliance implement the full profile correctly. Integration testing against specific hardware is required before deployment — do not assume compliance.
- **Smart charging requires grid operator coordination.** Dynamic power management that interacts with building loads or grid demand response requires integration with the building energy management system or utility demand response programs. This integration is frequently out of scope initially and then becomes urgent.
- **ISO 15118 / Plug & Charge PKI is complex.** The PKI infrastructure for Plug & Charge (OEM Provisioning Certificates, Contract Certificates, V2G root CA) involves multiple parties (OEM, eMSP, CPMS) and is not trivial to implement. Validate PKI architecture before committing to Plug & Charge support.
- **Transaction reliability is customer-facing.** A charging session that starts but fails to stop billing, or a charger that appears available but won't start, is an immediate customer complaint. Transaction state management must be designed for network interruptions.
- **Hardware failures are frequent.** EVSE hardware in public deployments fails regularly — cable damage, card reader failures, network dropouts. Robust remote diagnostics, automatic fault detection, and NOC (network operations center) workflow are operational requirements, not nice-to-haves.

## Industry Insight
🚗 **Industry Insight — EV Charging**: You're building EV charging infrastructure software. OCPP vendor compliance varies significantly — build hardware integration testing into the project plan, not just vendor certification review. Smart charging that dynamically adjusts power based on grid or building load requires explicit integration with energy management systems; scope this as a separate integration track. ISO 15118 Plug & Charge requires PKI infrastructure involving OEMs, eMSPs, and root CAs — validate the PKI architecture before committing to PnC support. → `industry-vertical-repository/automotive/ev-charging.md`

## Solutions Context
**Typical engagement patterns**: CSMS platform build, smart charging optimization, Plug & Charge enablement, roaming network integration (OCPI), CPO fleet management, V2G platform, charging analytics.

**Common scope anchors**: OCPP 2.0.1 integration, CSMS backend, smart charging optimization, ISO 15118 / Plug & Charge PKI, OCPI roaming, payment and billing, network operations and diagnostics.

**Risk factors**: EVSE hardware OCPP compliance issues discovered in integration testing. PKI infrastructure for Plug & Charge involves external parties (OEMs, root CA) with their own timelines. Grid/utility integration for smart charging adds energy domain complexity.

## Related Entries
- [Automotive Overview](_overview.md)
- [Connected Vehicle](connected-vehicle.md)
- [Renewable Integration](../energy-utilities/renewable-integration.md)
