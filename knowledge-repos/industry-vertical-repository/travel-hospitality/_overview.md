---
id: travel-hospitality-overview
vertical: travel-hospitality
tags: [travel, hospitality, airline, hotel, gds, pms, booking, overview]
surfaces-at: [requirements-analysis, application-design]
related: []
---

# Travel & Hospitality — Industry Overview

## What It Is
Travel and hospitality technology spans airlines (reservations, operations, loyalty), hotels and lodging (property management, reservations, revenue management), online travel agencies (OTAs), and ground transportation. The domain is defined by inventory management (perishable, time-sensitive capacity), dynamic pricing, complex distribution through multiple channels, and high consumer expectations for digital experience.

## Why It Matters
Travel is a high-velocity, high-stakes digital commerce domain. A seat or room that goes unsold is revenue permanently lost. Pricing engines make millions of decisions per day. Distribution is multi-channel and fragmented — direct, OTA, GDS, corporate — each with different economics and integration requirements. The consumer experience is scrutinized intensely; a booking flow with friction directly costs revenue.

## Key Concepts
- **GDS (Global Distribution System)**: The legacy B2B distribution infrastructure for airline and hotel inventory — Amadeus, Sabre, Travelport. Travel agents and OTAs access inventory through GDS. Despite age, GDS remains essential for corporate travel and many distribution channels.
- **PMS (Property Management System)**: The operational system of record for a hotel — reservations, check-in/check-out, room assignments, billing, and housekeeping. Opera (Oracle) dominates. PMS integration is required for any hotel technology engagement.
- **PSS (Passenger Service System)**: The airline equivalent of PMS — reservations, departure control, loyalty, and revenue management. Amadeus Altéa, Sabre SynXis, and SITA are major platforms.
- **Revenue Management System (RMS)**: Optimization system that sets prices dynamically based on demand forecasts, competitive rates, and inventory levels. The commercial brain of airline and hotel operations.
- **PNR (Passenger Name Record)**: The core data record in airline reservations — contains all details of a booking. PNR format and content are governed by IATA standards and airline-specific rules.
- **NDC (New Distribution Capability)**: IATA's XML-based standard for direct airline-to-OTA/agency distribution, bypassing GDS. Enables richer offer content (ancillaries, bundles, personalized offers) than GDS allows. Airlines are driving NDC adoption to reduce GDS fees and enable product differentiation.
- **Loyalty Programs**: Frequent flyer / hotel loyalty programs are major revenue and customer retention engines. Points currencies, tier management, partner redemption, and fraud prevention are complex system requirements.
- **Channel Management**: For hotels, distributing accurate availability and rates across OTAs (Booking.com, Expedia), GDS, and direct channels simultaneously — with correct rate parity and inventory allocation — is a real-time synchronization challenge.

## Common System Archetypes
- **Booking Engine**: Consumer-facing search and booking (flights, hotels, packages)
- **Channel Manager**: Real-time distribution of hotel inventory and rates across channels
- **Revenue Management System**: Dynamic pricing and inventory optimization
- **Loyalty Platform**: Points earning, redemption, tier management, and partner integration

## Industry Insight
✈️ **Industry Insight — Travel & Hospitality**: You're working in travel. GDS integration (Amadeus, Sabre, Travelport) is unavoidable for any airline or hotel distribution system — understand the GDS API constraints and content limitations before designing product features that depend on rich offer data. Real-time inventory synchronization across channels (OTA, GDS, direct) is the core technical challenge in hotel technology; race conditions in availability and rate updates lead directly to overbooking and customer impact. → `industry-vertical-repository/travel-hospitality/_overview.md`

## Solutions Context
**Typical engagement patterns**: Booking engine modernization, NDC integration, channel management platform, loyalty program platform, revenue management integration, hotel digital experience.

**Common scope anchors**: GDS or NDC integration, PMS/PSS integration, real-time inventory synchronization, booking flow, loyalty engine, pricing and availability API, payment processing.

**Risk factors**: GDS API complexity and content limitations frequently constrain feature design. PMS integration (Opera, Amadeus) has limited API surface and poor documentation. Real-time inventory synchronization at scale requires careful distributed systems design.
