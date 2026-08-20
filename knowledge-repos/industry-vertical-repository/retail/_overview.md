---
id: retail-overview
vertical: retail
tags: [retail, ecommerce, omnichannel, inventory, oms, overview]
surfaces-at: [requirements-analysis, application-design]
related: []
---

# Retail — Industry Overview

## What It Is
Retail technology covers the systems that enable buying and selling of goods — online (e-commerce), in-store, or across both (omnichannel). Engagements typically touch commerce platforms, order management, inventory, fulfillment, and the integrations between them. The domain is well-understood but the operational scale and data consistency challenges are significant.

## Why It Matters
Retail systems operate at high transaction volume with strong consistency requirements (inventory must not oversell) and strict latency expectations (checkout must be fast). The shift to omnichannel — where a customer can buy online, return in-store, and check inventory anywhere — has made system integration complexity the primary challenge for most retail clients.

## Key Concepts
- **OMS (Order Management System)**: The system of record for orders across all channels. Manages order lifecycle from placement through fulfillment and return.
- **WMS (Warehouse Management System)**: Manages physical inventory in fulfillment centers — receiving, putaway, pick/pack/ship.
- **PIM (Product Information Management)**: The system of record for product catalog data — descriptions, attributes, images, pricing. Feeds all downstream commerce surfaces.
- **Inventory Availability**: The real-time (or near-real-time) view of what can be sold. Balancing accuracy against performance is a core design problem — full real-time inventory is expensive; stale inventory leads to oversell.
- **Omnichannel**: The capability to serve customers consistently across physical and digital channels. Requires shared inventory visibility, consistent pricing, and cross-channel order management.
- **3PL (Third-Party Logistics)**: Outsourced warehousing and fulfillment. Integration with 3PL providers (ShipBob, Flexport, etc.) is common for mid-market retailers.

## Common System Archetypes
- **E-commerce Platform**: Customer-facing web/mobile commerce (Shopify, Salesforce Commerce Cloud, custom builds)
- **Order Management System**: Cross-channel order orchestration and fulfillment routing
- **Inventory Platform**: Real-time inventory availability and allocation across locations
- **Returns Management**: RMA workflow, restocking, and customer credit processing

## Common Integration Points
- **ERP**: SAP, Oracle, Microsoft Dynamics — the financial and operational backbone. Inventory and order data often flows to/from ERP.
- **Payment Gateways**: Stripe, Adyen, Braintree — card processing at checkout.
- **3PL / WMS**: Fulfillment provider APIs for order submission and shipment tracking.
- **Shipping Carriers**: FedEx, UPS, USPS APIs for label generation and tracking.
- **Tax Engines**: Avalara, Vertex — sales tax calculation across jurisdictions.

## Industry Insight
🛒 **Industry Insight — Retail**: You're working in retail. Inventory consistency is the central design challenge — define your oversell tolerance and inventory reservation strategy before designing the data model. Omnichannel requirements (buy online / return in-store, ship-from-store) require shared inventory visibility across channels; this is frequently underestimated in scope. → `industry-vertical-repository/retail/_overview.md`

## Solutions Context
**Typical engagement patterns**: E-commerce platform builds or re-platforms, omnichannel order management, inventory platform modernization, 3PL integration, checkout and payments optimization.

**Common scope anchors**: OMS design, inventory availability and reservation model, omnichannel integration layer, ERP integration, 3PL/carrier integration, returns workflow.

**Risk factors**: Inventory consistency at scale requires careful distributed systems design — optimistic vs pessimistic reservation strategies have significant performance and correctness tradeoffs. ERP integrations are frequently the long pole. Holiday/peak traffic requirements can drive significant infrastructure scope.

**Estimation notes**: Omnichannel OMS is a substantial engagement. Each channel (web, mobile, in-store POS, marketplace) should be scoped as a separate integration track. Inventory platform work should include a load/performance testing track sized to peak traffic expectations.
