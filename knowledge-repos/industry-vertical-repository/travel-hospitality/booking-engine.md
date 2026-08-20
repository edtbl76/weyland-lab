---
id: booking-engine
vertical: travel-hospitality
tags: [travel, booking, search, availability, reservations, gds, ndc]
surfaces-at: [application-design, functional-design]
related: [travel-hospitality-overview, revenue-management, loyalty]
---

# Booking Engine

## What It Is
A booking engine is the consumer-facing search, availability, and transaction platform through which travelers search for and purchase flights, hotels, rental cars, and travel packages. It spans the availability search layer (querying real-time inventory from airlines, hotels, and aggregators), the offer presentation layer (displaying results with pricing and options), and the checkout and reservation layer (capturing payment and confirming the booking). Booking engines serve OTAs (Expedia, Booking.com), airline and hotel direct channels, corporate travel management companies (TMCs), and metasearch aggregators (Google Flights, Kayak).

## Why It Matters in Travel & Hospitality
The booking engine is revenue. Conversion rate at each step of the funnel — search to results, results to select, select to checkout, checkout to confirm — directly determines revenue. A 1% improvement in checkout conversion is material for a high-volume OTA. Search latency, result relevance, and price accuracy are the three primary technical drivers of conversion. For airlines and hotels, direct channel booking (bypassing OTA commissions of 15–25%) is a strategic and financial priority.

## Key Concepts
- **Availability Search**: The query that retrieves available inventory and pricing for a travel search (origin, destination, dates, passengers). For airlines, this hits multiple sources simultaneously — GDS (Amadeus, Sabre, Travelport), airline NDC APIs, and low-cost carrier direct APIs. For hotels, it hits GDS, OTA extranets, and direct hotel/chain APIs. Fan-out search with aggregation and deduplication is the standard pattern.
- **GDS (Global Distribution System)**: The legacy B2B inventory distribution infrastructure. Amadeus, Sabre, and Travelport aggregate airline and hotel inventory from thousands of suppliers into a single queryable database. GDS is still essential for full market coverage — airlines not on NDC, corporate fares, and complex itineraries.
- **NDC (New Distribution Capability)**: IATA's modern XML-based standard for airline direct distribution. Bypasses GDS for airlines that have implemented it, enabling richer content (branded fares, seat maps, ancillaries, personalized offers). Airlines are aggressively pushing NDC adoption to reduce GDS fees.
- **Fare Rules / Conditions**: The restrictions attached to a fare — refundability, change fees, advance purchase requirements, minimum/maximum stay, blackout dates. Fare rules must be displayed accurately at time of booking; failure to disclose is a regulatory issue in many jurisdictions.
- **Offer Composition**: The assembly of a complete travel offer from components — base fare + ancillaries (seat, bag, meal) for flights; room rate + inclusions for hotels. Modern offer composition (driven by NDC and ONE Order) is more complex than legacy simple fares.
- **Price Caching / Search Cache**: Caching availability search results to reduce GDS query costs and improve search latency. Cache freshness (how quickly prices go stale) vs cost (GDS queries are charged per transaction) is a fundamental design tradeoff.
- **Book-Then-Ticket (BTT) vs Instant Purchase**: Two booking models for air. BTT holds a reservation without immediate payment — allows price locking or itinerary review before ticketing. Instant purchase tickets immediately. Each has different operational implications for payment timing and GDS hold management.
- **PNR (Passenger Name Record)**: The reservation record in the airline or GDS system. The booking engine creates a PNR for each booking and must manage its lifecycle — modifications, cancellations, special service requests.

## Common Patterns / Gotchas
- **Fan-out search latency is the hardest performance problem.** Querying GDS, multiple NDC airlines, and LCC direct APIs simultaneously — with different response times — requires careful timeout management, partial result presentation, and progressive loading. The slowest source should not block the overall response.
- **Price accuracy at confirmation is a regulatory and trust issue.** Prices displayed in search results must match the price at checkout. Price changes between search and booking (airline repricing, GDS fare updates) must be handled with repricing logic and transparent customer disclosure — not silent price changes.
- **GDS content limitations constrain feature design.** GDS fare content is rich for traditional fares but limited for ancillaries, branded fares, and NDC-era rich offers. Features that depend on content not available in GDS (bundled ancillary offers, seat maps for all airlines) require NDC or direct airline integration.
- **Mobile booking has distinct UX requirements.** Booking a complex multi-leg itinerary on mobile is inherently harder than desktop. Progressive disclosure, simplified fare selection, and frictionless mobile payment (Apple Pay, Google Pay) are conversion drivers on mobile that desktop does not require to the same degree.
- **Payment and fraud complexity is high.** Travel is a high-fraud-value transaction category — flight tickets are liquid assets. Payment processing requires real-time fraud scoring, 3DS2 authentication, and multi-currency support. Chargebacks from fraudulent bookings are a material cost.

## Industry Insight
✈️ **Industry Insight — Booking Engine**: You're designing a travel booking engine. Fan-out search across GDS, NDC, and direct APIs requires explicit timeout and partial result handling — the slowest source cannot block the response. Price accuracy between search and confirmation is both a regulatory requirement and a conversion factor; build repricing validation at checkout as a first-class component. GDS content limitations will constrain feature design for ancillaries and rich offers — validate content availability for target airlines and hotel chains before committing to feature scope. → `industry-vertical-repository/travel-hospitality/booking-engine.md`

## Solutions Context
**Typical engagement patterns**: OTA platform build or modernization, airline direct channel (NDC implementation), hotel direct booking engine, corporate travel booking tool, metasearch integration.

**Common scope anchors**: GDS integration (Amadeus/Sabre/Travelport), NDC airline integration, availability search with fan-out and aggregation, fare display and rules, offer composition, PNR management, checkout and payment, mobile booking UX.

**Risk factors**: GDS integration complexity and content limitations are frequently underestimated. NDC implementation maturity varies by airline — some have full content parity, others have significant gaps. Payment fraud management requires ongoing model tuning.

## Related Entries
- [Travel & Hospitality Overview](_overview.md)
- [Revenue Management](revenue-management.md)
- [Loyalty](loyalty.md)
