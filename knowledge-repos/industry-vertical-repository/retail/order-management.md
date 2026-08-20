---
id: order-management
vertical: retail
tags: [retail, oms, order-management, fulfillment, omnichannel, ship-from-store]
surfaces-at: [application-design, functional-design]
related: [retail-overview, inventory-management, customer-data-platform, dynamic-configuration-management]
---

# Order Management

## What It Is
Order Management Systems (OMS) are the operational backbone of retail fulfillment — receiving orders from all channels (web, mobile, in-store, marketplace, call center), making fulfillment routing decisions, orchestrating picking and shipping across fulfillment nodes (DCs, stores, dropship vendors), and managing the order lifecycle through to delivery and return. In omnichannel retail, OMS is the system that makes "buy anywhere, fulfill from anywhere, return anywhere" operationally possible.

## Why It Matters in Retail
Without a capable OMS, retailers cannot fulfill omnichannel promises. A customer ordering online cannot have their order fulfilled from a nearby store. A buy-online-return-in-store (BORIS) transaction requires the OMS and store system to reconcile. Inventory allocation decisions made by the OMS directly determine whether fulfillment costs are optimized or wasteful — routing every order to a distant DC when a nearby store has stock is a margin problem. For retailers with physical footprints, OMS is one of the highest-leverage technology investments.

## Key Concepts
- **Order Lifecycle**: The states an order moves through — placed → payment authorized → allocated → released to fulfillment → picked → shipped → delivered → (optionally) returned. Each state transition may trigger downstream actions (inventory reservation, carrier label generation, customer notification).
- **Fulfillment Routing / DOM (Distributed Order Management)**: The logic that decides which fulfillment node (DC, store, vendor) fills each order or line item. Routing considers inventory availability, proximity to customer, node capacity, cost, and SLA. This is the highest-value and most complex logic in OMS.
- **Split Shipments**: When items in a single order are fulfilled from multiple nodes. The customer receives multiple packages. Splitting has cost implications (multiple shipping labels) and experience implications (partial deliveries). Routing logic must balance split rate against fulfillment cost.
- **BOPIS / BORIS / SFS**:
  - BOPIS (Buy Online Pick Up In Store): Customer orders online, picks up at store. Requires store to receive and stage the order.
  - BORIS (Buy Online Return In Store): Customer returns an online order at a physical location. Requires OMS-POS reconciliation.
  - SFS (Ship From Store): A store fulfills an online order and ships it directly to the customer. Turns stores into mini-distribution centers.
- **Dropship**: An order fulfilled directly by a vendor or supplier, not from the retailer's own inventory. The retailer transmits the order to the vendor; the vendor ships direct to the customer. OMS must manage vendor SLAs, tracking, and exceptions.
- **Backorder / Pre-order**: Orders placed against future inventory. OMS must hold the order, monitor inventory receipt, and release to fulfillment automatically when stock arrives.
- **Carrier Integration**: OMS generates shipping labels and transmits manifests to carriers (FedEx, UPS, USPS, regional carriers). Requires carrier API integration for label generation, tracking, and rate shopping.
- **Returns Management (RMA)**: The reverse logistics workflow — authorizing returns, routing returned inventory back to stock or to liquidation, processing refunds or exchanges. Returns are operationally expensive and require dedicated workflow design.

## Common Patterns / Gotchas
- **Fulfillment routing is never "done."** Routing rules must be tuned continuously as inventory patterns, carrier rates, and network capacity change. Build a configurable routing rules engine, not hardcoded logic. Retailers need to adjust routing without a code deployment.
- **Store fulfillment operations are different from DC fulfillment.** Store associates are not warehouse workers. SFS and BOPIS workflows must be designed for a store environment — simple mobile UX, fit-for-purpose picking flow, minimal training burden. Do not design warehouse-grade workflows for stores.
- **Payment authorization and fulfillment timing matter.** Auth-capture timing rules vary by payment method and jurisdiction. Capturing payment too early (before shipment) violates card network rules; too late risks auth expiry. OMS must coordinate with the payment platform on capture timing.
- **Cancellation windows are complex.** Customers expect to cancel orders quickly. But once an order is released to a warehouse WMS and picking has started, cancellation may require a call or return rather than a simple system cancel. Define cancellation cutoff logic explicitly.
- **External fulfillment (dropship/3PL) requires exception management.** Vendors miss SLAs, send incorrect tracking, or run out of stock post-commitment. OMS must monitor vendor performance, surface exceptions automatically, and have escalation workflows. Passive dropship integrations that just send orders and hope fail in production.
- **Returns complexity is underscoped.** Returns touch OMS, payment, inventory, store systems, and customer service. The permutations (full return, partial return, exchange, store credit, damaged goods, vendor returns) create a large decision matrix. Scope returns as a dedicated workstream.

## Industry Insight
🛒 **Industry Insight — Order Management**: You're designing an OMS. Fulfillment routing logic (DOM) is the highest-value and most complex component — build it as a configurable rules engine that merchandising and operations teams can tune without code deployments. SFS and BOPIS workflows must be designed for store associate usability, not adapted from warehouse workflows. Returns are consistently the most complex and most underscoped workstream in OMS programs; treat them as a distinct module from day one. → `industry-vertical-repository/retail/order-management.md`

## Solutions Context
**Typical engagement patterns**: OMS implementation or modernization, omnichannel fulfillment capability (SFS, BOPIS, BORIS), dropship vendor integration, returns management, carrier rate shopping and integration.

**Common scope anchors**: Order lifecycle state machine, fulfillment routing (DOM) engine, store fulfillment workflows (SFS, BOPIS), dropship vendor integration, carrier integration, returns/RMA workflow, payment capture coordination.

**Risk factors**: Routing rule complexity grows with network size — start simple and iterate. Store associate adoption of SFS workflows is a change management risk as much as a technology risk. Returns complexity is consistently underestimated in initial scope.

## Related Entries
- [Retail Overview](_overview.md)
- [Inventory Management](inventory-management.md)
- [Dynamic Configuration Management](../../engineering-knowledge-repository/dynamic-configuration-management.md) — fulfillment routing rules must be tunable by operations without code deployments; build a configurable rules engine
